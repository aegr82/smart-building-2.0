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

TARGET_BUILDING = 'Bull_lodging_Melissa'

def load_pipeline_module(name, rel_path):
    file_path = os.path.join(PIPELINES_DIR, rel_path)
    folder_path = os.path.dirname(file_path)
    if folder_path not in sys.path:
        sys.path.insert(0, folder_path)
        
    spec = importlib.util.spec_from_file_location(name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

st.title("🤖 AI Pipelines UI Tester")
st.markdown("Dashboard privado para validar los modelos sobre el 50% de los datos históricos (Evitando Data Leakage).")

tab1, tab2, tab3 = st.tabs(["📊 Traditional AI (Predicción)", "📝 Generative AI (Analista)", "⚡ Agentic AI (Controlador)"])

# --- TAB 1: TRADITIONAL AI ---
with tab1:
    st.header("Entrenamiento y Predicción Tradicional")
    try:
        df = pd.read_csv(os.path.join(DATA_DIR, "electricity.csv"))
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # 1. Sólo el 50% histórico
        half_idx = int(len(df) * 0.5)
        df_hist = df.iloc[:half_idx].copy()
        
        # 2. Split 80/20 train/test
        split_idx = int(len(df_hist) * 0.8)
        
        st.write(f"**Dataset Total:** {len(df)} filas | **Mitad Histórica (50%):** {len(df_hist)} filas")
        st.write(f"→ **Train (80%):** {split_idx} filas | **Test (20%):** {len(df_hist) - split_idx} filas")
        
        # Prep for plotting
        plot_df = pd.DataFrame({'timestamp': df_hist['timestamp']}).set_index('timestamp')
        plot_df['Train (80%)'] = df_hist.iloc[:split_idx][TARGET_BUILDING]
        plot_df['Test / Val (20%)'] = df_hist.iloc[split_idx:][TARGET_BUILDING]
        
        st.line_chart(plot_df, color=['#1f77b4', '#ff7f0e'])
        
        col1, col2 = st.columns(2)
        with col1:
            st.info("Para re-entrenar el modelo, debes ejecutar la imagen de docker o el script `train.py` directamente por terminal por su volumen de cómputo.")
        with col2:
            if st.button("Probar Inferencia Rápida (Sensor Simulado)"):
                with st.spinner("Cargando PyTorch..."):
                    inf_module = load_pipeline_module("trad_inf", "01_traditional_ai/inference.py")
                    res = inf_module.inference_step(12.5, 4.2, 14, 1150.0)
                    st.success("Inferencia exitosa")
                    st.json(res)
    except Exception as e:
        st.error(f"Error cargando datos: {e}")

# --- TAB 2: GENERATIVE AI ---
with tab2:
    st.header("Analista Generativo (Gemini Flash)")
    st.write("Genera resúmenes ejecutivos a partir de un contexto simulado del comportamiento del edificio.")
    
    if st.button("EJECUTAR ANALISTA LLM"):
        with st.spinner("Llamando a Gemini 3.1 Flash Lite Preview..."):
            try:
                gen_module = load_pipeline_module("gen_inf", "02_generative_ai/inference.py")
                res = gen_module.generative_inference()
                if res:
                    st.success(f"Reporte recibido en {res['latency']:.2f}s")
                    st.write(res['text'])
                    st.caption(f"Tokens IN: {res['tokens_in']} | OUT: {res['tokens_out']}")
                else:
                    st.error("Revisa tu GEMINI_API_KEY")
            except Exception as e:
                st.error(f"Error: {e}")

# --- TAB 3: AGENTIC AI ---
with tab3:
    st.header("Control Automático (Agente JSON)")
    st.write("Simula la lectura de sensores y devuelve un payload JSON estructurado listo para enviarse al BMS.")
    
    colA, colB = st.columns(2)
    with colA:
        st.markdown("**Estado Simulado Actual:**")
        st.code("""
{
    "timestamp": "2026-03-28T18:00:00",
    "air_temperature_celsius": 14.5,
    "building_occupancy": "LOW",
    "chiller_status": "ON"
}
        """, language="json")
        
    with colB:
        if st.button("CONSULTAR AGENTE PARA ACCIÓN"):
            with st.spinner("Modelando decisión determinística..."):
                try:
                    agent_mod = load_pipeline_module("agent_inf", "03_agentic_ai/inference.py")
                    res = agent_mod.agentic_inference()
                    if res:
                        st.success(f"Comando JSON generado en {res['latency']:.2f}s")
                        st.json(res['payload'])
                        if res['payload'].get('action') == 'TURN_OFF':
                            st.balloons()
                    else:
                        st.error("Error contactando API")
                except Exception as e:
                    st.error(f"Error: {e}")
