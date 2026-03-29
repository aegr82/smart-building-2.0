import os
import time
import json
from dotenv import load_dotenv

import httpx

# --- CONFIGURATION ---
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path)

API_KEY = os.environ.get("GEMINI_API_KEY")

# Simulated BMS Environment State
CURRENT_STATE = {
    "timestamp": "2026-03-28T18:00:00",
    "air_temperature_celsius": 14.5,
    "building_occupancy": "LOW (Employees leaving)",
    "chiller_status": "ON",
    "chilled_water_flow": "1200 gal/hr",
    "energy_price_tier": "PEAK"
}

# The prompt asks the model to act as a system controller returning strictly JSON
SYSTEM_PROMPT = f"""
Actúa como un Controlador Autónomo de un Smart Building (Agentic AI).
Tu único objetivo es reducir el consumo de energía en forma segura.

Reglas:
1. Analiza el estado actual de los sensores del edificio.
2. Si la temperatura es <= 15°C y la ocupación es baja, no necesitamos el Chiller (Agua Helada).
3. Tu respuesta DEBE ser ÚNICAMENTE un objeto JSON válido con la siguiente estructura:
{{
  "action": "TURN_OFF" o "MAINTAIN" o "TURN_ON",
  "target_equipment": "Chiller",
  "reason": "Explicación breve de la decisión",
  "estimated_savings_kwh": número estimado
}}

ESTADO ACTUAL:
{json.dumps(CURRENT_STATE, indent=2)}
"""

def agentic_inference():
    print("=== AGENTIC AI PIPELINE: AUTONOMOUS CONTROL PHASE ===")
    
    if not API_KEY or API_KEY == "AIza...":
        print("Error: Configura tu llave GEMINI_API_KEY válida en el .env")
        return

    print("[1/3] Reading building sensors (simulated)...")
    for key, val in CURRENT_STATE.items():
        print(f"   -> {key}: {val}")
        
    print("\n[2/3] Querying Agentic LLM for JSON action...")
    start_time = time.time()
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": SYSTEM_PROMPT}]}],
        "generationConfig": {
            "temperature": 0.0, # Agents should be deterministic
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
    
    print(f"[3/3] Agent Action received in {latency:.2f}s")
    print(f"--- [STATS] ---")
    print(f"Latency={latency:.2f}s | Prompt Length={len(SYSTEM_PROMPT)} chars")
    print(f"---------------")
    
    # 3. Simulate Execution
    print("\n[EXECUTING ACTION TO NODE-RED / BMS]")
    print(json.dumps(action_payload, indent=2))
    
    if action_payload.get("action") == "TURN_OFF":
        print(f"\n✅ SUCCESS: Command sent. Saving estimated {action_payload.get('estimated_savings_kwh')} kWh.")
        
    return {
        "payload": action_payload,
        "latency": latency
    }

if __name__ == "__main__":
    agentic_inference()
