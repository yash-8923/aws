import os
import subprocess
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from fastapi import FastAPI, File, UploadFile, Form
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
import mimetypes
import time
import uuid
import io
from aws_services.transcribe import upload_audio_to_s3, start_transcription_job, poll_transcription_job, extract_transcript
from aws_services.location import reverse_geocode, verify_address
from aws_services.bedrock import get_portal_routing, generate_complaint_draft, generate_cluster_complaint
from aws_services.detection_worker import process_video_segment
from aws_services.rekognition import RekognitionService
import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor

# Load environment variables from .env file
load_dotenv()

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

app = FastAPI(title="JanSahay PWA API (Mock)")
_dashcam_executor = ThreadPoolExecutor(max_workers=int(os.getenv("DASHCAM_WORKERS", "2")))

# CORS Middleware to allow requests from the Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session Middleware for Authlib OAuth
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY") or os.urandom(24).hex(),
    https_only=True,
    same_site='none'
)

oauth = OAuth()

cognito_metadata_url = f"https://cognito-idp.{os.getenv('AWS_REGION', 'ap-south-1')}.amazonaws.com/{os.getenv('COGNITO_USER_POOL_ID')}/.well-known/openid-configuration"

oauth.register(
    name='cognito',
    client_id=os.getenv("COGNITO_CLIENT_ID", "mock-client-id"),
    client_secret=os.getenv("COGNITO_CLIENT_SECRET", "mock-secret"),
    server_metadata_url=cognito_metadata_url,
    client_kwargs={'scope': 'email openid phone'}
)

oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID", "mock-google-client-id"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", "mock-google-secret"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

@app.get("/api/health")
def read_root():
    return {"message": "JanSahay AWS API Running"}

# --- AWS Configuration & Initialization ---
import boto3
from botocore.exceptions import ClientError, BotoCoreError, NoCredentialsError, NoCredentialsError
from fastapi import HTTPException

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
USERS_TABLE_NAME = os.getenv("USERS_TABLE_NAME")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

try:
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    cognito_client = boto3.client('cognito-idp', region_name=AWS_REGION)
    rekognition_service = RekognitionService(region_name=AWS_REGION)
    # Maintain the attribute for backward compatibility if needed, though we'll use rekognition_service
    rekognition_client = rekognition_service.client 
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    reports_table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    users_table = dynamodb.Table(USERS_TABLE_NAME)
    print("AWS Services (S3, Cognito, Rekognition, DynamoDB) configured successfully.")
except Exception as e:
    print(f"Warning: Failed to initialize AWS clients. Ensure credentials are set. Error: {e}")
    s3_client, cognito_client, rekognition_client, rekognition_service, reports_table, users_table = None, None, None, None, None, None

# --- Per-user in-memory event store for detected potholes ---
# Dict mapping userId -> list of events.  Each user only sees their own.
POTHOLE_EVENTS = {}   # { userId: [event1, event2, ...] }

# --- Engineer 1: Identity & Authorization (OAuth 2.0 Hosted UI) ---

