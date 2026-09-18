import boto3
import os
import json
import logging
import time
from typing import Any
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

REGION = os.getenv("BEDROCK_REGION", "us-east-1")
MODEL_ID = "amazon.nova-micro-v1:0"

_bedrock_client = None


def _get_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client("bedrock-runtime", region_name=REGION)
        logger.info("Bedrock client initialised (region=%s, model=%s)", REGION, MODEL_ID)
    return _bedrock_client


MAX_RETRIES = int(os.getenv("BEDROCK_MAX_RETRIES", "3"))
RETRY_BASE_DELAY = float(os.getenv("BEDROCK_RETRY_BASE_DELAY", "1.0"))
_RETRYABLE_ERROR_CODES = {"ThrottlingException", "ServiceUnavailableException", "ModelTimeoutException"}


def _invoke_model(
    system_prompt: str,
    user_text: str,
    max_tokens: int = 512,
    temperature: float = 0.1,
) -> str:
    """Invoke Bedrock with retries and return the raw output text."""
    client = _get_client()
    messages = [{"role": "user", "content": [{"text": user_text}]}]
    body = json.dumps({
        "system": [{"text": system_prompt}],
        "messages": messages,
        "inferenceConfig": {"max_new_tokens": max_tokens, "temperature": temperature},
    })

    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.invoke_model(
                modelId=MODEL_ID,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            response_body = json.loads(response["body"].read().decode("utf-8"))
            text = (
                response_body
                .get("output", {})
                .get("message", {})
                .get("content", [{}])[0]
                .get("text", "")
            )
            return text

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            last_err = exc
            if error_code in _RETRYABLE_ERROR_CODES and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Bedrock retryable error %s (attempt %d/%d), retrying in %.1fs",
                    error_code, attempt, MAX_RETRIES, delay,
                )
                time.sleep(delay)
                continue
            raise
        except Exception as exc:
            last_err = exc
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Bedrock unexpected error (attempt %d/%d): %s – retrying in %.1fs",
                    attempt, MAX_RETRIES, exc, delay,
                )
                time.sleep(delay)
                continue
            raise

    raise last_err  # type: ignore[misc]


def _parse_json_from_llm(raw: str) -> dict[str, Any]:
    """Strip markdown fences and parse JSON from LLM output."""
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Public API (signatures unchanged)
# ---------------------------------------------------------------------------

def get_portal_routing(location_string: str, portals_db: dict) -> dict:
    system_prompt = f"""System Role: You are the Lead Dispatcher for the JanSahay Road Infrastructure Platform. Your job is to analyze a location string and select the single most appropriate government portal for filing a road complaint.

Rules:
If the address contains "NH" or "National Highway", select NHAI.
If the address contains "SH" or "State Highway", select the specific State PWD portal.
If the address is within a major city limit (e.g., Mumbai, Delhi) and not a highway, select the Municipal Corporation.
If the authority is ambiguous but the issue is serious, default to CPGRAMS.

Input Data: 
> - Location: {location_string}

Portal_DB: {json.dumps(portals_db)}

Output Format: (Strict JSON)
{{"portal_name": "...", "portal_url": "...", "reasoning": "..."}}"""

    try:
        raw = _invoke_model(
            system_prompt=system_prompt,
            user_text="Please provide the portal routing details based on the location provided.",
            max_tokens=512,
            temperature=0.1,
        )
        return _parse_json_from_llm(raw)

    except Exception as e:
        logger.error("Bedrock Routing Error: %s", e, exc_info=True)
        return {
            "portal_name": "CPGRAMS",
            "portal_url": portals_db.get("CENTRAL", {}).get("CPGRAMS", ""),
            "reasoning": f"Default fallback due to an error processing the request or LLM failure: {e}",
        }


