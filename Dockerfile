FROM python:3.12-slim

WORKDIR /app

# Устанавливаем build dependencies для libsql
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Cloud Run использует PORT из env
ENV PORT=8080

# Запускаем webhook сервер
CMD ["python", "-m", "nutrition_tracker.webhook_server"]

