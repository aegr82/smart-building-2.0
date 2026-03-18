from fastapi import FastAPI
import pandas as pd
import os
from dotenv import load_dotenv
from functools import lru_cache
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import CollectorRegistry
from fastapi.responses import Response
import httpx

# Cargar variables de entorno desde .env (local/dev) y desde el entorno Docker
load_dotenv()

app = FastAPI(title="Smart Building 2.0")

# Make the CSV path configurable for tests / different environments.
DEFAULT_CSV_PATH = "/app/data/electricity.csv"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Which columns to expose as Prometheus metrics (comma-separated). Uses the first 3 columns after timestamp if unset.
PROM_METRIC_COLUMNS = os.getenv("PROM_METRIC_COLUMNS")


def get_csv_path() -> str:
    """Resolve the CSV path from env (so tests can override it)."""
    return os.getenv("CSV_PATH", DEFAULT_CSV_PATH)


def get_node_red_url() -> str:
    return os.getenv("NODE_RED_URL", "http://gateway:1880")


@lru_cache(maxsize=2)
def _load_dataset(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(csv_path)
    return pd.read_csv(csv_path)


@lru_cache(maxsize=2)
def _load_snapshot_columns(csv_path: str) -> list[str]:
    """Return the list of columns we will expose as Prometheus metrics."""
    if PROM_METRIC_COLUMNS:
        return [c.strip() for c in PROM_METRIC_COLUMNS.split(",") if c.strip()]

    # Default: take first 3 columns after timestamp from the CSV header.
    if not os.path.exists(csv_path):
        return []

    df = pd.read_csv(csv_path, nrows=1)
    cols = [c for c in df.columns if c != "timestamp"]
    return cols[:3]


@lru_cache(maxsize=2)
def _get_metrics_registry(csv_path: str):
    """Create or reuse a Prometheus registry + gauges for a given dataset."""
    cols = _load_snapshot_columns(csv_path)
    registry = CollectorRegistry()
    gauges: dict[str, Gauge] = {}
    for col in cols:
        gauges[col] = Gauge(
            "electricity_value",
            "Electricity value (from dataset)",
            ["meter"],
            registry=registry,
        )
    return registry, gauges


def _update_metrics_from_row(row: pd.Series, gauges: dict[str, Gauge]) -> None:
    """Update Prometheus gauges from a single row of the dataframe."""
    for col, gauge in gauges.items():
        if col in row:
            try:
                gauge.labels(meter=col).set(float(row[col]))
            except Exception:
                # Skip invalid values
                pass


def _http_client() -> httpx.Client:
    """Create an HTTP client for external requests (Node-RED)."""
    return httpx.Client(timeout=5.0)


# Replay/step-through state (demo mode)
_REPLAY_INDEX = 0


@app.get("/")
def read_root():
    return {"status": "Online", "structure": "Verified"}

@app.get("/test-data")
def test_data():
    try:
        df = _load_dataset(get_csv_path())
    except FileNotFoundError:
        return {"error": "CSV no encontrado"}

    return df.head(5).to_dict(orient="records")


@app.get("/metrics")
def metrics() -> Response:
    """Prometheus scrape endpoint.

    Each scrape advances through the dataset so Grafana can plot a time series.
    """

    csv_path = get_csv_path()

    try:
        df = _load_dataset(csv_path)
    except FileNotFoundError:
        # No data available; return empty metrics payload
        empty_registry, _ = _get_metrics_registry(csv_path)
        return Response(content=generate_latest(empty_registry), media_type=CONTENT_TYPE_LATEST)

    registry, gauges = _get_metrics_registry(csv_path)

    index = int(os.getenv("METRICS_ROW_INDEX", "0"))
    index = index % len(df)
    _update_metrics_from_row(df.iloc[index], gauges)
    os.environ["METRICS_ROW_INDEX"] = str((index + 1) % len(df))

    data = generate_latest(registry)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/nodered/latest")
def nodered_latest():
    """Proxy endpoint: obtiene el último dato que Node-RED tiene almacenado."""

    node_red_url = get_node_red_url().rstrip("/") + "/latest"
    try:
        with _http_client() as client:
            resp = client.get(node_red_url)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return {"error": "No se pudo obtener datos de Node-RED"}


@app.post("/replay/step")
def replay_step(count: int = 1):
    """Avanza el replay en el dataset en pasos (modo demo).

    Cada llamada avanza `count` filas y envía el registro actual a Node-RED.
    """

    global _REPLAY_INDEX

    df = _load_dataset(get_csv_path())
    total = len(df)

    node_red_url = get_node_red_url().rstrip("/") + "/replay"
    payloads = []

    with _http_client() as client:
        for _ in range(count):
            row = df.iloc[_REPLAY_INDEX].to_dict()
            payloads.append(row)
            try:
                client.post(node_red_url, json=row)
            except Exception:
                pass
            _REPLAY_INDEX = (_REPLAY_INDEX + 1) % total

    return {"sent": len(payloads), "index": _REPLAY_INDEX, "total": total}


@app.get("/replay/status")
def replay_status():
    """Estado actual del replay (índice + total)."""

    df = _load_dataset(get_csv_path())
    return {"index": _REPLAY_INDEX, "total": len(df)}


@app.post("/replay/reset")
def replay_reset():
    """Reinicia el índice de replay a cero."""

    global _REPLAY_INDEX
    _REPLAY_INDEX = 0
    return {"index": _REPLAY_INDEX}
