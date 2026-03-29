import os
import torch
import torch.nn as nn
from train import EnergyPredictor, TARGET_BUILDING, MODEL_PATH

def inference_step(air_temp: float, wind_speed: float, hour: int, actual_consumption: float):
    print("=== TRADITIONAL AI PIPELINE: INFERENCE PHASE ===")
    
    # 1. Load Model
    if not os.path.exists(MODEL_PATH):
        print(f"Error: Model not found at {MODEL_PATH}. Run train.py first.")
        return
        
    device = torch.device('cpu') # Inference is fine on CPU
    model = EnergyPredictor().to(device)
    model.load_state_dict(torch.load(MODEL_PATH, map_location=device, weights_only=True))
    model.eval()
    
    # 2. Prepare Data
    tensor_input = torch.tensor([[air_temp, wind_speed, hour]], dtype=torch.float32)
    
    # 3. Predict
    print(f"[1/3] Feeding data to Neural Network: Temp={air_temp}°C, Wind={wind_speed}m/s, Hour={hour}:00")
    with torch.no_grad():
        predicted = model(tensor_input).item()
        
    print(f"[2/3] Model Prediction for {TARGET_BUILDING}: {predicted:.2f} kWh")
    print(f"[3/3] Actual Sensor  for {TARGET_BUILDING}: {actual_consumption:.2f} kWh")
    
    # 4. Anomaly Logic
    diff_percent = ((actual_consumption - predicted) / predicted) * 100 if predicted > 0 else 0
    if diff_percent > 30:
        print(f"-> 🚨 ANOMALY DETECTED: Consumption is {diff_percent:.1f}% higher than AI baseline!")
    elif diff_percent < -30:
        print(f"-> ✅ OPTIMAL: Consumption is {abs(diff_percent):.1f}% lower than AI baseline (Savings!).")
    else:
        print("-> 🟢 NORMAL: Consumption matches AI expected baseline.")

    return {
        "predicted": predicted,
        "actual": actual_consumption,
        "diff_percent": diff_percent
    }

if __name__ == "__main__":
    # Simulated current state (e.g., pulling right now from Grafana/Prometheus)
    current_temp = 12.5 # °C
    current_wind = 4.2 # m/s
    current_hour = 14 # 2 PM
    actual_kwh = 1150.0 # Pretend high anomaly
    
    inference_step(current_temp, current_wind, current_hour, actual_kwh)
