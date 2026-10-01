"""
Feature Engineering and Preprocessing Pipeline
Handles data cleaning, physics-based feature interactions, scaling, and leakage-safe splits.
"""

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = [
    "furnace_temp_c",
    "injection_pressure_mpa",
    "spindle_speed_rpm",
    "feed_rate_mm_s",
    "vibration_amplitude_g",
    "tool_wear_min",
    "coolant_flow_l_min",
    "ambient_humidity_pct"
]

DERIVED_COLUMNS = [
    "temp_pressure_interaction",
    "vibration_feed_ratio",
    "tool_vibration_index",
    "cooling_efficiency"
]

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes nonlinear domain interaction terms.
    """
    df_out = df.copy()
    
    # Physics interactions
    df_out["temp_pressure_interaction"] = (df_out["furnace_temp_c"] * df_out["injection_pressure_mpa"]) / 1000.0
    df_out["vibration_feed_ratio"] = df_out["vibration_amplitude_g"] / (df_out["feed_rate_mm_s"] + 1e-5)
    df_out["tool_vibration_index"] = (df_out["tool_wear_min"] / 100.0) * df_out["vibration_amplitude_g"]
    df_out["cooling_efficiency"] = df_out["coolant_flow_l_min"] / ((df_out["furnace_temp_c"] / 100.0) + 1e-5)
    
    return df_out

class ManufacturingPreprocessor:
    def __init__(self):
        self.scaler = StandardScaler()
        self.feature_names = FEATURE_COLUMNS + DERIVED_COLUMNS
        self.is_fitted = False
        
    def fit_transform(self, df: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
        df_eng = engineer_features(df)
        X_raw = df_eng[self.feature_names].values
        X_scaled = self.scaler.fit_transform(X_raw)
        self.is_fitted = True
        return X_scaled, df_eng
        
    def transform(self, df: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
        if not self.is_fitted:
            raise ValueError("Preprocessor has not been fitted yet.")
        df_eng = engineer_features(df)
        X_raw = df_eng[self.feature_names].values
        X_scaled = self.scaler.transform(X_raw)
        return X_scaled, df_eng
        
    def transform_single_dict(self, record: dict) -> np.ndarray:
        df_single = pd.DataFrame([record])
        X_scaled, _ = self.transform(df_single)
        return X_scaled[0]
        
    def save(self, filepath: str = "data/processed/preprocessor.joblib"):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump({
            "scaler": self.scaler,
            "feature_names": self.feature_names,
            "is_fitted": self.is_fitted
        }, filepath)
        
    @classmethod
    def load(cls, filepath: str = "data/processed/preprocessor.joblib") -> "ManufacturingPreprocessor":
        data = joblib.load(filepath)
        instance = cls()
        instance.scaler = data["scaler"]
        instance.feature_names = data["feature_names"]
        instance.is_fitted = data["is_fitted"]
        return instance


def process_and_split_data(
    input_csv: str = "data/raw/manufacturing_process_data.csv",
    output_dir: str = "data/processed"
):
    os.makedirs(output_dir, exist_ok=True)
    df = pd.read_csv(input_csv)
    
    # Train / Val / Test split (70% / 15% / 15%) stratified by defect_label
    train_df, temp_df = train_test_split(
        df, test_size=0.30, random_state=42, stratify=df["defect_label"]
    )
    val_df, test_df = train_test_split(
        temp_df, test_size=0.50, random_state=42, stratify=temp_df["defect_label"]
    )
    
    preprocessor = ManufacturingPreprocessor()
    preprocessor.fit_transform(train_df)
    preprocessor.save(os.path.join(output_dir, "preprocessor.joblib"))
    
    train_df.to_csv(os.path.join(output_dir, "train.csv"), index=False)
    val_df.to_csv(os.path.join(output_dir, "val.csv"), index=False)
    test_df.to_csv(os.path.join(output_dir, "test.csv"), index=False)
    
    print(f"Data split & preprocessor saved: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")

if __name__ == "__main__":
    process_and_split_data()
