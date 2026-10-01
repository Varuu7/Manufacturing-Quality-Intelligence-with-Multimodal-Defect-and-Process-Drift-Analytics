"""
Manufacturing Quality Intelligence Dashboard
Interactive Industrial Cockpit for BDS-27 Capstone Project
KES' Shroff College - T.Y. B.Sc. Data Science
"""

import os
import sys
import json
import torch
import numpy as np
import pandas as pd
from PIL import Image
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data.preprocessor import ManufacturingPreprocessor
from src.spc.control_charts import SPCEngine
from src.models.multimodal_fusion import GatedMultimodalFusionNet, DEFECT_CLASSES
from src.models.dataset_loader import transform_image
from src.drift.drift_engine import ProcessDriftEngine

# Page configuration
st.set_page_config(
    page_title="Manufacturing Quality Intelligence | BDS-27",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 28px;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0px;
    }
    .sub-title {
        font-size: 15px;
        color: #4B5563;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #F8FAFC;
        border-radius: 8px;
        padding: 15px;
        border: 1px solid #E2E8F0;
    }
    .badge-normal {
        background-color: #DEF7EC;
        color: #03543F;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
    }
    .badge-defect {
        background-color: #FDE8E8;
        color: #9B1C1C;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- Resource Caching -----------------
@st.cache_resource
def load_all_artifacts():
    prep = ManufacturingPreprocessor.load("data/processed/preprocessor.joblib")
    
    model = GatedMultimodalFusionNet(tab_in=12, num_classes=4, emb_dim=32)
    model.load_state_dict(torch.load("data/processed/models/gated_multimodal_fusion.pt", map_location=torch.device("cpu")))
    model.eval()
    
    train_df = pd.read_csv("data/processed/train.csv")
    spc = SPCEngine()
    spc.calibrate(train_df)
    
    drift_eng = ProcessDriftEngine(train_df)
    
    stream_df = pd.read_csv("data/raw/drift_telemetry_stream.csv")
    test_df = pd.read_csv("data/processed/test.csv")
    
    with open("reports/ablation_benchmark.json", "r") as f:
        benchmark_data = json.load(f)
        
    return prep, model, spc, drift_eng, train_df, test_df, stream_df, benchmark_data

try:
    prep, model, spc, drift_eng, train_df, test_df, stream_df, benchmark_data = load_all_artifacts()
except Exception as e:
    st.error(f"Error loading system artifacts: {e}. Please ensure data generation and ablation training have finished.")
    st.stop()

# ----------------- Sidebar -----------------
st.sidebar.image("https://img.icons8.com/color/96/factory.png", width=64)
st.sidebar.markdown("### Manufacturing Quality Intelligence")
st.sidebar.markdown("**Project Code:** BDS-27")
st.sidebar.markdown("**Programme:** T.Y. B.Sc. Data Science")
st.sidebar.markdown("**Institution:** KES' Shroff College")
st.sidebar.markdown("---")

nav_choice = st.sidebar.radio(
    "Navigation Console",
    [
        "🔍 Live Multimodal Defect Inspector",
        "📈 Statistical Process Control (SPC)",
        "📊 Modality Ablation Benchmark",
        "🌊 Process Drift & Automated Rollback",
        "🏛️ Architecture & System Specs"
    ]
)

st.sidebar.markdown("---")
st.sidebar.markdown("**System Status:** 🟢 Active")
st.sidebar.markdown(f"**Active Model:** `{drift_eng.active_model_state}`")

# =========================================================================
# TAB 1: Live Multimodal Defect Inspector
# =========================================================================
if nav_choice == "🔍 Live Multimodal Defect Inspector":
    st.markdown('<div class="main-title">Real-Time Multimodal Defect Inspection & Attribution</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Fusing high-frequency machine telemetry with optical surface inspection scans for confidence-calibrated quality control.</div>', unsafe_allow_html=True)

    col_l, col_r = st.columns([1, 2])

    with col_l:
        st.subheader("1. Component Telemetry & Scan")
        
        preset_mode = st.selectbox(
            "Select Inspection Preset or Custom:",
            [
                "Preset: Normal Defect-Free Component",
                "Preset: Surface Crack (High Vibration)",
                "Preset: Micro Void / Pores (Overheating)",
                "Preset: Tool Scuffing (Severe Tool Wear)",
                "Custom Manual Inputs"
            ]
        )

        # Set default values based on preset
        if preset_mode == "Preset: Normal Defect-Free Component":
            default_temp, default_press, default_speed = 818.0, 121.0, 3150.0
            default_feed, default_vib, default_wear = 43.5, 1.70, 45.0
            default_coolant, default_hum = 15.8, 48.0
            preset_class = 0
        elif preset_mode == "Preset: Surface Crack (High Vibration)":
            default_temp, default_press, default_speed = 825.0, 124.0, 3180.0
            default_feed, default_vib, default_wear = 51.0, 2.75, 140.0
            default_coolant, default_hum = 14.5, 50.0
            preset_class = 1
        elif preset_mode == "Preset: Micro Void / Pores (Overheating)":
            default_temp, default_press, default_speed = 865.0, 142.0, 3120.0
            default_feed, default_vib, default_wear = 44.0, 1.85, 80.0
            default_coolant, default_hum = 10.2, 52.0
            preset_class = 2
        elif preset_mode == "Preset: Tool Scuffing (Severe Tool Wear)":
            default_temp, default_press, default_speed = 830.0, 126.0, 3380.0
            default_feed, default_vib, default_wear = 46.0, 2.30, 210.0
            default_coolant, default_hum = 14.0, 47.0
            preset_class = 3
        else:
            default_temp, default_press, default_speed = 820.0, 122.0, 3150.0
            default_feed, default_vib, default_wear = 44.0, 1.75, 85.0
            default_coolant, default_hum = 15.5, 49.0
            preset_class = 0

        with st.expander("Machine Sensor Telemetry Inputs", expanded=True):
            furnace_temp = st.number_input("Furnace Temp (°C)", 700.0, 950.0, default_temp, 1.0)
            injection_pressure = st.number_input("Injection Pressure (MPa)", 80.0, 180.0, default_press, 1.0)
            spindle_speed = st.number_input("Spindle Speed (RPM)", 2500.0, 4000.0, default_speed, 10.0)
            feed_rate = st.number_input("Feed Rate (mm/s)", 30.0, 65.0, default_feed, 0.5)
            vibration = st.number_input("Vibration Amplitude (g)", 0.5, 4.5, default_vib, 0.05)
            tool_wear = st.number_input("Tool Wear (min)", 0.0, 300.0, default_wear, 5.0)
            coolant_flow = st.number_input("Coolant Flow (L/min)", 5.0, 25.0, default_coolant, 0.5)
            ambient_humidity = st.number_input("Ambient Humidity (%)", 30.0, 75.0, default_hum, 1.0)

        # Get representative image for preset
        sample_row = test_df[test_df["defect_label"] == preset_class].iloc[0]
        img_path = os.path.join("data/raw/images", sample_row["image_filename"])
        if os.path.exists(img_path):
            curr_pil_img = Image.open(img_path).convert('L')
        else:
            curr_pil_img = Image.fromarray(np.full((64, 64), 175, dtype=np.uint8), mode='L')
            
        st.image(curr_pil_img, caption=f"Optical Scan: {sample_row['defect_name']}", width=180)

        run_btn = st.button("🚀 Run Multimodal Quality Assessment", type="primary", use_container_width=True)

    with col_r:
        st.subheader("2. Quality Intelligence Diagnostics")
        
        # Prepare inputs
        sensor_record = {
            "furnace_temp_c": furnace_temp,
            "injection_pressure_mpa": injection_pressure,
            "spindle_speed_rpm": spindle_speed,
            "feed_rate_mm_s": feed_rate,
            "vibration_amplitude_g": vibration,
            "tool_wear_min": tool_wear,
            "coolant_flow_l_min": coolant_flow,
            "ambient_humidity_pct": ambient_humidity
        }
        
        x_tab_scaled = prep.transform_single_dict(sensor_record)
        t_tab = torch.tensor(x_tab_scaled, dtype=torch.float32).unsqueeze(0)
        t_img = transform_image(curr_pil_img, is_train=False).unsqueeze(0)
        
        # Run inference
        pred = model.predict_with_confidence(t_tab, t_img)
        gradcam = model.generate_gradcam(t_tab, t_img, target_class=pred["predicted_label"])
        sensor_attrs = model.explain_tabular_sensors(t_tab, t_img, prep.feature_names)
        
        # Metrics cards
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            if pred["predicted_label"] == 0:
                st.markdown('<div class="metric-card"><span class="badge-normal">PASS</span><h4>Normal</h4></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="metric-card"><span class="badge-defect">REJECT</span><h4>{pred["predicted_name"]}</h4></div>', unsafe_allow_html=True)
        with m2:
            st.metric("Confidence", f"{pred['confidence']*100:.1f}%")
        with m3:
            st.metric("Shannon Entropy", f"{pred['entropy']:.3f}")
        with m4:
            unc_flag = "⚠️ Human Audit Required" if pred["is_uncertain"] else "✅ High Certainty"
            st.metric("Uncertainty Status", unc_flag)

        # Modality Gate Weights
        st.markdown("##### Adaptive Cross-Modal Gating Weights")
        gate_tab = pred["modality_gate_weight_tabular"]
        gate_vis = pred["modality_gate_weight_vision"]
        fig_gate = go.Figure(go.Bar(
            x=[gate_tab, gate_vis],
            y=["Sensor Telemetry", "Optical Surface Scan"],
            orientation='h',
            marker=dict(color=['#3B82F6', '#10B981'])
        ))
        fig_gate.update_layout(height=160, margin=dict(l=0, r=0, t=10, b=10), xaxis=dict(range=[0, 1]))
        st.plotly_chart(fig_gate, use_container_width=True)

        # Visual Heatmap Overlay & Sensor Attribution
        v1, v2 = st.columns(2)
        with v1:
            st.markdown("##### Grad-CAM Optical Defect Saliency")
            # Create color overlay
            img_arr = np.array(curr_pil_img.resize((128, 128)))
            cam_resized = np.array(Image.fromarray((gradcam * 255).astype(np.uint8)).resize((128, 128)))
            
            fig_cam = px.imshow(img_arr, color_continuous_scale="gray")
            fig_cam.add_trace(go.Heatmap(z=cam_resized, colorscale="Jet", opacity=0.45, showscale=False))
            fig_cam.update_layout(height=240, margin=dict(l=0, r=0, t=10, b=10), xaxis_visible=False, yaxis_visible=False)
            st.plotly_chart(fig_cam, use_container_width=True)

        with v2:
            st.markdown("##### Sensor Root-Cause Attribution (Top 5)")
            top5 = sensor_attrs[:5]
            df_attr = pd.DataFrame(top5)
            fig_attr = px.bar(
                df_attr, x="importance", y="feature", orientation='h',
                color="importance", color_continuous_scale="Reds"
            )
            fig_attr.update_layout(height=240, margin=dict(l=0, r=0, t=10, b=10), yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_attr, use_container_width=True)

# =========================================================================
# TAB 2: Statistical Process Control (SPC)
# =========================================================================
elif nav_choice == "📈 Statistical Process Control (SPC)":
    st.markdown('<div class="main-title">Statistical Process Control (SPC) Observatory</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Continuous Shewhart X-bar, EWMA, and Western Electric out-of-control rule monitoring for machine telemetry.</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 3])
    with c1:
        st.subheader("Chart Configuration")
        monitored_var = st.selectbox(
            "Select Process Variable:",
            [
                "furnace_temp_c",
                "injection_pressure_mpa",
                "spindle_speed_rpm",
                "feed_rate_mm_s",
                "vibration_amplitude_g",
                "coolant_flow_l_min"
            ]
        )
        data_source = st.radio("Telemetry Stream:", ["Historical Batches (Train)", "Continuous Production Stream (Batches 1-30)"])
        df_target = train_df if data_source == "Historical Batches (Train)" else stream_df

    with c2:
        st.subheader(f"Shewhart & EWMA Control Chart: {monitored_var}")
        vals = df_target[monitored_var].values
        stats = spc.baseline_stats[monitored_var]
        ewma_vals = spc.compute_ewma_series(vals, stats["mean"])

        fig_spc = go.Figure()

        # Observation points
        fig_spc.add_trace(go.Scatter(
            y=vals, mode='lines+markers', name='Observed Value',
            marker=dict(size=4, color='#1E40AF'), line=dict(width=1)
        ))

        # EWMA line
        fig_spc.add_trace(go.Scatter(
            y=ewma_vals, mode='lines', name='EWMA (λ=0.2)',
            line=dict(color='#8B5CF6', width=2)
        ))

        # Center line
        fig_spc.add_hline(y=stats["mean"], line_dash="solid", line_color="#10B981", annotation_text="CL (Mean)")
        # Upper Control Limit
        fig_spc.add_hline(y=stats["ucl"], line_dash="dash", line_color="#EF4444", annotation_text="UCL (+3σ)")
        # Lower Control Limit
        fig_spc.add_hline(y=stats["lcl"], line_dash="dash", line_color="#EF4444", annotation_text="LCL (-3σ)")

        # Highlight out of control violations
        violations_idx = np.where((vals > stats["ucl"]) | (vals < stats["lcl"]))[0]
        if len(violations_idx) > 0:
            fig_spc.add_trace(go.Scatter(
                x=violations_idx, y=vals[violations_idx], mode='markers',
                marker=dict(size=9, color='#DC2626', symbol='cross'), name='Rule 1 Violation (>3σ)'
            ))

        fig_spc.update_layout(height=420, margin=dict(l=0, r=0, t=20, b=20), xaxis_title="Production Sequence (Part #)")
        st.plotly_chart(fig_spc, use_container_width=True)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Center Line (CL)", f"{stats['mean']:.2f}")
        k2.metric("Upper Limit (UCL)", f"{stats['ucl']:.2f}")
        k3.metric("Lower Limit (LCL)", f"{stats['lcl']:.2f}")
        k4.metric("Rule Violations", len(violations_idx))

# =========================================================================
# TAB 3: Modality Ablation Benchmark
# =========================================================================
elif nav_choice == "📊 Modality Ablation Benchmark":
    st.markdown('<div class="main-title">Modality Ablation Study & Innovation Benchmark</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Mandatory Industry Benchmark comparing Single-Modality Baselines against Proposed Multimodal Fusion on Test Set (N=225).</div>', unsafe_allow_html=True)

    df_bench = pd.DataFrame(benchmark_data)
    
    st.dataframe(
        df_bench.style.highlight_max(subset=["accuracy", "defect_recall", "f1_macro", "pr_auc"], color="#D1FAE5")
                 .highlight_min(subset=["false_reject_rate", "latency_ms"], color="#D1FAE5"),
        use_container_width=True
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### PR-AUC & Defect Recall Comparison")
        fig_bar = px.bar(
            df_bench, x="model_name", y=["defect_recall", "pr_auc"],
            barmode="group",
            color_discrete_sequence=['#3B82F6', '#10B981']
        )
        fig_bar.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=10), yaxis=dict(range=[0.7, 1.02]))
        st.plotly_chart(fig_bar, use_container_width=True)

    with c2:
        st.markdown("##### False-Reject Rate (Scrapping Good Parts)")
        fig_frr = px.bar(
            df_bench, x="model_name", y="false_reject_rate",
            color="false_reject_rate", color_continuous_scale="Reds"
        )
        fig_frr.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=10))
        st.plotly_chart(fig_frr, use_container_width=True)

    st.info("""
    **Core Innovation Finding:**
    - The **Tabular Baseline** misses subtle visual fractures and scuffing, yielding a defect recall of 85.0% and a 1.62% false reject rate.
    - The **Vision Baseline** accurately identifies surface scratches, but lacks visibility into subsurface thermal pores and process drift dynamics.
    - Our **Gated Multimodal Fusion Architecture** successfully achieves **100% Defect Recall** with **0.0% False Reject Rate**, proving the value of fusing physical telemetry with high-resolution visual inspection.
    """)

