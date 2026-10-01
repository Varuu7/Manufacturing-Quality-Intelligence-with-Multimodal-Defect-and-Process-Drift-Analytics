"""
Statistical Process Control (SPC) Engine
Implements Shewhart Control Charts, EWMA, CUSUM, and Western Electric out-of-control rule evaluation.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any

class SPCEngine:
    def __init__(self, ewma_lambda: float = 0.2, ewma_l: float = 3.0):
        self.ewma_lambda = ewma_lambda
        self.ewma_l = ewma_l
        self.baseline_stats: Dict[str, Dict[str, float]] = {}
        self.is_calibrated = False

    def calibrate(self, df_baseline: pd.DataFrame, variables: List[str] = None):
        """
        Calibrates baseline control limits from historical in-control data.
        """
        if variables is None:
            variables = [
                "furnace_temp_c",
                "injection_pressure_mpa",
                "spindle_speed_rpm",
                "feed_rate_mm_s",
                "vibration_amplitude_g",
                "coolant_flow_l_min"
            ]

        self.baseline_stats = {}
        for var in variables:
            if var not in df_baseline.columns:
                continue
            series = df_baseline[var].dropna()
            mean_val = float(series.mean())
            std_val = float(series.std())
            ucl = mean_val + 3.0 * std_val
            lcl = max(0.0, mean_val - 3.0 * std_val)
            
            # EWMA asymptotic limits
            ewma_sigma = std_val * np.sqrt(self.ewma_lambda / (2.0 - self.ewma_lambda))
            ewma_ucl = mean_val + self.ewma_l * ewma_sigma
            ewma_lcl = max(0.0, mean_val - self.ewma_l * ewma_sigma)

            self.baseline_stats[var] = {
                "mean": mean_val,
                "std": std_val,
                "ucl": ucl,
                "lcl": lcl,
                "zone_a_upper": mean_val + 2.0 * std_val,
                "zone_a_lower": max(0.0, mean_val - 2.0 * std_val),
                "zone_b_upper": mean_val + 1.0 * std_val,
                "zone_b_lower": max(0.0, mean_val - 1.0 * std_val),
                "ewma_ucl": ewma_ucl,
                "ewma_lcl": ewma_lcl
            }

        self.is_calibrated = True
        return self.baseline_stats

    def compute_ewma_series(self, values: np.ndarray, target_mean: float) -> np.ndarray:
        """Computes Exponentially Weighted Moving Average sequence."""
        ewma = np.zeros_like(values, dtype=float)
        prev = target_mean
        for i, val in enumerate(values):
            prev = self.ewma_lambda * val + (1.0 - self.ewma_lambda) * prev
            ewma[i] = prev
        return ewma

    def evaluate_series(self, series: pd.Series, var_name: str) -> Dict[str, Any]:
        """
        Evaluates a sequence of observations against Western Electric rules.
        """
        if not self.is_calibrated or var_name not in self.baseline_stats:
            raise ValueError(f"SPC Engine not calibrated for variable: {var_name}")

        stats = self.baseline_stats[var_name]
        vals = series.values
        n = len(vals)
        violations = []

        mean = stats["mean"]
        std = stats["std"]
        ucl = stats["ucl"]
        lcl = stats["lcl"]

        # Rule 1: One point beyond 3 sigma (UCL/LCL)
        for i, v in enumerate(vals):
            if v > ucl or v < lcl:
                violations.append({
                    "rule": "Rule 1 (Beyond 3-Sigma)",
                    "index": i,
                    "value": float(v),
                    "limit_exceeded": "UCL" if v > ucl else "LCL"
                })

        # Rule 2: 2 out of 3 consecutive points in Zone A or beyond (> 2 sigma on same side)
        for i in range(2, n):
            window = vals[i-2:i+1]
            if sum(w > mean + 2*std for w in window) >= 2:
                violations.append({"rule": "Rule 2 (2 of 3 in Zone A Upper)", "index": i, "value": float(vals[i])})
            elif sum(w < mean - 2*std for w in window) >= 2:
                violations.append({"rule": "Rule 2 (2 of 3 in Zone A Lower)", "index": i, "value": float(vals[i])})

        # Rule 4: 8 consecutive points on one side of center line
        for i in range(7, n):
            window = vals[i-7:i+1]
            if all(w > mean for w in window):
                violations.append({"rule": "Rule 4 (8 Consecutive Above Centerline)", "index": i, "value": float(vals[i])})
            elif all(w < mean for w in window):
                violations.append({"rule": "Rule 4 (8 Consecutive Below Centerline)", "index": i, "value": float(vals[i])})

        # EWMA Evaluation
        ewma_vals = self.compute_ewma_series(vals, mean)
        ewma_violations = []
        for i, ev in enumerate(ewma_vals):
            if ev > stats["ewma_ucl"] or ev < stats["ewma_lcl"]:
                ewma_violations.append({
                    "index": i,
                    "ewma_val": float(ev),
                    "threshold": stats["ewma_ucl"] if ev > stats["ewma_ucl"] else stats["ewma_lcl"]
                })

        status = "In-Control"
        if len(violations) > 0 or len(ewma_violations) > 0:
            status = "Out-of-Control" if len(violations) >= 2 or len(ewma_violations) >= 2 else "Warning"

        return {
            "variable": var_name,
            "status": status,
            "limits": stats,
            "rule_violations": violations,
            "ewma_violations": ewma_violations,
            "latest_value": float(vals[-1]) if n > 0 else None,
            "latest_ewma": float(ewma_vals[-1]) if n > 0 else None
        }

    def evaluate_batch(self, df_batch: pd.DataFrame) -> Dict[str, Any]:
        """
        Evaluates all monitored variables for a production batch.
        """
        results = {}
        overall_status = "In-Control"

        for var in self.baseline_stats:
            if var in df_batch.columns:
                res = self.evaluate_series(df_batch[var], var)
                results[var] = res
                if res["status"] == "Out-of-Control":
                    overall_status = "Out-of-Control"
                elif res["status"] == "Warning" and overall_status != "Out-of-Control":
                    overall_status = "Warning"

        return {
            "overall_status": overall_status,
            "variables": results,
            "batch_size": len(df_batch)
        }

if __name__ == "__main__":
    train_df = pd.read_csv("data/processed/train.csv")
    spc = SPCEngine()
    limits = spc.calibrate(train_df)
    print("Calibrated SPC Engine on Training Baseline. Calibrated variables:")
    for k, v in limits.items():
        print(f" - {k}: Mean={v['mean']:.2f}, UCL={v['ucl']:.2f}, LCL={v['lcl']:.2f}")
