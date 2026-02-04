import asyncio
import logging
from datetime import datetime
from typing import Dict

import aiohttp
from bs4 import BeautifulSoup
from config import Config

# ───────────────────────
#  IMPORT «GROQ» (Асинхронный)
# ───────────────────────
try:
    from groq import AsyncGroq  # 👈 Используем AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

log = logging.getLogger(__name__)

class HoroscopeService:
    def __init__(self) -> None:
        self.groq_client = None
        self._cache = {} # Инициализируем кеш сразу
        if GROQ_AVAILABLE and Config.GROQ_API_KEY:
            try:
                # 👈 Создаем асинхронный клиент
                self.groq_client = AsyncGroq(api_key=Config.GROQ_API_KEY)
            except Exception as exc:
                log.error(f"❌ Инициализация Groq не удалась: {exc}")

    async def _fetch(self, url: str) -> str | None:
        try:
            # Добавляем User-Agent, чтобы сайты не блокировали запросы с Render
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        return await resp.text()
        except Exception as exc:
            log.debug(f"❌ {url} не удалось получить: {exc}")
        return None

    async def parse_horoscopes(self, zodiac_sign: str) -> str:
        zodiac_map = {
            "Овен": "aries", "Телец": "taurus", "Близнецы": "gemini",
            "Рак": "cancer", "Лев": "leo", "Дева": "virgo",
            "Весы": "libra", "Скорпион": "scorpio", "Стрелец": "sagittarius",
            "Козерог": "capricorn", "Водолей": "aquarius", "Рыбы": "pisces",
        }
        zodiac_en = zodiac_map.get(zodiac_sign, "aries")
        horoscopes: list[str] = []

        # Mail.ru
        url_mail = f"https://horo.mail.ru/prediction/{zodiac_en}/today/"
        html = await self._fetch(url_mail)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            elem = soup.find("div", class_="article__item")
            if elem:
                text = elem.get_text(strip=True)
                horoscopes.append(f"📧 *Mail.ru*:\n{text[:300]}...")

        return "\n\n".join(horoscopes) or "На сегодня внешние гороскопы временно недоступны."

    async def _generate_ai(self, user: Dict, zodiac_sign: str) -> str:
        if not self.groq_client:
            return "⚠️ Сервис AI-гороскопов недоступен (проверьте ключ)."

        today = datetime.now().strftime("%d.%m.%Y")
        prompt = f"""
Создай персональный гороскоп на {today} для человека:
Знак зодиака: {zodiac_sign}
Пол: {user.get('gender', 'N/A')}
Данные матрицы: {user.get('matrix', 'N/A')}

Стилизуй красиво, добавь эмодзи. Ответ на русском языке.
"""
        try:
            # 👈 Добавлен await и используется асинхронный клиент
            completion = await self.groq_client.chat.completions.create(
                model=getattr(Config, "GROQ_MODEL", "llama3-8b-8192"),
                messages=[
                    {"role": "system", "content": "Ты профессиональный астролог."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            return completion.choices[0].message.content.strip()
        except Exception as exc:
            log.error(f"Groq API Error: {exc}")
            return f"❌ Ошибка AI: {exc}"

    async def get_daily_horoscope(self, user_data: Dict) -> str:
        zodiac = user_data.get("zodiac", "Овен")
        cache_key = f"{zodiac}_{datetime.now():%Y-%m-%d}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        # Запускаем парсинг и AI параллельно для скорости
        parsed_task = self.parse_horoscopes(zodiac)
        
        if self.groq_client:
            ai_text = await self._generate_ai(user_data, zodiac)
        else:
            ai_text = ""

        parsed = await parsed_task

        if ai_text and not ai_text.startswith("❌"):
            res = f"✨ *ПЕРСОНАЛЬНЫЙ ГОРОСКОП* ✨\n📅 {datetime.now():%d.%m.%Y}\n\n{ai_text}\n\n📊 *Дополнительно*:\n{parsed}"
        else:
            res = f"✨ *ГОРОСКОП* ✨\n📅 {datetime.now():%d.%m.%Y}\n\n{parsed}"

        self._cache[cache_key] = res
        return res
