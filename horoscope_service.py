import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Optional

import aiohttp
from bs4 import BeautifulSoup
from groq import AsyncGroq
from config import Config

log = logging.getLogger(__name__)

class HoroscopeService:
    def __init__(self) -> None:
        self._cache = {}
        # Инициализируем асинхронный клиент Groq
        self.api_key = Config.GROQ_API_KEY
        if self.api_key:
            self.groq_client = AsyncGroq(api_key=self.api_key)
        else:
            self.groq_client = None
            log.warning("⚠️ GROQ_API_KEY не установлен. AI-функции будут недоступны.")

    # ---------------------------------------------------
    #  Вспомогательный метод для HTTP-запросов
    # ---------------------------------------------------
    async def _fetch(self, url: str) -> Optional[str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=12) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    log.error(f"❌ Ошибка парсинга {url}: статус {resp.status}")
        except Exception as exc:
            log.error(f"❌ Исключение при запросе к {url}: {exc}")
        return None

    # ---------------------------------------------------
    #  Парсинг внешних источников
    # ---------------------------------------------------
    async def parse_horoscopes(self, zodiac_sign: str) -> str:
        zodiac_map = {
            "Овен": "aries", "Телец": "taurus", "Близнецы": "gemini",
            "Рак": "cancer", "Лев": "leo", "Дева": "virgo",
            "Весы": "libra", "Скорпион": "scorpio", "Стрелец": "sagittarius",
            "Козерог": "capricorn", "Водолей": "aquarius", "Рыбы": "pisces",
        }
        zodiac_en = zodiac_map.get(zodiac_sign, "aries")
        results = []

        # Парсим Mail.ru
        html_mail = await self._fetch(f"https://horo.mail.ru/prediction/{zodiac_en}/today/")
        if html_mail:
            soup = BeautifulSoup(html_mail, "html.parser")
            article = soup.find("div", class_="article__item") or soup.find("article")
            if article:
                text = " ".join([p.get_text(strip=True) for p in article.find_all("p")])
                if text: results.append(f"Источник Mail.ru: {text[:400]}")

        # Парсим Rambler
        html_rambler = await self._fetch(f"https://horoscopes.rambler.ru/{zodiac_en}/")
        if html_rambler:
            soup = BeautifulSoup(html_rambler, "html.parser")
            main_div = soup.find("div", {"data-mt-part": "article"})
            if main_div and main_div.find("p"):
                text = main_div.find("p").get_text(strip=True)
                if text: results.append(f"Источник Rambler: {text[:400]}")

        return "\n\n".join(results) if results else "Данные из внешних источников временно недоступны."

    # ---------------------------------------------------
    #  AI-Агрегация через Groq
    # ---------------------------------------------------
    async def _generate_ai_aggregated(self, user_data: Dict, zodiac: str, context: str) -> str:
        if not self.groq_client:
            return "⚠️ AI-модуль не сконфигурирован."

        today = datetime.now().strftime("%d.%m.%Y")
        # Извлекаем данные матрицы для персонализации
        matrix = user_data.get("matrix", {})
        
        prompt = f"""
Ты — элитный астролог и нумеролог. Составь ОДИН мощный персонализированный гороскоп на {today} для знака {zodiac}.

ИСПОЛЬЗУЙ ЭТИ ДАННЫЕ ДЛЯ АНАЛИЗА:
1. Контекст из СМИ: {context}
2. Числа из матрицы пользователя: {matrix.get('full_array', 'не указаны')}
3. Число судьбы: {matrix.get('additional', [0])[0]}

ТВОЯ ЗАДАЧА:
- Объединить прогнозы СМИ в одну логичную картину.
- Добавить уникальный нумерологический совет дня.
- Тон: мистический, но поддерживающий и четкий.
- Форматирование: используй Markdown (жирный текст, списки) и много эмодзи.
- Длина: около 800-1000 символов.
- ОТВЕТ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.
"""
        try:
            # Используем актуальную модель Llama 3.1 8B
            model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
            
            completion = await self.groq_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Ты профессиональный астро-аналитик."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=1000
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            log.error(f"AI Aggregation Error: {e}")
            return f"❌ Ошибка генерации AI: {e}\n\nНо вот что говорят звезды в сети:\n{context}"

    # ---------------------------------------------------
    #  Главный метод (Оркестратор)
    # ---------------------------------------------------
    async def get_daily_horoscope(self, user_data: Dict) -> str:
        zodiac = user_data.get("zodiac", "Овен")
        cache_key = f"{zodiac}_{datetime.now():%Y-%m-%d}"

        # Проверка кеша
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 1. Собираем данные из интернета
        external_context = await self.parse_horoscopes(zodiac)

        # 2. Отправляем в AI для агрегации и анализа
        final_forecast = await self._generate_ai_aggregated(user_data, zodiac, external_context)

        # Сохраняем результат
        self._cache[cache_key] = final_forecast
        return final_forecast
