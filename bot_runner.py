# bot_runner.py
import os
import time
import threading
import asyncio
from app import main

def keep_alive():
    """Функция для поддержания работы приложения"""
    while True:
        time.sleep(300)  # Каждые 5 минут

if __name__ == '__main__':
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=main)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Запускаем keep-alive в основном потоке
    keep_alive()
