FROM python:3.11-slim

# Instalar FFmpeg en el contenedor
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del bot
COPY . .

# Comando de inicio del bot en Railway
CMD ["python", "bot_stream_multicanal.py"]
