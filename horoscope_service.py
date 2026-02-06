import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Optional, List
import re

import aiohttp
from bs4 import BeautifulSoup
from config import Config

log = logging.getLogger(__name__)

class HoroscopeService:
    def __init__(self) -> None:
        self._cache = {}
        self.api_key = Config.GROQ_API_KEY
        self.groq_client = None
        
        # Пытаемся импортировать Groq
        if self.api_key:
            try:
                from groq import AsyncGroq
                self.groq_client = AsyncGroq(api_key=self.api_key)
                log.info("✅ Groq API инициализирован")
            except ImportError:
                log.warning("⚠️ Библиотека groq не установлена. Установите: pip install groq")
            except Exception as e:
                log.error(f"❌ Ошибка инициализации Groq: {e}")
        else:
            log.warning("⚠️ GROQ_API_KEY не установлен. AI-функции будут недоступны.")

    def _get_zodiac_mapping(self) -> Dict[str, str]:
        """Возвращает маппинг русских знаков на английские"""
        return {
            "♈ Овен": "aries", "Овен": "aries",
            "♉ Телец": "taurus", "Телец": "taurus",
            "♊ Близнецы": "gemini", "Близнецы": "gemini",
            "♋ Рак": "cancer", "Рак": "cancer",
            "♌ Лев": "leo", "Лев": "leo",
            "♍ Дева": "virgo", "Дева": "virgo",
            "♎ Весы": "libra", "Весы": "libra",
            "♏ Скорпион": "scorpio", "Скорпион": "scorpio",
            "♐ Стрелец": "sagittarius", "Стрелец": "sagittarius",
            "♑ Козерог": "capricorn", "Козерог": "capricorn",
            "♒ Водолей": "aquarius", "Водолей": "aquarius",
            "♓ Рыбы": "pisces", "Рыбы": "pisces",
        }

    def _clean_zodiac_name(self, zodiac: str) -> str:
        """Очищает название знака от эмодзи"""
        cleaned = re.sub(r'^[^\w\s]+\s*', '', zodiac)
        return cleaned.strip()

    async def _fetch(self, url: str, timeout: int = 10) -> Optional[str]:
        """Выполняет HTTP-запрос с таймаутом и обработкой ошибок"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout_obj) as session:
                async with session.get(url, ssl=False) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        log.info(f"✅ Успешно получен контент с {url} ({len(html)} символов)")
                        return html
                    else:
                        log.warning(f"⚠️ Статус {resp.status} для {url}")
        except asyncio.TimeoutError:
            log.error(f"⏱️ Таймаут при запросе к {url}")
        except Exception as exc:
            log.error(f"❌ Ошибка при запросе к {url}: {type(exc).__name__}: {exc}")
        return None

    async def _parse_mail_ru(self, zodiac_en: str) -> Optional[str]:
        """Парсит гороскоп с Horo.mail.ru"""
        url = f"https://horo.mail.ru/prediction/{zodiac_en}/today/"
        log.info(f"🔍 Парсинг Mail.ru: {url}")
        
        html = await self._fetch(url)
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")
            
            content = None
            article = soup.find("div", class_="article__item")
            if article:
                paragraphs = article.find_all("p")
                if paragraphs:
                    content = " ".join([p.get_text(strip=True) for p in paragraphs])
            
            if not content:
                article = soup.find("article")
                if article:
                    paragraphs = article.find_all("p")
                    if paragraphs:
                        content = " ".join([p.get_text(strip=True) for p in paragraphs])
            
            if not content:
                article = soup.find("div", {"data-qa": "Article"})
                if article:
                    paragraphs = article.find_all("p")
                    if paragraphs:
                        content = " ".join([p.get_text(strip=True) for p in paragraphs])
            
            if content and len(content) > 50:
                log.info(f"✅ Mail.ru: получено {len(content)} символов")
                return content[:800]
            else:
                log.warning("⚠️ Mail.ru: контент не найден или слишком короткий")
                
        except Exception as e:
            log.error(f"❌ Ошибка парсинга Mail.ru: {e}")
        
        return None

    async def _parse_rambler(self, zodiac_en: str) -> Optional[str]:
        """Парсит гороскоп с Rambler"""
        url = f"https://horoscopes.rambler.ru/{zodiac_en}/"
        log.info(f"🔍 Парсинг Rambler: {url}")
        
        html = await self._fetch(url)
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")
            
            main_div = soup.find("div", {"data-mt-part": "article"})
            if main_div:
                paragraph = main_div.find("p")
                if paragraph:
                    content = paragraph.get_text(strip=True)
                    if len(content) > 50:
                        log.info(f"✅ Rambler: получено {len(content)} символов")
                        return content[:800]
            
            article = soup.find("article")
            if article:
                paragraph = article.find("p")
                if paragraph:
                    content = paragraph.get_text(strip=True)
                    if len(content) > 50:
                        log.info(f"✅ Rambler: получено {len(content)} символов")
                        return content[:800]
            
            log.warning("⚠️ Rambler: контент не найден")
                
        except Exception as e:
            log.error(f"❌ Ошибка парсинга Rambler: {e}")
        
        return None

    async def parse_horoscopes(self, zodiac_sign: str) -> Dict[str, str]:
        """Парсит гороскопы из нескольких источников параллельно"""
        zodiac_clean = self._clean_zodiac_name(zodiac_sign)
        zodiac_map = self._get_zodiac_mapping()
        zodiac_en = zodiac_map.get(zodiac_clean, zodiac_map.get(zodiac_sign, "aries"))
        
        log.info(f"🔮 Начинаем парсинг для {zodiac_sign} ({zodiac_en})")
        
        tasks = [
            self._parse_mail_ru(zodiac_en),
            self._parse_rambler(zodiac_en),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        horoscopes = {}
        if results[0] and not isinstance(results[0], Exception):
            horoscopes["Mail.ru"] = results[0]
        if results[1] and not isinstance(results[1], Exception):
            horoscopes["Rambler"] = results[1]
        
        log.info(f"✅ Получено гороскопов: {len(horoscopes)} из 2")
        return horoscopes

    def _generate_basic_horoscope(self, zodiac: str, horoscopes: Dict[str, str]) -> str:
        """Генерирует эмоциональный гороскоп с разделами БЕЗ AI"""
        today = datetime.now().strftime("%d.%m.%Y")
        zodiac_clean = self._clean_zodiac_name(zodiac)
        
        if not horoscopes:
            return (
                f"🔮 *Гороскоп для {zodiac_clean} на {today}*\n\n"
                f"К сожалению, звезды сегодня скрыты за облаками тайны... 🌫️\n\n"
                f"Но помните: ваша судьба в ваших руках! Действуйте с верой в лучшее, "
                f"и Вселенная откроет перед вами нужные двери. ✨\n\n"
                f"_Попробуйте обновить гороскоп позже._"
            )
        
        # Генерируем рейтинг дня (на основе количества источников и длины текста)
        rating = min(10, 6 + len(horoscopes) * 2)
        stars = "⭐" * rating
        
        # Генерируем энергетику сфер (случайно, но реалистично)
        import random
        random.seed(datetime.now().day)  # Одинаковый рейтинг в течение дня
        
        love_energy = random.randint(60, 95)
        career_energy = random.randint(55, 90)
        money_energy = random.randint(65, 95)
        health_energy = random.randint(50, 85)
        luck_energy = random.randint(60, 90)
        
        def make_bar(percent):
            filled = int(percent / 10)
            return "█" * filled + "░" * (10 - filled)
        
        result = []
        result.append(f"━━━━━━━━━━━━━━━━━━━━━")
        result.append(f"🔮 *ГОРОСКОП на {today}*")
        result.append(f"*{zodiac_clean}*")
        result.append(f"━━━━━━━━━━━━━━━━━━━━━\n")
        
        result.append(f"⭐ *РЕЙТИНГ ДНЯ: {rating}/10* {stars[:5]}")
        result.append("")
        
        result.append(f"📊 *ЭНЕРГЕТИКА СФЕР:*\n")
        result.append(f"❤️ Любовь:     {make_bar(love_energy)} {love_energy}%")
        result.append(f"💼 Карьера:    {make_bar(career_energy)} {career_energy}%")
        result.append(f"💰 Финансы:    {make_bar(money_energy)} {money_energy}%")
        result.append(f"💚 Здоровье:   {make_bar(health_energy)} {health_energy}%")
        result.append(f"🎯 Удача:      {make_bar(luck_energy)} {luck_energy}%\n")
        
        result.append(f"━━━━━━━━━━━━━━━━━━━━━\n")
        
        # Показываем источники
        result.append("📰 *Прогноз от астрологов:*\n")
        
        for i, (source, text) in enumerate(horoscopes.items(), 1):
            result.append(f"✨ *{source}:*")
            result.append(f"{text}\n")
        
        # Добавляем разделы с советами
        result.append("━━━━━━━━━━━━━━━━━━━━━")
        result.append("💫 *Основные сферы дня:*\n")
        
        result.append(f"❤️ *Любовь и отношения:* {love_energy}%")
        result.append("Прислушайтесь к своему сердцу. Звезды благоволят искренности и открытости. "
                     "Не бойтесь проявлять чувства — это укрепит ваши связи.\n")
        
        result.append(f"💼 *Карьера и финансы:* {career_energy}%")
        result.append("Сегодня благоприятный день для важных решений. Доверяйте своей интуиции, "
                     "но не забывайте про практичность. Возможны неожиданные возможности!\n")
        
        result.append(f"💚 *Здоровье и энергия:* {health_energy}%")
        result.append("Прислушивайтесь к сигналам своего тела. Найдите время для отдыха и восстановления. "
                     "Даже 15 минут медитации или прогулки принесут пользу.\n")
        
        result.append("━━━━━━━━━━━━━━━━━━━━━\n")
        
        result.append("🎯 *Совет дня от звезд:*")
        result.append("Будьте открыты переменам и новым возможностям. Ваша энергия сегодня особенно сильна — "
                     "используйте её для достижения целей!\n")
        
        result.append("⚠️ *На что обратить внимание:*")
        result.append("Избегайте импульсивных решений в важных вопросах. Дайте себе время обдумать ситуацию. "
                     "Терпение — ваш союзник сегодня.")
        
        return "\n".join(result)

    async def _generate_ai_aggregated(
        self, 
        user_data: Dict, 
        zodiac: str, 
        horoscopes: Dict[str, str]
    ) -> str:
        """Генерирует эмоциональный персонализированный гороскоп с AI"""
        
        if not self.groq_client:
            log.warning("⚠️ Groq client недоступен, используем базовую генерацию")
            return self._generate_basic_horoscope(zodiac, horoscopes)
        
        if not horoscopes:
            return self._generate_basic_horoscope(zodiac, horoscopes)

        today = datetime.now().strftime("%d.%m.%Y")
        zodiac_clean = self._clean_zodiac_name(zodiac)
        
        # Подготавливаем контекст из источников
        context_parts = []
        for source, text in horoscopes.items():
            context_parts.append(f"📰 {source}:\n{text}")
        context = "\n\n".join(context_parts)
        
        # Извлекаем данные матрицы
        matrix = user_data.get("matrix", {})
        additional = matrix.get("additional", [])
        soul_number = additional[1] if len(additional) > 1 else "не указано"
        
        prompt = f"""Ты — вдохновляющий астролог с мистическим даром. Создай ЭМОЦИОНАЛЬНЫЙ гороскоп на {today} для знака {zodiac_clean}.

