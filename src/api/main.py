"""
Production FastAPI Application for Manufacturing Quality Intelligence
Exposes RESTful endpoints for Multimodal Defect Inference, SPC Evaluation, and Drift Monitoring.
"""

import os
import sys
import io
import base64
from typing import List, Dict, Optional, Any
from datetime import datetime

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import torch
import numpy as np
import pandas as pd
from PIL import Image
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.data.preprocessor import ManufacturingPreprocessor
from src.spc.control_charts import SPCEngine
from src.models.multimodal_fusion import GatedMultimodalFusionNet, DEFECT_CLASSES
from src.models.dataset_loader import transform_image
from src.drift.drift_engine import ProcessDriftEngine

# Initialize FastAPI App
app = FastAPI(
    title="Manufacturing Quality Intelligence API",
    description="Multimodal Defect Detection, Statistical Process Control (SPC), and Process Drift Analytics Engine.",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Global System State & Singletons -----------------
GLOBAL_STATE = {
    "preprocessor": None,
    "multimodal_model": None,
    "spc_engine": None,
    "drift_engine": None,
    "device": torch.device("cpu"),
    "model_state": "PRODUCTION_GATED_MULTIMODAL"
}

@app.on_event("startup")
def startup_event():
    """Initializes models and engines on server startup."""
    print("Initializing Manufacturing Quality Intelligence System...")
    
    # 1. Load Preprocessor
    prep_path = "data/processed/preprocessor.joblib"
    if os.path.exists(prep_path):
        GLOBAL_STATE["preprocessor"] = ManufacturingPreprocessor.load(prep_path)
    
    # 2. Load Multimodal Model
    model = GatedMultimodalFusionNet(tab_in=12, num_classes=4, emb_dim=32)
    model_path = "data/processed/models/gated_multimodal_fusion.pt"
    if os.path.exists(model_path):
        model.load_state_dict(torch.load(model_path, map_location=GLOBAL_STATE["device"]))
        model.eval()
        GLOBAL_STATE["multimodal_model"] = model
    
    # 3. Calibrate SPC Engine
    train_csv = "data/processed/train.csv"
    if os.path.exists(train_csv):
        train_df = pd.read_csv(train_csv)
        spc = SPCEngine()
        spc.calibrate(train_df)
        GLOBAL_STATE["spc_engine"] = spc
        
        # 4. Initialize Drift Engine
        drift_eng = ProcessDriftEngine(train_df)
        GLOBAL_STATE["drift_engine"] = drift_eng
        
    print("All intelligence services successfully loaded.")

# ----------------- Pydantic Data Contracts -----------------
class SensorTelemetry(BaseModel):
    furnace_temp_c: float = Field(820.0, description="Furnace Chamber Temperature in Celsius")
    injection_pressure_mpa: float = Field(122.0, description="Injection Pressure in MPa")
    spindle_speed_rpm: float = Field(3150.0, description="Spindle Rotation Speed in RPM")
    feed_rate_mm_s: float = Field(44.0, description="Milling Feed Rate in mm/s")
    vibration_amplitude_g: float = Field(1.75, description="Spindle Vibration Amplitude in g")
    tool_wear_min: float = Field(85.0, description="Cumulative Tool Wear in minutes")
    coolant_flow_l_min: float = Field(15.5, description="Coolant Flow Rate in L/min")
    ambient_humidity_pct: float = Field(49.0, description="Factory Ambient Humidity %")

class MultimodalInferenceRequest(BaseModel):
    sample_id: Optional[str] = "TEST-SAMPLE-001"
    sensors: SensorTelemetry
    image_base64: Optional[str] = Field(None, description="Base64 encoded 64x64 optical surface inspection scan")

class MultimodalInferenceResponse(BaseModel):
    sample_id: str
    predicted_label: int
    predicted_name: str
    confidence: float
    entropy: float
    is_uncertain: bool
    probabilities: Dict[str, float]
    modality_weights: Dict[str, float]
    top_sensor_attributions: List[Dict[str, Any]]
    gradcam_base64: Optional[str] = None
    timestamp: str

class SPCEvaluationRequest(BaseModel):
    variable_name: str = "furnace_temp_c"
    series_values: List[float] = Field(..., min_length=3, description="Sequential process observations")

class SPCEvaluationResponse(BaseModel):
    variable: str
    status: str
    latest_value: float
    latest_ewma: float
    ucl: float
    lcl: float
    mean: float
    violations_count: int
    violations: List[Dict[str, Any]]

class BatchDriftRequest(BaseModel):
    batch_id: str = "BATCH-INCOMING-001"
    records: List[SensorTelemetry]

# ----------------- API Endpoints -----------------

@app.get("/")
def root():
    return {
        "service": "Manufacturing Quality Intelligence API",
        "project_code": "BDS-27",
        "institution": "KES' Shroff College - Department of IT & Data Science",
        "docs_url": "/docs",
        "status": "ONLINE"
    }

@app.get("/health")
def health_check():
    return {
        "status": "HEALTHY",
        "model_loaded": GLOBAL_STATE["multimodal_model"] is not None,
        "preprocessor_loaded": GLOBAL_STATE["preprocessor"] is not None,
        "spc_calibrated": GLOBAL_STATE["spc_engine"] is not None and GLOBAL_STATE["spc_engine"].is_calibrated,
        "drift_engine_active": GLOBAL_STATE["drift_engine"] is not None,
        "active_model_state": GLOBAL_STATE["model_state"],
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/predict/multimodal", response_model=MultimodalInferenceResponse)
def predict_multimodal(req: MultimodalInferenceRequest):
    """
    Executes end-to-end multimodal defect classification fusing tabular telemetry and optical scans.
    """
    preprocessor = GLOBAL_STATE["preprocessor"]
    model = GLOBAL_STATE["multimodal_model"]
    
    if preprocessor is None or model is None:
        raise HTTPException(status_code=503, detail="Models not loaded")

    # 1. Process Tabular Input
    sensor_dict = req.sensors.model_dump() if hasattr(req.sensors, "model_dump") else req.sensors.dict()

    x_tab_scaled = preprocessor.transform_single_dict(sensor_dict)
    t_tab = torch.tensor(x_tab_scaled, dtype=torch.float32).unsqueeze(0)

    # 2. Process Optical Image
    if req.image_base64:
        try:
            img_bytes = base64.b64decode(req.image_base64)
            pil_img = Image.open(io.BytesIO(img_bytes)).convert('L').resize((64, 64))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 image: {str(e)}")
    else:
        # Default metallic texture
        arr = np.random.normal(175, 12, (64, 64)).clip(100, 240).astype(np.uint8)
        pil_img = Image.fromarray(arr, mode='L')

    t_img = transform_image(pil_img, is_train=False).unsqueeze(0)

    # 3. Model Prediction
    pred_res = model.predict_with_confidence(t_tab, t_img)

    # 4. Grad-CAM Heatmap
    gradcam_map = model.generate_gradcam(t_tab, t_img, target_class=pred_res["predicted_label"])
    
    # Encode Grad-CAM to Base64 PNG
    cam_uint8 = (gradcam_map * 255.0).astype(np.uint8)
    cam_img = Image.fromarray(cam_uint8, mode='L')
    buf = io.BytesIO()
    cam_img.save(buf, format="PNG")
    cam_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    # 5. Tabular Sensor Attribution
    attributions = model.explain_tabular_sensors(t_tab, t_img, preprocessor.feature_names)

    return MultimodalInferenceResponse(
        sample_id=req.sample_id,
        predicted_label=pred_res["predicted_label"],
        predicted_name=pred_res["predicted_name"],
        confidence=pred_res["confidence"],
        entropy=pred_res["entropy"],
        is_uncertain=pred_res["is_uncertain"],
        probabilities=pred_res["probabilities"],
        modality_weights={
            "tabular": pred_res["modality_gate_weight_tabular"],
            "vision": pred_res["modality_gate_weight_vision"]
        },
        top_sensor_attributions=attributions[:5],
        gradcam_base64=cam_b64,
        timestamp=datetime.now().isoformat()
    )

@app.post("/api/v1/spc/evaluate", response_model=SPCEvaluationResponse)
def evaluate_spc(req: SPCEvaluationRequest):
    """
    Evaluates sequential process sensor observations against Shewhart & Western Electric SPC rules.
    """
    spc = GLOBAL_STATE["spc_engine"]
    if spc is None:
        raise HTTPException(status_code=503, detail="SPC engine not calibrated")

    try:
        s = pd.Series(req.series_values)
        res = spc.evaluate_series(s, req.variable_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SPCEvaluationResponse(
        variable=res["variable"],
        status=res["status"],
        latest_value=res["latest_value"],
        latest_ewma=res["latest_ewma"],
        ucl=res["limits"]["ucl"],
        lcl=res["limits"]["lcl"],
        mean=res["limits"]["mean"],
        violations_count=len(res["rule_violations"]),
        violations=res["rule_violations"]
    )

@app.post("/api/v1/drift/analyze")
def analyze_drift(req: BatchDriftRequest):
    """
    Evaluates incoming batch telemetry for distribution drift and triggers automated rollback if critical.
    """
    drift_eng = GLOBAL_STATE["drift_engine"]
    if drift_eng is None:
        raise HTTPException(status_code=503, detail="Drift engine not initialized")

    records_dict = [r.dict() for r in req.records]
    df_batch = pd.DataFrame(records_dict)
    
    drift_res = drift_eng.analyze_batch_drift(df_batch, batch_id=req.batch_id)
    GLOBAL_STATE["model_state"] = drift_eng.active_model_state
    return drift_res

@app.get("/api/v1/models/ablation-benchmark")
def get_ablation_benchmark():
    """
    Returns the ablation benchmark results comparing Tabular, Vision, and Fusion architectures.
    """
    path = "reports/ablation_benchmark.json"
    if os.path.exists(path):
        import json
        with open(path, "r") as f:
            return json.load(f)
    return {"message": "Benchmark not found, run src/models/ablation_study.py"}
