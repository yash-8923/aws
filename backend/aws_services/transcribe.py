import os
import time
import json
import boto3
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

def get_aws_session():
    return boto3.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "ap-south-1")
    )

def get_s3_client():
    session = get_aws_session()
    return session.client("s3")

def get_transcribe_client():
    session = get_aws_session()
    return session.client("transcribe")

def upload_audio_to_s3(file_path: str, bucket_name: str, object_name: str) -> str:
    """Uploads an audio file to S3 and returns the S3 URI."""
    s3_client = get_s3_client()
    try:
        s3_client.upload_file(file_path, bucket_name, object_name)
        return f"s3://{bucket_name}/{object_name}"
    except Exception as e:
        print(f"Error uploading to S3: Type: {type(e).__name__} Message: {str(e)}")
        return ""

def start_transcription_job(job_name: str, media_uri: str, format: str = "webm") -> Optional[str]:
    """Starts a transcription job with language identification."""
    transcribe_client = get_transcribe_client()
    try:
        response = transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': media_uri},
            MediaFormat=format,
            IdentifyLanguage=True, # Auto-detect Indic language
        )
        return response['TranscriptionJob']['TranscriptionJobName']
    except Exception as e:
        print(f"Error starting transcription job: {e}")
        return None

def poll_transcription_job(job_name: str, max_retries: int = 60, wait_seconds: int = 2) -> Dict[str, Any]:
    """Polls the transcription job until it completes or fails."""
    transcribe_client = get_transcribe_client()
    
    for _ in range(max_retries):
        response = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        status = response['TranscriptionJob']['TranscriptionJobStatus']
        
        if status in ['COMPLETED', 'FAILED']:
            return response['TranscriptionJob']
            
        time.sleep(wait_seconds)
        
    return {"TranscriptionJobStatus": "TIMEOUT"}

def extract_transcript(transcript_result: Dict[str, Any]) -> str:
    """Extracts the transcript text from the completed job result."""
    import urllib.request
    
    if transcript_result.get("TranscriptionJobStatus") != "COMPLETED":
        return ""
        
    transcript_uri = transcript_result.get("Transcript", {}).get("TranscriptFileUri")
    if not transcript_uri:
        return ""
        
    try:
        with urllib.request.urlopen(transcript_uri) as response:
            data = json.loads(response.read().decode())
            return data["results"]["transcripts"][0]["transcript"]
    except Exception as e:
        print(f"Error fetching transcript from URI: {e}")
        return ""
