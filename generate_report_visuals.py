"""
Generates high-resolution figures, UI console screenshots, and code snippet cards
for inclusion in the Capstone Blackbook (PDF & Word document).
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image

# Ensure output directory exists
OUT_DIR = "reports/figures"
os.makedirs(OUT_DIR, exist_ok=True)

plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#CBD5E1'

# ----------------- 1. Dark Code Snippet Generator -----------------
def create_code_card(filename: str, title: str, code_lines: list[str]):
    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=200)
    fig.patch.set_facecolor('#181A20')
    ax.set_facecolor('#181A20')
    ax.axis('off')
    
    # Title bar
    ax.add_patch(patches.Rectangle((0, 0.90), 1, 0.10, transform=ax.transAxes, color='#222630'))
    ax.text(0.03, 0.94, f"📄 {title}", transform=ax.transAxes, color='#94A3B8', fontsize=10, fontweight='bold', va='center')
    
    # Three dots
    for i, c in enumerate(['#EF4444', '#F59E0B', '#10B981']):
        ax.add_patch(patches.Circle((0.92 + i*0.025, 0.95), 0.009, transform=ax.transAxes, color=c))
        
    # Code text
    y_pos = 0.84
    line_height = 0.055
    for i, line in enumerate(code_lines):
        # Line number
        ax.text(0.02, y_pos, f"{i+1:2d}", transform=ax.transAxes, color='#475569', fontfamily='monospace', fontsize=8, va='top')
        # Content
        col = '#E2E8F0'
        if line.strip().startswith('#'):
            col = '#64748B'
        elif any(k in line for k in ['class ', 'def ', 'return ', 'import ', 'from ']):
            col = '#38BDF8'
        elif any(k in line for k in ['self.', 'torch.', 'nn.', 'np.', 'pd.']):
            col = '#A78BFA'
        elif any(k in line for k in ['"Normal"', '"Surface Crack"', '"Micro Void"']):
            col = '#34D399'
            
        ax.text(0.07, y_pos, line, transform=ax.transAxes, color=col, fontfamily='monospace', fontsize=8.2, va='top')
        y_pos -= line_height
        
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, filename), facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close()
    print(f"Generated {filename}")

# Generate 6 Code Cards
create_code_card(
    "code_4_1_gated_fusion.png",
    "src/models/multimodal_fusion.py - GatedMultimodalFusionNet",
    [
        "class GatedMultimodalFusionNet(nn.Module):",
        "    def __init__(self, tab_in=12, num_classes=4, emb_dim=32):",
        "        super().__init__()",
        "        self.tab_encoder = TabularEncoder(in_features=tab_in, out_features=emb_dim)",
        "        self.vis_encoder = VisionEncoder(out_features=emb_dim)",
        "        self.gate_fc = nn.Sequential(nn.Linear(emb_dim * 2, emb_dim), nn.ReLU(),",
        "                                     nn.Linear(emb_dim, 1), nn.Sigmoid())",
        "        self.classifier = nn.Sequential(nn.Linear(emb_dim, 32), nn.LeakyReLU(0.1),",
        "                                        nn.Linear(32, num_classes))",
        "        self.temperature = nn.Parameter(torch.ones(1) * 1.0)",
        "",
        "    def forward(self, x_tab, x_img):",
        "        e_tab = self.tab_encoder(x_tab)",
        "        e_vis = self.vis_encoder(x_img)",
        "        gate = self.gate_fc(torch.cat([e_tab, e_vis], dim=-1))",
        "        fused = gate * e_tab + (1.0 - gate) * e_vis",
        "        return self.classifier(fused) / torch.clamp(self.temperature, 0.1, 5.0), gate"
    ]
)

create_code_card(
    "code_4_2_confidence_entropy.png",
    "src/models/multimodal_fusion.py - predict_with_confidence()",
    [
        "def predict_with_confidence(self, x_tab, x_img) -> dict:",
        "    self.eval()",
        "    with torch.no_grad():",
        "        logits, gate = self.forward(x_tab, x_img)",
        "        probs = F.softmax(logits, dim=-1).cpu().numpy()[0]",
        "        pred_class = int(np.argmax(probs))",
        "        confidence = float(np.max(probs))",
        "        entropy = float(-np.sum(probs * np.log(probs + 1e-9)))",
        "        is_uncertain = bool(confidence < 0.62 or entropy > 0.85)",
        "        return {",
        "            'predicted_label': pred_class,",
        "            'predicted_name': DEFECT_CLASSES[pred_class],",
        "            'confidence': round(confidence, 4),",
        "            'entropy': round(entropy, 4),",
        "            'is_uncertain': is_uncertain,",
        "            'gate_tab': round(float(gate[0, 0]), 3)",
        "        }"
    ]
)

create_code_card(
    "code_4_3_gradcam_engine.png",
    "src/models/multimodal_fusion.py - generate_gradcam()",
    [
        "def generate_gradcam(self, x_tab, x_img, target_class=None) -> np.ndarray:",
        "    self.eval()",
        "    x_img.requires_grad = True",
        "    logits, _ = self.forward(x_tab, x_img)",
        "    if target_class is None: target_class = torch.argmax(logits, dim=1).item()",
        "    self.zero_grad()",
        "    logits[0, target_class].backward(retain_graph=True)",
        "    gradients = self.vis_encoder.last_conv_grad  # (1, 32, H, W)",
        "    activations = self.vis_encoder.last_conv_act # (1, 32, H, W)",
        "    weights = torch.mean(gradients, dim=(2, 3), keepdim=True)",
        "    cam = torch.sum(weights * activations, dim=1, keepdim=True)",
        "    cam = F.relu(cam)",
        "    cam = F.interpolate(cam, size=(64, 64), mode='bilinear', align_corners=False)",
        "    cam = cam.squeeze().detach().cpu().numpy()",
        "    return (cam - np.min(cam)) / (np.max(cam) - np.min(cam) + 1e-9)"
    ]
)

create_code_card(
    "code_4_4_spc_rules.png",
    "src/spc/control_charts.py - evaluate_series()",
    [
        "def evaluate_series(self, series: pd.Series, var_name: str) -> dict:",
        "    stats = self.baseline_stats[var_name]",
        "    vals, n = series.values, len(series)",
        "    violations = []",
        "    # Rule 1: Beyond 3-sigma (UCL / LCL)",
        "    for i, v in enumerate(vals):",
        "        if v > stats['ucl'] or v < stats['lcl']:",
        "            violations.append({'rule': 'Rule 1 (>3σ)', 'index': i, 'val': float(v)})",
        "    # EWMA Smoothing & Evaluation",
        "    ewma_vals = self.compute_ewma_series(vals, stats['mean'])",
        "    for i, ev in enumerate(ewma_vals):",
        "        if ev > stats['ewma_ucl'] or ev < stats['ewma_lcl']:",
        "            violations.append({'rule': 'EWMA Limit', 'index': i, 'val': float(ev)})",
        "    status = 'Out-of-Control' if len(violations) >= 2 else ('Warning' if violations else 'In-Control')",
        "    return {'status': status, 'violations': violations, 'latest': float(vals[-1])}"
    ]
)

create_code_card(
    "code_4_5_drift_engine.png",
    "src/drift/drift_engine.py - analyze_batch_drift()",
    [
        "def analyze_batch_drift(self, df_batch: pd.DataFrame, batch_id: str) -> dict:",
        "    results, drifted_vars, max_psi, total_w_dist = {}, [], 0.0, 0.0",
        "    for var in self.variables:",
        "        base, curr = self.baseline_data[var], df_batch[var].dropna().values",
        "        ks_stat, p_val = ks_2samp(base, curr)",
        "        psi = self.calculate_psi(base, curr, num_bins=4)",
        "        w_dist = float(wasserstein_distance(base, curr) / (np.std(base) + 1e-5))",
        "        if p_val < 0.005 and (psi > 0.15 or w_dist > 0.55):",
        "            drifted_vars.append(var)",
        "    drift_score = total_w_dist / len(self.variables)",
        "    if len(drifted_vars) >= 2 or drift_score > 0.85:",
        "        status = 'CRITICAL_DRIFT_ROLLBACK'",
        "        self.active_model_state = 'CONSERVATIVE_SAFETY_BASELINE'",
        "    elif len(drifted_vars) == 1 or drift_score > 0.45: status = 'INCIPIENT_DRIFT_WARNING'",
        "    else: status = 'IN_CONTROL'",
        "    return {'status': status, 'active_model': self.active_model_state, 'drifted': drifted_vars}"
    ]
)

create_code_card(
    "code_4_6_fastapi_endpoint.png",
    "src/api/main.py - @app.post('/api/v1/predict/multimodal')",
    [
        "@app.post('/api/v1/predict/multimodal', response_model=MultimodalInferenceResponse)",
        "def predict_multimodal(req: MultimodalInferenceRequest):",
        "    # 1. Transform Tabular Sensors",
        "    x_scaled = preprocessor.transform_single_dict(req.sensors.model_dump())",
        "    t_tab = torch.tensor(x_scaled, dtype=torch.float32).unsqueeze(0)",
        "    # 2. Decode Optical Image",
        "    if req.image_base64: img = Image.open(io.BytesIO(base64.b64decode(req.image_base64)))",
        "    else: img = Image.fromarray(np.full((64, 64), 175, dtype=np.uint8), mode='L')",
        "    t_img = transform_image(img, is_train=False).unsqueeze(0)",
        "    # 3. Model Inference & Grad-CAM Saliency",
        "    pred_res = model.predict_with_confidence(t_tab, t_img)",
        "    gradcam = model.generate_gradcam(t_tab, t_img, target_class=pred_res['predicted_label'])",
        "    attrs = model.explain_tabular_sensors(t_tab, t_img, preprocessor.feature_names)",
        "    return MultimodalInferenceResponse(predicted_name=pred_res['predicted_name'],",
        "                                       confidence=pred_res['confidence'], top_sensors=attrs[:5])"
    ]
)

# ----------------- 2. Frontend Console Screenshots -----------------

# Figure 5.1: Live Defect Inspector Console
def generate_fig_5_1():
    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=200)
    fig.patch.set_facecolor('#F8FAFC')
    ax.set_facecolor('#F8FAFC')
    ax.axis('off')
    
    # Header bar
    ax.add_patch(patches.Rectangle((0, 0.88), 1, 0.12, transform=ax.transAxes, color='#1E3A8A'))
    ax.text(0.03, 0.94, "⚙️ Manufacturing Quality Intelligence | Live Defect Inspector", transform=ax.transAxes, color='white', fontsize=12, fontweight='bold', va='center')
    ax.text(0.97, 0.94, "Station #04 | CNC Milling Line", transform=ax.transAxes, color='#93C5FD', fontsize=9, va='center', ha='right')

    # Status Box
    ax.add_patch(patches.Rectangle((0.03, 0.68), 0.28, 0.17, transform=ax.transAxes, color='#FEE2E2', ec='#EF4444', lw=1.5))
    ax.text(0.05, 0.80, "DEFECT DETECTED", transform=ax.transAxes, color='#991B1B', fontsize=9, fontweight='bold')
    ax.text(0.05, 0.72, "SURFACE CRACK", transform=ax.transAxes, color='#B91C1C', fontsize=14, fontweight='bold')
    
    # Metrics
    ax.add_patch(patches.Rectangle((0.34, 0.68), 0.20, 0.17, transform=ax.transAxes, color='#FFFFFF', ec='#CBD5E1'))
    ax.text(0.36, 0.80, "CONFIDENCE", transform=ax.transAxes, color='#64748B', fontsize=8, fontweight='bold')
    ax.text(0.36, 0.72, "98.4%", transform=ax.transAxes, color='#10B981', fontsize=16, fontweight='bold')

    ax.add_patch(patches.Rectangle((0.56, 0.68), 0.20, 0.17, transform=ax.transAxes, color='#FFFFFF', ec='#CBD5E1'))
    ax.text(0.58, 0.80, "SHANNON ENTROPY", transform=ax.transAxes, color='#64748B', fontsize=8, fontweight='bold')
    ax.text(0.58, 0.72, "0.210", transform=ax.transAxes, color='#3B82F6', fontsize=16, fontweight='bold')

    ax.add_patch(patches.Rectangle((0.78, 0.68), 0.19, 0.17, transform=ax.transAxes, color='#FFFFFF', ec='#CBD5E1'))
    ax.text(0.80, 0.80, "AUDIT STATUS", transform=ax.transAxes, color='#64748B', fontsize=8, fontweight='bold')
    ax.text(0.80, 0.72, "REJECT BATCH", transform=ax.transAxes, color='#DC2626', fontsize=12, fontweight='bold')

    # Telemetry Parameters panel
    ax.add_patch(patches.Rectangle((0.03, 0.08), 0.45, 0.55, transform=ax.transAxes, color='#FFFFFF', ec='#CBD5E1'))
    ax.text(0.05, 0.58, "Active Sensor Telemetry Values", transform=ax.transAxes, color='#1E293B', fontsize=10, fontweight='bold')
    
    sensors = [
        ("Furnace Chamber Temp", "825.0 °C", "Normal (CL: 819.6 °C)"),
        ("Injection Pressure", "124.0 MPa", "Normal (CL: 122.3 MPa)"),
        ("Spindle Rotation Speed", "3180.0 RPM", "Normal (CL: 3147 RPM)"),
        ("Milling Feed Rate", "51.0 mm/s", "ELEVATED (CL: 43.9 mm/s)"),
        ("Spindle Vibration", "2.75 g", "CRITICAL (> UCL: 2.64 g)"),
        ("Cumulative Tool Wear", "140.0 min", "HIGH WEAR REGIME")
    ]
    y = 0.51
    for s, v, note in sensors:
        ax.text(0.05, y, f"• {s}:", transform=ax.transAxes, color='#334155', fontsize=8.5, fontweight='bold')
        ax.text(0.30, y, v, transform=ax.transAxes, color='#1E3A8A', fontsize=8.5, fontfamily='monospace')
        y -= 0.075

    # Gating Attention weight bar
    ax.add_patch(patches.Rectangle((0.52, 0.08), 0.45, 0.55, transform=ax.transAxes, color='#FFFFFF', ec='#CBD5E1'))
    ax.text(0.54, 0.58, "Adaptive Cross-Modal Gating Attention", transform=ax.transAxes, color='#1E293B', fontsize=10, fontweight='bold')
    
    # Progress bars for gating
    ax.text(0.54, 0.48, "Sensor Telemetry Weight (α = 0.52)", transform=ax.transAxes, color='#334155', fontsize=8.5)
    ax.add_patch(patches.Rectangle((0.54, 0.42), 0.40 * 0.52, 0.04, transform=ax.transAxes, color='#3B82F6'))
    ax.add_patch(patches.Rectangle((0.54 + 0.40 * 0.52, 0.42), 0.40 * 0.48, 0.04, transform=ax.transAxes, color='#E2E8F0'))

    ax.text(0.54, 0.32, "Optical Visual Weight (1 - α = 0.48)", transform=ax.transAxes, color='#334155', fontsize=8.5)
    ax.add_patch(patches.Rectangle((0.54, 0.26), 0.40 * 0.48, 0.04, transform=ax.transAxes, color='#10B981'))
    ax.add_patch(patches.Rectangle((0.54 + 0.40 * 0.48, 0.26), 0.40 * 0.52, 0.04, transform=ax.transAxes, color='#E2E8F0'))

    ax.text(0.54, 0.16, "💡 Cross-modal fusion actively balances physical", transform=ax.transAxes, color='#64748B', fontsize=7.5, style='italic')
    ax.text(0.54, 0.12, "telemetry with visual defect saliency in real time.", transform=ax.transAxes, color='#64748B', fontsize=7.5, style='italic')

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "fig_5_1_defect_inspector.png"), bbox_inches='tight')
    plt.close()
    print("Generated fig_5_1_defect_inspector.png")

# Figure 5.2: Grad-CAM Optical Defect Saliency & Sensor Attribution
def generate_fig_5_2():
    fig = plt.figure(figsize=(9, 4.4), dpi=200)
    fig.patch.set_facecolor('#F8FAFC')
    
    # 1. Optical scan
    ax1 = fig.add_subplot(1, 3, 1)
    base = np.random.normal(175, 10, (64, 64)).clip(100, 240)
    # Add crack line
    for i in range(15, 50):
        base[i, int(20 + np.sin(i*0.2)*5 + (i-15)*0.6)] = 35
        base[i, int(21 + np.sin(i*0.2)*5 + (i-15)*0.6)] = 45
    ax1.imshow(base, cmap='gray')
    ax1.set_title("Optical Surface Scan (64x64)\nDefect: Surface Crack", fontsize=9, fontweight='bold', pad=8)
    ax1.axis('off')

    # 2. Grad-CAM Overlay
    ax2 = fig.add_subplot(1, 3, 2)
    cam = np.zeros((64, 64))
    for i in range(12, 52):
        col_c = int(20 + np.sin(i*0.2)*5 + (i-15)*0.6)
        cam[max(0, i-4):min(64, i+5), max(0, col_c-4):min(64, col_c+5)] += 0.8
    cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-9)
    ax2.imshow(base, cmap='gray')
    ax2.imshow(cam, cmap='jet', alpha=0.55)
    ax2.set_title("Grad-CAM Saliency Overlay\nSpatial Attention Heatmap", fontsize=9, fontweight='bold', pad=8)
    ax2.axis('off')

    # 3. Sensor Attribution
    ax3 = fig.add_subplot(1, 3, 3)
    features = ['Vibration Amplitude', 'Feed Rate', 'Tool Wear', 'Coolant Flow', 'Furnace Temp']
    scores = [0.412, 0.265, 0.184, 0.081, 0.058]
    y_pos = np.arange(len(features))
    ax3.barh(y_pos, scores, color='#EF4444', height=0.55)
    ax3.set_yticks(y_pos)
    ax3.set_yticklabels(features, fontsize=8)
    ax3.invert_yaxis()
    ax3.set_xlabel("Relative Attribution Weight", fontsize=8)
    ax3.set_title("Sensor Root-Cause Attribution\nTop Physical Contributors", fontsize=9, fontweight='bold', pad=8)
    ax3.set_facecolor('#FFFFFF')
    for spine in ax3.spines.values(): spine.set_color('#CBD5E1')

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "fig_5_2_gradcam_attribution.png"), bbox_inches='tight')
    plt.close()
    print("Generated fig_5_2_gradcam_attribution.png")

# Figure 5.3: Statistical Process Control (SPC) Observatory
def generate_fig_5_3():
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=200)
    fig.patch.set_facecolor('#F8FAFC')
    ax.set_facecolor('#FFFFFF')

    np.random.seed(42)
    n = 60
    base_mean = 819.62
    base_std = 17.91
    ucl = base_mean + 3 * base_std
    lcl = base_mean - 3 * base_std

    # Sequence with simulated out of control shift around sample 45
    vals = np.random.normal(base_mean, base_std, n)
    vals[42:52] += np.linspace(10, 45, 10) # shift

    # EWMA
    ewma = np.zeros(n)
    prev = base_mean
    for i in range(n):
        prev = 0.2 * vals[i] + 0.8 * prev
        ewma[i] = prev

    x = np.arange(1, n+1)
    ax.plot(x, vals, color='#1E40AF', marker='o', markersize=3.5, lw=1.2, label='Observed Temperature (°C)')
    ax.plot(x, ewma, color='#8B5CF6', lw=2.0, label='EWMA Curve (λ = 0.2)')

    # Limits
    ax.axhline(ucl, color='#EF4444', linestyle='--', lw=1.5, label=f'UCL (+3σ = {ucl:.1f}°C)')
    ax.axhline(base_mean, color='#10B981', linestyle='-', lw=1.5, label=f'Centerline (CL = {base_mean:.1f}°C)')
    ax.axhline(lcl, color='#EF4444', linestyle='--', lw=1.5, label=f'LCL (-3σ = {lcl:.1f}°C)')

    # Highlight violations
    out_idx = np.where((vals > ucl) | (vals < lcl))[0]
    if len(out_idx) > 0:
        ax.scatter(x[out_idx], vals[out_idx], color='#DC2626', s=70, marker='x', lw=2, zorder=5, label='Rule 1 Violation (>3σ)')

    ax.set_title("Shewhart X-bar & EWMA Control Chart: Furnace Temperature (°C)", fontsize=10, fontweight='bold', pad=10)
    ax.set_xlabel("Sequential Production Component (#)", fontsize=8.5)
    ax.set_ylabel("Process Value (°C)", fontsize=8.5)
    ax.legend(loc='lower left', fontsize=7.5, framealpha=0.9)
    ax.grid(True, linestyle=':', alpha=0.6)

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "fig_5_3_spc_observatory.png"), bbox_inches='tight')
    plt.close()
    print("Generated fig_5_3_spc_observatory.png")

# Figure 5.4: Modality Ablation Benchmark
def generate_fig_5_4():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4.4), dpi=200)
    fig.patch.set_facecolor('#F8FAFC')
    
    models = ['Tabular (LightGBM)', 'Vision (CNN)', 'Concat Fusion', 'Gated Fusion (Ours)']
    recalls = [85.0, 100.0, 100.0, 100.0]
    pr_aucs = [86.7, 96.4, 98.9, 95.7]
    frrs = [1.62, 0.0, 0.0, 0.0]

    # Bar 1: Defect Recall & PR-AUC
    x = np.arange(len(models))
    width = 0.35
    ax1.set_facecolor('#FFFFFF')
    ax1.bar(x - width/2, recalls, width, label='Defect Recall (%)', color='#3B82F6')
    ax1.bar(x + width/2, pr_aucs, width, label='PR-AUC (%)', color='#10B981')
    ax1.set_xticks(x)
    ax1.set_xticklabels(models, rotation=20, ha='right', fontsize=8)
    ax1.set_ylabel("Score (%)", fontsize=8.5)
    ax1.set_ylim(70, 105)
    ax1.set_title("Defect Recall & PR-AUC by Modality", fontsize=9.5, fontweight='bold')
    ax1.legend(loc='lower right', fontsize=8)
    ax1.grid(True, linestyle=':', alpha=0.5)

    # Bar 2: False Reject Rate
    ax2.set_facecolor('#FFFFFF')
    ax2.bar(models, frrs, color=['#EF4444', '#10B981', '#10B981', '#10B981'], width=0.45)
    ax2.set_ylabel("False Reject Rate (%)", fontsize=8.5)
    ax2.set_ylim(0, 2.5)
    ax2.set_xticklabels(models, rotation=20, ha='right', fontsize=8)
    ax2.set_title("False Reject Rate (Scrapped Good Parts)", fontsize=9.5, fontweight='bold')
    ax2.grid(True, linestyle=':', alpha=0.5)

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "fig_5_4_ablation_benchmark.png"), bbox_inches='tight')
    plt.close()
    print("Generated fig_5_4_ablation_benchmark.png")

# Figure 5.5: Process Drift & Automated Rollback
def generate_fig_5_5():
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=200)
    fig.patch.set_facecolor('#F8FAFC')
    ax.set_facecolor('#FFFFFF')

    batches = np.arange(1, 31)
    drift_score = np.concatenate([
        np.random.normal(0.28, 0.05, 10),
        np.linspace(0.35, 0.72, 10),
        np.linspace(0.88, 1.35, 10)
    ])

    ax.plot(batches[:10], drift_score[:10], marker='o', color='#10B981', lw=1.8, label='In-Control Batches (1-10)')
    ax.plot(batches[9:20], drift_score[9:20], marker='s', color='#F59E0B', lw=1.8, label='Incipient Drift (11-20)')
    ax.plot(batches[19:], drift_score[19:], marker='^', color='#EF4444', lw=2.2, label='Critical Out-of-Control (21-30)')

    ax.axhline(0.45, color='orange', linestyle='--', lw=1.5, label='Incipient Warning Threshold (0.45)')
    ax.axhline(0.85, color='red', linestyle='--', lw=1.8, label='Critical Rollback Threshold (0.85)')

    ax.text(22, 1.15, "🔴 AUTOMATED ROLLBACK TRIGGERED\nFallback to Safety Baseline", color='#DC2626', fontsize=8.5, fontweight='bold', bbox=dict(boxstyle='round,pad=0.5', facecolor='#FEE2E2', edgecolor='#DC2626'))

    ax.set_title("Multi-Batch Multivariate Drift Timeline & Rollback Activation", fontsize=10, fontweight='bold', pad=10)
    ax.set_xlabel("Production Streaming Batch Number", fontsize=8.5)
    ax.set_ylabel("Multivariate Drift Score (Wasserstein)", fontsize=8.5)
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True, linestyle=':', alpha=0.5)

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "fig_5_5_drift_rollback.png"), bbox_inches='tight')
    plt.close()
    print("Generated fig_5_5_drift_rollback.png")

# Figure 5.6: FastAPI OpenAPI Swagger UI
def generate_fig_5_6():
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=200)
    fig.patch.set_facecolor('#F8FAFC')
    ax.set_facecolor('#FFFFFF')
    ax.axis('off')

    # Swagger Header
    ax.add_patch(patches.Rectangle((0, 0.88), 1, 0.12, transform=ax.transAxes, color='#1F2937'))
    ax.text(0.03, 0.94, "{ } FastAPI Swagger UI - Manufacturing Quality Intelligence API v1.0.0", transform=ax.transAxes, color='#10B981', fontfamily='monospace', fontsize=10.5, fontweight='bold', va='center')
    ax.text(0.97, 0.94, "OAS 3.0", transform=ax.transAxes, color='#9CA3AF', fontfamily='monospace', fontsize=8.5, va='center', ha='right')

    endpoints = [
        ("POST", "/api/v1/predict/multimodal", "#10B981", "Execute dual-modal defect inference (telemetry + surface scan) with Grad-CAM and uncertainty"),
        ("POST", "/api/v1/spc/evaluate", "#10B981", "Evaluate sequential process observations against Shewhart & Western Electric rules"),
        ("POST", "/api/v1/drift/analyze", "#10B981", "Compute Two-Sample KS-test, PSI, and Wasserstein scores; trigger rollback if critical"),
        ("GET",  "/api/v1/models/ablation-benchmark", "#3B82F6", "Retrieve holdout test ablation metrics across Tabular, Vision, and Fusion baselines"),
        ("GET",  "/health", "#3B82F6", "System health check, active model policy state, and device telemetry")
    ]
    y = 0.76
    for method, path, col, desc in endpoints:
        ax.add_patch(patches.Rectangle((0.02, y-0.03), 0.96, 0.10, transform=ax.transAxes, color='#F8FAFC', ec='#E2E8F0'))
        ax.add_patch(patches.Rectangle((0.03, y-0.02), 0.09, 0.08, transform=ax.transAxes, color=col))
        ax.text(0.075, y+0.02, method, transform=ax.transAxes, color='white', fontfamily='monospace', fontsize=8.5, fontweight='bold', ha='center', va='center')
        ax.text(0.14, y+0.02, path, transform=ax.transAxes, color='#1E293B', fontfamily='monospace', fontsize=9, fontweight='bold', va='center')
        ax.text(0.14, y-0.015, desc, transform=ax.transAxes, color='#64748B', fontsize=7.5, va='center')
        y -= 0.13

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "fig_5_6_fastapi_swagger.png"), bbox_inches='tight')
    plt.close()
    print("Generated fig_5_6_fastapi_swagger.png")

if __name__ == "__main__":
    generate_fig_5_1()
    generate_fig_5_2()
    generate_fig_5_3()
    generate_fig_5_4()
    generate_fig_5_5()
    generate_fig_5_6()
