# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем всё остальное
COPY . .

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PORT=${PORT}

# Открываем порт  
EXPOSE 8080

# Запускаем бота
CMD ["python", "main.py"]
