import boto3
import cv2
import numpy as np
import os
import io
from PIL import Image, ImageDraw, ImageFilter

class RekognitionService:
    def __init__(self, region_name=None):
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-south-1")
        self.client = boto3.client(
            'rekognition',
            region_name=self.region_name,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )

    def redact_pii(self, image_bytes):
        """
        Detects faces and text in an image and redacts them.
        Returns redacted image bytes.
        """
        try:
            # 1. Detect Faces
            face_response = self.client.detect_faces(Image={'Bytes': image_bytes})
            faces = face_response.get('FaceDetails', [])
            
            # 2. Detect Text (for license plates, etc.)
            text_response = self.client.detect_text(Image={'Bytes': image_bytes})
            texts = text_response.get('TextDetections', [])
            
            # Filter for lines/words that we might want to redact
            # In a real scenario, we might use heuristics for license plates
            text_to_redact = [t for t in texts if t['Type'] == 'LINE']
            
            # 3. Apply Redaction using Pillow (easier for drawing boxes on bytes)
            image = Image.open(io.BytesIO(image_bytes))
            draw = ImageDraw.Draw(image)
            width, height = image.size
            
            # Redact Faces
            for face in faces:
                box = face['BoundingBox']
                left = width * box['Left']
                top = height * box['Top']
                right = left + (width * box['Width'])
                bottom = top + (height * box['Height'])
                
                # Apply Blur
                face_region = image.crop((left, top, right, bottom))
                blurred_face = face_region.filter(ImageFilter.GaussianBlur(radius=20))
                image.paste(blurred_face, (int(left), int(top)))
                
            # Redact Text
            for text in text_to_redact:
                box = text['Geometry']['BoundingBox']
                left = width * box['Left']
                top = height * box['Top']
                right = left + (width * box['Width'])
                bottom = top + (height * box['Height'])
                
                # Apply Blur
                text_region = image.crop((left, top, right, bottom))
                blurred_text = text_region.filter(ImageFilter.GaussianBlur(radius=15))
                image.paste(blurred_text, (int(left), int(top)))
            
            # Save to buffer
            output_buffer = io.BytesIO()
            img_format = image.format if image.format else "JPEG"
            image.save(output_buffer, format=img_format)
            return output_buffer.getvalue(), len(faces), len(text_to_redact)
            
        except Exception as e:
            print(f"Error in Rekognition PII redaction: {e}")
            return image_bytes, 0, 0

    def get_pii_boxes(self, image_bytes):
        """
        Returns the bounding boxes of faces and text for live UI masking.
        """
        try:
            face_response = self.client.detect_faces(Image={'Bytes': image_bytes})
            text_response = self.client.detect_text(Image={'Bytes': image_bytes})
            
            return {
                "faces": [f['BoundingBox'] for f in face_response.get('FaceDetails', [])],
                "text": [t['Geometry']['BoundingBox'] for t in text_response.get('TextDetections', []) if t['Type'] == 'LINE']
            }
        except Exception:
            return {"faces": [], "text": []}

    def redact_video(self, input_path, output_path):
        """
        Redacts PII from an entire video file. 
        Note: This is computationally intensive as it processes frame by frame.
        """
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            return False

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # We use mp4v or h264 for the output
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Performance optimization: Realistically, Rekognition takes ~1s per frame.
            # In a real app, we might use Rekognition Video (Async) and then apply masks.
            # For this implementation, we'll redact every 5th frame and interpolate, 
            # or just do every frame if the clip is short.
            
            redacted_frame = self.redact_image_ndarray(frame)
            out.write(redacted_frame)
            frame_count += 1
            
        cap.release()
        out.release()
        return True

    def redact_image_ndarray(self, frame):
        """
        Same as redact_pii but takes and returns a numpy ndarray (OpenCV format).
        """
        success, encoded = cv2.imencode('.jpg', frame)
        if not success:
            return frame
            
        redacted_bytes, faces_count, text_count = self.redact_pii(encoded.tobytes())
        
        nparr = np.frombuffer(redacted_bytes, np.uint8)
        redacted_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return redacted_frame
