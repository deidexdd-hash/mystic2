import logging
import asyncio
import os
from datetime import datetime
from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackContext,
    filters,
)
from config import Config
from matrix_calculator import MatrixCalculator
from interpretations import Interpretations
from horoscope_service import HoroscopeService

# ===== Logging =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ===== Conversation states =====
DATE, GENDER = range(2)

# ===== Bot class =====
class NumerologyBot:
    def __init__(self):
        self.matrix_calc = MatrixCalculator()
        self.interpretations = Interpretations()
        self.horoscope_service = HoroscopeService()
        self.user_data_store = {}

    async def start(self, update: Update, context: CallbackContext) -> int:
        await update.message.reply_text(
            "👋 Добро пожаловать в бот нумерологии!\n\n"
            "Пожалуйста, введите вашу дату рождения в формате ДД.ММ.ГГГГ:\n"
            "Например: 15.05.1990"
        )
        return DATE

    async def receive_date(self, update: Update, context: CallbackContext) -> int:
        user_date = update.message.text
        try:
            datetime.strptime(user_date, "%d.%m.%Y")
            context.user_data["birth_date"] = user_date
            keyboard = [[KeyboardButton("Мужской"), KeyboardButton("Женский")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            await update.message.reply_text(
                "✅ Дата рождения принята!\n"
                "Теперь выберите ваш пол:",
                reply_markup=reply_markup,
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
        gender = update.message.text
        birth_date = context.user_data.get("birth_date")
        if gender not in ["Мужской", "Женский"]:
            await update.message.reply_text(
                "❌ Пожалуйста, выберите пол из предложенных вариантов"
            )
            return GENDER
        user_id = update.effective_user.id
        self.user_data_store[user_id] = {
            "birth_date": birth_date,
            "gender": gender,
            "chat_id": update.effective_chat.id,
        }
        matrix_data = self.matrix_calc.calculate_matrix(birth_date, gender)
        self.user_data_store[user_id]["matrix"] = matrix_data
        keyboard = [
            [KeyboardButton("🔮 Полная матрица"), KeyboardButton("🌟 Гороскоп на сегодня")],
            [KeyboardButton("📊 Только матрица 3x3"), KeyboardButton("ℹ️ О боте")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            f"✅ Отлично! Ваши данные сохранены:\n"
            f"📅 Дата: {birth_date}\n"
            f"⚧ Пол: {gender}\n"
            f"♈ Знак зодиака: {matrix_data['zodiac']}\n\n"
            f"Выберите действие:",
            reply_markup=reply_markup,
        )
        return ConversationHandler.END

    async def show_full_matrix(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        user_data = self.user_data_store.get(user_id)
        if not user_data or "matrix" not in user_data:
            await update.message.reply_text("❌ Сначала введите ваши данные через команду /start")
            return
        matrix_data = user_data["matrix"]
        matrix_display = self.matrix_calc.format_matrix_display(matrix_data)
        await update.message.reply_text(
            f"📊 *Ваша нумерологическая матрица:*\n\n{matrix_display}",
            parse_mode="Markdown",
        )
        try:
            interpretation = self.interpretations.generate_full_interpretation(matrix_data)
            max_len = 4000
            for i in range(0, len(interpretation), max_len):
                part = interpretation[i : i + max_len]
                await update.message.reply_text(part, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка генерации интерпретации: {e}")
            await update.message.reply_text("⚠️ Интерпретации временно недоступны.")
        await self.show_main_keyboard(update, context)

    async def show_daily_horoscope(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        user_data = self.user_data_store.get(user_id)
        if not user_data or "matrix" not in user_data:
            await update.message.reply_text("❌ Сначала введите ваши данные через команду /start")
            return
        processing_msg = await update.message.reply_text("🔮 Генерирую ваш персональный гороскоп...")
        try:
            horoscope = await self.horoscope_service.get_daily_horoscope(
                user_data["matrix"]
            )
            await processing_msg.delete()
            max_len = 4000
            for i in range(0, len(horoscope), max_len):
                part = horoscope[i : i + max_len]
                await update.message.reply_text(part, parse_mode="Markdown")
        except Exception as e:
            await processing_msg.delete()
            logger.error(f"Ошибка получения гороскопа: {e}")
            await update.message.reply_text("❌ Ошибка при получении гороскопа. Попробуйте позже.")
        await self.show_main_keyboard(update, context)

    async def show_matrix_only(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        user_data = self.user_data_store.get(user_id)
        if not user_data or "matrix" not in user_data:
            await update.message.reply_text("❌ Сначала введите ваши данные через команду /start")
            return
        matrix_data = user_data["matrix"]
        matrix_display = self.matrix_calc.format_matrix_display(matrix_data)
        additional_numbers = ".".join(map(str, matrix_data["additional"]))
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
        await update.message.reply_text(response, parse_mode="Markdown")
        await self.show_main_keyboard(update, context)

    async def show_about(self, update: Update, context: CallbackContext):
        about_text = """
🤖 *НУМЕРОЛОГИЧЕСКИЙ БОТ* 🤖

Этот бот рассчитывает вашу персональную нумерологическую матрицу на основе даты рождения.

*Функции:*
🔮 Полная матрица - подробный расчёт с интерпретациями
🌟 Гороскоп на сегодня - персональный прогноз с AI
📊 Матрица 3x3 - только визуальный вывод

*Технологии:*
• Python + python‑telegram‑bot
• Groq AI для генерации гороскопов
• Парсинг астрологических сайтов

Для начала работы нажмите /start
        """
        await update.message.reply_text(about_text, parse_mode="Markdown")
        await self.show_main_keyboard(update, context)

    async def show_main_keyboard(self, update: Update, context: CallbackContext):
        keyboard = [
            [KeyboardButton("🔮 Полная матрица"), KeyboardButton("🌟 Гороскоп на сегодня")],
            [KeyboardButton("📊 Только матрица 3x3"), KeyboardButton("ℹ️ О боте")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

    async def handle_message(self, update: Update, context: CallbackContext):
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
        logger.error(f"Ошибка: {context.error}")
        try:
            await update.message.reply_text(
                "❌ Произошла ошибка. Пожалуйста, попробуйте снова."
            )
        except:
            pass


# ===== Main =====
async def main():
    # Проверяем токен – без него бот не стартует
    if not Config.BOT_TOKEN:
        logger.error("❌ Была не задана переменная BOT_TOKEN!")
        return

    bot = NumerologyBot()
    application = Application.builder().token(Config.BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", bot.start)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_date)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_gender)],
        },
        fallbacks=[CommandHandler("start", bot.start)],
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    application.add_error_handler(bot.error_handler)

    # ===== Health‑check web server =====
    web_app = web.Application()
    web_app.router.add_get("/", lambda _: web.Response(text="Bot is running"))
    web_app.router.add_get("/health", lambda _: web.Response(text="Bot is running"))
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8080))

    # Run bot and web server concurrently
    await asyncio.gather(
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            check_interval=1.0,
            drop_pending_updates=True,
        ),
        web._run_app(web_app, host=host, port=port),
    )


if __name__ == "__main__":
    asyncio.run(main())
