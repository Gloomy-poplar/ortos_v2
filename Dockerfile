FROM python:3.12-slim

# Устанавливаем системные зависимости для torch, faiss
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ libgomp1 git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python-пакеты
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# КЭШИРУЕМ МОДЕЛЬ (чтобы не скачивать при запуске)
RUN python -c "from sentence_transformers import SentenceTransformer; \
    print('Загружаю модель...'); \
    SentenceTransformer('intfloat/multilingual-e5-base')"

# Копируем код
COPY . .

# Запускаем бота
CMD ["python", "app.py"]