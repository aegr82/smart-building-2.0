import streamlit as st
import pandas as pd
import os
import sys
import importlib.util

st.set_page_config(page_title="Smart Building AI Tester", layout="wide")

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGIC_DIR = os.path.join(BASE_DIR, '..')
PIPELINES_DIR = os.path.join(LOGIC_DIR, 'ai_pipelines')
DATA_DIR = os.path.join(LOGIC_DIR, '..', 'data')

TARGET_BUILDING = 'Eagle_office_Marisela'

def load_pipeline_module(name, rel_path):
    file_path = os.path.join(PIPELINES_DIR, rel_path)
    folder_path = os.path.dirname(file_path)
    if folder_path not in sys.path:
        sys.path.insert(0, folder_path)
        
    spec = importlib.util.spec_from_file_location(name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

sys.path.insert(0, LOGIC_DIR)
from app.data_manager import extract_sensor_payload_at_index, get_electricity_len

st.title("🤖 AI Pipelines UI Tester")
st.markdown("Dashboard para validar Controladores (Agentes) y Modelos Predictivos puramente sobre el 50% inédito de operaciones (Previniendo Data Leakage).")

tab1, tab2 = st.tabs(["📊 Modelos Gemelos (PyTorch)", "⚡ Autonomía Agentic AI"])

total_len = get_electricity_len()
start_idx = int(total_len * 0.5)

def _get_weather(p):
    """Extract weather data from payload safely."""
    weather_keys = list(p.get('weather', {}).keys())
    return p['weather'][weather_keys[0]] if weather_keys else {'airTemperature': 15.0, 'windSpeed': 5.0, 'dewTemperature': None}

# --- TAB 1: TRADITIONAL AI ---
with tab1:
    st.header("Entrenamiento y Predicción Tradicional")
    
    # 1. Training Controls
    st.subheader("1. Entrenar Inteligencia Matemática")
    if st.button("▶ RE-ENTRENAR MODELOS GEMELOS"):
        with st.spinner("Entrenando PyTorch (Electricidad y Agua Helada) con 50 épocas..."):
            try:
                train_mod = load_pipeline_module("train_mod", "01_traditional_ai/train.py")
                metrics_elec = train_mod.train_model("electricity.csv", "model_elec.pth")
                metrics_cw = train_mod.train_model("chilledwater.csv", "model_cw.pth")
                st.success("✅ Modelos exportados (4 features: airTemp, dewTemp, windSpeed, hour).")
                
                # Display training results
                for label, m in [("⚡ Electricity Model", metrics_elec), ("❄️ Chilled Water Model", metrics_cw)]:
                    if m:
                        st.markdown(f"**{label}**")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Train MAE", f"{m['train_mae']:.2f} kWh")
                        m2.metric("Val MAE", f"{m['val_mae']:.2f} kWh")
                        m3.metric("Duración", f"{m['duration_s']}s")
                        m4.metric("Muestras", f"{m['train_samples']} train / {m['val_samples']} val")
            except Exception as e:
                st.error(f"Error entrenando: {e}")

    st.divider()
    
    # 2. Inference Control
    st.subheader("2. Simulador de Operación Inédita (Inferencia)")
    
    st.write(f"Desliza para cargar el estado del BMS en el timestamp inédito seleccionado (Rango: {start_idx} al {total_len})")
    sim_index = st.slider("Índice de Simulación IoT", min_value=start_idx, max_value=total_len-1, value=start_idx, step=1)
    
    if st.button("CARGAR ESTADO DE SENSORES"):
        st.session_state.sim_index = sim_index
        payload = extract_sensor_payload_at_index(sim_index, [TARGET_BUILDING])
        st.session_state.payload = payload
        st.success("Sensores Obtenidos")
        
    if 'payload' in st.session_state:
        p = st.session_state.payload
        b_data = p.get('buildings', {}).get(TARGET_BUILDING, {})
        w_data = _get_weather(p)
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Timestamp", str(p.get('timestamp')))
        c2.metric("Temperatura", f"{w_data.get('airTemperature')} °C")
        dew_val = w_data.get('dewTemperature')
        c3.metric("Punto de Rocío", f"{dew_val} °C" if dew_val is not None else "N/A")
        c4.metric("Electricidad Actual", f"{b_data.get('electricity_kwh')} kWh")
        c5.metric("Chilled Water Actual", f"{b_data.get('chilledwater_kwh')} kWh")
        
        if st.button("ANALIZAR ANOMALÍA (PyTorch)"):
            with st.spinner("Evaluando huella energética..."):
                try:
                    hour = pd.to_datetime(p['timestamp']).hour if p.get('timestamp') else 12
                    dew = float(dew_val) if dew_val is not None else 0.0
                    inf_module = load_pipeline_module("trad_inf", "01_traditional_ai/inference.py")
                    res = inf_module.inference_step(
                        float(w_data.get('airTemperature', 20.0)),
                        float(w_data.get('windSpeed', 5.0)),
                        hour,
                        float(b_data.get('electricity_kwh', 0.0)),
                        float(b_data.get('chilledwater_kwh', 0.0)),
                        dew_temp=dew
                    )
                    st.json(res)
                except Exception as e:
                    st.error(f"Error prediciendo: {e}")

# --- TAB 2: AGENTIC AI ---
with tab2:
    st.header("Control Automático (Agente LLM + Herramientas PyTorch)")
    st.write("El Agente leerá el estado actual del edificio y utilizará los modelos predicitivos Gemelos como sus consejeros ('Tooling') para decidir qué maquinaria apagar.")
    
    if 'payload' not in st.session_state:
        st.warning("⚠️ Primero ve a la pestaña de Modelos Gemelos y carga un Estado de Sensores en el Slider.")
    else:
        p = st.session_state.payload
        b_data = p.get('buildings', {}).get(TARGET_BUILDING, {})
        w_data = _get_weather(p)
        hour = pd.to_datetime(p['timestamp']).hour if p.get('timestamp') else 12
        dew_val = w_data.get('dewTemperature')
        dew = float(dew_val) if dew_val is not None else 0.0

        st.info("Variables en Caché Listas para Inferencia Autónoma.")
        
        if st.button("CONSULTAR AGENTE PARA ACCIÓN"):
            with st.spinner("Agente invocando modelos matemáticos y razonando..."):
                try:
                    agent_mod = load_pipeline_module("agent_inf", "03_agentic_ai/inference.py")
                    res = agent_mod.agentic_inference(
                        float(w_data.get('airTemperature', 20.0)),
                        float(w_data.get('windSpeed', 5.0)),
                        hour,
                        float(b_data.get('electricity_kwh', 0.0)),
                        float(b_data.get('chilledwater_kwh', 0.0)),
                        "LOW", # simulated
                        "ON", # simulated
                        dew_temp=dew
                    )
                    if res:
                        st.success(f"Comando Creado en {res['latency']:.2f}s interactuando con Herramientas Matemáticas.")
                        cA, cB = st.columns(2)
                        with cA:
                            st.write("**Respuesta Evaluada por System 1 (Tools):**")
                            st.json(res.get('tool_predictions', {}))
                        with cB:
                            st.write("**Decisión Ejecutiva (System 2):**")
                            st.json(res['payload'])
                            if res['payload'].get('action') == 'TURN_OFF':
                                st.balloons()
                    else:
                        st.error("Error contactando API de Gemini")
                except Exception as e:
                    st.error(f"Error: {e}")

