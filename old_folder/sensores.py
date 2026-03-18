import requests
import time
import random

URL_BMS = "http://localhost:1880/datos-bms"

print("--- SISTEMA DE SENSORES ACTIVO ---")

while True:
    # Simulamos temperatura ambiente (25°C - 38°C)
    valor_sensor = round(random.uniform(15.0, 45.0), 1)
    
    try:
        # Enviamos el dato al "BMS" (Node-RED)
        requests.post(URL_BMS, json={"payload": valor_sensor})
        print(f"Sensor enviando: {valor_sensor}°C")
    except:
        print("Error: Node-RED no responde.")
        
    time.sleep(1) # Envía datos cada segundo