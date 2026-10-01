"""
Process and Data Drift Analytics Engine with Automated Rollback and Retraining Policies
Implements:
- Two-Sample Kolmogorov-Smirnov (KS) tests per sensor variable
- Population Stability Index (PSI) calculation
- Wasserstein Distance multivariate drift scoring
- Automated Policy Controller: Warning, Alert, and Rollback to Conservative Baseline
"""

import os
import json
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, wasserstein_distance
from datetime import datetime

class ProcessDriftEngine:
    def __init__(self, baseline_df: pd.DataFrame, variables: list[str] = None):
        self.variables = variables or [
            "furnace_temp_c",
            "injection_pressure_mpa",
            "spindle_speed_rpm",
            "feed_rate_mm_s",
            "vibration_amplitude_g",
            "coolant_flow_l_min"
        ]
        self.baseline_data = {var: baseline_df[var].dropna().values for var in self.variables}
        self.active_model_state = "PRODUCTION_GATED_MULTIMODAL"
        self.rollback_history = []
        
    def calculate_psi(self, baseline: np.ndarray, current: np.ndarray, num_bins: int = 4) -> float:
        """
        Calculates Population Stability Index (PSI) using quartile bins for small batch reliability.
        """
        quantiles = np.linspace(0, 100, num_bins + 1)
        bin_edges = np.percentile(baseline, quantiles)
        bin_edges[0] -= 1e-4
        bin_edges[-1] += 1e-4
        bin_edges = np.unique(bin_edges)
        if len(bin_edges) < 3:
            return 0.0

        b_counts, _ = np.histogram(baseline, bins=bin_edges)
        c_counts, _ = np.histogram(current, bins=bin_edges)

        # Proportional Laplace smoothing
        b_pct = (b_counts + 1.0) / (np.sum(b_counts) + len(b_counts))
        c_pct = (c_counts + 1.0) / (np.sum(c_counts) + len(c_counts))

        psi_val = np.sum((c_pct - b_pct) * np.log(c_pct / b_pct))
        return float(psi_val)

    def analyze_batch_drift(self, df_batch: pd.DataFrame, batch_id: str = "BATCH_UNKNOWN") -> dict:
        """
        Runs comprehensive statistical tests across all variables for an incoming batch.
        """
        results = {}
        drifted_vars = []
        max_psi = 0.0
        total_w_dist = 0.0

        for var in self.variables:
            if var not in df_batch.columns:
                continue
            curr_vals = df_batch[var].dropna().values
            if len(curr_vals) < 5:
                continue
                
            base_vals = self.baseline_data[var]
            
            # 1. Kolmogorov-Smirnov Test
            ks_stat, p_val = ks_2samp(base_vals, curr_vals)
            
            # 2. Population Stability Index
            psi = self.calculate_psi(base_vals, curr_vals)
            max_psi = max(max_psi, psi)
            
            # 3. Normalized Wasserstein distance
            std_norm = np.std(base_vals) + 1e-5
            w_dist = float(wasserstein_distance(base_vals, curr_vals) / std_norm)
            total_w_dist += w_dist

            is_drifted = bool(p_val < 0.005 and (psi > 0.15 or w_dist > 0.55))
            if is_drifted:
                drifted_vars.append(var)

            results[var] = {
                "ks_statistic": round(float(ks_stat), 4),
                "p_value": round(float(p_val), 6),
                "psi": round(float(psi), 4),
                "norm_wasserstein": round(float(w_dist), 4),
                "drift_detected": is_drifted,
                "current_mean": round(float(np.mean(curr_vals)), 2),
                "baseline_mean": round(float(np.mean(base_vals)), 2)
            }

        multivariate_drift_score = round(total_w_dist / len(self.variables), 4)

        # Decide Policy State with consensus
        if len(drifted_vars) >= 2 or (len(drifted_vars) >= 1 and multivariate_drift_score > 0.75) or multivariate_drift_score > 1.0:
            status = "CRITICAL_DRIFT_ROLLBACK"
            recommended_action = "TRIGGER_AUTOMATIC_ROLLBACK_AND_RETRAIN"
        elif len(drifted_vars) == 1 or multivariate_drift_score > 0.45:
            status = "INCIPIENT_DRIFT_WARNING"
            recommended_action = "FLAG_PROCESS_MAINTENANCE"
        else:
            status = "IN_CONTROL"
            recommended_action = "MAINTAIN_CURRENT_PRODUCTION_MODEL"



        # Execute Automated Policy Action if Critical
        rollback_event = None
        if status == "CRITICAL_DRIFT_ROLLBACK" and self.active_model_state != "CONSERVATIVE_SAFETY_BASELINE":
            rollback_event = {
                "timestamp": datetime.now().isoformat(),
                "batch_id": batch_id,
                "previous_state": self.active_model_state,
                "new_state": "CONSERVATIVE_SAFETY_BASELINE",
                "reason": f"Critical drift detected in variables: {', '.join(drifted_vars)} (Max PSI: {max_psi:.3f})",
                "action_executed": "Model rolled back to high-recall safety baseline; quarantine batch for engineer audit."
            }
            self.active_model_state = "CONSERVATIVE_SAFETY_BASELINE"
            self.rollback_history.append(rollback_event)

        return {
            "batch_id": batch_id,
            "overall_status": status,
            "recommended_action": recommended_action,
            "active_model_state": self.active_model_state,
            "multivariate_drift_score": multivariate_drift_score,
            "max_psi": round(max_psi, 4),
            "drifted_variables_count": len(drifted_vars),
            "drifted_variables": drifted_vars,
            "variable_metrics": results,
            "rollback_event": rollback_event
        }

if __name__ == "__main__":
    train_df = pd.read_csv("data/processed/train.csv")
    stream_df = pd.read_csv("data/raw/drift_telemetry_stream.csv")
    
    engine = ProcessDriftEngine(train_df)
    
    # Test batch 5 (In-control)
    b5 = stream_df[stream_df["batch_num"] == 5]
    res_b5 = engine.analyze_batch_drift(b5, batch_id="STREAM-BATCH-005")
    print(f"\n--- Batch 5 Analysis (Expected In-Control) ---")
    print(f"Status: {res_b5['overall_status']}, Drift Score: {res_b5['multivariate_drift_score']}, Action: {res_b5['recommended_action']}")

    # Test batch 16 (Incipient drift)
    b16 = stream_df[stream_df["batch_num"] == 16]
    res_b16 = engine.analyze_batch_drift(b16, batch_id="STREAM-BATCH-016")
    print(f"\n--- Batch 16 Analysis (Expected Incipient Drift) ---")
    print(f"Status: {res_b16['overall_status']}, Drifted Vars: {res_b16['drifted_variables']}, Action: {res_b16['recommended_action']}")

    # Test batch 28 (Severe drift -> Rollback)
    b28 = stream_df[stream_df["batch_num"] == 28]
    res_b28 = engine.analyze_batch_drift(b28, batch_id="STREAM-BATCH-028")
    print(f"\n--- Batch 28 Analysis (Expected Critical Rollback) ---")
    print(f"Status: {res_b28['overall_status']}, Active Model: {res_b28['active_model_state']}")
    if res_b28['rollback_event']:
        print(f"Rollback Triggered: {res_b28['rollback_event']['reason']}")
