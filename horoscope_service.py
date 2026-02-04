# horoscope_service_simple.py
import requests
from datetime import datetime
from config import Config
from bs4 import BeautifulSoup
import time

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
