"""
Dataset Generator for Manufacturing Quality Intelligence
Produces paired tabular sensor telemetry and surface inspection images with physics-based defect mechanisms.
"""

import os
import random
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFilter

SEED = 42
np.random.seed(SEED)
random.seed(SEED)

DEFECT_CLASSES = {
    0: "Normal",
    1: "Surface Crack",
    2: "Micro Void",
    3: "Tool Scuffing"
}

def generate_surface_image(sample_id: str, defect_type: int, output_dir: str, size: int = 64) -> str:
    """
    Generates a realistic synthetic metallurgical inspection scan corresponding to defect physics.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Base metallic surface: grey background with anisotropic grain texture
    base_val = np.random.normal(loc=175, scale=12, size=(size, size)).clip(100, 240).astype(np.uint8)
    img = Image.fromarray(base_val, mode='L')
    draw = ImageDraw.Draw(img)
    
    if defect_type == 1:
        # Surface Crack: Jagged dark linear fracture
        start_x = np.random.randint(10, size // 3)
        start_y = np.random.randint(10, size - 10)
        curr_x, curr_y = start_x, start_y
        points = [(curr_x, curr_y)]
        
        while curr_x < size - 10:
            step_x = np.random.randint(3, 8)
            step_y = np.random.randint(-4, 5)
            curr_x += step_x
            curr_y = np.clip(curr_y + step_y, 5, size - 5)
            points.append((curr_x, curr_y))
            
        for i in range(len(points) - 1):
            draw.line([points[i], points[i+1]], fill=np.random.randint(30, 70), width=np.random.choice([1, 2]))
            
    elif defect_type == 2:
        # Micro Void: Circular/elliptical dark pitting cavities
        num_pores = np.random.randint(3, 7)
        for _ in range(num_pores):
            cx = np.random.randint(12, size - 12)
            cy = np.random.randint(12, size - 12)
            r = np.random.randint(2, 6)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=np.random.randint(25, 65))
            
    elif defect_type == 3:
        # Tool Scuffing: Parallel striated micro-scratches from tool chattering
        num_scratches = np.random.randint(4, 9)
        base_angle = np.random.uniform(-0.3, 0.3)
        offset_y = np.random.randint(10, size - 30)
        for s in range(num_scratches):
            y_pos = offset_y + s * np.random.randint(2, 5)
            if y_pos >= size - 5:
                break
            x0 = np.random.randint(5, 15)
            x1 = np.random.randint(size - 15, size - 5)
            y0 = y_pos
            y1 = int(y_pos + (x1 - x0) * base_angle)
            y1 = np.clip(y1, 2, size - 2)
            draw.line([(x0, y0), (x1, y1)], fill=np.random.randint(40, 85), width=1)
            
    # Apply slight smoothing for optical diffusion
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    # Save as PNG
    file_name = f"{sample_id}.png"
    file_path = os.path.join(output_dir, file_name)
    img.save(file_path)
    return file_name

def generate_manufacturing_dataset(
    n_samples: int = 1500,
    output_csv_path: str = "data/raw/manufacturing_process_data.csv",
    images_dir: str = "data/raw/images"
):
    """
    Generates synthetic industrial manufacturing dataset with physical interactions.
    """
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    
    records = []
    samples_per_batch = 50
    num_batches = (n_samples + samples_per_batch - 1) // samples_per_batch
    
    sample_counter = 0
    for b in range(1, num_batches + 1):
        batch_id = f"BATCH-{b:03d}"
        
        # Simulating progressive tool wear accumulation within batches
        batch_base_tool_wear = (b % 10) * 22.0
        
        for s in range(samples_per_batch):
            if sample_counter >= n_samples:
                break
            sample_counter += 1
            sample_id = f"MFG-{sample_counter:04d}"
            
            # Nominal process parameters
            furnace_temp = np.random.normal(820.0, 18.0)
            injection_pressure = np.random.normal(122.0, 9.0)
            spindle_speed = np.random.normal(3150.0, 120.0)
            feed_rate = np.random.normal(44.0, 3.5)
            vibration = np.random.normal(1.75, 0.3)
            tool_wear = batch_base_tool_wear + (s / samples_per_batch) * 20.0 + np.random.normal(0, 2.0)
            tool_wear = max(5.0, tool_wear)
            coolant_flow = np.random.normal(15.5, 1.4)
            ambient_humidity = np.random.normal(49.0, 4.5)
            
            # Physics-based defect risk scores
            crack_score = (
                0.35 * max(0, vibration - 2.1) +
                0.25 * max(0, (feed_rate - 47.0) / 5.0) +
                0.30 * max(0, (tool_wear - 150.0) / 50.0) +
                np.random.uniform(0, 0.15)
            )
            
            void_score = (
                0.40 * max(0, (furnace_temp - 842.0) / 15.0) +
                0.35 * max(0, (injection_pressure - 134.0) / 10.0) +
                0.25 * max(0, (13.5 - coolant_flow) / 3.0) +
                np.random.uniform(0, 0.15)
            )
            
            scuff_score = (
                0.50 * max(0, (tool_wear - 170.0) / 35.0) +
                0.30 * max(0, (spindle_speed - 3320.0) / 150.0) +
                0.20 * max(0, vibration - 2.0) +
                np.random.uniform(0, 0.15)
            )
            
            # Decide defect classification
            scores = [0.25, crack_score, void_score, scuff_score]
            max_idx = np.argmax(scores)
            
            if max_idx == 0 or max(scores[1:]) < 0.38:
                defect_class = 0 # Normal
            else:
                defect_class = int(max_idx)
                
            # Synthesize defect inspection image
            img_rel_path = generate_surface_image(sample_id, defect_class, images_dir)
            
            records.append({
                "sample_id": sample_id,
                "batch_id": batch_id,
                "furnace_temp_c": round(float(furnace_temp), 2),
                "injection_pressure_mpa": round(float(injection_pressure), 2),
                "spindle_speed_rpm": round(float(spindle_speed), 1),
                "feed_rate_mm_s": round(float(feed_rate), 2),
                "vibration_amplitude_g": round(float(vibration), 3),
                "tool_wear_min": round(float(tool_wear), 2),
                "coolant_flow_l_min": round(float(coolant_flow), 2),
                "ambient_humidity_pct": round(float(ambient_humidity), 2),
                "image_filename": img_rel_path,
                "defect_label": defect_class,
                "defect_name": DEFECT_CLASSES[defect_class]
            })
            
    df = pd.DataFrame(records)
    df.to_csv(output_csv_path, index=False)
    print(f"Generated {len(df)} manufacturing records with images at {output_csv_path}")
    print("Defect distribution:")
    print(df["defect_name"].value_counts(normalize=True).round(3))
    return df

def generate_drift_stream(
    n_batches: int = 30,
    samples_per_batch: int = 25,
    output_csv_path: str = "data/raw/drift_telemetry_stream.csv"
):
    """
    Generates time-series streaming batches showing:
    - Batches 1 to 10: In-Control baseline process
    - Batches 11 to 20: Incipient process drift (coolant degradation & thermal drift)
    - Batches 21 to 30: Severe Out-of-control distribution shift causing high defects
    """
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    records = []
    
    for b in range(1, n_batches + 1):
        batch_id = f"STREAM-BATCH-{b:03d}"
        
        # Drift factors based on regime
        if b <= 10:
            regime = "In-Control"
            temp_offset = 0.0
            coolant_offset = 0.0
            vib_offset = 0.0
        elif b <= 20:
            regime = "Incipient-Drift"
            # Gradual thermal runaway & coolant decay
            progress = (b - 10) / 10.0
            temp_offset = progress * 28.0
            coolant_offset = -progress * 4.5
            vib_offset = progress * 0.4
        else:
            regime = "Severe-Out-Of-Control"
            temp_offset = 35.0 + (b - 20) * 1.5
            coolant_offset = -6.0
            vib_offset = 0.85
            
        for s in range(samples_per_batch):
            sample_id = f"STREAM-{b:03d}-{s:02d}"
            furnace_temp = np.random.normal(820.0 + temp_offset, 16.0)
            injection_pressure = np.random.normal(122.0 + (temp_offset * 0.2), 9.0)
            spindle_speed = np.random.normal(3150.0, 110.0)
            feed_rate = np.random.normal(44.0, 3.2)
            vibration = np.random.normal(1.75 + vib_offset, 0.3)
            tool_wear = 60.0 + (b * 6.0) + np.random.normal(0, 3.0)
            coolant_flow = max(5.0, np.random.normal(15.5 + coolant_offset, 1.2))
            ambient_humidity = np.random.normal(49.0, 4.0)
            
            # Defect risk
            p_defect = 0.05
            if regime == "Incipient-Drift":
                p_defect = 0.22
            elif regime == "Severe-Out-Of-Control":
                p_defect = 0.65
                
            is_defect = 1 if np.random.random() < p_defect else 0
            
            records.append({
                "stream_sample_id": sample_id,
                "batch_id": batch_id,
                "batch_num": b,
                "process_regime": regime,
                "furnace_temp_c": round(float(furnace_temp), 2),
                "injection_pressure_mpa": round(float(injection_pressure), 2),
                "spindle_speed_rpm": round(float(spindle_speed), 1),
                "feed_rate_mm_s": round(float(feed_rate), 2),
                "vibration_amplitude_g": round(float(vibration), 3),
                "tool_wear_min": round(float(tool_wear), 2),
                "coolant_flow_l_min": round(float(coolant_flow), 2),
                "ambient_humidity_pct": round(float(ambient_humidity), 2),
                "is_defect": is_defect
            })
            
    df_stream = pd.DataFrame(records)
    df_stream.to_csv(output_csv_path, index=False)
    print(f"Generated drift stream with {len(df_stream)} observations across {n_batches} batches at {output_csv_path}")
    return df_stream

if __name__ == "__main__":
    generate_manufacturing_dataset()
    generate_drift_stream()
