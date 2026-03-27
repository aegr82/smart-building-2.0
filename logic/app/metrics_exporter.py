from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry

# Configurar el registro
registry = CollectorRegistry()

# Métricas
consumption_gauge = Gauge(
    "building_electricity_kwh",
    "Consumo eléctrico actual del dataset",
    ["building_id"],
    registry=registry
)

chilledwater_gauge = Gauge(
    "building_chilledwater_kwh",
    "Consumo de agua fría actual del dataset (chilledwater)",
    ["building_id"],
    registry=registry
)

temperature_gauge = Gauge(
    "site_air_temperature",
    "Temperatura del aire actual del dataset",
    ["site_id"],
    registry=registry
)

wind_speed_gauge = Gauge(
    "site_wind_speed",
    "Velocidad del viento actual del dataset",
    ["site_id"],
    registry=registry
)

def export_as_response():
    """Genera la respuesta HTTP formateada para Prometheus."""
    from fastapi import Response
    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
