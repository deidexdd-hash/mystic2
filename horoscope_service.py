# horoscope_service_simple.py
import requests
from datetime import datetime
from config import Config
from bs4 import BeautifulSoup
import time# horoscope_service.py
"""
Сервис парсинга гороскопов + генерацию AI‑гороскопа через Groq
"""

from datetime import datetime
import asyncio
import requests
from bs4 import BeautifulSoup
from config import Config

# ---- Попытка импортировать groq (может не быть) ----
try:
    from groq import Groq               # версия 0.3.x+
    GROQ_AVAILABLE = True
except Exception:
    # Фallback: g俄罗斯си вокруг API
    try:
        import groq
        if hasattr(groq, "Groq"):
            Groq = groq.Groq
            GROQ_AVAILABLE = True
        elif hasattr(groq, "Client"):
            Groq = groq.Client
            GROQ_AVAILABLE = True
        else:
            GROQ_AVAILABLE = False
    except Exception:
        GROQ_AVAILABLE = False


class HoroscopeService:
    def __init__(self):
        """Инициализация клиента Groq (если API‑ключ задать)"""
        self.groq_client = None
        if GROQ_AVAILABLE and Config.GROQ_API_KEY:
            try:
                self.groq_client = Groq(api_key=Config.GROQ_API_KEY)
            except Exception as e:
                print(f"❌ Инициализация Groq не удалась: {e}")
                self.groq_client = None

        # кэшь гороскопов по дням (только в памяти пока)
        self._cache = {}

    # -------------------------------------------------
    # 1.  ПАРСИНГ ОТ СОБСТВЕННЫХ ИЗ РАЗЛИЧНЫХ САЙТОВ
    # -------------------------------------------------
    async def _fetch_page(self, session, url):
        try:
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    return await response.text()
        except Exception:
            return ""

    async def parse_horoscopes(self, zodiac_sign: str) -> str:
        """Парсим гороскопы с главных сайтов по запросу знак зодиака."""
        horoscopes = []
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

        async with aiohttp.ClientSession() as session:
            # Mail.ru
            try:
                url = f"https://horo.mail.ru/prediction/{zodiac_en}/today/"
                html = await self._fetch_page(session, url)
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    elem = soup.find("div", class_="article__item")
                    if elem:
                        text = elem.get_text().strip()
                        if text:
                            horoscopes.append(f"📧 *Mail.ru*:\n{text[:300]}...")
            except Exception as e:
                print("❌ Mail.ru:", e)

            # Rambler
            try:
                url = f"https://horoscopes.rambler.ru/{zodiac_en}/"
                html = await self._fetch_page(session, url)
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    for cls in ["_1RrZR", "article__text", "content", "text"]:
                        elem = soup.find("p", class_=cls)
                        if elem:
                            text = elem.get_text().strip()
                            if text:
                                horoscopes.append(f"🌐 *Rambler*:\n{text[:300]}...")
                                break
            except Exception as e:
                print("❌ Rambler:", e)

        return "\n\n".join(horoscopes) if horoscopes else "На сегодня гороскопы временно недоступны."

    # -------------------------------------------------
    # 2.  ИНТЕГР. AI‑ГОРоскопА
    # -------------------------------------------------
    async def generate_ai_horoscope(self, user_data: dict, zodiac_sign: str) -> str:
        """Генерирует персональный гороскоп через Groq AI."""
        if not self.groq_client:
            return "⚠️ Сервис генерации гороскопов временно недоступен."

        today = datetime.now().strftime("%d.%m.%Y")
        prompt = f"""
        Создай персональный гороскоп на {today} для человека со следующими данными:
        
        Дата рождения: {user_data['date']}
        Знак зодиака: {zodiac_sign}
        Пол: {user_data['gender']}
        Число судьбы: {user_data.get('second', 'N/A')}
        Число души: {user_data.get('fourth', 'N/A')}
        
        Включи:
        1. Общий прогноз дня
        2. Любовные отношения
        3. Финансы/карьера
        4. Здоровье
        5. Совет дня
        
        Стилизуй, добавь эмодзи, длина < 800 символов
        """
        try:
            resp = self.groq_client.chat.completions.create(
                model=Config.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "Ты профессиональный астролог и нумеролог."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"❌ Ошибка генерации гороскопа: {e}"

    # -------------------------------------------------
    # 3.  Интеграция with cache
    # -------------------------------------------------
    async def get_daily_horoscope(self, user_data: dict) -> str:
        """Получает полный гороскоп (парсинг + AI) и кеширует по дню/знак."""
        zodiac_sign = user_data.get("zodiac", "Овен")
        key = f"{zodiac_sign}_{datetime.now().strftime('%Y-%m-%d')}"

        # кэш? – для простоты в памяти
        if key in self._cache:
            return self._cache[key]

        parsed = await self.parse_horoscopes(zodiac_sign)

        ai_horoscope = ""
        if self.groq_client:
            ai_horoscope = await self.generate_ai_horoscope(user_data, zodiac_sign)

        if ai_horoscope and not ai_horoscope.startswith("❌"):
            result = f"""
✨ *ПЕРСОНАЛЬНЫЙ ГОРОСКОП* ✨
📅 {datetime.now().strftime('%d.%m.%Y')}
♈ Знак зодиака: {zodiac_sign}

🌟 *Ваш персональный прогноз на сегодня* 🌟

{ai_horoscope}

📊 *Сводка с других источников* 📊

{parsed}

💫 *Совет от нумеролога* 💫
Используйте число {user_data.get('second', '1')} как ваш талисман!
"""
        else:
            result = f"""
✨ *ГОРОСКОП НА СЕГОДНЯ* ✨
📅 {datetime.now().strftime('%d.%m.%Y')}
♈ Знак зодиака: {zodiac_sign}

{parsed}

💫 *Совет дня* 💫
Сегодня благоприятный день для новых начинаний! Используйте число {user_data.get('second', '1')} как ваш талисман.
"""

        self._cache[key] = result
        return result



class SimpleHoroscopeService:
    def __init__(self):
        self.cache = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def parse_horoscopes(self, zodiac_sign: str) -> str:
        """Парсинг гороскопов с использованием requests вместо aiohttp"""
        horoscopes = []
        
        zodiac_map = {
            "Овен": "aries", "Телец": "taurus", "Близнецы": "gemini",
            "Рак": "cancer", "Лев": "leo", "Дева": "virgo",
            "Весы": "libra", "Скорпион": "scorpio", "Стрелец": "sagittarius",
            "Козерог": "capricorn", "Водолей": "aquarius", "Рыбы": "pisces"
        }
        
        zodiac_en = zodiac_map.get(zodiac_sign, "aries")
        
        # Парсинг с Mail.ru
        try:
            url = f"https://horo.mail.ru/prediction/{zodiac_en}/today/"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                text_elem = soup.find('div', class_='article__item')
                if text_elem:
                    text = text_elem.get_text().strip()
                    if text:
                        horoscopes.append(f"📧 *Mail.ru*:\n{text[:300]}...")
        except Exception as e:
            print(f"Ошибка парсинга Mail.ru: {e}")
        
        # Добавляем задержку между запросами
        time.sleep(1)
        
        # Альтернативный источник - Astro7
        try:
            url = f"https://astro7.ru/horoscope/{zodiac_en}/today/"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Ищем текст гороскопа
                for class_name in ['horoscope-text', 'article-content', 'content']:
                    text_elem = soup.find('div', class_=class_name)
                    if text_elem:
                        text = text_elem.get_text().strip()
                        if text:
                            horoscopes.append(f"✨ *Astro7*:\n{text[:300]}...")
                            break
        except Exception as e:
            print(f"Ошибка парсинга Astro7: {e}")
        
        return "\n\n".join(horoscopes) if horoscopes else "На сегодня гороскопы временно недоступны."
    
    def get_daily_horoscope(self, user_data: dict) -> str:
        """Получение ежедневного гороскопа"""
        zodiac_sign = user_data.get('zodiac', 'Овен')
        cache_key = f"{zodiac_sign}_{datetime.now().strftime('%Y-%m-%d')}"
        
        # Проверяем кэш
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Парсим гороскопы
        parsed_horoscopes = self.parse_horoscopes(zodiac_sign)
        
        result = f"""
✨ *ГОРОСКОП НА СЕГОДНЯ* ✨
📅 {datetime.now().strftime("%d.%m.%Y")}
♈ Знак зодиака: {zodiac_sign}

{parsed_horoscopes}

💫 *Совет от нумеролога* 💫
Сегодня благоприятный день для новых начинаний! 
Ваше число-талисман сегодня: {user_data.get('second', '1')}
        """
        
        # Сохраняем в кэш
        self.cache[cache_key] = result
        return result
