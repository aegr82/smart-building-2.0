import os
import httpx
import pandas as pd
from functools import lru_cache
from fastapi import FastAPI, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
from dotenv import load_dotenv

load_dotenv()

SERVER_IP = "192.168.1.14"

app = FastAPI(title="Smart Building 2.0 - Intelligence Service")

# --- VARIABLES DE CONTROL ---
_REPLAY_INDEX = 0

_DEFAULT_NODE_RED = f"http://{SERVER_IP}:1880" if SERVER_IP != "127.0.0.1" else "http://localhost:1880"
NODE_RED_URL = os.getenv("NODE_RED_URL", _DEFAULT_NODE_RED)

# Determinar la ruta del CSV: en Docker /app/data, local ../data
if os.path.exists("/app/data/electricity.csv"):
    CSV_PATH = "/app/data/electricity.csv"
else:
    CSV_PATH = os.path.join(os.path.dirname(__file__), "../data/electricity.csv")

@lru_cache(maxsize=1)
def get_dataset():
    """Carga el dataset de forma eficiente."""
    if not os.path.exists(CSV_PATH):
        return None
    try:
        df = pd.read_csv(CSV_PATH, engine='python')
        cols = [c for c in df.columns if c != 'timestamp']
        df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
        return df
    except Exception as e:
        print(f"Error loading CSV: {e}")
        try:
            df = pd.read_csv(CSV_PATH, low_memory=False)
            cols = [c for c in df.columns if c != 'timestamp']
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
            return df
        except Exception:
            return None

def get_building_list():
    df = get_dataset()
    if df is None: return []
    return [col for col in df.columns if col != "timestamp"]

def get_consumption_peak(building_id: str):
    df = get_dataset()
    if df is None or building_id not in df.columns:
        return {"error": "Building not found or no data"}
    peak = df[building_id].max()
    return {"building_id": building_id, "peak_consumption": float(peak)}


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
    
    # Tomamos 3 edificios específicos que sí tienen datos registrados desde el inicio
    cols = ['Robin_public_Carolina', 'Robin_lodging_Dorthy', 'Robin_education_Zenia']
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