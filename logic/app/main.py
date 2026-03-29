import httpx
from fastapi import FastAPI
from app.config import SERVER_IP, NODE_RED_URL
from app.data_manager import get_building_list, get_consumption_peak
from app.metrics_exporter import export_as_response, consumption_gauge, chilledwater_gauge, temperature_gauge, wind_speed_gauge

app = FastAPI(title="Smart Building 2.0 - Intelligence & Metrics Bridge")

@app.get("/")
def read_root():
    return {
        "status": "Online", 
        "architecture": "IoT Aligned (Sensors -> Node-RED -> Metrics Bridge)",
        "ip_servidor": SERVER_IP, 
        "node_red": NODE_RED_URL
    }

# --- METRICS INITIALIZATION ---
# Pre-instantiate targets so Prometheus sees them even before the first Node-RED fetch
TARGET_BUILDINGS = ['Bull_lodging_Melissa', 'Fox_office_Easter', 'Eagle_office_Marisela']
TARGET_SITES = ['Bull', 'Fox', 'Panther'] # Panther also exists in metadata

for b_id in TARGET_BUILDINGS:
    consumption_gauge.labels(building_id=b_id).set(0.0)
    chilledwater_gauge.labels(building_id=b_id).set(0.0)

for s_id in TARGET_SITES:
    temperature_gauge.labels(site_id=s_id).set(0.0)
    wind_speed_gauge.labels(site_id=s_id).set(0.0)

@app.get("/buildings")
def list_buildings():
    return get_building_list()

@app.get("/analyze/peak/{building_id}")
def analyze_peak(building_id: str):
    return get_consumption_peak(building_id)

@app.get("/metrics")
def metrics():
    """
    [Metrics Bridge]: En vez de inventar los datos, lee la verdad absoluta del 
    Gateway (Node-RED) como en la vida real, lo convierte a Gauges de Prometheus, y los sirve a Grafana.
    """
    try:
        # PULL FROM NODE-RED's LATEST STATE (which is being pumped physically by replay.py)
        response = httpx.get("http://gateway:1880/latest", timeout=3.0)
        
        if response.status_code == 200:
            payload = response.json()
            
            # --- Update Building KPIs ---
            buildings = payload.get("buildings", {})
            for b_id, b_data in buildings.items():
                consumption_gauge.labels(building_id=b_id).set(b_data.get("electricity_kwh", 0.0))
                chilledwater_gauge.labels(building_id=b_id).set(b_data.get("chilledwater_kwh", 0.0))
            
            # --- Update Weather KPIs ---
            weather = payload.get("weather", {})
            for s_id, s_data in weather.items():
                if s_data.get("airTemperature") is not None:
                    temperature_gauge.labels(site_id=s_id).set(s_data["airTemperature"])
                if s_data.get("windSpeed") is not None:
                    wind_speed_gauge.labels(site_id=s_id).set(s_data["windSpeed"])

    except Exception as e:
        print(f"Metrics Scrape Bridge Error: {e}")

    # Export them to prometheus format seamlessly
    return export_as_response()

# Funciones de control obsoletas (El loop simulador ya se movió al hardware virtual replay.py)
@app.post("/replay/step")
async def replay_step(count: int = 1):
    return {"status": "deprecated", "message": "Replay is purely handled physically by scripts/replay.py"}

@app.post("/replay/reset")
def reset_simulation():
    return {"status": "deprecated"}
