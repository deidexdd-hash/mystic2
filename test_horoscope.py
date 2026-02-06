#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы HoroscopeService
"""

import asyncio
import sys
from horoscope_service import HoroscopeService

async def test_horoscope():
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ HOROSCOPE SERVICE")
    print("=" * 60)
    
    service = HoroscopeService()
    
    # Тестовые данные пользователя
    test_user = {
        "zodiac": "♌ Лев",
        "date": "15.08.1990",
        "matrix": {
            "additional": [32, 5, 30, 3],
            "full_array": [1, 5, 0, 8, 1, 9, 9, 0]
        }
    }
    
    print(f"\n📋 Тестовые данные:")
    print(f"Знак: {test_user['zodiac']}")
    print(f"Дата: {test_user['date']}")
    print(f"Число судьбы: {test_user['matrix']['additional'][0]}")
    
    # Тест 1: Парсинг источников
    print("\n" + "=" * 60)
    print("ТЕСТ 1: Парсинг источников")
    print("=" * 60)
    
    horoscopes = await service.parse_horoscopes(test_user["zodiac"])
    
    if horoscopes:
        print(f"\n✅ Успешно получено источников: {len(horoscopes)}")
        for source, text in horoscopes.items():
            print(f"\n📰 {source}:")
            print(f"{text[:200]}...")
    else:
        print("\n❌ Не удалось получить гороскопы из источников")
    
    # Тест 2: Базовая генерация (без AI)
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Базовая генерация (без AI)")
    print("=" * 60)
    
    basic_horoscope = service._generate_basic_horoscope(
        test_user["zodiac"], 
        horoscopes
    )
    print(f"\n{basic_horoscope}")
    
    # Тест 3: Полная генерация (с AI если доступен)
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Полная генерация гороскопа")
    print("=" * 60)
    
    if service.groq_client:
        print("\n🤖 Groq API доступен - будет использован AI")
    else:
        print("\n📝 Groq API недоступен - будет базовая генерация")
    
    print("\n⏳ Генерируем гороскоп...")
    
    final_horoscope = await service.get_daily_horoscope(test_user)
    
    print("\n" + "=" * 60)
    print("ФИНАЛЬНЫЙ ГОРОСКОП:")
    print("=" * 60)
    print(f"\n{final_horoscope}")
    
    # Тест 4: Проверка кеширования
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Проверка кеширования")
    print("=" * 60)
    
    print("\n⏳ Повторный запрос гороскопа...")
    cached_horoscope = await service.get_daily_horoscope(test_user)
    
    if cached_horoscope == final_horoscope:
        print("✅ Кеширование работает корректно!")
    else:
        print("❌ Проблема с кешированием!")
    
    # Тест 5: Разные знаки
    print("\n" + "=" * 60)
    print("ТЕСТ 5: Проверка разных знаков зодиака")
    print("=" * 60)
    
    test_signs = ["♈ Овен", "♊ Близнецы", "♏ Скорпион"]
    
    for sign in test_signs:
        print(f"\n🔍 Тестируем {sign}...")
        test_user_variant = test_user.copy()
        test_user_variant["zodiac"] = sign
        
        # Очищаем кеш для этого теста
        service._cache.clear()
        
        horoscope = await service.get_daily_horoscope(test_user_variant)
        if horoscope and len(horoscope) > 50:
            print(f"✅ {sign}: получен гороскоп ({len(horoscope)} символов)")
        else:
            print(f"⚠️ {sign}: гороскоп слишком короткий или пустой")
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(test_horoscope())
    except KeyboardInterrupt:
        print("\n\n⚠️ Тестирование прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
