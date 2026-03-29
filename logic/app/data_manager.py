import os
import pandas as pd
from functools import lru_cache
from app.config import DATA_DIR
from app.metrics_exporter import consumption_gauge, chilledwater_gauge, temperature_gauge, wind_speed_gauge, dew_temperature_gauge

@lru_cache(maxsize=1)
def load_datasets():
    datasets = {}
    try:
        # 1. Electricidad
        path_e = os.path.join(DATA_DIR, "electricity.csv")
        df_e = pd.read_csv(path_e)
        df_e['timestamp'] = pd.to_datetime(df_e['timestamp'])
        datasets['electricity'] = df_e

        # 2. Chilled Water
        path_cw = os.path.join(DATA_DIR, "chilledwater.csv")
        if os.path.exists(path_cw):
            df_cw = pd.read_csv(path_cw)
            df_cw['timestamp'] = pd.to_datetime(df_cw['timestamp'])
            datasets['chilledwater'] = df_cw

        # 3. Metadata
        path_m = os.path.join(DATA_DIR, "metadata.csv")
        if os.path.exists(path_m):
            df_m = pd.read_csv(path_m)
            datasets['metadata'] = df_m.set_index('building_id')

        # 4. Weather (con timestamp parseado y ordenado para merge_asof / nearest)
        path_w = os.path.join(DATA_DIR, "weather.csv")
        if os.path.exists(path_w):
            df_w = pd.read_csv(path_w)
            df_w['timestamp'] = pd.to_datetime(df_w['timestamp'])
            df_w = df_w.sort_values('timestamp').reset_index(drop=True)
            datasets['weather'] = df_w

        return datasets
    except Exception as e:
        print(f"Error loading datasets: {e}")
        return None

def get_building_list():
    ds = load_datasets()
    if ds is None or 'electricity' not in ds: return []
    return [col for col in ds['electricity'].columns if col != "timestamp"]

def get_consumption_peak(building_id: str):
    ds = load_datasets()
    if ds is None or 'electricity' not in ds:
        return {"error": "Building not found or no data"}
    df = ds['electricity']
    if building_id not in df.columns:
        return {"error": "Building not found"}
    peak = df[building_id].max()
    return {"building_id": building_id, "peak_consumption": float(peak)}

def update_building_metrics(replay_index: int, target_buildings: list):
    """Actualiza las métricas combinando data del dataframe usando interpolación temporal."""
    ds = load_datasets()
    if ds is None or 'electricity' not in ds:
        return False

    df_e = ds['electricity']
    if replay_index >= len(df_e): return False
    
    row_e = df_e.iloc[replay_index]
    ts = row_e.get('timestamp')
    
    for build_id in target_buildings:
        # ELECTRICIDAD
        try:
            val_e = float(row_e[build_id]) if pd.notna(row_e[build_id]) else 0.0
            consumption_gauge.labels(building_id=build_id).set(val_e)
        except Exception:
            pass
            
        # CHILLED WATER
        if 'chilledwater' in ds and build_id in ds['chilledwater'].columns:
            df_cw = ds['chilledwater']
            row_cw = df_cw.iloc[replay_index % len(df_cw)] # safe iteration based on exact same sequential row structure
            try:
                val_cw = float(row_cw[build_id]) if pd.notna(row_cw[build_id]) else 0.0
                chilledwater_gauge.labels(building_id=build_id).set(val_cw)
            except Exception:
                pass
                
        # WEATHER & SITE METRICS (Tolerancia Interpolada de hasta 1.5 horas)
        if 'metadata' in ds and 'weather' in ds:
            try:
                if build_id in ds['metadata'].index:
                    site_id = ds['metadata'].loc[build_id, 'site_id']
                    if hasattr(site_id, 'iloc'): site_id = site_id.iloc[0]
                    
                    w_df = ds['weather']
                    site_w = w_df[w_df['site_id'] == site_id].copy()
                    
                    if not site_w.empty:
                        # Nearest interpolación de timestamp (tolerancia nativa de pandas merge_asof en vez de buscar índice numérico que podría fallar si faltan rows)
                        # Alternativa simple: usar idx
                        nearest_idx = site_w['timestamp'].searchsorted(ts)
                        
                        # Boundary checks
                        if nearest_idx >= len(site_w): 
                            nearest_idx = len(site_w) - 1
                            
                        # Si `nearest_idx` no es exacto, podemos chequear cuál está más cerca, pero basarnos en `searchsorted` 
                        # asume la siguiente hora, lo cual es útil. Para no sobrecomplicar la interpolación, usamos el índice devuelto:
                        w_row = site_w.iloc[nearest_idx]
                        
                        # Verificar que la diferencia no sea mayor a 2 horas (tolerancia de conexión)
                        td = abs(w_row['timestamp'] - ts)
                        if td.total_seconds() < 7200:
                            temp = w_row['airTemperature']
                            wind = w_row['windSpeed']
                            dew = w_row.get('dewTemperature')
                            if pd.notna(temp): temperature_gauge.labels(site_id=site_id).set(float(temp))
                            if pd.notna(wind): wind_speed_gauge.labels(site_id=site_id).set(float(wind))
                            if dew is not None and pd.notna(dew): dew_temperature_gauge.labels(site_id=site_id).set(float(dew))
            except Exception as e:
                pass

    return True

