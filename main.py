# app.py (бывший main (4).py)
import logging
import asyncio
import os
from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ConversationHandler, CallbackContext, filters
)
from config import Config
from matrix_calculator import MatrixCalculator
from interpretations import Interpretations
from horoscope_service import HoroscopeService
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
DATE, GENDER = range(2)

class NumerologyBot:
    def __init__(self):
        self.matrix_calc = MatrixCalculator()
        self.interpretations = Interpretations()
        self.horoscope_service = HoroscopeService()
        self.user_data_store = {}
    
    async def start(self, update: Update, context: CallbackContext) -> int:
        """Начало диалога, запрос даты рождения"""
        await update.message.reply_text(
            "👋 Добро пожаловать в бот нумерологии!\n\n"
            "Пожалуйста, введите вашу дату рождения в формате ДД.ММ.ГГГГ:\n"
            "Например: 15.05.1990"
        )
        return DATE
    
    async def receive_date(self, update: Update, context: CallbackContext) -> int:
        """Получение даты рождения"""
        user_date = update.message.text
        
        try:
            # Проверяем формат даты
            datetime.strptime(user_date, "%d.%m.%Y")
            context.user_data['birth_date'] = user_date
            
            # Создаем клавиатуру для выбора пола
            keyboard = [
                [KeyboardButton("Мужской"), KeyboardButton("Женский")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            
            await update.message.reply_text(
                "✅ Дата рождения принята!\n"
                "Теперь выберите ваш пол:",
                reply_markup=reply_markup
            )
            return GENDER
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты!\n"
                "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ\n"
                "Например: 15.05.1990"
            )
            return DATE
    
    async def receive_gender(self, update: Update, context: CallbackContext) -> int:
        """Получение пола и расчет матрицы"""
        gender = update.message.text
        birth_date = context.user_data.get('birth_date')
        
        if gender not in ["Мужской", "Женский"]:
            await update.message.reply_text(
                "❌ Пожалуйста, выберите пол из предложенных вариантов"
            )
            return GENDER
        
        # Сохраняем данные пользователя
        user_id = update.effective_user.id
        self.user_data_store[user_id] = {
            'birth_date': birth_date,
            'gender': gender,
            'chat_id': update.effective_chat.id
        }
        
        # Рассчитываем матрицу
        matrix_data = self.matrix_calc.calculate_matrix(birth_date, gender)
        
        # Сохраняем расчет
        self.user_data_store[user_id]['matrix'] = matrix_data
        
        # Создаем основную клавиатуру
        keyboard = [
            [KeyboardButton("🔮 Полная матрица"), KeyboardButton("🌟 Гороскоп на сегодня")],
            [KeyboardButton("📊 Только матрица 3x3"), KeyboardButton("ℹ️ О боте")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Отправляем приветственное сообщение
        await update.message.reply_text(
            f"✅ Отлично! Ваши данные сохранены:\n"
            f"📅 Дата: {birth_date}\n"
            f"⚧ Пол: {gender}\n"
            f"♈ Знак зодиака: {matrix_data['zodiac']}\n\n"
            f"Выберите действие:",
            reply_markup=reply_markup
        )
        
        return ConversationHandler.END
    
    async def show_full_matrix(self, update: Update, context: CallbackContext):
        """Показать полную матрицу с интерпретациями"""
        user_id = update.effective_user.id
        user_data = self.user_data_store.get(user_id)
        
        if not user_data or 'matrix' not in user_data:
            await update.message.reply_text("❌ Сначала введите ваши данные через команду /start")
            return
        
        matrix_data = user_data['matrix']
        
        # Отправляем матрицу 3x3
        matrix_display = self.matrix_calc.format_matrix_display(matrix_data)
        await update.message.reply_text(f"📊 *Ваша нумерологическая матрица:*\n\n{matrix_display}", parse_mode='Markdown')
        
        # Отправляем интерпретации
        try:
            interpretation = self.interpretations.generate_full_interpretation(matrix_data)
            
            # Разбиваем на части если слишком длинное
            max_length = 4000
            for i in range(0, len(interpretation), max_length):
                part = interpretation[i:i + max_length]
                await update.message.reply_text(part, parse_mode='Markdown')
        except AttributeError as e:
            logger.error(f"Ошибка генерации интерпретации: {e}")
            await update.message.reply_text("⚠️ Интерпретации временно недоступны.")
        
        # Показываем клавиатуру
        await self.show_main_keyboard(update, context)
    
    async def show_daily_horoscope(self, update: Update, context: CallbackContext):
        """Показать гороскоп на сегодня"""
        user_id = update.effective_user.id
        user_data = self.user_data_store.get(user_id)
        
        if not user_data or 'matrix' not in user_data:
            await update.message.reply_text("❌ Сначала введите ваши данные через команду /start")
            return
        
        # Отправляем сообщение о генерации
        processing_msg = await update.message.reply_text("🔮 Генерирую ваш персональный гороскоп...")
        
        try:
            # Получаем гороскоп
            horoscope = await self.horoscope_service.get_daily_horoscope(user_data['matrix'])
            
            # Удаляем сообщение о генерации
            await processing_msg.delete()
            
            # Отправляем гороскоп по частям
            max_length = 4000
            for i in range(0, len(horoscope), max_length):
                part = horoscope[i:i + max_length]
                await update.message.reply_text(part, parse_mode='Markdown')
        except Exception as e:
            await processing_msg.delete()
            logger.error(f"Ошибка получения гороскопа: {e}")
            await update.message.reply_text("❌ Ошибка при получении гороскопа. Попробуйте позже.")
        
        await self.show_main_keyboard(update, context)
    
    async def show_matrix_only(self, update: Update, context: CallbackContext):
        """Показать только матрицу 3x3"""
        user_id = update.effective_user.id
        user_data = self.user_data_store.get(user_id)
        
        if not user_data or 'matrix' not in user_data:
            await update.message.reply_text("❌ Сначала введите ваши данные через команду /start")
            return
        
        matrix_data = user_data['matrix']
        matrix_display = self.matrix_calc.format_matrix_display(matrix_data)
        
        additional_numbers = ".".join(map(str, matrix_data['additional']))
        
        response = f"""
📊 *ВАША МАТРИЦА* 📊

*Дата рождения:* {matrix_data['date']}
*Знак зодиака:* {matrix_data['zodiac']}
*Доп. числа:* {additional_numbers}

{matrix_display}

*Расшифровка:*
1️⃣: {len([x for x in matrix_data['full_array'] if x == 1])} шт.
2️⃣: {len([x for x in matrix_data['full_array'] if x == 2])} шт.
3️⃣: {len([x for x in matrix_data['full_array'] if x == 3])} шт.
4️⃣: {len([x for x in matrix_data['full_array'] if x == 4])} шт.
5️⃣: {len([x for x in matrix_data['full_array'] if x == 5])} шт.
6️⃣: {len([x for x in matrix_data['full_array'] if x == 6])} шт.
7️⃣: {len([x for x in matrix_data['full_array'] if x == 7])} шт.
8️⃣: {len([x for x in matrix_data['full_array'] if x == 8])} шт.
9️⃣: {len([x for x in matrix_data['full_array'] if x == 9])} шт.
        """
        
        await update.message.reply_text(response, parse_mode='Markdown')
        await self.show_main_keyboard(update, context)
    
    async def show_about(self, update: Update, context: CallbackContext):
        """Информация о боте"""
        about_text = """
🤖 *НУМЕРОЛОГИЧЕСКИЙ БОТ* 🤖

Этот бот рассчитывает вашу персональную нумерологическую матрицу на основе даты рождения.

*Функции:*
🔮 **Полная матрица** - подробный расчет с интерпретациями
🌟 **Гороскоп на сегодня** - персональный прогноз с использованием AI
📊 **Матрица 3x3** - только визуализация матрицы

*Как использовать:*
1. Введите дату рождения по запросу бота
2. Выберите ваш пол
3. Используйте кнопки для навигации

*Технологии:*
• Python + python-telegram-bot
• Groq AI для генерации гороскопов
• Парсинг астрологических сайтов

Для начала работы нажмите /start
        """
        await update.message.reply_text(about_text, parse_mode='Markdown')
        await self.show_main_keyboard(update, context)
    
    async def show_main_keyboard(self, update: Update, context: CallbackContext):
        """Показать основную клавиатуру"""
        keyboard = [
            [KeyboardButton("🔮 Полная матрица"), KeyboardButton("🌟 Гороскоп на сегодня")],
            [KeyboardButton("📊 Только матрица 3x3"), KeyboardButton("ℹ️ О боте")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    
    async def handle_message(self, update: Update, context: CallbackContext):
        """Обработка текстовых сообщений"""
        text = update.message.text
        
        if text == "🔮 Полная матрица":
            await self.show_full_matrix(update, context)
        elif text == "🌟 Гороскоп на сегодня":
            await self.show_daily_horoscope(update, context)
        elif text == "📊 Только матрица 3x3":
            await self.show_matrix_only(update, context)
        elif text == "ℹ️ О боте":
            await self.show_about(update, context)
        else:
            await update.message.reply_text("Используйте кнопки для навигации или /start для начала")
    
    async def error_handler(self, update: Update, context: CallbackContext):
        """Обработка ошибок"""
        logger.error(f"Ошибка: {context.error}")
        try:
            await update.message.reply_text("❌ Произошла ошибка. Пожалуйста, попробуйте снова.")
        except:
            pass

# Создаем простой веб-сервер для Render
async def health_check(request):
    return web.Response(text="Bot is running")

async def start_bot():
    """Запуск бота"""
    # Проверяем токен
    if not Config.BOT_TOKEN:
        logger.error("❌ ОШИБКА: Не задан токен бота!")
        logger.error("Пожалуйста, задайте BOT_TOKEN в переменных окружения")
        logger.error("На Render: Settings -> Environment Variables")
        print("❌ ОШИБКА: Не задан токен бота!")
        return
    
    logger.info(f"✅ Токен бота загружен. Длина: {len(Config.BOT_TOKEN)} символов")
    
    bot = NumerologyBot()
    
    # Создаем приложение
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Настраиваем диалог
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', bot.start)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_date)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_gender)],
        },
        fallbacks=[CommandHandler('start', bot.start)]
    )
    
    # Регистрируем обработчики
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    application.add_error_handler(bot.error_handler)
    
    # Запускаем бота
    logger.info("🤖 Бот запущен...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Главная функция"""
    import threading
    
    # Проверяем переменные окружения
    logger.info(f"PORT: {os.environ.get('PORT', 8080)}")
    logger.info(f"BOT_TOKEN присутствует: {'BOT_TOKEN' in os.environ}")
    
    if not Config.BOT_TOKEN:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не задан!")
        logger.error("Добавьте переменную окружения BOT_TOKEN в Render:")
        logger.error("Settings -> Environment Variables")
        print("=" * 60)
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не задан!")
        print("Добавьте переменную окружения BOT_TOKEN в Render:")
        print("Settings -> Environment Variables")
        print("=" * 60)
        return
    
    # Запускаем бота в отдельном потоке
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Запускаем бота
    bot_thread = threading.Thread(target=lambda: loop.run_until_complete(start_bot()))
    bot_thread.daemon = True
    bot_thread.start()
    
    # Запускаем веб-сервер для health checks
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🌐 Веб-сервер запущен на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()
