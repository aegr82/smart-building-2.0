import httpx
from fastapi import FastAPI
from app.config import SERVER_IP, NODE_RED_URL
from app.data_manager import get_building_list, get_consumption_peak, update_building_metrics, get_electricity_len, get_current_electricity_row
from app.metrics_exporter import export_as_response

app = FastAPI(title="Smart Building 2.0 - Intelligence Service")

# --- VARIABLES DE CONTROL ---
_REPLAY_INDEX = 0

@app.get("/")
def read_root():
    return {"status": "Online", "ip_servidor": SERVER_IP, "node_red": NODE_RED_URL}

@app.get("/buildings")
def list_buildings():
    return get_building_list()

@app.get("/analyze/peak/{building_id}")
def analyze_peak(building_id: str):
    return get_consumption_peak(building_id)

@app.get("/metrics")
def metrics():
    """Expone de forma continua el consumo y variables ambientales como métricas."""
    global _REPLAY_INDEX
    
    target_buildings = ['Bull_lodging_Melissa', 'Fox_office_Easter', 'Eagle_office_Marisela']
    success = update_building_metrics(_REPLAY_INDEX, target_buildings)
    
    if success:
        _REPLAY_INDEX = (_REPLAY_INDEX + 1) % get_electricity_len()
        
    return export_as_response()

@app.post("/replay/step")
async def replay_step(count: int = 1):
    """Envía datos a Node-RED usando la IP."""
    global _REPLAY_INDEX
    
    async with httpx.AsyncClient() as client:
        for _ in range(count):
            row = get_current_electricity_row(_REPLAY_INDEX)
            if not row:
                return {"error": "No data available"}
                
            try:
                await client.post(f"{NODE_RED_URL}/data", json=row)
            except Exception as e:
                print(f"Error enviando a Node-RED: {e}")
            
            _REPLAY_INDEX = (_REPLAY_INDEX + 1) % get_electricity_len()

    return {"status": "sent", "index": _REPLAY_INDEX}

@app.post("/replay/reset")
def reset_simulation():
    global _REPLAY_INDEX
    _REPLAY_INDEX = 0
    return {"status": "reset"}
