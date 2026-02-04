# horoscope_service.py
import asyncio
import logging
from datetime import datetime
from typing import Dict

import aiohttp
from bs4 import BeautifulSoup
from config import Config

# ────────────────────────────────────────
#  ГЛУБОКИЙ ГЕНЕРАТОР И ОТКРЫТЫЙ ДЛЯ 3.13
# ────────────────────────────────────────
log = logging.getLogger(__name__)

# ───────────────────────
#  IMPORT «GROQ» (НЕобязательно)
# ───────────────────────
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except Exception:
    GROQ_AVAILABLE = False


class HoroscopeService:
    def __init__(self) -> None:
        # «Гороскопы‑AI» → только если ключ задан
        self.groq_client = None
        if GROQ_AVAILABLE and Config.GROQ_API_KEY:
            try:
                self.groq_client = Groq(api_key=Config.GROQ_API_KEY)
            except Exception as exc:
                log.error(f"❌ Инициализация Groq не удалась: {exc}")

    # ---------------------------------------------------
    #  Асинхронный HTML‑запрос
    # ---------------------------------------------------
    async def _fetch(self, url: str) -> str | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        return await resp.text()
        except Exception as exc:
            log.debug(f"❌ {url} не удалось получить: {exc}")
        return None

    # ---------------------------------------------------
    #  Статический парсинг из внешних сайтов
    # ---------------------------------------------------
    async def parse_horoscopes(self, zodiac_sign: str) -> str:
        zodiac_map = {
            "Овен": "aries",
            "Телец": "taurus",
            "Близнецы": "gemini",
            "Рак": "cancer",
            "Лев": "leo",
            "Дева": "virgo",
            "Весы": "libra",
            "Скорпион": "scorpio",
            "Стрелец": "sagittarius",
            "Козерог": "capricorn",
            "Водолей": "aquarius",
            "Рыбы": "pisces",
        }

        zodiac_en = zodiac_map.get(zodiac_sign, "aries")
        horoscopes: list[str] = []

        # -- Mail.ru ----------------------------------------------------
        url_mail = f"https://horo.mail.ru/prediction/{zodiac_en}/today/"
        html = await self._fetch(url_mail)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            elem = soup.find("div", class_="article__item")
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    horoscopes.append(f"📧 *Mail.ru*:\n{text[:300]}...")

        # -- Rambler ---------------------------------------------------
        url_rambler = f"https://horoscopes.rambler.ru/{zodiac_en}/"
        html = await self._fetch(url_rambler)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for cls in ["_1RrZR", "article__text", "content", "text"]:
                elem = soup.find("p", class_=cls)
                if elem:
                    text = elem.get_text(strip=True)
                    if text:
                        horoscopes.append(f"🌐 *Rambler*:\n{text[:300]}...")
                        break

        return "\n\n".join(horoscopes) or "На сегодня гороскопы временно недоступны."

    # ---------------------------------------------------
    #  GN‑Генерация персонального AI‑гороскопа (Groq)
    # ---------------------------------------------------
    async def _generate_ai(self, user: Dict, zodiac_sign: str) -> str:
        if not self.groq_client:
            return "⚠️ Сервис генерации гороскопов недоступен."

        today = datetime.now().strftime("%d.%m.%Y")
        prompt = f"""
Создай персональный гороскоп на {today} для человека со следующими данными:

Дата рождения: {user.get('date', 'N/A')}
Знак зодиака: {zodiac_sign}
Пол: {user.get('gender', 'N/A')}
Число судьбы: {user.get('second', 'N/A')}
Число души: {user.get('fourth', 'N/A')}

1. Общий прогноз дня
2. Любовные отношения
3. Финансы/карьера
4. Здоровье
5. Совет дня

Стилизуйте, добавьте эмодзи, длина < 800 символов

"""

        try:
            completion = self.groq_client.chat.completions.create(
                model=Config.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "Ты астролог и нумеролог. Твои прогнозы точные и мотивирующие."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            return completion.choices[0].message.content.strip()
        except Exception as exc:
            return f"❌ Ошибка генерации AI‑гороскопа: {exc}"

    # ---------------------------------------------------
    #  Полный «дневной» гороскоп (парсинг + AI + кеш)
    # ---------------------------------------------------
    async def get_daily_horoscope(self, user_data: Dict) -> str:
        zodiac = user_data.get("zodiac", "Овен")
        cache_key = f"{zodiac}_{datetime.now():%Y-%m-%d}"

        # Кеш – только в памяти, в продакшн можно вынести в memcached/redis
        if hasattr(self, "_cache") and cache_key in self._cache:
            return self._cache[cache_key]

        parsed = await self.parse_horoscopes(zodiac)

        ai_text = ""
        if self.groq_client:
            ai_text = await self._generate_ai(user_data, zodiac)

        if ai_text and not ai_text.startswith("❌"):
            res = f"""
✨ *ПЕРСОНАЛЬНЫЙ ГОРОСКОП* ✨
📅 {datetime.now():%d.%m.%Y}
♈ Знак зодиака: {zodiac}

🌟 *Ваш персональный прогноз на сегодня* 🌟

{ai_text}

📊 *Сводка с других источников* 📊

{parsed}

💫 *Совет от нумеролога* 💫
Используйте число {user_data.get('second', '1')} как ваш талисман сегодня!
"""
        else:
            res = f"""
✨ *ГОРОСКОП НА СЕГОДНЯ* ✨
📅 {datetime.now():%d.%m.%Y}
♈ Знак зодиака: {zodiac}

{parsed}

💫 *Совет дня* 💫
Сегодня благоприятный день для новых начинаний! Используйте число {user_data.get('second', '1')} как ваш талисман.
"""

        self._cache = getattr(self, "_cache", {})
        self._cache[cache_key] = res
        return res
