# Usar una imagen base de Python
FROM python:3.11-slim

# Instalar las dependencias del sistema: FFmpeg y Opus
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus-dev

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar los archivos de requisitos e instalar las librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de los archivos del bot
COPY . .

# El comando para iniciar el bot
CMD ["python", "main.py"]
