"""
Multimodal Deep Neural Network with Gated Cross-Modal Fusion,
Calibrated Uncertainty Estimation, Grad-CAM Visual Heatmaps, and Tabular Attribution.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

DEFECT_CLASSES = {
    0: "Normal",
    1: "Surface Crack",
    2: "Micro Void",
    3: "Tool Scuffing"
}

class TabularEncoder(nn.Module):
    def __init__(self, in_features: int = 12, out_features: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, 64),
            nn.LayerNorm(64),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.2),
            nn.Linear(64, out_features),
            nn.LayerNorm(out_features),
            nn.LeakyReLU(0.1)
        )
        
    def forward(self, x):
        return self.net(x)

class VisionEncoder(nn.Module):
    def __init__(self, out_features: int = 32):
        super().__init__()
        # Conv block 1
        self.conv1 = nn.Conv2d(1, 16, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(16)
        
        # Conv block 2 (target for Grad-CAM)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(32)
        
        self.pool = nn.MaxPool2d(2, 2)
        self.fc = nn.Sequential(
            nn.AdaptiveAvgPool2d((4, 4)),
            nn.Flatten(),
            nn.Linear(32 * 4 * 4, out_features),
            nn.LayerNorm(out_features),
            nn.LeakyReLU(0.1)
        )
        
        self.last_conv_act = None
        self.last_conv_grad = None

    def activations_hook(self, grad):
        self.last_conv_grad = grad

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.pool(x)
        
        # Conv 2
        x = F.relu(self.bn2(self.conv2(x)))
        if x.requires_grad:
            h = x.register_hook(self.activations_hook)
        self.last_conv_act = x
        
        x = self.pool(x)
        features = self.fc(x)
        return features

class GatedMultimodalFusionNet(nn.Module):
    def __init__(self, tab_in: int = 12, num_classes: int = 4, emb_dim: int = 32):
        super().__init__()
        self.tab_encoder = TabularEncoder(in_features=tab_in, out_features=emb_dim)
        self.vis_encoder = VisionEncoder(out_features=emb_dim)
        
        # Gating attention mechanism: balances telemetry vs vision reliability
        self.gate_fc = nn.Sequential(
            nn.Linear(emb_dim * 2, emb_dim),
            nn.ReLU(),
            nn.Linear(emb_dim, 1),
            nn.Sigmoid()
        )
        
        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(emb_dim, 32),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.15),
            nn.Linear(32, num_classes)
        )
        
        # Learnable temperature for probability calibration
        self.temperature = nn.Parameter(torch.ones(1) * 1.0)
        
    def forward(self, x_tab, x_img):
        e_tab = self.tab_encoder(x_tab)
        e_vis = self.vis_encoder(x_img)
        
        # Gated fusion
        concat = torch.cat([e_tab, e_vis], dim=-1)
        gate = self.gate_fc(concat) # Shape: (B, 1)
        fused = gate * e_tab + (1.0 - gate) * e_vis
        
        logits = self.classifier(fused)
        calibrated_logits = logits / torch.clamp(self.temperature, min=0.1, max=5.0)
        return calibrated_logits, gate

    def predict_with_confidence(self, x_tab: torch.Tensor, x_img: torch.Tensor) -> dict:
        """
        Inference with confidence scoring, uncertainty entropy, and ambiguity detection.
        """
        self.eval()
        with torch.no_grad():
            logits, gate = self.forward(x_tab, x_img)
            probs = F.softmax(logits, dim=-1).cpu().numpy()[0]
            pred_class = int(np.argmax(probs))
            confidence = float(np.max(probs))
            
            # Shannon entropy: H(p) = -sum(p * log(p))
            entropy = float(-np.sum(probs * np.log(probs + 1e-9)))
            
            # Out-of-Distribution or Ambiguity Flag
            is_uncertain = bool(confidence < 0.62 or entropy > 0.85)
            
            return {
                "predicted_label": pred_class,
                "predicted_name": DEFECT_CLASSES[pred_class],
                "confidence": round(confidence, 4),
                "entropy": round(entropy, 4),
                "is_uncertain": is_uncertain,
                "probabilities": {DEFECT_CLASSES[i]: round(float(probs[i]), 4) for i in range(len(probs))},
                "modality_gate_weight_tabular": round(float(gate.cpu().numpy()[0, 0]), 3),
                "modality_gate_weight_vision": round(1.0 - float(gate.cpu().numpy()[0, 0]), 3)
            }

    def generate_gradcam(self, x_tab: torch.Tensor, x_img: torch.Tensor, target_class: int = None) -> np.ndarray:
        """
        Generates 2D spatial Grad-CAM activation heatmap for visual defect localization.
        """
        self.eval()
        x_img.requires_grad = True
        logits, _ = self.forward(x_tab, x_img)
        
        if target_class is None:
            target_class = torch.argmax(logits, dim=1).item()
            
        self.zero_grad()
        score = logits[0, target_class]
        score.backward(retain_graph=True)
        
        # Retrieve gradients and activations from VisionEncoder conv2
        gradients = self.vis_encoder.last_conv_grad # (1, 32, H, W)
        activations = self.vis_encoder.last_conv_act # (1, 32, H, W)
        
        if gradients is None or activations is None:
            return np.zeros((64, 64), dtype=np.float32)
            
        # Global average pooling on gradients
        weights = torch.mean(gradients, dim=(2, 3), keepdim=True)
        cam = torch.sum(weights * activations, dim=1, keepdim=True)
        cam = F.relu(cam)
        cam = F.interpolate(cam, size=(64, 64), mode='bilinear', align_corners=False)
        cam = cam.squeeze().detach().cpu().numpy()
        
        # Normalize
        cam_min, cam_max = np.min(cam), np.max(cam)
        if cam_max > cam_min:
            cam = (cam - cam_min) / (cam_max - cam_min)
        else:
            cam = np.zeros_like(cam)
            
        return cam

    def explain_tabular_sensors(self, x_tab: torch.Tensor, x_img: torch.Tensor, feature_names: list[str]) -> list[dict]:
        """
        Gradient-based sensor attribution quantifying each telemetry variable's impact on defect score.
        """
        self.eval()
        x_tab_var = x_tab.clone().detach().requires_grad_(True)
        logits, _ = self.forward(x_tab_var, x_img)
        pred_class = torch.argmax(logits, dim=1).item()
        
        self.zero_grad()
        logits[0, pred_class].backward()
        
        grads = torch.abs(x_tab_var.grad[0]).cpu().numpy()
        total_attribution = np.sum(grads) + 1e-9
        norm_attr = grads / total_attribution
        
        attributions = []
        for name, score in zip(feature_names, norm_attr):
            attributions.append({
                "feature": name,
                "importance": round(float(score), 4)
            })
            
        attributions.sort(key=lambda x: x["importance"], reverse=True)
        return attributions