📊 ДАННЫЕ ИЗ ИСТОЧНИКОВ (используй ОБЯЗАТЕЛЬНО!):
{context}

🔮 ПЕРСОНАЛЬНЫЕ ДАННЫЕ:
• Число души: {soul_number}

📝 ТВОЯ ЗАДАЧА:
1. Прочитай прогнозы и объедини их в СВЯЗНЫЙ эмоциональный рассказ
2. Оцени день по 10-бальной шкале (рейтинг дня)
3. Дай энергетику для каждой сферы (в процентах 0-100%)
4. Используй конкретную информацию из источников!
5. Добавь мистику и вдохновение
6. Учти влияние числа души

🎯 СТРУКТУРА (СТРОГО СОБЛЮДАЙ):

━━━━━━━━━━━━━━━━━━━━━
🔮 *ГОРОСКОП на {today}*
*{zodiac_clean}*
━━━━━━━━━━━━━━━━━━━━━

⭐ *РЕЙТИНГ ДНЯ: [X]/10* ⭐⭐⭐⭐⭐

📊 *ЭНЕРГЕТИКА СФЕР:*

❤️ Любовь:     ████████░░ [XX]%
💼 Карьера:    ████████░░ [XX]%
💰 Финансы:    ████████░░ [XX]%
💚 Здоровье:   ████████░░ [XX]%
🎯 Удача:      ████████░░ [XX]%