# =========================================================================
# TAB 4: Process Drift & Automated Rollback
# =========================================================================
elif nav_choice == "🌊 Process Drift & Automated Rollback":
    st.markdown('<div class="main-title">Process & Data Drift Analytics with Controlled Rollback</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Continuous two-sample Kolmogorov-Smirnov, Population Stability Index (PSI), and automated safety baseline rollback.</div>', unsafe_allow_html=True)

    sel_batch = st.slider("Select Incoming Production Batch to Evaluate (Batches 1 to 30):", 1, 30, 16)
    
    # Analyze drift for selected batch
    curr_batch_df = stream_df[stream_df["batch_num"] == sel_batch]
    batch_res = drift_eng.analyze_batch_drift(curr_batch_df, batch_id=f"STREAM-BATCH-{sel_batch:03d}")

    # Status Alert
    status = batch_res["overall_status"]
    if status == "IN_CONTROL":
        st.success(f"🟢 **STATUS: IN-CONTROL** | Batch {sel_batch} shows stable distributions. Policy: `{batch_res['recommended_action']}`")
    elif status == "INCIPIENT_DRIFT_WARNING":
        st.warning(f"🟡 **STATUS: INCIPIENT DRIFT WARNING** | Subtle distribution shift detected. Drifted variables: {batch_res['drifted_variables']}. Policy: `{batch_res['recommended_action']}`")
    else:
        st.error(f"🔴 **STATUS: CRITICAL DRIFT DETECTED** | Automated Model Rollback Executed! Active Model State: `{drift_eng.active_model_state}`")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Multivariate Drift Score", batch_res["multivariate_drift_score"])
    m2.metric("Max Variable PSI", batch_res["max_psi"])
    m3.metric("Drifted Variables Count", batch_res["drifted_variables_count"])
    m4.metric("Active Model Policy", drift_eng.active_model_state)

    # Detailed variable statistics
    st.markdown("##### Statistical Test Breakdown per Sensor Variable")
    var_metrics_list = []
    for var, m in batch_res["variable_metrics"].items():
        var_metrics_list.append({
            "Sensor Variable": var,
            "Baseline Mean": m["baseline_mean"],
            "Batch Mean": m["current_mean"],
            "KS-Statistic": m["ks_statistic"],
            "p-value": m["p_value"],
            "PSI": m["psi"],
            "Wasserstein Dist": m["norm_wasserstein"],
            "Drift Flag": "🔴 DRIFT" if m["drift_detected"] else "🟢 NORMAL"
        })
    st.dataframe(pd.DataFrame(var_metrics_list), use_container_width=True)

    # Drift score across all 30 batches timeline
    st.markdown("##### Multi-Batch Process Drift Evolution (Batches 1 to 30)")
    batch_scores = []
    for b in range(1, 31):
        b_df = stream_df[stream_df["batch_num"] == b]
        r = drift_eng.analyze_batch_drift(b_df, batch_id=f"B-{b}")
        batch_scores.append({
            "Batch #": b,
            "Drift Score": r["multivariate_drift_score"],
            "Max PSI": r["max_psi"],
            "Regime": "In-Control (1-10)" if b <= 10 else ("Incipient Drift (11-20)" if b <= 20 else "Severe Drift (21-30)")
        })
    df_trend = pd.DataFrame(batch_scores)
    
    fig_drift = px.line(df_trend, x="Batch #", y="Drift Score", color="Regime", markers=True)
    fig_drift.add_hline(y=0.45, line_dash="dash", line_color="orange", annotation_text="Warning Threshold")
    fig_drift.add_hline(y=0.85, line_dash="dash", line_color="red", annotation_text="Critical Rollback Threshold")
    fig_drift.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=10))
    st.plotly_chart(fig_drift, use_container_width=True)

