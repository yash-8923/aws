import argparse
import json
import os
import time

import boto3
import cv2
from botocore.config import Config
from dotenv import load_dotenv


def get_boto_client():
    """
    Creates a Boto3 SageMaker Runtime client with a high timeout
    to accommodate Serverless cold starts.
    """
    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

    my_config = Config(
        read_timeout=int(os.getenv("SAGEMAKER_READ_TIMEOUT_SECONDS", "120")),
        connect_timeout=int(os.getenv("SAGEMAKER_CONNECT_TIMEOUT_SECONDS", "10")),
        retries={"max_attempts": int(os.getenv("SAGEMAKER_MAX_ATTEMPTS", "1"))},
    )

    return boto3.client(
        "sagemaker-runtime",
        config=my_config,
        region_name=os.environ.get("AWS_REGION", os.environ.get("SAGEMAKER_REGION", "ap-south-1")),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )


def draw_boxes(frame, predictions):
    """Draw yellow bounding boxes and labels on the image frame."""
    for box_data in predictions:
        label = f"{box_data.get('class', 'damage')} ({box_data.get('confidence', 0.0):.2f})"
        try:
            x1, y1, x2, y2 = box_data.get("box", [0, 0, 0, 0])
        except Exception:
            continue

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1 - 20), (x1 + w, y1), (0, 255, 255), -1)
        cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    return frame


def stream_video_to_sagemaker(video_path: str, endpoint_name: str):
    """Stream frames from webcam/video to a SageMaker endpoint."""
    cap = cv2.VideoCapture(0 if video_path == "webcam" else video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video source {video_path}")
        return

    sagemaker_client = get_boto_client()

    print(f"Endpoint: {endpoint_name}")
    print("Starting video stream. Press 'q' to quit.")

    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            print("End of video stream.")
            break

        resized_frame = cv2.resize(frame, (640, 480))
        success, encoded_image = cv2.imencode(".jpg", resized_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not success:
            continue

        image_bytes = encoded_image.tobytes()
        start_time = time.time()
        try:
            if frame_count == 0:
                print("Sending first frame... (serverless cold start can take ~1 min)")

            response = sagemaker_client.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType="image/jpeg",
                Accept="application/json",
                Body=image_bytes,
            )
            response_body = response["Body"].read().decode("utf-8")
            result_json = json.loads(response_body)
            predictions = result_json.get("predictions", [])

            latency = time.time() - start_time
            print(f"Received {len(predictions)} detections in {latency:.2f}s")

            display_frame = draw_boxes(resized_frame, predictions)
            cv2.imshow("Road Damage Detection (Live)", display_frame)
            frame_count += 1
        except Exception as e:
            print(f"SageMaker invocation error: {e}")
            cv2.imshow("Road Damage Detection (Live)", resized_frame)
            time.sleep(1)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stream video frames to a SageMaker Endpoint")
    parser.add_argument("--video", type=str, default="webcam", help='Path to video file or "webcam"')
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.getenv("SAGEMAKER_ENDPOINT_NAME", "road-damage-yolov8-endpoint-serverless"),
        help="SageMaker endpoint name",
    )
    args = parser.parse_args()
    stream_video_to_sagemaker(args.video, args.endpoint)

