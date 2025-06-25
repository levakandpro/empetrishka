FROM python:3.10-slim

# Установка зависимостей для yt_dlp + ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    curl \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
 && apt-get clean

# Установка последней версии yt_dlp отдельно
RUN pip install --no-cache-dir yt-dlp

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
