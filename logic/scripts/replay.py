"""IoT Sensor Array Simulator (Smart Building 2.0).

Este script se ejecuta de forma asíncrona a la API central e inyecta 
paquetes unificados de los medidores directamente a Node-RED (Gateway).
Evita fugas de datos garantizando que la simulación ocurra EXCLUSIVAMENTE 
sobre el 50% final de los datos (la primera mitad histórica es solo para entrenar IA).
"""

import os
import time
import httpx
from app.data_manager import extract_sensor_payload_at_index, get_electricity_len

def get_node_red_url() -> str:
    default = os.getenv("NODE_RED_DEFAULT", "http://gateway:1880/replay")
    return os.getenv("NODE_RED_URL", default)

def get_interval() -> float:
    try:
        return float(os.getenv("REPLAY_INTERVAL_SECONDS", "1"))
    except Exception:
        return 1.0

def main() -> None:
    node_red_url = get_node_red_url()
    interval = get_interval()

    total_len = get_electricity_len()
    if total_len <= 1:
        raise SystemExit("Dataset is too small or missing")

    # REGLA ORO: NUNCA EMITIR EL PRIMER 50% DE LOS DATOS (HISTÓRICO IA).
    start_idx = int(total_len * 0.5)
    idx = start_idx

    target_buildings = ['Bull_lodging_Melissa', 'Fox_office_Easter', 'Eagle_office_Marisela']
    
    client = httpx.Client(timeout=10.0)
    print(f"🛡️ IoT Sim: Starting unified sensor replay from index {start_idx} to {total_len} (Data Leakage Prevented).")

    while True:
        payload = extract_sensor_payload_at_index(idx, target_buildings)
        try:
            client.post(node_red_url, json=payload)
        except Exception as e:
            print(f"Gateway connection error: {e}")

        idx += 1
        # Loop over the 50% segment seamlessly
        if idx >= total_len:
            idx = start_idx
            
        time.sleep(interval)

if __name__ == "__main__":
    main()
