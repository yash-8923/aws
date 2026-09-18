import sys
import os
import json

# Ensure the backend directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Create mock dist directory to avoid RuntimeError on startup
os.makedirs(os.path.abspath(os.path.join(os.path.dirname(__file__), "../dist/assets")), exist_ok=True)

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_route_with_real_gps():
    payload = {
        "lat": 23.020547,
        "lng": 72.612954
    }

    response = client.post("/api/route", json=payload)

    assert response.status_code == 200

    body = response.json()
    print(json.dumps(body, indent=2))

    assert body["routing"] is not None


def test_route_with_real_manual_address():
    payload = {
        "state": "Maharashtra",
        "city": "Mumbai",
        "address": "Andheri West"
    }

    response = client.post("/api/route", json=payload)

    assert response.status_code == 200

    body = response.json()
    print(json.dumps(body, indent=2))

    assert body["routing"] is not None


def test_route_with_fallback():
    payload = {}

    response = client.post("/api/route", json=payload)

    assert response.status_code == 200

    body = response.json()
    print(json.dumps(body, indent=2))

    assert body["routing"]["portal_name"] == "CPGRAMS"