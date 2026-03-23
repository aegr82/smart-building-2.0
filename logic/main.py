import os
import sys
from pathlib import Path
import httpx
import pandas as pd
from fastapi import FastAPI, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
from dotenv import load_dotenv

# Asegura que la ruta del paquete core/config se encuentre en el path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Importamos tu lógica de datos
from core.tools import get_dataset, get_building_list, get_consumption_peak
from config.config import SERVER_IP

load_dotenv()

app = FastAPI(title="Smart Building 2.0 - Intelligence Service")

# --- VARIABLES DE CONTROL ---
_REPLAY_INDEX = 0
# Usamos la IP directa para evitar fallos de DNS de Docker hacia afuera
NODE_RED_URL = f"http://{SERVER_IP}:1880"

# --- PROMETHEUS SETUP ---
registry = CollectorRegistry()
consumption_gauge = Gauge(
    "building_electricity_kwh",
    "Consumo eléctrico actual del dataset",
    ["building_id"],
    registry=registry
)

# --- RUTAS ---

@app.get("/")
def read_root():
    return {"status": "Online", "ip_servidor": SERVER_IP}

@app.get("/buildings")
def list_buildings():
    return get_building_list()

@app.get("/analyze/peak/{building_id}")
def analyze_peak(building_id: str):
    return get_consumption_peak(building_id)

@app.get("/metrics")
def metrics():
    """Avanza el simulador con cada lectura de Prometheus."""
    global _REPLAY_INDEX
    df = get_dataset()
    
    if df is None:
        return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    row = df.iloc[_REPLAY_INDEX]
    
    # Tomamos los primeros 3 edificios para el dashboard de Grafana
    cols = [c for c in df.columns if c != "timestamp"][:3]
    for col in cols:
        try:
            value = float(row[col]) if pd.notna(row[col]) else 0.0
            consumption_gauge.labels(building_id=col).set(value)
        except (ValueError, TypeError):
            consumption_gauge.labels(building_id=col).set(0.0)

    _REPLAY_INDEX = (_REPLAY_INDEX + 1) % len(df)
    
    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

@app.post("/replay/step")
async def replay_step(count: int = 1):
    """Envía datos a Node-RED usando la IP."""
    global _REPLAY_INDEX
    df = get_dataset()
    if df is None: return {"error": "No data"}

    async with httpx.AsyncClient() as client:
        for _ in range(count):
            row = df.iloc[_REPLAY_INDEX].to_dict()
            try:
                # Node-RED recibirá el JSON en su IP local
                await client.post(f"{NODE_RED_URL}/data", json=row)
            except Exception as e:
                print(f"Error enviando a Node-RED: {e}")
            
            _REPLAY_INDEX = (_REPLAY_INDEX + 1) % len(df)

    return {"status": "sent", "index": _REPLAY_INDEX}

@app.post("/replay/reset")
def reset_simulation():
    global _REPLAY_INDEX
    _REPLAY_INDEX = 0
    return {"status": "reset"}