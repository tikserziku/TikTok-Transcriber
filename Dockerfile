FROM python:3.10-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    python3-dev \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование файлов проекта
COPY requirements.txt .
COPY main.py .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Обновление yt-dlp
RUN yt-dlp -U

# Переменные окружения
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PATH="/usr/lib/chromium:${PATH}"

# Запуск приложения
CMD uvicorn main:app --host=0.0.0.0 --port=$PORT
