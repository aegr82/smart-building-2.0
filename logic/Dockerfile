FROM python:3.11-slim

WORKDIR /app

# Instalamos dependencias del sistema
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copiamos requirements desde la carpeta config
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el contenido de /logic al WORKDIR (/app)
COPY . .

# Exponemos el puerto de FastAPI
EXPOSE 8000

# Ejecutamos main.py que está dentro de app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]