# horoscope_service.py
"""
Сервис для парсинга гороскопов из внешних сайтов
и генерации персонального AI‑гороскопа через Groq (если ключ задан).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, List

import aiohttp
import requests          # просто для 2–хлайн кода → заменить на aiohttp, если нужно
from bs4 import BeautifulSoup
from config import Config

# ---------- GROQ INITIALISATION (optional) ----------
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except Exception:          # В случае, если пакет groq отсутствует
    GROQ_AVAILABLE = False

# ---------- LOGGING ----------
log = logging.getLogger(__name__)


# ---------- SERVICE CLASS ----------
class HoroscopeService:
    """
    Простой API для:
        * Статического парсинга гороскопов (Mail.ru / Rambler)
        * Динамического генерирования AI‑гороскопа через Groq
        * Кеширования (пока в памяти)
    """

    def __init__(self) -> None:
        # Инициализация клиента Groq, если ключ задан и пакет стоит
        self.groq_client = None
        if GROQ_AVAILABLE and Config.GROQ_API_KEY:
            try:
                self.groq_client = Groq(api_key=Config.GROQ_API_KEY)
                log.info("✅ Groq клиент подключён")
            except Exception as exc:
                log.error(f"❌ Не удалось подключить Groq: {exc}")
                self.groq_client = None

        self._cache: Dict[str, str] = {}  # кеш гороскопов по ключу <zodiac>_<date>
        self._session = aiohttp.ClientSession()  # один общий session

    # -------------------------------------------------
    #  парсинг из внешних сайтов (async)
    # -------------------------------------------------
    async def _fetch_page(self, url: str) -> str | None:
        """Асинхронно скачиваем страницу и возвращаем текст."""
        try:
            async with self._session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception as exc:
            log.debug(f"❌ Не удалось скачать {url}: {exc}")
        return None

    async def parse_horoscopes(self, zodiac_sign: str) -> str:
        """Собирает гороскопы с Mail.ru и Rambler."""
        horoscopes: List[str] = []

        # ---- MAP: рус → eng ----
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

        zodiac = zodiac_map.get(zodiac_sign, "aries")  # fallback

        # ----- Mail.ru -----
        url_mail = f"https://horo.mail.ru/prediction/{zodiac}/today/"
        html = await self._fetch_page(url_mail)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            data = soup.find("div", class_="article__item")
            if data:
                txt = data.get_text().strip()
                if txt:
                    horoscopes.append(f"📧 *Mail.ru*:\n{txt[:300]}...")

        # ----- Rambler -----
        url_rambler = f"https://horoscopes.rambler.ru/{zodiac}/"
        html = await self._fetch_page(url_rambler)
        if html:
            soup = BeautifulSoup(html, "html.parser")

            for cls in ["_1RrZR", "article__text", "content", "text"]:
                data = soup.find("p", class_=cls)
                if data:
                    txt = data.get_text().strip()
                    if txt:
                        horoscopes.append(f"🌐 *Rambler*:\n{txt[:300]}...")
                        break

        return "\n\n".join(horoscopes) or "На сегодня гороскопы временно недоступны."

    # -------------------------------------------------
    # AI‑Гороскоп (Groq)
    # -------------------------------------------------
    async def _generate_ai(self, user: dict, zodiac_sign: str) -> str:
        """Генерируем персональный гороскоп через Groq."""
        if not self.groq_client:
            return "⚠️ Сервис AI‑гороскопа временно недоступен."

        today = datetime.now().strftime("%d.%m.%Y")
        prompt = f"""
Создай персональный гороскоп на {today} для человека с:
Дата рождения: {user['date']}
Знак зодиака: {zodiac_sign}
Пол: {user['gender']}
Число судьбы: {user.get('second', 'N/A')}
Число души: {user.get('fourth', 'N/A')}

Включи:
1. Общий прогноз дня
2. Любовные отношения
3. Финансы/карьера
4. Здоровье
5. Совет дня

Стилизуй, добавь эмодзи, ограничь 800 символов.
        """

        try:
            resp = self.groq_client.chat.completions.create(
                model=Config.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "Ты астролог и нумеролог – мотивируй сейчас."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            log.error(f"❌ Ошибка Groq: {exc}")
            return f"❌ Ошибка генерации AI‑гороскопа: {exc}"

    # -------------------------------------------------
    # Интеграция: полная домашняя функция
    # -------------------------------------------------
    async def get_daily_horoscope(self, user: dict) -> str:
        """Возвращает готовый гороскоп (парсинг + AI)."""
        zodiac = user.get("zodiac", "Овен")
        cache_key = f"{zodiac}_{datetime.now().strftime('%Y-%m-%d')}"

        # Кеш? пока в памяти
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 1) Статический парсинг
        static = await self.parse_horoscopes(zodiac)

        # 2) AI‑часть, если Groq подключён
        ai = ""
        if self.groq_client:
            ai = await self._generate_ai(user, zodiac)

        # 3) Формируем итоговой текст
        if ai and not ai.startswith("❌"):
            res = f"""
✨ *ПЕРСОНАЛЬНЫЙ ГОРОСКОП* ✨
📅 {datetime.now().strftime('%d.%m.%Y')}
♈ Знак зодиака: {zodiac}

🌟 *Ваш персональный прогноз на сегодня* 🌟
{ai}

📊 *Сводка с других источников* 📊
{static}

💫 *Совет от нумеролога* 💫
Используйте число {user.get('second', '1')} как свой талисман сегодня.
"""
        else:
            res = f"""
✨ *ГОРОСКОП НА СЕГОДНЯ* ✨
📅 {datetime.now().strftime('%d.%m.%Y')}
♈ Знак зодиака: {zodiac}

{static}

💫 *Совет дня* 💫
Сегодня благоприятный день для новых начинаний! Используйте число {user.get('second', '1')} как свой талисман.
"""

        self._cache[cache_key] = res
        return res

    async def close(self) -> None:
        """Закрываем сессию aiohttp (если понадобится)."""
        await self._session.close()


# ------------- ВКЛЮЧЕНИЕ В BOT‑КОД -------------
# Просто импортировав `HoroscopeService` и создав экземпляр,
# вы сразу можете обращаться к `service.get_daily_horoscope(user_dict)`.
# Сервис готов к использованию как раньше с `HoroscopeService = ...`.



