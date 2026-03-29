import os
import torch
import torch.nn as nn
from train import EnergyPredictor, TARGET_BUILDING

MODEL_DIR = os.path.dirname(__file__)
MODEL_ELEC_PATH = os.path.join(MODEL_DIR, 'model_elec.pth')
MODEL_CW_PATH = os.path.join(MODEL_DIR, 'model_cw.pth')

def _predict_single(model_path: str, tensor_input: torch.Tensor, device: torch.device):
    if not os.path.exists(model_path):
        return None
    model = EnergyPredictor().to(device)
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()
    with torch.no_grad():
        return model(tensor_input).item()

def inference_step(air_temp: float, wind_speed: float, hour: int, actual_elec: float, actual_cw: float, dew_temp: float = 0.0):
    print("=== TRADITIONAL AI PIPELINE: DUAL INFERENCE PHASE ===")
    
    device = torch.device('cpu') # Inference is fine on CPU
    tensor_input = torch.tensor([[air_temp, dew_temp, wind_speed, hour]], dtype=torch.float32)
    
    print(f"🌡️ Weather Context: Temp={air_temp}°C, Dew={dew_temp}°C, Wind={wind_speed}m/s, Hour={hour}:00")
    
    # Predict Electricity
    pred_elec = _predict_single(MODEL_ELEC_PATH, tensor_input, device)
    # Predict Chilled Water
    pred_cw = _predict_single(MODEL_CW_PATH, tensor_input, device)
    
    results = {}
    
    # Analysis Logic Function
    def _analyze(name, pred, actual):
        if pred is None:
            return {"error": "Model not trained"}
        diff_percent = ((actual - pred) / pred) * 100 if pred > 0 else 0
        if diff_percent > 30:
            status = "🚨 ANOMALY: Too High!"
        elif diff_percent < -30:
            status = "✅ OPTIMAL: Saving Energy!"
        else:
            status = "🟢 NORMAL: Baseline."
        
        print(f"[{name}] Predicted: {pred:.1f} | Actual: {actual:.1f} | {status}")
        return {
            "predicted": pred,
            "actual": actual,
            "diff_percent": diff_percent,
            "status": status
        }

    results["electricity"] = _analyze("Electricity (kWh)", pred_elec, actual_elec)
    results["chilledwater"] = _analyze("Chilled Water", pred_cw, actual_cw)

    return results

if __name__ == "__main__":
    inference_step(12.5, 4.2, 14, 130.0, 360000.0, dew_temp=5.0)

