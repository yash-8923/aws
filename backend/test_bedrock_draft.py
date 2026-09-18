import sys
import os
import json

# Ensure the backend directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.abspath(os.path.join(os.path.dirname(__file__), "../dist/assets")), exist_ok=True)

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _sample_draft_payload():
    return {
        "analysis": {
            "damage_type": "Pothole",
            "severity": "High",
            "suggested_description": "Deep pothole near school crossing.",
        },
        "transcription": {
            "transcript": "There is a pothole on Main Road that has been there for weeks.",
        },
        "jurisdiction": {
            "portal_name": "Municipal Corporation",
            "ward_district": "Ward 12",
        },
        "location_context": "Near City Primary School, Sector 4",
    }


def test_draft_endpoint_with_full_payload():
    response = client.post("/api/draft", json=_sample_draft_payload())

    assert response.status_code == 200
    body = response.json()
    print(json.dumps(body, indent=2))

    assert "description" in body
    assert isinstance(body["description"], str) and len(body["description"].strip()) > 0
    # Endpoint always ensures a placeholder phone when missing
    assert "phoneNumber" in body


def test_draft_endpoint_minimal_payload_fallback():
    """Empty/minimal body should still return 200 (fallback draft in bedrock)."""
    response = client.post("/api/draft", json={})

    assert response.status_code == 200
    body = response.json()
    print(json.dumps(body, indent=2))

    assert "description" in body
    assert isinstance(body["description"], str)
