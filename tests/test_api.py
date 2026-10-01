import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.api.main import app, startup_event

@pytest.fixture(scope="module")
def client():
    startup_event()
    with TestClient(app) as c:
        yield c

def test_root_endpoint(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["project_code"] == "BDS-27"

def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert data["model_loaded"] is True

def test_spc_evaluate_endpoint(client):
    payload = {
        "variable_name": "furnace_temp_c",
        "series_values": [819.0, 821.0, 820.5, 818.2, 822.0]
    }
    res = client.post("/api/v1/spc/evaluate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "ucl" in data

def test_multimodal_predict_endpoint(client):
    payload = {
        "sample_id": "TEST-PROD-01",
        "sensors": {
            "furnace_temp_c": 820.0,
            "injection_pressure_mpa": 122.0,
            "spindle_speed_rpm": 3150.0,
            "feed_rate_mm_s": 44.0,
            "vibration_amplitude_g": 1.75,
            "tool_wear_min": 50.0,
            "coolant_flow_l_min": 15.5,
            "ambient_humidity_pct": 49.0
        }
    }
    res = client.post("/api/v1/predict/multimodal", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "predicted_label" in data
    assert "confidence" in data
    assert "gradcam_base64" in data
    assert len(data["top_sensor_attributions"]) > 0

def test_ablation_benchmark_endpoint(client):
    res = client.get("/api/v1/models/ablation-benchmark")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 3
