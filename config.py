import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "mixtral-8x7b-32768")

    # Параметры парсинга гороскопов
    HOROSCOPE_SOURCES = [
        "https://horo.mail.ru/prediction/",
        "https://www.astromeridian.ru/horoscope/",
        "https://horo.rambler.ru/",
    ]

    # Кэширование
    CACHE_TTL = 3600  # 1 час
