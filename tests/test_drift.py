import sys
import os
import pytest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.drift.drift_engine import ProcessDriftEngine

@pytest.fixture
def drift_engine():
    train_df = pd.read_csv("data/processed/train.csv")
    return ProcessDriftEngine(train_df)

def test_psi_identical_distributions(drift_engine):
    base = np.random.normal(100, 10, 1000)
    psi = drift_engine.calculate_psi(base, base)
    assert psi < 0.05

def test_psi_shifted_distributions(drift_engine):
    base = np.random.normal(100, 10, 1000)
    shifted = np.random.normal(130, 10, 100)
    psi = drift_engine.calculate_psi(base, shifted)
    assert psi > 0.25

def test_analyze_batch_in_control(drift_engine):
    stream_df = pd.read_csv("data/raw/drift_telemetry_stream.csv")
    b5 = stream_df[stream_df["batch_num"] == 5]
    res = drift_engine.analyze_batch_drift(b5, batch_id="BATCH-005")
    assert res["overall_status"] in ["IN_CONTROL", "INCIPIENT_DRIFT_WARNING"]

def test_automated_rollback_on_critical_drift(drift_engine):
    stream_df = pd.read_csv("data/raw/drift_telemetry_stream.csv")
    b28 = stream_df[stream_df["batch_num"] == 28]
    res = drift_engine.analyze_batch_drift(b28, batch_id="BATCH-028")
    assert res["overall_status"] == "CRITICAL_DRIFT_ROLLBACK"
    assert drift_engine.active_model_state == "CONSERVATIVE_SAFETY_BASELINE"
