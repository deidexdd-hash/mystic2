# horoscope_service.py
"""
Сервис парсинга гороскопов (Mail.ru / Rambler) + генерации AI‑гороскопа через Groq.
"""

import asyncio
from datetime import datetime
from typing import Dict

import aiohttp
from bs4 import BeautifulSoup
from config import Config

# ----------------------------------------------------------------------
#  Грациальная инициализация Groq
# ----------------------------------------------------------------------
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except Exception:
    GROQ_AVAILABLE = False


class HoroscopeService:
    def __init__(self) -> None:
        """Создаём клиент Groq, если ключ задан."""
        self.groq_client: Groq | None = None
        if GROQ_AVAILABLE and Config.GROQ_API_KEY:
            try:
                self.groq_client = Groq(api_key=Config.GROQ_API_KEY)
            except Exception:
                # В случае неудачи не пробрасываем исключение – просто не будем генерировать AI‑ге
                pass

    # ------------------------------------------------------------------
    #  Асинхронный HTTP‑запрос
    # ------------------------------------------------------------------
    async def _fetch(self, url: str) -> str | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        return await resp.text()
        except Exception:          # любые network‑ошибки – просто None
            return None
        return None

    # ------------------------------------------------------------------
    #  Парсим гороскопы с внешних сайтов
    # ------------------------------------------------------------------
    async def parse_horoscopes(self, zodiac_sign: str) -> str:
        """Возвращает простую строку с гороскопами Mail.ru и Rambler."""
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

        # Mail.ru
        url_mail = f"https://horo.mail.ru/prediction/{zodiac_en}/today/"
        html = await self._fetch(url_mail)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            elem = soup.find("div", class_="article__item")
            if elem:
                txt = elem.get_text().strip()
                if txt:
                    horoscopes.append(f"📧 *Mail.ru*:\n{txt[:300]}...")

        # Rambler
        url_rambler = f"https://horoscopes.rambler.ru/{zodiac_en}/"
        html = await self._fetch(url_rambler)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for cls in ["_1RrZR", "article__text", "content", "text"]:
                elem = soup.find("p", class_=cls)
                if elem:
                    txt = elem.get_text().strip()
                    if txt:
                        horoscopes.append(f"🌐 *Rambler*:\n{txt[:300]}...")
                        break

        return "\n\n".join(horoscopes) or "На сегодня гороскопы временно недоступны."

    # ------------------------------------------------------------------
    #  Генерация AI‑гороскопа через Groq
    # ------------------------------------------------------------------
    async def _generate_ai(self, user: dict, zodiac_sign: str) -> str:
        if not self.groq_client:
            return "⚠️ Сервис AI‑гороскопа недоступен."

        today = datetime.now().strftime("%d.%m.%Y")
        prompt = f"""
Создай персональный гороскоп на {today}:

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
Стилизовано, добавляются эмодзи, длина < 800 символов.
        """
        try:
            completion = self.groq_client.chat.completions.create(
                model=Config.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "Ты астролог и нумеролог."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            return completion.choices[0].message.content.strip()
        except Exception as exc:
            return f"❌ Ошибка AI‑гороскопа: {exc}"

    # ------------------------------------------------------------------
    #  Весь дневной гороскоп (парс, AI, объединяем)
    # ------------------------------------------------------------------
    async def get_daily_horoscope(self, user_data: dict) -> str:
        zodiac = user_data.get("zodiac", "Овен")
        static_text = await self.parse_horoscopes(zodiac)

        ai_text = ""
        if self.groq_client:
            ai_text = await self._generate_ai(user_data, zodiac)

        if ai_text and not ai_text.startswith("❌"):
            return f"""✨ *ПЕРСОНАЛЬНЫЙ ГОРОСКОП* ✨
📅 {datetime.now().strftime("%d.%m.%Y")}
♈ Знак зодиака: {zodiac}

🌟 *Ваш персональный прогноз на сегодня* 🌟
{ai_text}

📊 *Сводка с других источников* 📊
{static_text}

💫 *Совет от нумеролога* 💫
Используйте число {user_data.get('second', '1')} как ваш талисман сегодня.
"""
        else:
            return f"""✨ *ГОРОСКОП НА СЕГОДНЯ* ✨
📅 {datetime.now().strftime("%d.%m.%Y")}
♈ Знак зодиака: {zodiac}

{static_text}

💫 *Совет дня* 💫
Сегодня благоприятный день для новых начинаний! Используйте число {user_data.get('second', '1')} как ваш талисман.
"""
