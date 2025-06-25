FROM python:3.10-slim

RUN apt-get update && apt-get install -y ffmpeg gcc && apt-get clean

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
