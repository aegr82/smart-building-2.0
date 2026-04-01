import os
import time
import json
import httpx
import sys
import pandas as pd
from dotenv import load_dotenv

# --- CONFIGURATION ---
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path)
API_KEY = os.environ.get("GEMINI_API_KEY")

# --- TOOL REGISTRY ---
import importlib.util
trad_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '01_traditional_ai', 'inference.py'))

traditional_inference = None
if os.path.exists(trad_path):
    try:
        spec = importlib.util.spec_from_file_location("trad_tool", trad_path)
        trad_mod = importlib.util.module_from_spec(spec)
        t_dir = os.path.dirname(trad_path)
        if t_dir not in sys.path:
            sys.path.insert(0, t_dir)
        spec.loader.exec_module(trad_mod)
        traditional_inference = trad_mod.inference_step
    except Exception as e:
        print(f"Error loading Traditional AI Tool: {e}")

# --- BUILDING PROFILE (loaded once from metadata) ---
def _load_building_profile(building_id: str = 'Eagle_office_Marisela') -> dict:
    """Loads static building metadata (sqm, type, etc.) for context enrichment."""
    try:
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data'))
        if os.path.exists("/app/data"):
            data_dir = "/app/data"
        meta_path = os.path.join(data_dir, "metadata.csv")
        if not os.path.exists(meta_path):
            return {}
        df = pd.read_csv(meta_path)
        row = df[df['building_id'] == building_id]
        if row.empty:
            return {}
        r = row.iloc[0]
        profile = {}
        for col in ['primaryspaceusage', 'sqm', 'sqft', 'numberoffloors', 'occupants', 'heatingtype', 'yearbuilt']:
            val = r.get(col)
            if val is not None and pd.notna(val):
                profile[col] = val
        return profile
    except Exception:
        return {}

BUILDING_PROFILE = _load_building_profile()

def agentic_inference(air_temp=14.5, wind=12.0, hour=18, actual_elec=130.0, actual_cw=360000.0, 
                      occupancy="LOW", chiller_status="ON", dew_temp=0.0):
    print("=== AGENTIC AI PIPELINE: AUTONOMOUS CONTROL PHASE ===")
    
    if not API_KEY or API_KEY == "AIza...":
        print("Error: Configura tu llave GEMINI_API_KEY válida en el .env")
        return

    # 1. READ SENSORS
    current_state = {
        "timestamp": f"2026-03-28T{hour:02d}:00:00",
        "air_temperature_celsius": air_temp,
        "dew_temperature_celsius": dew_temp,
        "wind_speed_mps": wind,
        "building_occupancy": occupancy,
        "chiller_status": chiller_status,
        "actual_electricity_kwh": actual_elec,
        "actual_chilledwater_kwh": actual_cw
    }
    
    # 2. INVOKE TRADITIONAL AI (TOOL CALL)
    print("\n[1/4] Invoking TRADITIONAL AI (System 1) for predictive tooling...")
    ai_predictions = {}
    if traditional_inference:
        ai_predictions = traditional_inference(air_temp, wind, hour, actual_elec, actual_cw, dew_temp=dew_temp)
        print("-> Tool call successful. Predictions retrieved.")
    else:
        print("-> Warning: Traditional AI tool unavailable.")

    # 3. CONSTRUCT AGENTIC PROMPT
    print("\n[2/4] Querying Agentic LLM (System 2) for JSON action...")
    start_time = time.time()

    # Build a clean data summary for the LLM, free of pre-baked labels
    tool_summary = {}
    for key in ["electricity", "chilledwater"]:
        entry = ai_predictions.get(key, {})
        if "error" in entry:
            tool_summary[key] = entry
        elif entry:
            predicted = entry.get("predicted", 0)
            actual = entry.get("actual", 0)
            diff = entry.get("diff_percent", 0)
            direction = "OVER baseline" if diff > 0 else "UNDER baseline"
            tool_summary[key] = {
                "predicted_kwh": round(predicted, 2),
                "actual_kwh": round(actual, 2),
                "deviation_percent": round(diff, 2),
                "direction": direction
            }

    # Build building context string
    bldg_context = ""
    if BUILDING_PROFILE:
        bldg_context = f"""
C) BUILDING PROFILE (static metadata):
{json.dumps(BUILDING_PROFILE, indent=2)}
"""

    system_prompt = f"""Eres el controlador autónomo de un edificio inteligente comercial.
Objetivo: minimizar el costo energético manteniendo el confort de los ocupantes.

DATOS:

A) SENSORES EN TIEMPO REAL:
{json.dumps(current_state, indent=2)}

B) PREDICCIONES DEL MODELO (PyTorch — variables climáticas vs. consumo):
{json.dumps(tool_summary, indent=2)}
{bldg_context}
La herramienta predictiva compara el consumo ESPERADO (predicted) vs. el REAL (actual).
- Desviación positiva = consumo MAYOR al esperado.
- Desviación negativa = consumo MENOR al esperado.

REGLAS DE ANÁLISIS:
- El Chiller impulsa el consumo de Agua Helada. La electricidad depende de iluminación, cargas y compresor del Chiller.
- Verifica CUÁL métrica desvía y en qué dirección antes de actuar.
- Si el Agua Helada real está POR DEBAJO de la predicción, el Chiller ya es eficiente — apagarlo sería redundante.
- Punto de rocío alto = alta humedad = mayor carga de enfriamiento.
- Temperaturas bajo cero permiten enfriamiento libre (free cooling).

RESPONDE SOLO con un JSON válido, completamente en español:
{{
  "action": "TURN_OFF" | "REDUCE" | "MAINTAIN" | "TURN_ON",
  "target_equipment": "Chiller" | "Iluminación" | "Cargas Eléctricas",
  "reasoning": "Máximo 3 oraciones breves en español explicando la anomalía y la acción",
  "estimated_savings_kwh": número
}}

IMPORTANTE: El campo "reasoning" debe tener MÁXIMO 3 oraciones cortas en español."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "maxOutputTokens": 512
        }
    }
    
    try:
        response = httpx.post(url, json=payload, timeout=15.0)
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
    agentic_inference(dew_temp=-15.0)

