import os
from dotenv import load_dotenv

load_dotenv()

SERVER_IP = "192.168.1.14"

_DEFAULT_NODE_RED = f"http://{SERVER_IP}:1880" if SERVER_IP != "127.0.0.1" else "http://localhost:1880"
NODE_RED_URL = os.getenv("NODE_RED_URL", _DEFAULT_NODE_RED)

# Determina el directorio de datos dependiendo de si se corre en Docker o Local.
DATA_DIR = "/app/data" if os.path.exists("/app/data") else os.path.join(os.path.dirname(__file__), "../../data")
