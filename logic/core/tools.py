# logic/core/tools.py
import pandas as pd
import os
from functools import lru_cache

CSV_PATH = os.path.join(os.path.dirname(__file__), "../../data/electricity.csv")

@lru_cache(maxsize=1)
def get_dataset():
    """Carga el dataset de forma eficiente."""
    if not os.path.exists(CSV_PATH):
        return None
    # Tip pro: Usamos tipos de datos más ligeros para ahorrar RAM
    return pd.read_csv(CSV_PATH)

def get_current_reading(index: int):
    """Obtiene una fila específica para el simulador/agente."""
    df = get_dataset()
    if df is not None and index < len(df):
        return df.iloc[index].to_dict()
    return None

def detect_anomaly(data: dict, threshold=1.5):
    """
    Primera lógica de 'Inteligencia': 
    Compara el valor actual con el promedio para detectar picos.
    """
    # Aquí irá la lógica agéntica pronto
    pass

def get_building_list():
    """Devuelve la lista de nombres de edificios disponibles."""
    df = get_dataset()
    if df is None:
        return []
    # Excluir timestamp y devolver las columnas de edificios
    return [col for col in df.columns if col != "timestamp"]

def get_consumption_peak(building_id: str):
    """Calcula el pico de consumo para un edificio específico."""
    df = get_dataset()
    if df is None or building_id not in df.columns:
        return {"error": "Building not found or no data"}
    
    # Calcular el máximo consumo para el edificio
    peak = df[building_id].max()
    return {"building_id": building_id, "peak_consumption": float(peak)}