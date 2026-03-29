import threading
import time
from fastapi import FastAPI
from app.config import SERVER_IP, NODE_RED_URL
from app.data_manager import get_building_list, get_consumption_peak, update_building_metrics, get_electricity_len
from app.metrics_exporter import export_as_response, dew_temperature_gauge

app = FastAPI(title="Smart Building 2.0 - Stable Metrics Engine")

# --- SIMULATION MOTOR (Background Thread) ---
# This replaces the external replayer to guarantee stability.
CURRENT_INDEX = 0

def simulation_loop():
    global CURRENT_INDEX
    total_len = get_electricity_len()
    if total_len <= 1:
        print("Simulation error: Dataset empty or not found.")
        return

    # 50% split for Real-Time Simulation (Anti-Leakage)
    start_idx = int(total_len * 0.5)
    CURRENT_INDEX = start_idx
    
    target_buildings = ['Bull_lodging_Melissa', 'Fox_office_Easter', 'Eagle_office_Marisela']
    
    print(f"🚀 Stable Motor: Starting internal simulation at index {start_idx}")
    
    while True:
        try:
            update_building_metrics(CURRENT_INDEX, target_buildings)
            CURRENT_INDEX += 1
            if CURRENT_INDEX >= total_len:
                CURRENT_INDEX = start_idx
        except Exception as e:
            print(f"Simulation Motor Loop Error: {e}")
            
        time.sleep(1.0) # 1 second tick

# Start the motor on app startup
@app.on_event("startup")
async def startup_event():
    thread = threading.Thread(target=simulation_loop, daemon=True)
    thread.start()

@app.get("/")
def read_root():
    return {
        "status": "Online & Stable", 
        "architecture": "Self-Contained Simulation (Stable)",
        "current_index": CURRENT_INDEX
    }

@app.get("/buildings")
def list_buildings():
    return get_building_list()

@app.get("/analyze/peak/{building_id}")
def analyze_peak(building_id: str):
    return get_consumption_peak(building_id)

@app.get("/metrics")
def metrics():
    """
    [Stable Bridge]: Returns metrics directly from memory, updated by the background motor.
    Zero failure points.
    """
    return export_as_response()

# Legacy control functions (handled by motor)
@app.post("/replay/step")
async def replay_step(count: int = 1):
    return {"status": "internal_motor_active"}

@app.post("/replay/reset")
def reset_simulation():
    global CURRENT_INDEX
    total_len = get_electricity_len()
    CURRENT_INDEX = int(total_len * 0.5)
    return {"status": "reset_to_50_percent"}
