# Numerology Telegram Bot

A Telegram bot that plays with numerology, astrology, and AI‑generated horoscopes.

## Features

- **Сбор данных**: дата рождения + пол.
- **Нумерология**: расчёт матрицы 3×3 + интерпретации.
- **Гороскоп**: парсинг популярных сайтов + персональный AI‑гипер‑часть.
- **Кнопки**: простая навигация через клавиатуру.
- **Health‑check**: `/health` возвращает «Bot is running».
- **Cron**: пример ежедневной задачи (можно настроить архивы, отправку сообщений и т.д.).

## Deploying to Render

1. Создайте репозиторий и запушьте файлы выше.
2. В Render:  
   * **Services** → **Add new** → **Web Service** → **Git** → `https://github.com/<org>/<repo>.git`.
3. Укажите **Environment variables**:  
   * `BOT_TOKEN` – токен Telegram‑бота.  
   * `GROQ_API_KEY` – API‑ключ от Groq (по желанию, AI‑часть будет работать без него).  
   * `GROQ_MODEL` – название модели (по умолчанию `mixtral-8x7b-32768`).
4. Позавтракайте — Render будет билдить Docker‑образ и запустить сервис.

## Local Development

```bash
# Скопировать .env.example в .env и заполнить переменными
cp .env.example .env

pip install -r requirements.txt
python main.py
