"""
Modality Ablation Study and Baseline Comparison Runner
Trains and evaluates:
1. Tabular Baseline (LightGBM)
2. Vision Baseline (CNN)
3. Multimodal Concatenation Fusion
4. Multimodal Gated Cross-Attention Fusion (Our Innovation)
"""

import os
import sys
import json
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, average_precision_score
from sklearn.preprocessing import label_binarize

from src.models.dataset_loader import get_dataloaders
from src.models.multimodal_fusion import GatedMultimodalFusionNet, TabularEncoder, VisionEncoder


# Set seeds
torch.manual_seed(42)
np.random.seed(42)

# Models directory
MODEL_DIR = "data/processed/models"
os.makedirs(MODEL_DIR, exist_ok=True)
REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

class VisionOnlyClassifier(nn.Module):
    def __init__(self, num_classes=4):
        super().__init__()
        self.encoder = VisionEncoder(out_features=32)
        self.head = nn.Linear(32, num_classes)
        
    def forward(self, x_img):
        feat = self.encoder(x_img)
        return self.head(feat)

class ConcatFusionClassifier(nn.Module):
    def __init__(self, tab_in=12, num_classes=4):
        super().__init__()
        self.tab_encoder = TabularEncoder(in_features=tab_in, out_features=32)
        self.vis_encoder = VisionEncoder(out_features=32)
        self.head = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, num_classes)
        )
        
    def forward(self, x_tab, x_img):
        e_tab = self.tab_encoder(x_tab)
        e_vis = self.vis_encoder(x_img)
        fused = torch.cat([e_tab, e_vis], dim=-1)
        return self.head(fused)

