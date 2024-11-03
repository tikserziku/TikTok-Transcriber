# Dockerfile
FROM python:3.10-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование файлов проекта
COPY requirements.txt .
COPY app.py .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Проверка установки ffmpeg
RUN ffmpeg -version

# Переменные окружения
ENV PORT=8080

# Запуск приложения
CMD python app.py