@app.get("/login")
async def login(request: Request):
    if os.getenv('COGNITO_USER_POOL_ID') is None:
        # If no real Cognito pool is configured, jump straight to the mock fallback
        return RedirectResponse(url=f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/authorize")
    
    redirect_uri = f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/authorize"
    return await oauth.cognito.authorize_redirect(request, redirect_uri)

@app.get("/authorize")
async def authorize(request: Request):
    try:
        token = await oauth.cognito.authorize_access_token(request)
        user = token.get('userinfo')
        if user:
            # Avoid saving id_token and access_token in session. They exceed 4KB cookie limits!
            
            uuid_sub = user.get('sub')
            user_email = user.get('email', '')
            user_metadata = None
            if uuid_sub and users_table:
                try:
                    from boto3.dynamodb.conditions import Attr
                    # 1. Try to find user by email first
                    if user_email:
                        response = users_table.scan(FilterExpression=Attr('email').eq(user_email))
                        if response.get('Items'):
                            user_metadata = response['Items'][0]
                            uuid_sub = user_metadata.get('userId')
                            user['sub'] = uuid_sub # Force the session to use the existing mapped user id
                            print(f"Returning user found by email in DynamoDB: {user_email} -> {uuid_sub}")
                    
                    # 2. Fallback to sub if not found by email
                    if not user_metadata:
                        db_response = users_table.get_item(Key={'userId': uuid_sub})
                        user_metadata = db_response.get('Item')

                    if not user_metadata:
                        import time as _time
                        extracted_name = user.get('name')
                        if not extracted_name and user_email:
                            extracted_name = user_email.split('@')[0]
                            
                        user_metadata = {
                            'userId':       uuid_sub,
                            'name':         extracted_name or '',
                            'email':        user_email,
                            'phone_number': user.get('phone_number', ''),
                            'createdAt':    str(int(_time.time())),
                        }
                        users_table.put_item(Item=user_metadata)
                        print(f"New user created in DynamoDB: {uuid_sub}")
                    elif user_metadata:
                        print(f"Returning user found in DynamoDB: {uuid_sub}")

                except Exception as e:
                    print(f"Warning DB: {e}")
            
            request.session['user'] = user
            request.session['userData'] = user_metadata
            return RedirectResponse(url=f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth-success.html")
            
    except Exception as e:
        print(f"OAuth Callback Error: {e}")
        # fallback for mock testing without real AWS flow
        user = {"name": "Mock User", "email": "mock@example.com", "sub": "mock-sub-uuid", "phone_number": "+910000000000"}
        request.session['user'] = user
        request.session['id_token'] = "mock-token"
        
        if users_table:
            try:
                import time as _time
                user_metadata = {
                    'userId':       user['sub'],
                    'name':         user['name'],
                    'email':        user['email'],
                    'phone_number': user['phone_number'],
                    'createdAt':    str(int(_time.time())),
                }
                users_table.put_item(Item=user_metadata)
                request.session['userData'] = user_metadata
                print(f"Created mocked user in DynamoDB: {user['sub']}")
            except Exception as db_e:
                print(f"Warning DB Mock Insert: {db_e}")
                
        return RedirectResponse(url=f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth-success.html")
        
    return JSONResponse({"error": "Failed to login"}, status_code=400)

@app.get("/login/google")
async def login_google(request: Request):
    if os.getenv('GOOGLE_CLIENT_ID') is None:
        # If no real Google OAuth is configured, jump straight to the mock fallback
        return RedirectResponse(url=f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/authorize/google")
    
    redirect_uri = f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/authorize/google"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/authorize/google")
async def authorize_google(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user = token.get('userinfo')
        if user:
            # Avoid saving large tokens inside session dict
            
            uuid_sub = user.get('sub')
            user_email = user.get('email', '')
            user_metadata = None
            if uuid_sub and users_table:
                try:
                    from boto3.dynamodb.conditions import Attr
                    # 1. Try to find user by email first
                    if user_email:
                        response = users_table.scan(FilterExpression=Attr('email').eq(user_email))
                        if response.get('Items'):
                            user_metadata = response['Items'][0]
                            uuid_sub = user_metadata.get('userId')
                            user['sub'] = uuid_sub # Force the session to use the existing mapped user id
                            print(f"Returning Google user found by email in DynamoDB: {user_email} -> {uuid_sub}")
                    
                    # 2. Fallback to sub if not found by email
                    if not user_metadata:
                        db_response = users_table.get_item(Key={'userId': uuid_sub})
                        user_metadata = db_response.get('Item')

                    if not user_metadata:
                        import time as _time
                        user_metadata = {
                            'userId':       uuid_sub,
                            'name':         user.get('name', ''),
                            'email':        user_email,
                            'phone_number': '', # Google might not give phone based on scope
                            'createdAt':    str(int(_time.time())),
                            'provider':     'google'
                        }
                        users_table.put_item(Item=user_metadata)
                        print(f"New Google user created in DynamoDB: {uuid_sub}")
                    elif user_metadata:
                        print(f"Returning Google user found in DynamoDB: {uuid_sub}")

                except Exception as e:
                    print(f"Warning DB: {e}")
            
            request.session['user'] = user
            request.session['userData'] = user_metadata
            return RedirectResponse(url=f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/")
            
    except Exception as e:
        print(f"Google OAuth Callback Error: {e}")
        # fallback for mock testing without real Google flow
        user = {"email": "mock-google@example.com", "sub": "mock-google-uuid", "name": "Google User"}
        request.session['user'] = user
        request.session['id_token'] = "mock-google-token"
        
        if users_table:
            try:
                import time as _time
                user_metadata = {
                    'userId':       user['sub'],
                    'name':         user['name'],
                    'email':        user['email'],
                    'phone_number': '',
                    'createdAt':    str(int(_time.time())),
                    'provider':     'google'
                }
                users_table.put_item(Item=user_metadata)
                request.session['userData'] = user_metadata
            except Exception as db_e:
                print(f"Warning DB Mock Insert: {db_e}")
                
        return RedirectResponse(url=f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth-success.html")
        
    return JSONResponse({"error": "Failed to login with Google"}, status_code=400)

@app.get("/api/auth/me")
async def get_current_user(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    return {
        "user": user, 
        "userData": request.session.get('userData'),
        "token": request.session.get('id_token')
    }

@app.post("/api/auth/logout")
async def logout(request: Request):
    request.session.pop('user', None)
    request.session.pop('id_token', None)
    return {"message": "Logged out successfully"}

class DraftRequest(BaseModel):
    damageType: str | None = None
    severity: str | None = None
    jurisdiction: str | None = None
    ward: str | None = None
    description: str | None = None
    lat: float | str | None = None
    lng: float | str | None = None

# --- Engineer 1: Object Storage (S3 Evidence Vault) ---
@app.post("/api/evidence/upload")
async def upload_evidence_to_s3(evidence: UploadFile = File(...), ticketId: str = Form(...)):
    if not s3_client:
        print(f"[Mock S3] Uploading {evidence.filename} for ticket {ticketId}")
        time.sleep(1)
        return {"message": "Mock upload successful", "s3_uri": f"s3://mock-bucket/reports/{ticketId}/{evidence.filename}"}
    
    try:
        s3_key = f"reports/{ticketId}/{evidence.filename}"
        
        file_content = await evidence.read()
        final_content = file_content
        
        # Automatic PII Redaction for Images
        if evidence.content_type and "image" in evidence.content_type.lower() and rekognition_service:
            try:
                print(f"[Rekognition] Redacting PII from evidence: {evidence.filename}")
                redacted_bytes, faces, plates = rekognition_service.redact_pii(file_content)
                final_content = redacted_bytes
                print(f"[Rekognition] Redaction complete: {faces} faces, {plates} text regions.")
            except Exception as e:
                print(f"[Rekognition] Redaction failed, uploading original: {e}")
                final_content = file_content

        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=final_content,
            ContentType=evidence.content_type
        )
        return {
            "message": "Upload successful (Redaction applied if image)",
            "s3_uri": f"s3://{S3_BUCKET_NAME}/{s3_key}"
        }
    except Exception as e:
        print(f"S3 Upload Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload evidence to S3")

# --- Engineer 2: Dashcam Processing Pipeline ---
@app.post("/api/dashcam/upload")
async def upload_dashcam_segment(
    request: Request,
    segment: UploadFile = File(...), 
    lat: str = Form(None), 
    lng: str = Form(None)
):
    # Extract userId from the session so events are tied to this user
    user = request.session.get('user')
    user_id = user.get('sub', 'anonymous') if user else 'anonymous'

    print(f"[Dashcam] Received segment: {segment.filename} (Lat: {lat}, Lng: {lng}) [User: {user_id}]")
    
    # Save the chunk locally for the worker to process
    temp_dir = os.path.join(os.getcwd(), "temp", "dashcam")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{str(uuid.uuid4())[:8]}_{segment.filename}")
    
    with open(temp_path, "wb") as buffer:
        buffer.write(await segment.read())
        
    metadata = {
        "lat": lat,
        "lng": lng,
        "userId": user_id
    }
    
    # Ensure the user has an events list
    if user_id not in POTHOLE_EVENTS:
        POTHOLE_EVENTS[user_id] = []
    
    # Check duration to decide if we need to split the video
    import cv2 as _cv2
    cap = _cv2.VideoCapture(temp_path)
    fps = cap.get(_cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    duration = total_frames / fps if fps > 0 else 0

    SEGMENT_DURATION = 10  # seconds per chunk

    if duration > SEGMENT_DURATION + 2:
        # Split long video into SEGMENT_DURATION-second chunks using FFmpeg
        num_segments = int(duration // SEGMENT_DURATION) + (1 if duration % SEGMENT_DURATION > 2 else 0)
        print(f"[Dashcam] Long video detected ({duration:.1f}s). Splitting into {num_segments} segments of ~{SEGMENT_DURATION}s each.")

        segment_paths = []
        for i in range(num_segments):
            start_time = i * SEGMENT_DURATION
            seg_filename = f"seg{i}_{str(uuid.uuid4())[:6]}.mp4"
            seg_path = os.path.join(temp_dir, seg_filename)
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", temp_path,
                     "-ss", str(start_time), "-t", str(SEGMENT_DURATION),
                     "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-an",
                     seg_path],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=60
                )
                segment_paths.append(seg_path)
            except Exception as e:
                print(f"[Dashcam] FFmpeg segment {i} failed: {e}")

        # Remove original after splitting
        try:
            os.remove(temp_path)
        except Exception:
            pass

        if not segment_paths:
            return {"message": "Failed to split video", "status": "error"}

        # Queue each sub-segment for asynchronous processing
        for seg_path in segment_paths:
            _dashcam_executor.submit(process_video_segment, seg_path, metadata, reports_table, POTHOLE_EVENTS[user_id])

        return {
            "message": f"Video split into {len(segment_paths)} segments, all queued for AI detection",
            "status": "processing",
            "segments": len(segment_paths)
        }
    else:
        # Short video segment: process asynchronously
        _dashcam_executor.submit(process_video_segment, temp_path, metadata, reports_table, POTHOLE_EVENTS[user_id])
        return {"message": "Segment queued for AI detection", "status": "processing"}

# --- Engineer 1: Database (DynamoDB Reports Table) ---
@app.post("/api/reports/save")
async def save_report_dynamodb(request: Request, data: dict):
    # Attach userId from session so reports are tied to the user's account
    user = request.session.get('user')
    if user and user.get('sub'):
        data['userId'] = user['sub']

    if not reports_table:
        print(f"[Mock DynamoDB] Saving report: {data}")
        time.sleep(1)
        return {"message": "Mock save successful", "ticketId": data.get("ticketId")}
    
    try:
        # Convert any float values to strings to satisfy DynamoDB requirements easily
        if 'lat' in data and data['lat'] is not None: data['lat'] = str(data['lat'])
        if 'lng' in data and data['lng'] is not None: data['lng'] = str(data['lng'])
        
        reports_table.put_item(Item=data)
        return {"message": "Report saved successfully", "ticketId": data.get("ticketId")}
    except Exception as e:
        print(f"DynamoDB Save Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save report to DynamoDB")


# --- Fetch reports for the logged-in user (account-bound) ---
@app.get("/api/reports/me")
async def get_my_reports(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user.get('sub')
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in session")

    if not reports_table:
        # Mock fallback — return empty list when DynamoDB is not configured
        return {"reports": [], "count": 0}

    try:
        from boto3.dynamodb.conditions import Key, Attr

        # Try GSI first (userId-timestamp-index), fall back to scan + filter
        try:
            response = reports_table.query(
                IndexName='userId-timestamp-index',
                KeyConditionExpression=Key('userId').eq(user_id),
                ScanIndexForward=False  # newest first
            )
            items = response.get('Items', [])
        except Exception as gsi_err:
            print(f"GSI query failed ({gsi_err}), falling back to scan")
            response = reports_table.scan(
                FilterExpression=Attr('userId').eq(user_id)
            )
            items = response.get('Items', [])
            # Manual sort by timestamp descending
            items.sort(key=lambda x: int(x.get('timestamp', 0)), reverse=True)

        return {"reports": items, "count": len(items)}
    except Exception as e:
        print(f"DynamoDB Query Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to fetch reports")


# --- Profile stats for the logged-in user ---
@app.get("/api/profile/stats")
async def get_profile_stats(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user.get('sub')
    user_data = request.session.get('userData', {})

    report_count = 0
    areas_mapped = set()

    if reports_table and user_id:
        try:
            from boto3.dynamodb.conditions import Key, Attr
            try:
                response = reports_table.query(
                    IndexName='userId-timestamp-index',
                    KeyConditionExpression=Key('userId').eq(user_id),
                    Select='ALL_ATTRIBUTES'
                )
                items = response.get('Items', [])
            except Exception:
                response = reports_table.scan(
                    FilterExpression=Attr('userId').eq(user_id)
                )
                items = response.get('Items', [])

            report_count = len(items)
            for item in items:
                jurisdiction = item.get('jurisdiction')
                if isinstance(jurisdiction, dict):
                    ward = jurisdiction.get('ward_district', '')
                    if ward:
                        areas_mapped.add(ward)
                elif isinstance(jurisdiction, str) and jurisdiction:
                    areas_mapped.add(jurisdiction)
        except Exception as e:
            print(f"Profile stats error: {e}")

    # Determine contributor level based on report count
    if report_count >= 20:
        level = 5
    elif report_count >= 10:
        level = 4
    elif report_count >= 5:
        level = 3
    elif report_count >= 1:
        level = 2
    else:
        level = 1

    display_name = user_data.get('name') if user_data and user_data.get('name') else user.get('name')
    if not display_name and user.get('email'):
        display_name = user.get('email').split('@')[0]
    if not display_name:
        display_name = 'Citizen Reporter'

    return {
        "userId": user_id,
        "email": user.get('email', ''),
        "name": display_name,
        "report_count": report_count,
        "areas_mapped": len(areas_mapped),
        "contributor_level": level,
        "member_since": user_data.get('createdAt', '') if user_data else ''
    }


# Feature 2 Endpoint: Voice Transcription
@app.post("/api/transcribe")
async def mock_transcribe(audio: UploadFile = File(...)):
    print(f"[AWS Transcribe] Started transcription for {audio.filename}")
    print(f"DEBUG AWS_ACCESS_KEY_ID in main.py: {os.getenv('AWS_ACCESS_KEY_ID')}")
    print(f"DEBUG S3_BUCKET_NAME in main.py: {os.getenv('S3_BUCKET_NAME')}")
    
    # 1. Save uploaded file temporarily
    temp_dir = os.path.join(os.getcwd(), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{audio.filename}")
    
    with open(temp_path, "wb") as buffer:
        buffer.write(await audio.read())
        
    bucket_name = os.getenv("S3_BUCKET_NAME", "sewa-sahayak-evidence-vault-mumbai")
    s3_object_name = f"audio/{os.path.basename(temp_path)}"
    
    # 2. Upload to S3
    print(f"Uploading {temp_path} to S3 bucket {bucket_name} as {s3_object_name}...")
    s3_uri = upload_audio_to_s3(temp_path, bucket_name, s3_object_name)
    
    if not s3_uri:
        return {"error": "Failed to upload audio to S3"}
        
    # 3. Start Transcribe Job
    job_name = f"sewa_sahayak_transcribe_{str(uuid.uuid4())[:8]}"
    print(f"Starting Transcription Job: {job_name} for URI: {s3_uri}...")
    
    # Extract extension for format
    ext = audio.filename.split('.')[-1].lower()
    format_mapping = {'webm': 'webm', 'mp3': 'mp3', 'm4a': 'm4a', 'mp4': 'mp4', 'wav': 'wav'}
    audio_format = format_mapping.get(ext, 'webm')
    
    started_job = start_transcription_job(job_name, s3_uri, audio_format)
    if not started_job:
        return {"error": "Failed to start transcription job"}
        
    # 4. Poll and wait for completion
    print(f"Polling job {job_name} for completion...")
    result = poll_transcription_job(job_name, max_retries=60, wait_seconds=3)
    
    if result.get("TranscriptionJobStatus") != "COMPLETED":
        return {"error": "Transcription failed or timed out", "details": result}
        
    # 5. Extract the text
    print(f"Job {job_name} completed. Extracting transcript...")
    transcript_text = extract_transcript(result)
    detected_language = result.get("LanguageCode", "unknown")
    
    # Clean up temp file
    try:
        os.remove(temp_path)
    except Exception as e:
        print(f"Failed to remove temp file: {e}")
        
    # Note: PII redaction on transcript and specific damage extraction 
    # would ideally be done via Amazon Comprehend or Bedrock here.
    # For now, we return the raw transcript.
    
    return {
        "transcript": transcript_text,
        "detectedLanguage": detected_language,
        "extractedData": {
            "damage_type": "civic issue (requires AI extraction)",
            "location_description": "extracted from transcript",
            "severity_keywords": []
        },
        "confidence": 0.95,
        "piiRedacted": False
    }

# Feature 3 Endpoint
@app.post("/api/analyze")
async def mock_analyze(media: UploadFile = File(...), type: str = Form(...)):
    print(f"[Amazon Bedrock Nova Pro] Started visual analysis for: {type}")
    time.sleep(2.0) # Simulate LLM analysis
    return {
        "damage_type": "pothole",
        "severity": "high",
        "confidence_score": 0.98,
        "suggested_description": "Deep pothole identified on asphalt road surface. Edges are jagged indicating recent widening. Poses immediate risk to two-wheelers.",
        "bounding_box": {"x": 0.2, "y": 0.4, "w": 0.5, "h": 0.3}
    }

from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw
import io

# Feature 4 Endpoint
@app.post("/api/redact")
async def mock_redact(media: UploadFile = File(...)):
    print(f"[Amazon Rekognition] Scanning media for PII...")
    
    # Read the file bytes
    image_bytes = await media.read()
    
    if not rekognition_service:
        print("[Mock Rekognition] Returning unredacted mock image because service is None.")
        return StreamingResponse(io.BytesIO(image_bytes), media_type=media.content_type, headers={
            "X-Faces-Redacted": "0", "X-Plates-Redacted": "0"
        })
        
    try:
        redacted_bytes, faces_count, plates_count = rekognition_service.redact_pii(image_bytes)
        
        headers = {
            "X-Faces-Redacted": str(faces_count),
            "X-Plates-Redacted": str(plates_count),
            "Access-Control-Expose-Headers": "X-Faces-Redacted, X-Plates-Redacted"
        }
        
        print(f"[Amazon Rekognition] Successfully blurred {faces_count} faces and {plates_count} personal info regions.")
        return StreamingResponse(io.BytesIO(redacted_bytes), media_type=media.content_type, headers=headers)
            
    except Exception as e:
        print(f"Rekognition Error: {e}")
        return StreamingResponse(io.BytesIO(image_bytes), media_type=media.content_type, headers={
            "X-Faces-Redacted": "0", "X-Plates-Redacted": "0"
        })
        
# Note: Live redaction has been removed from the dashcam feed.
# PII redaction (faces, license plates) is applied only to evidence 
# artifacts (clips + images) generated by the detection_worker pipeline.

class RouteRequest(BaseModel):
    lat: float | None = None
    lng: float | None = None
    state: str | None = None
    city: str | None = None
    address: str | None = None

# Load PORTAL_DB
try:
    with open(os.path.join(os.path.dirname(__file__), "portals.json"), "r") as f:
        PORTALS_DB = json.load(f)
except Exception:
    PORTALS_DB = {}

# Feature 5 Endpoint: Cognitive Dispatcher
@app.post("/api/route")
def route_complaint(route_req: RouteRequest):
    print(f"[Cognitive Dispatcher] Processing routing request: {route_req}")
    structured_address = None
    
    # Scenario A: High-Trust Reporting (GPS Enabled)
    if route_req.lat is not None and route_req.lng is not None:
        print("[Location Service] Using Reverse Geocoding...")
        structured_address = reverse_geocode(route_req.lat, route_req.lng)
        
    # Scenario B: Manual Reporting (No GPS / Gallery Uploads)
    elif route_req.state and route_req.city and route_req.address:
        print("[Location Service] Using Geocoding Verification...")
        structured_address = verify_address(route_req.state, route_req.city, route_req.address)
        
    if not structured_address:
        if route_req.address or route_req.city or route_req.state:
            location_string = f"{route_req.address or ''}, {route_req.city or ''}, {route_req.state or ''}".strip(", ")
        else:
            return {
                "structured_address": None,
                "routing": {
                    "portal_name": "CPGRAMS",
                    "portal_url": PORTALS_DB.get("CENTRAL", {}).get("CPGRAMS", "https://pgportal.gov.in/Registration"),
                    "reasoning": "Insufficient location data provided. Routing to the central CPGRAMS portal as a default fallback."
                }
            }
    else:
        location_string = (
            structured_address.get("Address")
            if structured_address
            else f"{route_req.address or ''}, {route_req.city or ''}, {route_req.state or ''}"
        )
        
    print(f"[Bedrock Nova Pro] Determining portal for: {location_string}")
    # 2 & 3: The Routing Knowledge Base & The LLM System Prompt
    routing_result = get_portal_routing(location_string, PORTALS_DB)
    
    if not routing_result:
        raise HTTPException(status_code=500, detail="Failed to route complaint")
        
    # --- Nova Act: Extract form fields from the routed portal ---
    form_fields = {}
    portal_url = routing_result.get("portal_url", "")
    portal_name = routing_result.get("portal_name", "Unknown")
    if portal_url:
        try:
            print(f"[Nova Act] Scraping form fields from: {portal_name} ({portal_url})")
            form_fields = extract_form_fields(portal_url=portal_url, portal_name=portal_name)
        except Exception as e:
            print(f"[Nova Act] Scraping failed for {portal_name}, continuing without form fields: {e}")
            form_fields = {"error": str(e)}

    return {
        "structured_address": structured_address,
        "routing": routing_result,
        "form_schema": form_fields
    }

# Feature 6 Endpoint
@app.post("/api/draft")
async def generate_draft_endpoint(data: dict):
    print(f"[Amazon Bedrock] Generating dynamic AI draft for data: {data}")
    
    # Use the Bedrock service to generate a professional draft
    draft = generate_complaint_draft(data)
    
    # Ensure some fields are present even if LLM missed them
    if not draft.get("phoneNumber"):
        draft["phoneNumber"] = "+91-9876543210"
        
    return draft

# Serve static assets from Vite dist folder (only if built)
_dist_assets_dir = os.path.join(os.path.dirname(__file__), "..", "dist", "assets")
if os.path.isdir(_dist_assets_dir):
    app.mount("/assets", StaticFiles(directory=_dist_assets_dir), name="assets")

# Serve the temp directory for clips and extracted images
import os
os.makedirs("temp", exist_ok=True)
app.mount("/temp", StaticFiles(directory="temp"), name="temp")


# --- Engineer 3: Pothole Clustering & AI Complaint Generation ---

def _get_user_events(user_id: str) -> list:
    """Return the events list for a given userId (empty list if none)."""
    return POTHOLE_EVENTS.get(user_id, [])


def _build_portal_clusters(events: list):
    """
    Clusters detected pothole events in two tiers:
      1. Group by portal_url (which government website to file on)
      2. Within each portal, sub-group by sub_area (district/city/ward)
    Returns a flat list of clusters for the map, each tied to a portal.
    """
    from collections import defaultdict

    # Tier 1: group by portal_url
    portal_groups = defaultdict(list)
    for event in events:
        portal_url = event.get("portal_url", "unknown")
        portal_groups[portal_url].append(event)

    clusters = []
    cluster_counter = 0

    for portal_url, portal_events in portal_groups.items():
        # Tier 2: sub-group by sub_area within this portal
        sub_area_groups = defaultdict(list)
        for ev in portal_events:
            sub_area_groups[ev.get("sub_area", "Unknown")].append(ev)

        for sub_area, sub_events in sub_area_groups.items():
            cluster_counter += 1

            # Compute aggregate stats
            lats = [float(e["lat"]) for e in sub_events if e.get("lat")]
            lngs = [float(e["lng"]) for e in sub_events if e.get("lng")]
            center_lat = sum(lats) / len(lats) if lats else 0
            center_lng = sum(lngs) / len(lngs) if lngs else 0

            severities = [e.get("severity", "minor") for e in sub_events]
            worst = "severe" if "severe" in severities else ("moderate" if "moderate" in severities else "minor")

            # Pick the most recent clip as representative
            sorted_events = sorted(sub_events, key=lambda e: e.get("timestamp", "0"), reverse=True)
            representative_clip = sorted_events[0].get("clip_url", "")
            
            # Gather best images (sorted by confidence)
            events_by_conf = sorted(sub_events, key=lambda e: e.get("confidence", 0), reverse=True)
            best_images = []
            for e in events_by_conf:
                images = e.get("extracted_images", [])
                for img in images:
                    if img not in best_images:
                        best_images.append(img)
                if len(best_images) >= 4:
                    break
            best_images = best_images[:4]

            clusters.append({
                "cluster_id": f"cluster_{cluster_counter:03d}",
                "portal_name": sub_events[0].get("portal_name", "Unknown"),
                "portal_url": portal_url,
                "sub_area": sub_area,
                "latitude": center_lat,
                "longitude": center_lng,
                "event_count": len(sub_events),
                "severity": worst,
                "road_name": sub_area,
                "representative_clip": representative_clip,
                "best_images": best_images,
                "events": [
                    {
                        "event_id": e["event_id"],
                        "severity": e["severity"],
                        "confidence": e["confidence"],
                        "lat": e.get("lat"),
                        "lng": e.get("lng"),
                        "clip_url": e.get("clip_url"),
                        "address": e.get("address", ""),
                        "timestamp": e.get("timestamp")
                    }
                    for e in sorted_events
                ]
            })

    return clusters


@app.get("/api/clusters")
def get_pothole_clusters(request: Request):
    """
    Returns pothole clusters for the logged-in user only.
    """
    user = request.session.get('user')
    user_id = user.get('sub', 'anonymous') if user else 'anonymous'
    user_events = _get_user_events(user_id)
    print(f"[Clustering Engine] Building clusters from {len(user_events)} events for user {user_id}...")
    clusters = _build_portal_clusters(user_events)
    print(f"[Clustering Engine] Produced {len(clusters)} clusters.")
    return {"clusters": clusters}


@app.get("/api/events")
def get_all_events(request: Request):
    """Returns all raw detected pothole events for the logged-in user."""
    user = request.session.get('user')
    user_id = user.get('sub', 'anonymous') if user else 'anonymous'
    user_events = _get_user_events(user_id)
    return {"events": user_events, "total": len(user_events)}


class MarkFiledRequest(BaseModel):
    cluster_id: str
    portal_url: str
    sub_area: str
    portal_name: str
    road_name: str
    latitude: float
    longitude: float

@app.post("/api/clusters/mark_filed")
def mark_cluster_filed(req: MarkFiledRequest, request: Request):
    """
    Marks a cluster as filed. Removes the associated events from the map
    and saves a reference to DynamoDB so it appears in "My Reports".
    """
    user = request.session.get('user')
    user_id = user.get('sub', 'anonymous') if user else 'anonymous'
    
    # 1. Store a report record in DynamoDB
    if reports_table:
        try:
            report_data = {
                "ticketId": f"FILED-{req.cluster_id}-{int(time.time())}",
                "userId": user_id,
                "jurisdiction": {
                    "portal_name": req.portal_name,
                    "ward_district": req.sub_area,
                    "portal_url": req.portal_url
                },
                "ward": req.sub_area,  # backward-compat for older frontend schemas
                "lat": str(req.latitude),
                "lng": str(req.longitude),
                "damageType": "Road Damage Cluster",
                "severity": "High",
                "status": "Submitted to Portal",
                "timestamp": int(time.time() * 1000),
                "description": f"Automated dashcam report filed to {req.portal_name} for area {req.sub_area}."
            }
            reports_table.put_item(Item=report_data)
        except Exception as e:
            print(f"Error saving filed report to DynamoDB: {e}")

    # 2. Clear those events from the user's active map
    if user_id in POTHOLE_EVENTS:
        original_count = len(POTHOLE_EVENTS[user_id])
        # Keep events that DO NOT match both portal_url and sub_area
        POTHOLE_EVENTS[user_id] = [
            e for e in POTHOLE_EVENTS[user_id]
            if not (e.get("portal_url") == req.portal_url and e.get("sub_area") == req.sub_area)
        ]
        removed_count = original_count - len(POTHOLE_EVENTS[user_id])
        print(f"[Map] Removed {removed_count} events from map since cluster {req.cluster_id} is filed.")

    return {"message": "Cluster filed successfully and events cleared from map."}



@app.post("/api/test/seed_events")
def seed_test_events(request: Request):
    """
    Injects realistic mock pothole events for the logged-in user.
    Creates multiple sub-areas within the same portal to verify grouping.
    """
    import random

    user = request.session.get('user')
    user_id = user.get('sub', 'anonymous') if user else 'anonymous'

    if user_id not in POTHOLE_EVENTS:
        POTHOLE_EVENTS[user_id] = []

    test_events = [
        # --- Portal: AHMEDABAD_AMC (3 sub-areas) ---
        # Sub-area: Navrangpura (3 events)
        {"lat": "23.0365", "lng": "72.5611", "sub_area": "Navrangpura", "portal_name": "AHMEDABAD_AMC",
         "portal_url": "https://www.amccrs.com/AMCPortal/View/ComplaintRegistration.aspx",
         "address": "CG Road, Navrangpura, Ahmedabad, Gujarat"},
        {"lat": "23.0370", "lng": "72.5620", "sub_area": "Navrangpura", "portal_name": "AHMEDABAD_AMC",
         "portal_url": "https://www.amccrs.com/AMCPortal/View/ComplaintRegistration.aspx",
         "address": "Law Garden, Navrangpura, Ahmedabad, Gujarat"},
        {"lat": "23.0358", "lng": "72.5605", "sub_area": "Navrangpura", "portal_name": "AHMEDABAD_AMC",
         "portal_url": "https://www.amccrs.com/AMCPortal/View/ComplaintRegistration.aspx",
         "address": "Swastik Cross Road, Navrangpura, Ahmedabad, Gujarat"},
        # Sub-area: Maninagar (2 events)
        {"lat": "23.0050", "lng": "72.6050", "sub_area": "Maninagar", "portal_name": "AHMEDABAD_AMC",
         "portal_url": "https://www.amccrs.com/AMCPortal/View/ComplaintRegistration.aspx",
         "address": "Maninagar Station Road, Maninagar, Ahmedabad, Gujarat"},
        {"lat": "23.0045", "lng": "72.6060", "sub_area": "Maninagar", "portal_name": "AHMEDABAD_AMC",
         "portal_url": "https://www.amccrs.com/AMCPortal/View/ComplaintRegistration.aspx",
         "address": "Kagdapith, Maninagar, Ahmedabad, Gujarat"},
        # Sub-area: SG Highway (2 events)
        {"lat": "23.0225", "lng": "72.5100", "sub_area": "SG Highway", "portal_name": "AHMEDABAD_AMC",
         "portal_url": "https://www.amccrs.com/AMCPortal/View/ComplaintRegistration.aspx",
         "address": "SG Highway near Thaltej, Ahmedabad, Gujarat"},
        {"lat": "23.0240", "lng": "72.5090", "sub_area": "SG Highway", "portal_name": "AHMEDABAD_AMC",
         "portal_url": "https://www.amccrs.com/AMCPortal/View/ComplaintRegistration.aspx",
         "address": "SG Highway near Sola, Ahmedabad, Gujarat"},

        # --- Portal: GUJARAT_SWAGAT (2 sub-areas) ---
        # Sub-area: Gandhinagar District (2 events)
        {"lat": "23.2156", "lng": "72.6369", "sub_area": "Gandhinagar District", "portal_name": "GUJARAT_SWAGAT",
         "portal_url": "https://swagat.gujarat.gov.in/",
         "address": "Sector 21, Gandhinagar, Gujarat"},
        {"lat": "23.2200", "lng": "72.6400", "sub_area": "Gandhinagar District", "portal_name": "GUJARAT_SWAGAT",
         "portal_url": "https://swagat.gujarat.gov.in/",
         "address": "Infocity, Gandhinagar, Gujarat"},
        # Sub-area: Mehsana District (1 event)
        {"lat": "23.5880", "lng": "72.3693", "sub_area": "Mehsana District", "portal_name": "GUJARAT_SWAGAT",
         "portal_url": "https://swagat.gujarat.gov.in/",
         "address": "NH-48 near Mehsana, Gujarat"},

        # --- Portal: NHAI (1 sub-area) ---
        {"lat": "23.1000", "lng": "72.5500", "sub_area": "NH-48 Stretch", "portal_name": "NHAI",
         "portal_url": "https://pgportal.gov.in/",
         "address": "NH-48 Ahmedabad-Vadodara Expressway, Gujarat"},
        {"lat": "23.1020", "lng": "72.5480", "sub_area": "NH-48 Stretch", "portal_name": "NHAI",
         "portal_url": "https://pgportal.gov.in/",
         "address": "NH-48 near Adalaj, Gujarat"},
    ]

    for ev_data in test_events:
        severity = random.choice(["minor", "moderate", "severe"])
        confidence = round(random.uniform(0.75, 0.98), 2)
        event = {
            "event_id": str(uuid.uuid4()),
            "type": "pothole",
            "severity": severity,
            "confidence": float(confidence),
            "lat": ev_data["lat"],
            "lng": ev_data["lng"],
            "timestamp": str(int(time.time()) - random.randint(0, 3600)),
            "clip_url": f"/temp/dashcam/clip_{str(uuid.uuid4())[:8]}.mp4",
            "address": ev_data["address"],
            "sub_area": ev_data["sub_area"],
            "portal_name": ev_data["portal_name"],
            "portal_url": ev_data["portal_url"],
            "userId": user_id
        }
        POTHOLE_EVENTS[user_id].append(event)

    total = len(POTHOLE_EVENTS[user_id])
    print(f"[Test Seed] Injected {len(test_events)} mock events for user {user_id}. Total user events: {total}")
    return {
        "message": f"Seeded {len(test_events)} test events for your account",
        "total_events": total,
        "expected_clusters": "3 portals: AHMEDABAD_AMC (3 sub-areas), GUJARAT_SWAGAT (2 sub-areas), NHAI (1 sub-area) = 6 clusters total"
    }


@app.post("/api/test/clear_events")
def clear_test_events(request: Request):
    """Clears pothole events for the logged-in user only."""
    user = request.session.get('user')
    user_id = user.get('sub', 'anonymous') if user else 'anonymous'
    if user_id in POTHOLE_EVENTS:
        POTHOLE_EVENTS[user_id].clear()
    print(f"[Test] Cleared all pothole events for user {user_id}.")
    return {"message": "All your events cleared", "total_events": 0}


class ComplaintRequest(BaseModel):
    cluster_id: str
    latitude: float
    longitude: float
    road_name: str
    event_count: int
    severity: str
    portal_name: str = "Unknown"
    portal_url: str = ""
    sub_area: str = ""

@app.post("/api/reports/generate_complaint")
def generate_pothole_complaint(req: ComplaintRequest):
    """
    Uses Amazon Bedrock to generate a professional cluster complaint.
    """
    print(f"[Bedrock] Generating dynamic AI complaint for cluster {req.cluster_id}")
    
    # Convert request to dict for Bedrock service
    data = req.dict()
    
    # Generate AI draft
    draft_text = generate_cluster_complaint(data)
    
    authority = req.portal_name if req.portal_name != "Unknown" else (
        "Municipal Corporation" if "Road" in req.road_name else "NHAI"
    )
    
    return {
        "complaint_id": str(uuid.uuid4()),
        "generated_draft": draft_text,
        "suggested_authority": authority,
        "portal_url": req.portal_url,
        "status": "ready_for_review"
    }

# Optional: serve public files like images/icons if they exist in dist root
_dist_dir = os.path.join(os.path.dirname(__file__), "..", "dist")

@app.get("/{file_name:path}")
async def serve_static_root(file_name: str):
    if file_name.startswith("api/"):
        return
    
    if not os.path.isdir(_dist_dir):
        return {"detail": "Frontend not built. Use Vite dev server at localhost:5173"}
    
    file_path = os.path.join(_dist_dir, file_name)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    
    index_path = os.path.join(_dist_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    
    return {"detail": "Not found"}