def train_tabular_baseline(train_df, val_df, test_df, preprocessor):
    print("\n--- Training Tabular Baseline (LightGBM) ---")
    X_train, _ = preprocessor.transform(train_df)
    y_train = train_df["defect_label"].values
    
    X_val, _ = preprocessor.transform(val_df)
    y_val = val_df["defect_label"].values
    
    X_test, _ = preprocessor.transform(test_df)
    y_test = test_df["defect_label"].values
    
    # Class weights for imbalance
    counts = np.bincount(y_train)
    weights = {i: len(y_train) / (len(counts) * counts[i]) for i in range(len(counts))}
    
    model = LGBMClassifier(
        n_estimators=120,
        learning_rate=0.05,
        class_weight=weights,
        random_state=42,
        verbose=-1
    )
    
    start_time = time.time()
    model.fit(X_train, y_train)
    train_time = time.time() - start_time
    
    # Inference latency
    t0 = time.time()
    y_prob = model.predict_proba(X_test)
    y_pred = model.predict(X_test)
    latency_ms = ((time.time() - t0) / len(X_test)) * 1000.0
    
    # Calculate metrics
    y_test_bin = label_binarize(y_test, classes=[0, 1, 2, 3])
    pr_auc = float(average_precision_score(y_test_bin, y_prob, average="macro"))
    
    # False Reject Rate (Normal misclassified as defect)
    normal_mask = (y_test == 0)
    frr = float(np.mean(y_pred[normal_mask] != 0)) if np.sum(normal_mask) > 0 else 0.0
    
    metrics = {
        "model_name": "Tabular Baseline (LightGBM)",
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision_macro": round(float(precision_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "recall_macro": round(float(recall_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "defect_recall": round(float(recall_score(y_test != 0, y_pred != 0)), 4),
        "f1_macro": round(float(f1_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "pr_auc": round(pr_auc, 4),
        "false_reject_rate": round(frr, 4),
        "latency_ms": round(latency_ms, 3)
    }
    
    # Save model
    import joblib
    joblib.dump(model, os.path.join(MODEL_DIR, "tabular_baseline_lgbm.joblib"))
    print("Tabular Baseline Results:", metrics)
    return metrics

def train_vision_baseline(train_loader, val_loader, test_loader, epochs=10):
    print("\n--- Training Vision Baseline (CNN) ---")
    model = VisionOnlyClassifier(num_classes=4)
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()
    
    for epoch in range(epochs):
        model.train()
        for _, x_img, label in train_loader:
            optimizer.zero_grad()
            out = model(x_img)
            loss = criterion(out, label)
            loss.backward()
            optimizer.step()
            
    # Evaluation
    model.eval()
    all_preds, all_probs, all_targets = [], [], []
    t0 = time.time()
    with torch.no_grad():
        for _, x_img, label in test_loader:
            logits = model(x_img)
            probs = F.softmax(logits, dim=-1)
            preds = torch.argmax(probs, dim=-1)
            all_preds.extend(preds.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())
            all_targets.extend(label.cpu().numpy())
            
    latency_ms = ((time.time() - t0) / len(all_targets)) * 1000.0
    
    y_test = np.array(all_targets)
    y_pred = np.array(all_preds)
    y_prob = np.array(all_probs)
    
    y_test_bin = label_binarize(y_test, classes=[0, 1, 2, 3])
    pr_auc = float(average_precision_score(y_test_bin, y_prob, average="macro"))
    normal_mask = (y_test == 0)
    frr = float(np.mean(y_pred[normal_mask] != 0)) if np.sum(normal_mask) > 0 else 0.0
    
    metrics = {
        "model_name": "Vision Baseline (CNN)",
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision_macro": round(float(precision_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "recall_macro": round(float(recall_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "defect_recall": round(float(recall_score(y_test != 0, y_pred != 0)), 4),
        "f1_macro": round(float(f1_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "pr_auc": round(pr_auc, 4),
        "false_reject_rate": round(frr, 4),
        "latency_ms": round(latency_ms, 3)
    }
    
    torch.save(model.state_dict(), os.path.join(MODEL_DIR, "vision_baseline_cnn.pt"))
    print("Vision Baseline Results:", metrics)
    return metrics

def train_concat_fusion(train_loader, test_loader, epochs=12):
    print("\n--- Training Concat Multimodal Fusion ---")
    model = ConcatFusionClassifier(tab_in=12, num_classes=4)
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()
    
    for epoch in range(epochs):
        model.train()
        for x_tab, x_img, label in train_loader:
            optimizer.zero_grad()
            out = model(x_tab, x_img)
            loss = criterion(out, label)
            loss.backward()
            optimizer.step()
            
    # Evaluation
    model.eval()
    all_preds, all_probs, all_targets = [], [], []
    t0 = time.time()
    with torch.no_grad():
        for x_tab, x_img, label in test_loader:
            logits = model(x_tab, x_img)
            probs = F.softmax(logits, dim=-1)
            preds = torch.argmax(probs, dim=-1)
            all_preds.extend(preds.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())
            all_targets.extend(label.cpu().numpy())
            
    latency_ms = ((time.time() - t0) / len(all_targets)) * 1000.0
    
    y_test = np.array(all_targets)
    y_pred = np.array(all_preds)
    y_prob = np.array(all_probs)
    
    y_test_bin = label_binarize(y_test, classes=[0, 1, 2, 3])
    pr_auc = float(average_precision_score(y_test_bin, y_prob, average="macro"))
    normal_mask = (y_test == 0)
    frr = float(np.mean(y_pred[normal_mask] != 0)) if np.sum(normal_mask) > 0 else 0.0
    
    metrics = {
        "model_name": "Multimodal Concatenation Fusion",
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision_macro": round(float(precision_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "recall_macro": round(float(recall_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "defect_recall": round(float(recall_score(y_test != 0, y_pred != 0)), 4),
        "f1_macro": round(float(f1_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "pr_auc": round(pr_auc, 4),
        "false_reject_rate": round(frr, 4),
        "latency_ms": round(latency_ms, 3)
    }
    print("Concat Fusion Results:", metrics)
    return metrics

def train_gated_multimodal_fusion(train_loader, test_loader, epochs=14):
    print("\n--- Training Gated Multimodal Fusion (Proposed Innovation) ---")
    model = GatedMultimodalFusionNet(tab_in=12, num_classes=4, emb_dim=32)
    optimizer = optim.AdamW(model.parameters(), lr=1.2e-3, weight_decay=1e-4)
    # Focal / Weighted loss for severe imbalance
    weights = torch.tensor([1.0, 3.5, 3.0, 2.5])
    criterion = nn.CrossEntropyLoss(weight=weights)
    
    for epoch in range(epochs):
        model.train()
        for x_tab, x_img, label in train_loader:
            optimizer.zero_grad()
            logits, gate = model(x_tab, x_img)
            loss = criterion(logits, label)
            loss.backward()
            optimizer.step()
            
    # Evaluation
    model.eval()
    all_preds, all_probs, all_targets = [], [], []
    t0 = time.time()
    with torch.no_grad():
        for x_tab, x_img, label in test_loader:
            logits, gate = model(x_tab, x_img)
            probs = F.softmax(logits, dim=-1)
            preds = torch.argmax(probs, dim=-1)
            all_preds.extend(preds.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())
            all_targets.extend(label.cpu().numpy())
            
    latency_ms = ((time.time() - t0) / len(all_targets)) * 1000.0
    
    y_test = np.array(all_targets)
    y_pred = np.array(all_preds)
    y_prob = np.array(all_probs)
    
    y_test_bin = label_binarize(y_test, classes=[0, 1, 2, 3])
    pr_auc = float(average_precision_score(y_test_bin, y_prob, average="macro"))
    normal_mask = (y_test == 0)
    frr = float(np.mean(y_pred[normal_mask] != 0)) if np.sum(normal_mask) > 0 else 0.0
    
    metrics = {
        "model_name": "Gated Multimodal Fusion (Proposed)",
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision_macro": round(float(precision_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "recall_macro": round(float(recall_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "defect_recall": round(float(recall_score(y_test != 0, y_pred != 0)), 4),
        "f1_macro": round(float(f1_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "pr_auc": round(pr_auc, 4),
        "false_reject_rate": round(frr, 4),
        "latency_ms": round(latency_ms, 3)
    }
    
    # Save model weights
    torch.save(model.state_dict(), os.path.join(MODEL_DIR, "gated_multimodal_fusion.pt"))
    print("Gated Multimodal Fusion Results:", metrics)
    return metrics, model

def run_ablation_benchmark():
    from src.data.preprocessor import ManufacturingPreprocessor
    preprocessor = ManufacturingPreprocessor.load("data/processed/preprocessor.joblib")
    train_df = pd.read_csv("data/processed/train.csv")
    val_df = pd.read_csv("data/processed/val.csv")
    test_df = pd.read_csv("data/processed/test.csv")
    
    train_loader, val_loader, test_loader = get_dataloaders()
    
    results = []
    
    # 1. Tabular Baseline
    res_tab = train_tabular_baseline(train_df, val_df, test_df, preprocessor)
    results.append(res_tab)
    
    # 2. Vision Baseline
    res_vis = train_vision_baseline(train_loader, val_loader, test_loader, epochs=8)
    results.append(res_vis)
    
    # 3. Multimodal Concat Fusion
    res_concat = train_concat_fusion(train_loader, test_loader, epochs=10)
    results.append(res_concat)
    
    # 4. Multimodal Gated Fusion (Proposed)
    res_gated, _ = train_gated_multimodal_fusion(train_loader, test_loader, epochs=12)
    results.append(res_gated)
    
    # Save Benchmark to JSON & CSV
    df_results = pd.DataFrame(results)
    df_results.to_csv(os.path.join(REPORTS_DIR, "ablation_benchmark.csv"), index=False)
    with open(os.path.join(REPORTS_DIR, "ablation_benchmark.json"), "w") as f:
        json.dump(results, f, indent=2)
        
    print("\n================== ABLATION STUDY BENCHMARK SUMMARY ==================")
    print(df_results[["model_name", "accuracy", "defect_recall", "f1_macro", "pr_auc", "false_reject_rate", "latency_ms"]].to_string(index=False))
    print("======================================================================\n")
    return results

if __name__ == "__main__":
    run_ablation_benchmark()
