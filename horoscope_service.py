import aiohttp
import asyncio
from datetime import datetime
from groq import Groq
from config import Config
import requests
from bs4 import BeautifulSoup

class HoroscopeService:
    def __init__(self):
        self.groq_client = Groq(api_key=Config.GROQ_API_KEY)
        self.cache = {}
    
    async def parse_horoscopes(self, zodiac_sign: str) -> str:
        """Парсинг гороскопов с нескольких сайтов"""
        horoscopes = []
        
        # Преобразуем русское название в английское для URL
        zodiac_map = {
            "Овен": "aries", "Телец": "taurus", "Близнецы": "gemini",
            "Рак": "cancer", "Лев": "leo", "Дева": "virgo",
            "Весы": "libra", "Скорпион": "scorpio", "Стрелец": "sagittarius",
            "Козерог": "capricorn", "Водолей": "aquarius", "Рыбы": "pisces"
        }
        
        zodiac_en = zodiac_map.get(zodiac_sign, "aries")
        
        async with aiohttp.ClientSession() as session:
            # Парсинг с Mail.ru
            try:
                url = f"https://horo.mail.ru/prediction/{zodiac_en}/today/"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        soup = BeautifulSoup(await response.text(), 'html.parser')
                        text_elem = soup.find('div', class_='article__item')
                        if text_elem:
                            horoscopes.append(f"📧 *Mail.ru*:\n{text_elem.get_text()[:300]}...")
            except:
                pass
            
            # Парсинг с Rambler
            try:
                url = f"https://horoscopes.rambler.ru/{zodiac_en}/"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        soup = BeautifulSoup(await response.text(), 'html.parser')
                        text_elem = soup.find('p', class_='_1RrZR')
                        if text_elem:
                            horoscopes.append(f"🌐 *Rambler*:\n{text_elem.get_text()[:300]}...")
            except:
                pass
        
        return "\n\n".join(horoscopes) if horoscopes else ""
    
    async def generate_ai_horoscope(self, user_data: dict, zodiac_sign: str) -> str:
        """Генерация гороскопа через Groq AI"""
        today = datetime.now().strftime("%d.%m.%Y")
        
        prompt = f"""
        Создай персональный гороскоп на {today} для человека со следующими данными:
        
        Дата рождения: {user_data['date']}
        Знак зодиака: {zodiac_sign}
        Пол: {user_data['gender']}
        Число судьбы: {user_data.get('second', 'N/A')}
        Число души: {user_data.get('fourth', 'N/A')}
        
        Основные аспекты личности:
        {user_data.get('personality_aspects', '')}
        
        Создай красивый, мотивирующий и точный гороскоп на день, который включает:
        1. Общий прогноз на день
        2. Любовные отношения
        3. Финансы и карьера
        4. Здоровье
        5. Совет дня
        
        Будь креативным, используй эмодзи и делай текст вдохновляющим!
        """
        
        try:
            completion = self.groq_client.chat.completions.create(
                model=Config.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "Ты профессиональный астролог и нумеролог. Твои прогнозы точные и мотивирующие."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            return completion.choices[0].message.content
        except Exception as e:
            return f"❌ Ошибка генерации гороскопа: {str(e)}"
    
    async def get_daily_horoscope(self, user_data: dict) -> str:
        """Получение ежедневного гороскопа"""
        zodiac_sign = user_data.get('zodiac', 'Овен')
        cache_key = f"{zodiac_sign}_{datetime.now().strftime('%Y-%m-%d')}"
        
        # Проверяем кэш
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Парсим гороскопы
        parsed_horoscopes = await self.parse_horoscopes(zodiac_sign)
        
        # Генерируем AI гороскоп
        ai_horoscope = await self.generate_ai_horoscope(user_data, zodiac_sign)
        
        # Комбинируем результаты
        result = f"""
✨ *ПЕРСОНАЛЬНЫЙ ГОРОСКОП* ✨
📅 {datetime.now().strftime("%d.%m.%Y")}
♈ Знак зодиака: {zodiac_sign}

🌟 *Ваш персональный прогноз на сегодня* 🌟

{ai_horoscope}

📊 *Сводка с других источников* 📊

{parsed_horoscopes if parsed_horoscopes else 'Нет данных с внешних источников'}

💫 *Совет от нумеролога* 💫
Используйте число {user_data.get('second', '1')} как ваш талисман сегодня!
        """
        
        # Сохраняем в кэш
        self.cache[cache_key] = result
        return result