def get_current_electricity_row(replay_index: int) -> dict:
    ds = load_datasets()
    if ds is None or 'electricity' not in ds: return None
    df_e = ds['electricity']
    # Format to ISO string for compatibility
    row = df_e.iloc[replay_index].copy()
    row['timestamp'] = row['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
    return row.to_dict()

def get_electricity_len() -> int:
    ds = load_datasets()
    return len(ds['electricity']) if ds and 'electricity' in ds else 1

def extract_sensor_payload_at_index(replay_index: int, target_buildings: list) -> dict:
    """Extrae todas las mediciones crudas (Sensores IoT) para empaquetar hacia Node-RED."""
    ds = load_datasets()
    if ds is None or 'electricity' not in ds: return {}
    
    df_e = ds['electricity']
    if replay_index >= len(df_e): return {}
    
    row_e = df_e.iloc[replay_index]
    ts = row_e.get('timestamp')
    
    payload = {
        "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(ts) else "",
        "buildings": {},
        "weather": {}
    }
    
    for build_id in target_buildings:
        b_data = {"electricity_kwh": 0.0, "chilledwater_kwh": 0.0}
        
        # Electricidad
        try:
            val_e = float(row_e[build_id]) if pd.notna(row_e[build_id]) else 0.0
            b_data["electricity_kwh"] = val_e
        except Exception: pass
            
        # Agua Helada
        if 'chilledwater' in ds and build_id in ds['chilledwater'].columns:
            df_cw = ds['chilledwater']
            row_cw = df_cw.iloc[replay_index % len(df_cw)]
            try:
                val_cw = float(row_cw[build_id]) if pd.notna(row_cw[build_id]) else 0.0
                b_data["chilledwater_kwh"] = val_cw
            except Exception: pass
            
        payload["buildings"][build_id] = b_data
        
        # Clima
        if 'metadata' in ds and 'weather' in ds:
            try:
                if build_id in ds['metadata'].index:
                    site_id = ds['metadata'].loc[build_id, 'site_id']
                    if hasattr(site_id, 'iloc'): site_id = site_id.iloc[0]
                    
                    if site_id not in payload["weather"]:
                        w_df = ds['weather']
                        site_w = w_df[w_df['site_id'] == site_id].copy()
                        if not site_w.empty:
                            nearest_idx = site_w['timestamp'].searchsorted(ts)
                            if nearest_idx >= len(site_w): nearest_idx = len(site_w) - 1
                            w_row = site_w.iloc[nearest_idx]
                            
                            td = abs(w_row['timestamp'] - ts)
                            if td.total_seconds() < 7200:
                                dew_val = w_row.get('dewTemperature')
                                payload["weather"][site_id] = {
                                    "airTemperature": float(w_row['airTemperature']) if pd.notna(w_row['airTemperature']) else None,
                                    "windSpeed": float(w_row['windSpeed']) if pd.notna(w_row['windSpeed']) else None,
                                    "dewTemperature": float(dew_val) if dew_val is not None and pd.notna(dew_val) else None
                                }
            except Exception: pass

    return payload
