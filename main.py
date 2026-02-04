import asyncio
import logging
import os
from datetime import datetime

from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CallbackContext,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import Config
from matrix_calculator import MatrixCalculator
from interpretations import Interpretations
from horoscope_service import HoroscopeService

# --------------------------------- LOGGING ---------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --------------------------------- STATES ---------------------------------
DATE, GENDER = range(2)

# ========================= BOT LOGIC =========================
class NumerologyBot:
    def __init__(self):
        self.matrix_calc = MatrixCalculator()
        self.interpretations = Interpretations()
        self.horoscope_service = HoroscopeService()
        # Объект хранит данные по вручному сессиям пользователя
        self.data_store: dict[int, dict] = {}

    # ----------------- /start -----------------
    async def start(self, update: Update, _: CallbackContext) -> int:
        await update.message.reply_text(
            "👋 Добро пожаловать в бот нумерологии!\n\n"
            "Введите дату рождения в формате ДД.ММ.ГГГГ, например 15.05.1990"
        )
        return DATE

    # ----------------- Receive date -----------------
    async def receive_date(self, update: Update, ctx: CallbackContext) -> int:
        birth_date = update.message.text
        try:
            datetime.strptime(birth_date, "%d.%m.%Y")
            ctx.user_data["birth_date"] = birth_date
            kb = [
                [KeyboardButton("Мужской"), KeyboardButton("Женский")]
            ]
            await update.message.reply_text(
                "✅ Дата принята!\nВыберите ваш пол:",
                reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True),
            )
            return GENDER
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты.\nВведите как ДД.ММ.ГГГГ, например 15.05.1990"
            )
            return DATE

    # ----------------- Receive gender -----------------
    async def receive_gender(self, update: Update, ctx: CallbackContext) -> int:
        gender = update.message.text
        birth_date = ctx.user_data.get("birth_date")
        if gender not in ("Мужской", "Женский"):
            await update.message.reply_text(
                "❌ Пожалуйста, выберите один из предложенных вариантов."
            )
            return GENDER

        uid = update.effective_user.id
        matrix = self.matrix_calc.calculate_matrix(birth_date, gender)
        self.data_store[uid] = {
            "birth_date": birth_date,
            "gender": gender,
            "chat_id": update.effective_chat.id,
            "matrix": matrix,
        }

        kb = [
            [KeyboardButton("🔮 Полная матрица"), KeyboardButton("🌟 Гороскоп на сегодня")],
            [KeyboardButton("📊 Только матрица 3x3"), KeyboardButton("ℹ️ О боте")],
        ]
        await update.message.reply_text(
            f"✅ Отлично! Ваши данные сохранены:\n"
            f"📅 Дата: {birth_date}\n"
            f"⚧ Пол: {gender}\n"
            f"♈ Знак: {matrix['zodiac']}\n\n"
            "Выберите действие:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        )
        return ConversationHandler.END

    # ----------------- Полная матрица -----------------
    async def full_matrix(self, update: Update, _: CallbackContext):
        uid = update.effective_user.id
        user = self.data_store.get(uid)
        if not user:
            await update.message.reply_text("❌ Сначала заполните данные /start")
            return

        matrix_disp = self.matrix_calc.format_matrix_display(user["matrix"])
        await update.message.reply_text(
            f"📊 *Нумерологическая матрица:*\n\n{matrix_disp}",
            parse_mode="Markdown",
        )
        try:
            interp = self.interpretations.generate_full_interpretation(user["matrix"])
            for i in range(0, len(interp), 4096):
                await update.message.reply_text(interp[i : i + 4096], parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error generating interpretation: {e}")
            await update.message.reply_text("⚠️ Интерпретации временно недоступны.")
        await self.show_main_keyboard(update, None)

    # ----------------- Гороскоп на сегодня -----------------
    async def daily_horoscope(self, update: Update, _: CallbackContext):
        uid = update.effective_user.id
        user = self.data_store.get(uid)
        if not user:
            await update.message.reply_text("❌ Сначала заполните данные /start")
            return

        proc_msg = await update.message.reply_text("🔮 Генерирую персональный гороскоп…")
        try:
            horo = await self.horoscope_service.get_daily_horoscope(user["matrix"])
            await proc_msg.delete()
            for i in range(0, len(horo), 4096):
                await update.message.reply_text(horo[i : i + 4096], parse_mode="Markdown")
        except Exception as e:
            await proc_msg.delete()
            logger.error(f"Error getting horoscope: {e}")
            await update.message.reply_text("❌ Ошибка получения гороскопа. Попробуйте позже.")
        await self.show_main_keyboard(update, None)

    # ----------------- Только матрица 3x3 -----------------
    async def only_matrix(self, update: Update, _: CallbackContext):
        uid = update.effective_user.id
        user = self.data_store.get(uid)
        if not user:
            await update.message.reply_text("❌ Сначала заполните данные /start")
            return
        mat = user["matrix"]
        mat_disp = self.matrix_calc.format_matrix_display(mat)
        add_nums = ".".join(map(str, mat["additional"]))
        response = f"""
📊 *ВАША МАТРИЦА* 📊

*Дата:* {mat['date']}
*Знак:* {mat['zodiac']}
*Доп. числа:* {add_nums}

{mat_disp}

*Расшифровка:*
1️⃣: {len([x for x in mat["full_array"] if x == 1])} шт.
2️⃣: {len([x for x in mat["full_array"] if x == 2])} шт.
3️⃣: {len([x for x in mat["full_array"] if x == 3])} шт.
4️⃣: {len([x for x in mat["full_array"] if x == 4])} шт.
5️⃣: {len([x for x in mat["full_array"] if x == 5])} шт.
6️⃣: {len([x for x in mat["full_array"] if x == 6])} шт.
7️⃣: {len([x for x in mat["full_array"] if x == 7])} шт.
8️⃣: {len([x for x in mat["full_array"] if x == 8])} шт.
9️⃣: {len([x for x in mat["full_array"] if x == 9])} шт.
"""
        await update.message.reply_text(response, parse_mode="Markdown")
        await self.show_main_keyboard(update, None)

    # ----------------- О боте -----------------
    async def about(self, update: Update, _: CallbackContext):
        about_text = """
🤖 *НУМЕРОЛОГИЧЕСКИЙ БОТ* 🤖

Этот бот рассчитывает вашу персональную нумерологическую матрицу, а также
пользуется AI (Groq) для генерирования гороскопов.

*Функции:*
🔮 Полная матрица – подробный расчёт и интерпретации
🌟 Гороскоп на сегодня – персональный прогноз
📊 Матрица 3x3 – только визуализация

Нажмите /start и следуйте инструкциям."""
        await update.message.reply_text(about_text, parse_mode="Markdown")
        await self.show_main_keyboard(update, None)

    # ----------------- Главное меню -----------------
    async def show_main_keyboard(self, update: Update, _: CallbackContext):
        kb = [
            [KeyboardButton("🔮 Полная матрица"), KeyboardButton("🌟 Гороскоп на сегодня")],
            [KeyboardButton("📊 Только матрица 3x3"), KeyboardButton("ℹ️ О боте")],
        ]
        await update.message.reply_text(
            "Выберите действие:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )

    # ----------------- Обработчик произвольных text -----------------
    async def handle_text(self, update: Update, ctx: CallbackContext):
        txt = update.message.text
        if txt == "🔮 Полная матрица":
            await self.full_matrix(update, ctx)
        elif txt == "🌟 Гороскоп на сегодня":
            await self.daily_horoscope(update, ctx)
        elif txt == "📊 Только матрица 3x3":
            await self.only_matrix(update, ctx)
        elif txt == "ℹ️ О боте":
            await self.about(update, ctx)
        else:
            await update.message.reply_text("Используйте кнопки или /start")

    # ----------------- Ошибки -----------------
    async def error_handler(self, update: Update, ctx: CallbackContext):
        logger.error(f"Ошибка: {ctx.error}")
        try:
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте снова.")
        except Exception:
            pass


# -----------------------------------------------------------------------
#  Стартовые функции
# -----------------------------------------------------------------------

async def build_application() -> "Application":
    """
    Создаёт и конфигурирует Application – возвращает готовый объект.
    """
    bot = NumerologyBot()
    application = ApplicationBuilder().token(Config.BOT_TOKEN).build()

    # Handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", bot.start)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_date)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_gender)],
        },
        fallbacks=[CommandHandler("start", bot.start)],
    )
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    application.add_error_handler(bot.error_handler)

    return application


async def health_app() -> None:
    """Базовый health‑check сервис."""
    app = web.Application()
    app.router.add_get("/", lambda _: web.Response(text="Bot is running"))
    app.router.add_get("/health", lambda _: web.Response(text="Bot is running"))
    await web._run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))


async def main() -> None:
    application = await build_application()
    # Запускаем polling и health‑check параллельно
    await asyncio.gather(
        application.run_polling(allowed_updates=Update.ALL_TYPES),
        health_app(),
    )


if __name__ == "__main__":
    asyncio.run(main())
