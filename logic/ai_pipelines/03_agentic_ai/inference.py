import os
import time
import json
import httpx
import sys
from dotenv import load_dotenv

# --- CONFIGURATION ---
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path)
API_KEY = os.environ.get("GEMINI_API_KEY")

# --- TOOL REGISTRY ---
# Usamos un cargador explícito por ruta absoluta para evitar colisiones entre archivos "inference.py"
import importlib.util
trad_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '01_traditional_ai', 'inference.py'))

traditional_inference = None
if os.path.exists(trad_path):
    try:
        spec = importlib.util.spec_from_file_location("trad_tool", trad_path)
        trad_mod = importlib.util.module_from_spec(spec)
        # Aseguramos que el directorio del tool esté en path para sus propios imports (train.py)
        t_dir = os.path.dirname(trad_path)
        if t_dir not in sys.path:
            sys.path.insert(0, t_dir)
        spec.loader.exec_module(trad_mod)
        traditional_inference = trad_mod.inference_step
    except Exception as e:
        print(f"Error loading Traditional AI Tool: {e}")

def agentic_inference(air_temp=14.5, wind=12.0, hour=18, actual_elec=130.0, actual_cw=360000.0, occupancy="LOW", chiller_status="ON"):
    print("=== AGENTIC AI PIPELINE: AUTONOMOUS CONTROL PHASE ===")
    
    if not API_KEY or API_KEY == "AIza...":
        print("Error: Configura tu llave GEMINI_API_KEY válida en el .env")
        return

    # 1. READ SENSORS
    current_state = {
        "timestamp": f"2026-03-28T{hour:02d}:00:00",
        "air_temperature_celsius": air_temp,
        "wind_speed": wind,
        "building_occupancy": occupancy,
        "chiller_status": chiller_status,
        "actual_electricity_kwh": actual_elec,
        "actual_chilledwater_kwh": actual_cw
    }
    
    # 2. INVOKE TRADITIONAL AI (TOOL CALL)
    print("\n[1/4] Invoking TRADITIONAL AI (System 1) for predictive tooling...")
    ai_predictions = {}
    if traditional_inference:
        # Call the dual PyTorch models to get the baseline expected values
        ai_predictions = traditional_inference(air_temp, wind, hour, actual_elec, actual_cw)
        print("-> Tool call successful. Predictions retrieved.")
    else:
        print("-> Warning: Traditional AI tool unavailable.")

    # 3. CONSTRUCT AGENTIC PROMPT
    print("\n[2/4] Querying Agentic LLM (System 2) for JSON action...")
    start_time = time.time()
    
    system_prompt = f"""
Actúa como un Controlador Autónomo de un Smart Building (Agentic AI).
Tu único objetivo es reducir el consumo de energía térmica y eléctrica asegurando confort y usando inteligencia de datos.

Reglas:
1. Analiza el ESTADO ACTUAL de los sensores del edificio y las PREDICCIONES MATEMÁTICAS de tu herramienta (Traditional AI).
2. Si la herramienta indica que el consumo de Chilled Water o Electricidad tiene el status de 🚨 ANOMALÍA (Too High) en relación con el clima predicho, y la ocupación es baja o el clima exterior es amigable, reacciona apagando o manteniendo apagada la máquina responsable (Chiller).
3. Tu respuesta DEBE ser ÚNICAMENTE un objeto JSON válido con la siguiente estructura:
{{
  "action": "TURN_OFF" o "MAINTAIN" o "TURN_ON",
  "target_equipment": "Chiller" o "Lighting",
  "reason": "Explicación breve de la decisión basada estrictamente en las predicciones de tu tool matemática",
  "estimated_savings_kwh": número estimado
}}

ESTADO ACTUAL SENSOR:
{json.dumps(current_state, indent=2)}

PREDICCIONES TRADITIONAL AI (TU HERRAMIENTA):
{json.dumps(ai_predictions, indent=2)}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json"
        }
    }
    
    try:
        response = httpx.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        raw_json_string = data['candidates'][0]['content']['parts'][0]['text']
        action_payload = json.loads(raw_json_string)
    except Exception as e:
        print(f"Error acting: {e}")
        return None

    latency = time.time() - start_time
    
    print(f"[3/4] Agent Action received in {latency:.2f}s")
    
    # 4. Simulate Execution
    print("\n[4/4] EXECUTING ACTION TO NODE-RED / BMS")
    print(json.dumps(action_payload, indent=2))
    
    if action_payload.get("action") == "TURN_OFF":
        print(f"\n✅ SUCCESS: Command sent. Saving estimated {action_payload.get('estimated_savings_kwh')} kWh.")
    
    return {
        "payload": action_payload,
        "latency": latency,
        "tool_predictions": ai_predictions
    }

if __name__ == "__main__":
    agentic_inference()
