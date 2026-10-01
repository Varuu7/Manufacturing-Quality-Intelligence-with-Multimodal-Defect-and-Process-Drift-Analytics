import sys
import os
import pytest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.spc.control_charts import SPCEngine

@pytest.fixture
def calibrated_spc():
    df_train = pd.read_csv("data/processed/train.csv")
    engine = SPCEngine()
    engine.calibrate(df_train)
    return engine

def test_spc_calibration(calibrated_spc):
    assert calibrated_spc.is_calibrated is True
    assert "furnace_temp_c" in calibrated_spc.baseline_stats
    stats = calibrated_spc.baseline_stats["furnace_temp_c"]
    assert stats["ucl"] > stats["mean"]
    assert stats["lcl"] < stats["mean"]
    assert np.isclose(stats["ucl"] - stats["mean"], 3.0 * stats["std"])

def test_spc_in_control_series(calibrated_spc):
    # Series centered at mean with small noise
    mean = calibrated_spc.baseline_stats["furnace_temp_c"]["mean"]
    std = calibrated_spc.baseline_stats["furnace_temp_c"]["std"]
    normal_series = pd.Series(np.random.normal(mean, std * 0.5, size=20))
    res = calibrated_spc.evaluate_series(normal_series, "furnace_temp_c")
    assert res["status"] in ["In-Control", "Warning"]

def test_spc_out_of_control_rule1(calibrated_spc):
    # Point injected beyond UCL
    stats = calibrated_spc.baseline_stats["furnace_temp_c"]
    extreme_series = pd.Series([stats["mean"], stats["mean"], stats["ucl"] + 50.0])
    res = calibrated_spc.evaluate_series(extreme_series, "furnace_temp_c")
    assert len(res["rule_violations"]) >= 1
    assert res["rule_violations"][0]["rule"] == "Rule 1 (Beyond 3-Sigma)"
