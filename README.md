# Smart Building 2.0

Este repositorio contiene una prueba de concepto de un **BMS (Building Management System)** que simula datos en tiempo real desde datasets CSV usando **Docker + FastAPI + Node-RED + Grafana + Prometheus**.

---

## 🔧 Objetivo

- **Reproducir datos reales** (desde `data/*.csv`) como si fueran una fuente en tiempo real.
- **Enviar esos datos a Node-RED** para procesarlos/encaminarlos.
- **Conectar la app (FastAPI)** a Node-RED para consumir esos datos.
- **Visualizar** en Grafana usando Prometheus como intermediario.

---

## 📦 Componentes del stack

| Servicio | Rol |
|---|---|
| `intelligence` | FastAPI que expone métricas y puede consultar Node-RED. |
| `gateway` | Node-RED: recibe datos simulados y ofrece API (`/latest`). |
| `replayer` | Script que publica datos del CSV a Node-RED en “tiempo real”. |
| `prometheus` | Scrapea la API de FastAPI `/metrics` y guarda series temporales. |
| `grafana` | Visualiza métricas de Prometheus. |

---

## ▶️ Cómo ejecutar (en cualquier PC con Docker)

1) Copiar el proyecto a la máquina de destino (ZIP, `scp`, `rsync`, etc.).
2) Ajustar `.env` con tu clave y/o columnas opcionales:

```env
GEMINI_API_KEY=<tu clave>
#PROM_METRIC_COLUMNS=Panther_parking_Lorriane,Panther_lodging_Cora
```

3) Levantar todo el stack:

```sh
docker compose up --build
```

4) Abrir en el navegador:
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090
- Node-RED: http://localhost:1880
- API FastAPI: http://localhost:8000

---

## 🔁 Flujo de datos (simulado “tiempo real”)

### Modo demo paso a paso (recomendado para presentaciones)
La app FastAPI expone endpoints para avanzar manualmente el dataset hacia Node-RED, lo que permite simular “data arriving live” a demanda.

- `POST /replay/step` → avanza 1 fila (o varias con `count`) y la envía a Node-RED (`/replay`).
- `GET /replay/status` → muestra índice actual + total de filas.
- `POST /replay/reset` → reinicia el índice al inicio.

### Modo automático (solo si quieres)
El servicio `replayer` puede correr en modo continuo, publicando cada fila con un intervalo (configurable). Está dentro del perfil `replayer` y no se inicia por defecto.

1. Node-RED guarda la última fila recibida y la expone en `/latest`.
2. FastAPI consulta Node-RED en `/nodered/latest` o sirve métricas a Prometheus en `/metrics`.
3. Grafana muestra esa métrica en un dashboard ya aprovisionado.

---

## 🧩 ¿Qué hacer si quieres cambiar el dataset?

- Copia tus CSV a `data/`.
- Cambia el valor de `CSV_PATH` en `.env` (o deja el predeterminado `data/electricity.csv`).

---

## 🚀 Siguientes pasos (opcionales)

- Conectar tu lógica AI en FastAPI (o Node-RED) usando el endpoint `/nodered/latest`.
- Crear varias métricas de Prometheus a partir de más columnas del CSV.
- Añadir streaming real (MQTT / WebSocket) si quieres más “real-time”.
