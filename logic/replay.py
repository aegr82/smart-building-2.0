"""Simula datos en tiempo real enviando filas del dataset a Node-RED.

Este script se ejecuta como servicio dentro de Docker (via docker-compose) y
publica cada fila del CSV al endpoint /replay de Node-RED.

Para ajustarlo desde fuera, usa variables de entorno:
- CSV_PATH: path al CSV (por defecto /app/data/electricity.csv)
- REPLAY_INTERVAL_SECONDS: intervalo entre filas (por defecto 1)
- NODE_RED_URL: URL completa del endpoint de Node-RED (por defecto http://gateway:1880/replay)
"""

import os
import time
import pandas as pd
import httpx


def get_csv_path() -> str:
    return os.getenv("CSV_PATH", "/app/data/electricity.csv")


def get_node_red_url() -> str:
    # Default: intenta localhost (dev), luego gateway (Docker), luego config IP
    default = os.getenv("NODE_RED_DEFAULT", "http://localhost:1880/replay")
    return os.getenv("NODE_RED_URL", default)


def get_interval() -> float:
    try:
        return float(os.getenv("REPLAY_INTERVAL_SECONDS", "1"))
    except Exception:
        return 1.0


def main() -> None:
    csv_path = get_csv_path()
    node_red_url = get_node_red_url()
    interval = get_interval()

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    if df.empty:
        raise SystemExit("CSV is empty")

    client = httpx.Client(timeout=10.0)

    idx = 0
    while True:
        row = df.iloc[idx].to_dict()
        try:
            client.post(node_red_url, json=row)
        except Exception:
            # Ignore network issues and continue
            pass

        idx = (idx + 1) % len(df)
        time.sleep(interval)


if __name__ == "__main__":
    main()
