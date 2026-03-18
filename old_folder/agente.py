import requests
import time

URL_CONSULTA = "http://localhost:1880/consultar-estado"
URL_ACCION = "http://localhost:1880/accion-ia"

print("--- AGENTIC AI SIMPLIFICADO ---")

while True:
    try:
        # 1. El Agente recibe el NÚMERO directamente
        response = requests.get(URL_CONSULTA).text
        print(f"Agente recibe: {response}")
        temp_actual = float(response)  # Convertimos a número para análisis
        
        # 2. Lógica de Decisión (Simple y clara)
        if temp_actual > 35.0:
            msg, color = "ALERTA: Calor crítico.", "red"
        elif temp_actual < 20.0:
            msg, color = "AVISO: Temperatura baja.", "blue"
        else:
            msg, color = "Sistema OK.", "green"
        
        # 3. Informar al Dashboard
        requests.post(URL_ACCION, json={"payload": msg, "color": color})
        print(f"Análisis: {temp_actual}°C -> {msg}")
        
    except Exception as e:
        print(f"Sincronizando con BMS... {e}")
        
    time.sleep(3) # Consulta cada 3 segundos