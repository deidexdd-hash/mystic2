"""
PREMIUM HOROSCOPE SERVICE
Улучшенная версия с детальной энергетикой, благоприятными часами,
прогнозом по времени суток и глубокой интеграцией с матрицей Пифагора
"""
import asyncio
import logging
import os
from datetime import datetime, time
from typing import Dict, Optional, List, Tuple
import re
import random

import aiohttp
from bs4 import BeautifulSoup
from config import Config

log = logging.getLogger(__name__)


class PremiumHoroscopeService:
    def __init__(self) -> None:
        self._cache = {}
        self.api_key = Config.GROQ_API_KEY
        self.groq_client = None
        
        # Инициализация Groq
        if self.api_key:
            try:
                from groq import AsyncGroq
                self.groq_client = AsyncGroq(api_key=self.api_key)
                log.info("✅ Groq API инициализирован (Premium)")
            except ImportError:
                log.warning("⚠️ Библиотека groq не установлена")
            except Exception as e:
                log.error(f"❌ Ошибка инициализации Groq: {e}")
        else:
            log.warning("⚠️ GROQ_API_KEY не установлен")

    # ==================== БАЗОВЫЕ МЕТОДЫ (из оригинала) ====================
    
    def _get_zodiac_mapping(self) -> Dict[str, str]:
        """Маппинг русских знаков на английские"""
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
        """HTTP-запрос с таймаутом"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout_obj) as session:
                async with session.get(url, ssl=False) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        log.info(f"✅ Получен контент с {url}")
                        return html
                    else:
                        log.warning(f"⚠️ Статус {resp.status} для {url}")
        except Exception as exc:
            log.error(f"❌ Ошибка запроса к {url}: {exc}")
        return None

    async def _parse_mail_ru(self, zodiac_en: str) -> Optional[str]:
        """Парсит Mail.ru"""
        url = f"https://horo.mail.ru/prediction/{zodiac_en}/today/"
        html = await self._fetch(url)
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")
            article = soup.find("div", class_="article__item")
            if article:
                paragraphs = article.find_all("p")
                if paragraphs:
                    content = " ".join([p.get_text(strip=True) for p in paragraphs])
                    if len(content) > 50:
                        return content[:800]
        except Exception as e:
            log.error(f"❌ Ошибка парсинга Mail.ru: {e}")
        return None

    async def _parse_rambler(self, zodiac_en: str) -> Optional[str]:
        """Парсит Rambler"""
        url = f"https://horoscopes.rambler.ru/{zodiac_en}/"
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
                        return content[:800]
        except Exception as e:
            log.error(f"❌ Ошибка парсинга Rambler: {e}")
        return None

    async def parse_horoscopes(self, zodiac_sign: str) -> Dict[str, str]:
        """Парсит гороскопы параллельно"""
        zodiac_clean = self._clean_zodiac_name(zodiac_sign)
        zodiac_map = self._get_zodiac_mapping()
        zodiac_en = zodiac_map.get(zodiac_clean, zodiac_map.get(zodiac_sign, "aries"))
        
        log.info(f"🔮 Парсинг для {zodiac_sign} ({zodiac_en})")
        
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
        
        log.info(f"✅ Получено гороскопов: {len(horoscopes)}")
        return horoscopes

    # ==================== ПРЕМИУМ ФУНКЦИИ ====================
    
    def _get_lucky_symbols(self, zodiac_clean: str, matrix_data: Dict) -> Dict:
        """Генерирует счастливые символы на основе знака и матрицы"""
        
        # Базовые символы по знакам
        zodiac_symbols = {
            "Овен": {
                "numbers": [1, 9, 19],
                "colors": ["красный", "оранжевый"],
                "stone": "рубин",
                "aroma": "корица"
            },
            "Телец": {
                "numbers": [6, 15, 24],
                "colors": ["зеленый", "розовый"],
                "stone": "изумруд",
                "aroma": "роза"
            },
            "Близнецы": {
                "numbers": [5, 14, 23],
                "colors": ["желтый", "голубой"],
                "stone": "цитрин",
                "aroma": "мята"
            },
            "Рак": {
                "numbers": [2, 7, 16],
                "colors": ["серебряный", "белый"],
                "stone": "лунный камень",
                "aroma": "жасмин"
            },
            "Лев": {
                "numbers": [1, 10, 19],
                "colors": ["золотой", "оранжевый"],
                "stone": "янтарь",
                "aroma": "сандал"
            },
            "Дева": {
                "numbers": [5, 14, 23],
                "colors": ["бежевый", "коричневый"],
                "stone": "сапфир",
                "aroma": "лаванда"
            },
            "Весы": {
                "numbers": [6, 15, 24],
                "colors": ["розовый", "голубой"],
                "stone": "опал",
                "aroma": "иланг-иланг"
            },
            "Скорпион": {
                "numbers": [9, 18, 27],
                "colors": ["темно-красный", "черный"],
                "stone": "гранат",
                "aroma": "пачули"
            },
            "Стрелец": {
                "numbers": [3, 12, 21],
                "colors": ["фиолетовый", "синий"],
                "stone": "аметист",
                "aroma": "кедр"
            },
            "Козерог": {
                "numbers": [8, 17, 26],
                "colors": ["черный", "серый"],
                "stone": "оникс",
                "aroma": "мирра"
            },
            "Водолей": {
                "numbers": [4, 13, 22],
                "colors": ["голубой", "серебряный"],
                "stone": "аквамарин",
                "aroma": "эвкалипт"
            },
            "Рыбы": {
                "numbers": [7, 16, 25],
                "colors": ["морская волна", "фиолетовый"],
                "stone": "аметист",
                "aroma": "лотос"
            }
        }
        
        base_symbols = zodiac_symbols.get(zodiac_clean, zodiac_symbols["Овен"])
        
        # Добавляем влияние матрицы
        additional = matrix_data.get("additional", [])
        if len(additional) > 1:
            soul_number = additional[1]
            if soul_number in [1, 2, 3, 4, 5, 6, 7, 8, 9]:
                base_symbols["numbers"].insert(0, soul_number)
        
        return base_symbols

    def _calculate_favorable_hours(self, zodiac_clean: str) -> Dict:
        """Рассчитывает благоприятные часы на основе знака"""
        
        # Упрощенная планетарная система часов
        current_hour = datetime.now().hour
        
        # Базовые благоприятные периоды по знакам
        favorable_patterns = {
            "Овен": [(8, 10), (14, 16), (19, 21)],  # утро, день, вечер
            "Телец": [(9, 11), (15, 17), (20, 22)],
            "Близнецы": [(7, 9), (13, 15), (18, 20)],
            "Рак": [(6, 8), (12, 14), (19, 21)],
            "Лев": [(8, 10), (14, 16), (20, 22)],
            "Дева": [(7, 9), (13, 15), (18, 20)],
            "Весы": [(9, 11), (15, 17), (20, 22)],
            "Скорпион": [(8, 10), (14, 16), (21, 23)],
            "Стрелец": [(7, 9), (13, 15), (19, 21)],
            "Козерог": [(8, 10), (14, 16), (20, 22)],
            "Водолей": [(7, 9), (13, 15), (18, 20)],
            "Рыбы": [(9, 11), (15, 17), (20, 22)]
        }
        
        favorable = favorable_patterns.get(zodiac_clean, [(8, 10), (14, 16), (19, 21)])
        
        # Неблагоприятные часы (общие)
        unfavorable = [(12, 13), (17, 18)]
        
        return {
            "favorable": favorable,
            "unfavorable": unfavorable
        }

    def _analyze_matrix_influence(self, matrix_data: Dict, zodiac_clean: str) -> str:
        """Анализирует влияние матрицы на текущий день"""
        
        cells = matrix_data.get("cells", {})
        additional = matrix_data.get("additional", [])
        
        # Число души
        soul_number = additional[1] if len(additional) > 1 else 0
        
        # Число судьбы  
        destiny_number = additional[0] if len(additional) > 0 else 0
        
        # Анализ активности чисел
        active_numbers = []
        for num, count in cells.items():
            if count > 0:
                active_numbers.append((int(num), count))
        
        # Формируем анализ
        analysis_parts = []
        
        if soul_number:
            soul_influence = {
                1: "Ваше число души (1) сегодня усиливает лидерские качества. День для инициативы!",
                2: "Число души (2) делает вас особенно чувствительным к энергиям других. Используйте это для гармонии.",
                3: "Ваше число души (3) активирует творческую энергию. Идеальный день для самовыражения!",
                4: "Число души (4) призывает к практичности и стабильности. Займитесь конкретными делами.",
                5: "Ваше число души (5) открывает новые возможности. Будьте готовы к переменам!",
                6: "Число души (6) усиливает чувство ответственности. Помогите близким.",
                7: "Ваше число души (7) активирует интуицию на 140%! Доверяйте внутреннему голосу.",
                8: "Число души (8) дает силу для важных решений. День для амбициозных целей!",
                9: "Ваше число души (9) расширяет сознание. Время для духовных практик."
            }
            analysis_parts.append(soul_influence.get(soul_number, ""))
        
        # Проверяем сильные числа в матрице
        strong_numbers = [num for num, count in active_numbers if count >= 3]
        if strong_numbers:
            analysis_parts.append(
                f"Числа {', '.join(map(str, strong_numbers))} особенно активны в вашей матрице — "
                f"их энергия усилена сегодня!"
            )
        
        return " ".join(analysis_parts)

    def _calculate_detailed_energy(self, base_energy: int) -> Dict[str, int]:
        """Рассчитывает детальную энергетику по подсферам"""
        
        # Генерируем вариации на основе базовой энергии
        variation = random.randint(-10, 10)
        
        return {
            "romance": max(50, min(95, base_energy + variation)),
            "family": max(50, min(95, base_energy + random.randint(-8, 8))),
            "friendship": max(50, min(95, base_energy + random.randint(-5, 5))),
        }

    def _get_time_of_day_forecast(self, zodiac_clean: str, energy_level: int) -> Dict[str, str]:
        """Генерирует прогноз по времени суток"""
        
        morning_moods = [
            "Утро начнется с позитивной ноты. Идеальное время для планирования дня.",
            "Утренние часы принесут ясность мыслей. Займитесь важными решениями.",
            "Начало дня может быть немного медленным. Дайте себе время проснуться.",
        ]
        
        day_moods = [
            "Дневное время будет продуктивным. Используйте пик энергии для важных дел.",
            "Середина дня — время для активности и общения. Не упускайте возможности!",
            "День может принести неожиданности. Будьте гибкими в планах.",
        ]
        
        evening_moods = [
            "Вечер располагает к отдыху и размышлениям. Проведите время с близкими.",
            "Вечерние часы благоприятны для творчества. Займитесь хобби.",
            "Завершите день спокойно. Подведите итоги и отпустите напряжение.",
        ]
        
        # Выбираем на основе уровня энергии
        morning_idx = 0 if energy_level > 75 else (1 if energy_level > 60 else 2)
        day_idx = 0 if energy_level > 75 else (1 if energy_level > 60 else 2)
        evening_idx = random.randint(0, 2)
        
        return {
            "morning": morning_moods[morning_idx],
            "day": day_moods[day_idx],
            "evening": evening_moods[evening_idx]
        }

    def _make_progress_bar(self, percent: int, length: int = 10) -> str:
        """Создает прогресс-бар"""
        filled = int(percent / 10)
        filled = max(0, min(length, filled))
        return "█" * filled + "░" * (length - filled)

    async def _generate_premium_horoscope(
        self,
        user_data: Dict,
        zodiac: str,
        horoscopes: Dict[str, str]
    ) -> str:
        """Генерирует премиум гороскоп с расширенной аналитикой"""
        
        today = datetime.now().strftime("%d.%m.%Y")
        zodiac_clean = self._clean_zodiac_name(zodiac)
        
        # Получаем данные матрицы
        matrix = user_data.get("matrix", {})
        
        # Базовые энергии (с вариацией)
        love_energy = random.randint(65, 92)
        career_energy = random.randint(60, 88)
        health_energy = random.randint(70, 95)
        money_energy = random.randint(55, 85)
        luck_energy = random.randint(60, 90)
        
        # Рейтинг дня
        rating = random.randint(6, 9)
        
        # Детальные энергии
        love_detailed = self._calculate_detailed_energy(love_energy)
        career_detailed = {
            "work": max(50, min(95, career_energy + random.randint(-5, 5))),
            "business": max(50, min(95, career_energy + random.randint(-8, 8))),
            "finances": money_energy
        }
        health_detailed = {
            "physical": max(50, min(95, health_energy + random.randint(-5, 5))),
            "emotional": max(50, min(95, health_energy + random.randint(-5, 5)))
        }
        
        # Благоприятные часы
        hours_data = self._calculate_favorable_hours(zodiac_clean)
        
        # Счастливые символы
        symbols = self._get_lucky_symbols(zodiac_clean, matrix)
        
        # Анализ матрицы
        matrix_influence = self._analyze_matrix_influence(matrix, zodiac_clean)
        
        # Прогноз по времени суток
        avg_energy = (love_energy + career_energy + health_energy) // 3
        time_forecast = self._get_time_of_day_forecast(zodiac_clean, avg_energy)
        
        # Формируем гороскоп
        result = []
        
        # Заголовок
        result.append("━━━━━━━━━━━━━━━━━━━━━")
        result.append(f"🔮 *PREMIUM ГОРОСКОП*")
        result.append(f"*{zodiac_clean}*")
        result.append("━━━━━━━━━━━━━━━━━━━━━\n")
        
        # Рейтинг
        stars = "⭐" * rating + "☆" * (10 - rating)
        result.append(f"⭐ *Рейтинг дня: {rating}/10* {stars}\n")
        
        # Общая энергия
        overall_energy = (love_energy + career_energy + health_energy) // 3
        result.append(f"⚡ *Общая энергия: {overall_energy}%*")
        result.append(f"{self._make_progress_bar(overall_energy)}\n")
        
        # Прогноз по времени суток
        result.append("━━━━━━━━━━━━━━━━━━━━━")
        result.append("🌅 *ПРОГНОЗ ПО ВРЕМЕНИ СУТОК*")
        result.append("━━━━━━━━━━━━━━━━━━━━━\n")
        
        result.append(f"🌅 *УТРО (6:00-12:00):*")
        result.append(f"{time_forecast['morning']}\n")
        
        result.append(f"☀️ *ДЕНЬ (12:00-18:00):*")
        result.append(f"{time_forecast['day']}\n")
        
        result.append(f"🌙 *ВЕЧЕР (18:00-24:00):*")
        result.append(f"{time_forecast['evening']}\n")
        
        # Детальная энергетика
        result.append("━━━━━━━━━━━━━━━━━━━━━")
        result.append("📊 *ДЕТАЛЬНАЯ ЭНЕРГЕТИКА*")
        result.append("━━━━━━━━━━━━━━━━━━━━━\n")
        
        result.append(f"❤️ *ЛЮБОВЬ И ОТНОШЕНИЯ* ({love_energy}%)")
        result.append(f"├─ Романтика:  {self._make_progress_bar(love_detailed['romance'])} {love_detailed['romance']}%")
        result.append(f"├─ Семья:      {self._make_progress_bar(love_detailed['family'])} {love_detailed['family']}%")
        result.append(f"└─ Дружба:     {self._make_progress_bar(love_detailed['friendship'])} {love_detailed['friendship']}%\n")
        
        result.append(f"💼 *КАРЬЕРА И ДЕНЬГИ* ({career_energy}%)")
        result.append(f"├─ Работа:     {self._make_progress_bar(career_detailed['work'])} {career_detailed['work']}%")
        result.append(f"├─ Бизнес:     {self._make_progress_bar(career_detailed['business'])} {career_detailed['business']}%")
        result.append(f"└─ Финансы:    {self._make_progress_bar(career_detailed['finances'])} {career_detailed['finances']}%\n")
        
        result.append(f"💚 *ЗДОРОВЬЕ* ({health_energy}%)")
        result.append(f"├─ Физическое: {self._make_progress_bar(health_detailed['physical'])} {health_detailed['physical']}%")
        result.append(f"└─ Эмоциональное: {self._make_progress_bar(health_detailed['emotional'])} {health_detailed['emotional']}%\n")
        
        # Благоприятные часы
        result.append("━━━━━━━━━━━━━━━━━━━━━")
        result.append("🕐 *БЛАГОПРИЯТНЫЕ ЧАСЫ*")
        result.append("━━━━━━━━━━━━━━━━━━━━━\n")
        
        for start, end in hours_data['favorable']:
            activities = ["переговоры", "начинания", "важные решения"]
            activity = random.choice(activities)
            result.append(f"✨ {start:02d}:00-{end:02d}:00 ({activity})")
        
        result.append("\n⚠️ *Избегать:*")
        for start, end in hours_data['unfavorable']:
            result.append(f"🚫 {start:02d}:00-{end:02d}:00")
        
        result.append("")
        
        # Источники (если есть)
        if horoscopes:
            result.append("━━━━━━━━━━━━━━━━━━━━━")
            result.append("📰 *ЧТО ГОВОРЯТ АСТРОЛОГИ*")
            result.append("━━━━━━━━━━━━━━━━━━━━━\n")
            
            for source, text in list(horoscopes.items())[:1]:  # берем только первый источник
                short_text = text[:200] + "..." if len(text) > 200 else text
                result.append(f"✨ *{source}:* {short_text}\n")
        
        # Персональный анализ
        if matrix_influence:
            result.append("━━━━━━━━━━━━━━━━━━━━━")
            result.append("🔮 *ПЕРСОНАЛЬНЫЙ АНАЛИЗ*")
            result.append("━━━━━━━━━━━━━━━━━━━━━\n")
            result.append(f"{matrix_influence}\n")
        
        # Счастливые символы
        result.append("━━━━━━━━━━━━━━━━━━━━━")
        result.append("🔢 *СЧАСТЛИВЫЕ СИМВОЛЫ*")
        result.append("━━━━━━━━━━━━━━━━━━━━━\n")
        
        result.append(f"Числа: {', '.join(map(str, symbols['numbers']))}")
        result.append(f"Цвета: {', '.join(symbols['colors'])}")
        result.append(f"Камень: {symbols['stone']}")
        result.append(f"Аромат: {symbols['aroma']}")
        
        return "\n".join(result)

    async def get_daily_horoscope(self, user_data: Dict) -> str:
        """Главный метод получения премиум гороскопа"""
        zodiac = user_data.get("zodiac", "Овен")
        today = datetime.now().strftime("%Y-%m-%d")
        cache_key = f"premium_{zodiac}_{today}"

        if cache_key in self._cache:
            log.info(f"📦 Кешированный гороскоп для {zodiac}")
            return self._cache[cache_key]

        log.info(f"🚀 Генерация PREMIUM гороскопа для {zodiac}")
        
        # Парсим источники
        try:
            horoscopes = await self.parse_horoscopes(zodiac)
        except Exception as e:
            log.error(f"❌ Ошибка парсинга: {e}")
            horoscopes = {}
        
        # Генерируем премиум версию
        final_forecast = await self._generate_premium_horoscope(
            user_data, zodiac, horoscopes
        )
        
        # Кешируем
        self._cache[cache_key] = final_forecast
        log.info(f"✅ Premium гороскоп готов")
        
        return final_forecast