━━━━━━━━━━━━━━━━━━━━━

📰 *Что говорят астрологи:*

[Краткое упоминание ключевых моментов из источников]

━━━━━━━━━━━━━━━━━━━━━
💫 *ДЕТАЛЬНЫЙ ПРОГНОЗ*
━━━━━━━━━━━━━━━━━━━━━

❤️ *Любовь и отношения:* [XX]%
[2-3 предложения с конкретикой]

💼 *Карьера и финансы:* [XX]%
[2-3 предложения с конкретикой]

💚 *Здоровье:* [XX]%
[1-2 предложения]

━━━━━━━━━━━━━━━━━━━━━

🎯 *Совет дня:*
[1-2 предложения - вдохновляющий совет]

⚠️ *Предостережение:*
[1 предложение - мягкое предупреждение]

🔢 *Влияние числа души ({soul_number}):*
[1-2 предложения о влиянии числа на этот день]

ТРЕБОВАНИЯ:
• Рейтинг: число от 1 до 10 (реалистично оценивай день)
• Энергетика: проценты от 50% до 95% (не все 100%)
• Прогресс-бары: точное количество █ (10 = 100%, 8 = 80% и т.д.)
• Используй факты из источников!
• Будь эмоциональным и вдохновляющим
• Говори от лица звезд напрямую
• Длина: 700-900 символов
• Только на русском языке"""

        try:
            model = Config.GROQ_MODEL or "llama-3.1-8b-instant"
            log.info(f"🤖 Генерация AI-гороскопа с моделью {model}")
            
            completion = await self.groq_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system", 
                        "content": "Ты — вдохновляющий астролог-мистик. Твои прогнозы эмоциональны, точны и основаны на реальных данных. Ты ВСЕГДА включаешь рейтинг дня и энергетику сфер в процентах."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1500,
                top_p=0.9,
            )
            
            ai_response = completion.choices[0].message.content.strip()
            log.info(f"✅ AI-гороскоп сгенерирован ({len(ai_response)} символов)")
            
            return ai_response
            
        except Exception as e:
            log.error(f"❌ Ошибка генерации AI: {type(e).__name__}: {e}")
            return self._generate_basic_horoscope(zodiac, horoscopes)

    async def get_daily_horoscope(self, user_data: Dict) -> str:
        """Главный метод для получения дневного гороскопа"""
        zodiac = user_data.get("zodiac", "Овен")
        today = datetime.now().strftime("%Y-%m-%d")
        cache_key = f"{zodiac}_{today}"

        if cache_key in self._cache:
            log.info(f"📦 Используем кешированный гороскоп для {zodiac}")
            return self._cache[cache_key]

        log.info(f"🚀 Начинаем генерацию гороскопа для {zodiac}")
        
        # 1. Собираем данные из интернета
        horoscopes = await self.parse_horoscopes(zodiac)
        
        # 2. Генерируем финальный прогноз
        if self.groq_client and horoscopes:
            log.info("🤖 Используем AI для генерации")
            final_forecast = await self._generate_ai_aggregated(user_data, zodiac, horoscopes)
        else:
            log.info("📝 Используем базовую генерацию")
            final_forecast = self._generate_basic_horoscope(zodiac, horoscopes)
        
        # Сохраняем в кеш
        self._cache[cache_key] = final_forecast
        log.info(f"✅ Гороскоп готов и сохранен в кеш")
        
        return final_forecast
