FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    CANARY_CONFIG=/config/config.yaml

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config.example.yaml ./config.example.yaml

EXPOSE 8000

CMD ["python", "-m", "app.main"]
