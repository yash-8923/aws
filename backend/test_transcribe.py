import requests
import os
import urllib.request

# Ensure the backend server is running when you execute this script
BACKEND_URL = "http://localhost:8000"

def test_transcribe_endpoint():
    print("Testing /api/transcribe endpoint...")
    
    # Use the test_audio.mp3 provided by the user
    dummy_audio_path = "test_audio.mp3"
    
    if not os.path.exists(dummy_audio_path):
        print(f"Please place a valid audio file at '{dummy_audio_path}' so AWS Transcribe does not fail.")
        return
            
    try:
        with open(dummy_audio_path, 'rb') as audio_file:
            files = {'audio': (dummy_audio_path, audio_file, 'audio/mpeg')}
            print(f"Sending POST request to {BACKEND_URL}/api/transcribe ...")
            
            response = requests.post(f"{BACKEND_URL}/api/transcribe", files=files)
            
            print(f"Status Code: {response.status_code}")
            try:
                print("Response Body:")
                print(response.json())
            except Exception as e:
                print("Could not parse JSON response:", response.text)
                
    except Exception as e:
        print(f"Error making request: {e}")

if __name__ == "__main__":
    test_transcribe_endpoint()
