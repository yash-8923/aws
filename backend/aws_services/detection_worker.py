import os
import time
import subprocess
import uuid
import shutil
import json
import boto3
from botocore.config import Config
import cv2
import numpy as np

from .location import reverse_geocode
from .bedrock import get_portal_routing
from .rekognition import RekognitionService
from dotenv import load_dotenv

load_dotenv()

# Load portals database
_portals_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "portals.json")
try:
    with open(_portals_path, "r") as f:
        PORTALS_DB = json.load(f)
except Exception:
    PORTALS_DB = {}

# --- SageMaker YOLO Client ---
SAGEMAKER_ENDPOINT = "road-damage-yolov8-endpoint-serverless"
SAGEMAKER_REGION = os.getenv("SAGEMAKER_REGION", os.getenv("AWS_REGION", "ap-south-1"))

_sagemaker_client = None
_rekognition_service = None

def _get_sagemaker_client():
    """Lazily initialise the SageMaker Runtime client."""
    global _sagemaker_client
    if _sagemaker_client is None:
        # Serverless endpoints can have cold-start latency; keep the read timeout high.
        # Also keep retries low so we don't stack multiple long requests.
        my_config = Config(
            read_timeout=int(os.getenv("SAGEMAKER_READ_TIMEOUT_SECONDS", "120")),
            connect_timeout=int(os.getenv("SAGEMAKER_CONNECT_TIMEOUT_SECONDS", "10")),
            retries={"max_attempts": int(os.getenv("SAGEMAKER_MAX_ATTEMPTS", "1"))},
        )
        _sagemaker_client = boto3.client(
            'sagemaker-runtime',
            config=my_config,
            region_name=SAGEMAKER_REGION,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
    return _sagemaker_client

def _get_rekognition_service():
    """Lazily initialise the Rekognition Service."""
    global _rekognition_service
    if _rekognition_service is None:
        _rekognition_service = RekognitionService()
    return _rekognition_service


def _extract_frames(video_path: str, max_frames: int = 5) -> list:
    """
    Extract evenly-spaced frames from a video file using OpenCV.
    Handles WebM by first converting to MP4 via FFmpeg (OpenCV on Windows
    often can't decode VP8/VP9 WebM files directly).
    Returns a list of JPEG-encoded byte strings ready for SageMaker.
    """
    working_path = video_path

    # If the file is WebM, convert to a temp MP4 that OpenCV can read
    if video_path.lower().endswith('.webm'):
        mp4_path = video_path.rsplit('.', 1)[0] + '_conv.mp4'
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", video_path, "-c:v", "libx264", "-preset", "ultrafast",
                 "-crf", "28", "-an", mp4_path],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=30
            )
            working_path = mp4_path
            print(f"[Detection Worker] Converted WebM → MP4 for frame extraction")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"[Detection Worker] FFmpeg WebM→MP4 conversion failed: {e}")
            # Try OpenCV directly as a last resort
            working_path = video_path

    cap = cv2.VideoCapture(working_path)
    if not cap.isOpened():
        print(f"[Detection Worker] Could not open video: {working_path}")
        _cleanup_if_different(working_path, video_path)
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        total_frames = 150  # fallback for streams (~5s @ 30fps)

    # Pick evenly-spaced frame indices
    step = max(1, total_frames // max_frames)
    frame_indices = list(range(0, total_frames, step))[:max_frames]

    frames = []
    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        # Resize to 640x480 as expected by the endpoint
        resized = cv2.resize(frame, (640, 480))
        frames.append(resized)

    cap.release()
    _cleanup_if_different(working_path, video_path)
    return frames


def _cleanup_if_different(temp_path: str, original_path: str):
    """Remove the temp converted file if it's different from the original."""
    if temp_path != original_path:
        try:
            os.remove(temp_path)
        except Exception:
            pass


def _invoke_sagemaker(image_bytes: bytes) -> list:
    """
    Send a single JPEG frame to the SageMaker YOLO endpoint.
    Returns the predictions list: [{"class": "pothole", "confidence": 0.89, "box": [x1,y1,x2,y2]}, ...]
    """
    client = _get_sagemaker_client()
    try:
        response = client.invoke_endpoint(
            EndpointName=SAGEMAKER_ENDPOINT,
            ContentType='image/jpeg',
            Accept='application/json',
            Body=image_bytes
        )
        response_body = response['Body'].read().decode('utf-8')
        result = json.loads(response_body)
        return result.get('predictions', [])
    except Exception as e:
        print(f"[Detection Worker] SageMaker invocation error: {e}")
        return []

def _draw_boxes(frame: np.ndarray, predictions: list) -> np.ndarray:
    """Draw bounding boxes and labels on the image frame."""
    drawn = frame.copy()
    for box_data in predictions:
        # Expected format: {"class": "pothole", "confidence": 0.89, "box": [x1, y1, x2, y2]}
        label = f"{box_data.get('class', 'damage')} ({box_data.get('confidence', 0.0):.2f})"
        try:
            x1, y1, x2, y2 = [int(v) for v in box_data.get('box', [0,0,0,0])]
        except Exception:
            continue
            
        cv2.rectangle(drawn, (x1, y1), (x2, y2), (0, 255, 255), 2)
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(drawn, (x1, y1 - 20), (x1 + w, y1), (0, 255, 255), -1)
        cv2.putText(drawn, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    return drawn

def _compute_severity(predictions: list) -> tuple:
    """
    Aggregate per-frame predictions into a single severity + confidence.
    Returns (severity, best_confidence, damage_classes).
    """
    if not predictions:
        return None, 0.0, []

    damage_classes = list({p['class'] for p in predictions})
    best_confidence = max(p['confidence'] for p in predictions)
    total_detections = len(predictions)
    avg_confidence = sum(p['confidence'] for p in predictions) / total_detections

    # Severity heuristic: based on number of detections + confidence
    if total_detections >= 5 or best_confidence >= 0.92:
        severity = "severe"
    elif total_detections >= 2 or best_confidence >= 0.80:
        severity = "moderate"
    else:
        severity = "minor"

    return severity, round(float(best_confidence), 3), damage_classes


def process_video_segment(filepath: str, metadata: dict, reports_table=None, events_store: list = None):
    """
    Background worker that processes a 5-second dashcam segment.
    1. Extracts frames from the video.
    2. Sends each frame to the SageMaker YOLO endpoint for road damage detection.
    3. If damage detected → extract evidence clip via FFmpeg.
    4. Reverse-geocode the GPS → get address string.
    5. Call Bedrock portal routing → get portal_url + portal_name.
    6. Store full event (with portal_url and sub_area) into events_store.
    """
    print(f"\n[Detection Worker] Processing segment: {os.path.basename(filepath)}")
    print(f"[Detection Worker] Metadata: {metadata}")

    # --- Step 1: Extract frames from the video ---
    frames = _extract_frames(filepath, max_frames=10)
    if not frames:
        print("[Detection Worker] No frames could be extracted. Segment discarded.\n")
        _cleanup(filepath)
        return None

    print(f"[Detection Worker] Extracted {len(frames)} frames for inference.")

    # --- Step 2: Send frames to SageMaker YOLO ---
    all_predictions = []
    frame_results = []
    import numpy as np
    
    for i, frame in enumerate(frames):
        success, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not success: continue
        frame_bytes = encoded.tobytes()
        
        start = time.time()
        preds = _invoke_sagemaker(frame_bytes)
        latency = time.time() - start
        print(f"[Detection Worker] Frame {i+1}: {len(preds)} detections in {latency:.2f}s")
        all_predictions.extend(preds)
        
        best_conf = max([p.get('confidence', 0) for p in preds]) if preds else 0
        frame_results.append({
            "frame": frame,
            "preds": preds,
            "best_conf": best_conf
        })

    # --- Step 3: Evaluate results ---
    severity, confidence, damage_classes = _compute_severity(all_predictions)

    if severity is None:
        print("[Detection Worker] Status: No road damage detected by YOLO. Segment discarded.\n")
        _cleanup(filepath)
        return None

    damage_type = damage_classes[0] if damage_classes else "road_damage"
    print(f"[Detection Worker] Status: Alert! Damage detected → {', '.join(damage_classes)}")
    print(f"[Detection Worker] Severity: {severity} | Best confidence: {confidence}")
    print(f"[Detection Worker] Total detections across frames: {len(all_predictions)}")

    # --- Step 4: Clip Extraction ---
    # Always try to produce a browser-friendly MP4 (H.264, moov atom at start).
    # If FFmpeg is unavailable, fall back to the original container/codec.
    clip_id = str(uuid.uuid4())[:8]
    input_ext = (os.path.splitext(filepath)[1] or "").lower()
    clip_filename = f"clip_{clip_id}.mp4"
    clip_path = os.path.join(os.path.dirname(filepath), clip_filename)

    def _ensure_even_scale_filter() -> str:
        return "scale=trunc(iw/2)*2:trunc(ih/2)*2"

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                filepath,
                "-ss",
                "00:00:01",
                "-t",
                "00:00:02",
                "-vf",
                _ensure_even_scale_filter(),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "28",
                "-preset",
                "veryfast",
                "-an",
                "-movflags",
                "+faststart",
                clip_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"[Detection Worker] FFmpeg Extracted Clip (H.264 MP4): {clip_filename}")

        # Redact the clip using Rekognition (best-effort)
        try:
            print(f"[Detection Worker] Starting PII redaction for evidence clip...")
            redacted_clip_path = clip_path.replace(".mp4", "_redacted.mp4")
            rekog = _get_rekognition_service()
            if rekog.redact_video(clip_path, redacted_clip_path):
                final_clip_path = clip_path.replace(".mp4", "_final.mp4")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        redacted_clip_path,
                        "-vf",
                        _ensure_even_scale_filter(),
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-crf",
                        "28",
                        "-preset",
                        "veryfast",
                        "-an",
                        "-movflags",
                        "+faststart",
                        final_clip_path,
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                os.remove(clip_path)
                os.remove(redacted_clip_path)
                os.rename(final_clip_path, clip_path)
                print(f"[Detection Worker] PII Redaction complete for clip.")
        except Exception as e:
            print(f"[Detection Worker] Video redaction failed: {e}")

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # Likely happens when input is WebM and we can't transcode, or FFmpeg is missing.
        fallback_ext = input_ext if input_ext else ".webm"
        clip_filename = f"clip_{clip_id}{fallback_ext}"
        clip_path = os.path.join(os.path.dirname(filepath), clip_filename)
        print(f"[Detection Worker] FFmpeg transcode failed ({e}). Falling back to original segment: {clip_filename}")
        shutil.copy2(filepath, clip_path)

    # --- Step 4.5: Best Images Extraction ---
    # Sort frames by best confidence
    frame_results.sort(key=lambda x: x["best_conf"], reverse=True)
    best_frames = frame_results[:3]
    
    extracted_images = []
    rekog = _get_rekognition_service()
    for idx, f_res in enumerate(best_frames):
        if not f_res["preds"]: continue
        drawn_frame = _draw_boxes(f_res["frame"], f_res["preds"])
        
        # Redact PII (Faces, License Plates) using Amazon Rekognition
        try:
            print(f"[Detection Worker] Redacting PII in extracted image {idx+1}...")
            final_frame = rekog.redact_image_ndarray(drawn_frame)
        except Exception as e:
            print(f"[Detection Worker] Redaction failed for image {idx+1}: {e}")
            final_frame = drawn_frame

        img_id = str(uuid.uuid4())[:8]
        img_filename = f"img_{img_id}.jpg"
        img_path = os.path.join(os.path.dirname(filepath), img_filename)
        cv2.imwrite(img_path, final_frame)
        extracted_images.append(f"/temp/dashcam/{img_filename}")

    # --- Step 5: Reverse-geocode GPS coordinates ---
    lat = metadata.get("lat")
    lng = metadata.get("lng")
    # Clean up JS stringified nulls
    if str(lat).lower() in ("undefined", "null", "none", ""): lat = None
    if str(lng).lower() in ("undefined", "null", "none", ""): lng = None
    
    portal_name = "CPGRAMS"
    portal_url = PORTALS_DB.get("CENTRAL", {}).get("CPGRAMS", "https://pgportal.gov.in/")
    sub_area = "Manual Upload"
    address_label = "Location not provided"

    if lat and lng:
        try:
            lat_f = float(lat)
            lng_f = float(lng)
            print(f"[Detection Worker] Reverse geocoding GPS: ({lat_f}, {lng_f})")
            address = reverse_geocode(lat_f, lng_f)
            if address:
                address_label = address.get("Address", "")
                city = address.get("City", "")
                district = address.get("District", "")
                state = address.get("State", "")
                sub_area = district or city or state or "Unknown"

                location_string = f"{address_label}, {city}, {district}, {state}"
                print(f"[Detection Worker] Address resolved: {location_string}")

                # Step 6: Use Bedrock to route to the correct government portal
                print(f"[Detection Worker] Calling Bedrock for portal routing...")
                routing = get_portal_routing(location_string, PORTALS_DB)
                if routing:
                    portal_name = routing.get("portal_name", portal_name)
                    portal_url = routing.get("portal_url", portal_url)
                    print(f"[Detection Worker] Portal routed: {portal_name} → {portal_url}")
                    print(f"[Detection Worker] Reasoning: {routing.get('reasoning', 'N/A')}")
            else:
                print(f"[Detection Worker] Reverse geocode returned no results.")
        except Exception as e:
            print(f"[Detection Worker] Location/Portal routing error: {e}")

    # --- Step 7: Build the full event record ---
    event_data = {
        "event_id": str(uuid.uuid4()),
        "type": damage_type,
        "severity": severity,
        "confidence": confidence,
        "lat": lat if lat is not None else 0.0,
        "lng": lng if lng is not None else 0.0,
        "timestamp": str(int(time.time())),
        "clip_url": f"/temp/dashcam/{clip_filename}",
        "address": address_label,
        "sub_area": sub_area,
        "portal_name": portal_name,
        "portal_url": portal_url,
        "userId": metadata.get("userId", "anonymous"),
        "damage_classes": damage_classes,
        "total_detections": len(all_predictions),
        "extracted_images": extracted_images
    }

    print(f"[Detection Worker] Storing event: {event_data['event_id']}")
    print(f"[Detection Worker] Portal: {portal_name} | Sub-area: {sub_area}")

    # Step 8: Append to user's events store
    if events_store is not None:
        events_store.append(event_data)
        print(f"[Detection Worker] Total events in store: {len(events_store)}")

    # Clean up original segment file
    _cleanup(filepath)

    return event_data


def _cleanup(filepath: str):
    """Remove a temporary file, ignoring errors."""
    try:
        os.remove(filepath)
    except Exception:
        pass