def generate_complaint_draft(data: dict) -> dict:
    """Generates a formal, professional complaint draft using Amazon Bedrock Nova."""
    analysis = data.get("analysis", {})
    transcription = data.get("transcription", {})
    jurisdiction = data.get("jurisdiction", {})

    damage_type = analysis.get("damage_type", "Civic Issue")
    severity = analysis.get("severity", "Medium")
    location = jurisdiction.get("portal_name", "Local Authority")

    issue_description = analysis.get("suggested_description", "")
    voice_transcript = transcription.get("transcript", "")

    system_prompt = """System Role: You are an AI assistant for JanSahay, an Indian civic tech platform. 
Your goal is to generate a professional, formal, and persuasive complaint to be submitted to government officials.

Rules:
1. Use formal language (e.g., 'To the concerned authority', 'Requested to take immediate action').
2. Be specific about the issue based on the provided data.
3. Keep the tone respectful but firm.
4. If a voice transcript is provided, incorporate its key details into the formal description.
5. The output must be a valid JSON object with specific fields.

Output Format: (Strict JSON)
{
    "applicantName": "Citizen Reporter",
    "damageType": "...",
    "severity": "...",
    "jurisdiction": "...",
    "ward": "...",
    "description": "The full body of the complaint..."
}"""

    user_input = f"""Please generate a complaint draft for:
- Issue: {damage_type}
- Severity: {severity}
- Jurisdiction: {location}
- AI Analysis: {issue_description}
- User's Voice Report: {voice_transcript}
- Location Context: {data.get('location_context', 'Not provided')}"""

    try:
        raw = _invoke_model(
            system_prompt=system_prompt,
            user_text=user_input,
            max_tokens=1000,
            temperature=0.7,
        )
        return _parse_json_from_llm(raw)

    except Exception as e:
        logger.error("Bedrock Draft Generation Error: %s", e, exc_info=True)
        description = issue_description or ("Voice Report: " + voice_transcript) or "Observed civic hazard."
        return {
            "applicantName": "Citizen Reporter",
            "damageType": damage_type,
            "severity": severity,
            "jurisdiction": location,
            "ward": jurisdiction.get("ward_district") or "Default Ward",
            "description": (
                f"To the concerned authority,\n\n"
                f"I am reporting a issue regarding {damage_type}.\n\n"
                f"Details:\n{description}\n\n"
                f"Please address this at your earliest convenience.\n\n"
                f"Thank you."
            ),
        }


def generate_cluster_complaint(data: dict) -> str:
    """Generates a formal complaint for a cluster of detected issues."""
    authority = data.get("portal_name", "Local Authority")
    sub_area = data.get("sub_area", "this area")
    lat = data.get("latitude")
    lng = data.get("longitude")
    event_count = data.get("event_count", 1)
    severity = data.get("severity", "moderate")

    system_prompt = """System Role: You are an AI assistant for JanSahay. 
Your goal is to generate a comprehensive, formal complaint based on multiple dashcam detection events.

Rules:
1. Start with 'To the concerned [Authority]'.
2. Mention that this is an AI-validated report based on multiple dashcam captures.
3. Be professional, urgent (if severity is high), and clear.
4. Include the location details and GPS coordinates.
5. Emphasize that multiple events (provide the count) have been recorded in the same spot, indicating a recurring or persistent hazard.
6. The output must be the text of the complaint itself."""

    user_input = f"""Generate a complaint for:
- Authority: {authority}
- Location: {sub_area}
- GPS: {lat}, {lng}
- Detection Count: {event_count}
- Aggregate Severity: {severity}"""

    try:
        raw = _invoke_model(
            system_prompt=system_prompt,
            user_text=user_input,
            max_tokens=1000,
            temperature=0.7,
        )
        return raw.strip()

    except Exception as e:
        logger.error("Bedrock Cluster Complaint Error: %s", e, exc_info=True)
        return (
            f"To the concerned {authority},\n\n"
            f"This is a report regarding road damage at {sub_area} ({lat}, {lng}). "
            f"Multiple events ({event_count}) have been recorded. Please inspect."
        )