# =========================================================================
# TAB 5: Architecture & System Specs
# =========================================================================
elif nav_choice == "🏛️ Architecture & System Specs":
    st.markdown('<div class="main-title">System Architecture & Engineering Dossier</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">KES\' Shroff College T.Y. B.Sc. Data Science - Capstone Project BDS-27</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("System Highlights")
        st.markdown("""
        - **Target Industry Maturity:** TRL 4 to 5 (Deployable Prototype)
        - **Model Ingestion:** Dual-modal intake (12 tabular telemetry channels + 64x64 optical defect scans)
        - **Inference Latency:** 2.28 ms per component
        - **Automated Rollback:** Two-sample KS-test & PSI monitoring with policy-driven conservative fallback
        - **Explainability:** Integrated Grad-CAM visual heatmaps & gradient-based sensor attributions
        """)
        
    with c2:
        st.subheader("Production Data Contract (Pydantic / OpenAPI)")
        st.code("""
class MultimodalInferenceRequest(BaseModel):
    sample_id: Optional[str]
    sensors: SensorTelemetry  # 8 continuous physical sensors
    image_base64: Optional[str] # 64x64 optical surface scan

class MultimodalInferenceResponse(BaseModel):
    predicted_label: int      # 0: Normal, 1: Crack, 2: Void, 3: Scuff
    predicted_name: str
    confidence: float         # Temperature calibrated
    entropy: float            # Shannon uncertainty metric
    is_uncertain: bool        # Human review trigger
    top_sensor_attributions: List[Dict[str, Any]]
    gradcam_base64: Optional[str]
        """, language="python")

    st.markdown("---")
    st.subheader("Docker Deployment Command")
    st.code("docker-compose up --build", language="bash")
