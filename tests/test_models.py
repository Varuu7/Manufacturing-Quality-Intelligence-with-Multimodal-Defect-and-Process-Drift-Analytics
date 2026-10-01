"""
Unit tests for Multimodal Neural Network, Uncertainty, and Grad-CAM Saliency.
"""

import sys
import os
import pytest
import torch
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.models.multimodal_fusion import GatedMultimodalFusionNet

@pytest.fixture
def multimodal_model():
    model = GatedMultimodalFusionNet(tab_in=12, num_classes=4, emb_dim=32)
    path = "data/processed/models/gated_multimodal_fusion.pt"
    if os.path.exists(path):
        model.load_state_dict(torch.load(path, map_location="cpu"))
    model.eval()
    return model

def test_model_forward_pass(multimodal_model):
    x_tab = torch.randn(2, 12)
    x_img = torch.randn(2, 1, 64, 64)
    logits, gate = multimodal_model(x_tab, x_img)
    assert logits.shape == (2, 4)
    assert gate.shape == (2, 1)
    assert 0.0 <= gate.min().item() and gate.max().item() <= 1.0

def test_predict_with_confidence(multimodal_model):
    x_tab = torch.randn(1, 12)
    x_img = torch.randn(1, 1, 64, 64)
    res = multimodal_model.predict_with_confidence(x_tab, x_img)
    assert "predicted_label" in res
    assert res["predicted_label"] in [0, 1, 2, 3]
    assert 0.0 <= res["confidence"] <= 1.0
    assert res["entropy"] >= 0.0
    assert isinstance(res["is_uncertain"], bool)

def test_gradcam_generation(multimodal_model):
    x_tab = torch.randn(1, 12)
    x_img = torch.randn(1, 1, 64, 64)
    cam = multimodal_model.generate_gradcam(x_tab, x_img, target_class=1)
    assert cam.shape == (64, 64)
    assert 0.0 <= np.min(cam) and np.max(cam) <= 1.0
