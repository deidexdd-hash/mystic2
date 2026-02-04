import asyncio
import logging
import os
import threading
from datetime import datetime

from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
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

# ------------------------------------------------------------------
#  LOGGING
# ------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
#  ЛОКАЛЬНЫЕ СОСТОЯНИЯ ДИАЛОГА
# ------------------------------------------------------------------
DATE, GENDER = range(2)

# ------------------------------------------------------------------
#  КЛАСС БОТА
# ------------------------------------------------------------------
class NumerologyBot:
    def __init__(self):
        self.matrix_calc = MatrixCalculator()
        self.interpretations = Interpretations()
        self.horoscope_service = HoroscopeService()
        self.data_store: dict[int, dict] = {}

    # ─────────────────────────── COMMANDS ──────────────────────────────
    async def start(self, update: Update, ctx: CallbackContext) -> int:
        await update.message.reply_text(
            "👋 Добро пожаловать в бот нумерологии!\n\n"
            "Введите дату рождения в формате ДД.ММ.ГГГГ, например 15.05.1990"
        )
        return DATE

    async def receive_date(self, update: Update, ctx: CallbackContext) -> int:
        date_text = update.message.text
        try:
            datetime.strptime(date_text, "%d.%m.%Y")
            ctx.user_data["birth_date"] = date_text
            kb = [[KeyboardButton("Мужской"), KeyboardButton("Женский")]]
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

    async def receive_gender(self, update: Update, ctx: CallbackContext) -> int:
        gender = update.message.text
        birth_date = ctx.user_data.get("birth_date")
        if gender not in ("Мужской", "Женский"):
            await update.message.reply_text("❌ Пожалуйста, выберите пол из предложенных вариантов.")
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

    # ─────────────────────────── HELPERS ───────────────────────────────
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
                await update.message.reply_text(interp[i:i + 4096], parse_mode="Markdown")
        except Exception as exc:
            logger.error(f"Error generating interpretation: {exc}")
            await update.message.reply_text("⚠️ Интерпретации временно недоступны.")
        await self.show_main_keyboard(update, None)

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
                await update.message.reply_text(horo[i:i + 4096], parse_mode="Markdown")
        except Exception as exc:
            await proc_msg.delete()
            logger.error(f"Error getting horoscope: {exc}")
            await update.message.reply_text("❌ Ошибка получения гороскопа. Попробуйте позже.")
        await self.show_main_keyboard(update, None)

    async def only_matrix(self, update: Update, _: CallbackContext):
        uid = update.effective_user.id
        user = self.data_store.get(uid)
        if not user:
            await update.message.reply_text("❌ Сначала заполните данные /start")
            return

        mat = user["matrix"]
        add_nums = ".".join(map(str, mat["additional"]))
        response = f"""
📊 *ВАША МАТРИЦА* 📊

*Дата:* {mat['date']}
*Знак:* {mat['zodiac']}
*Доп. числа:* {add_nums}

{self.matrix_calc.format_matrix_display(mat)}

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

    async def about(self, update: Update, _: CallbackContext):
        about_text = """
🤖 *НУМЕРОЛОГИЧЕСКИЙ БОТ* 🤖

Этот бот рассчитывает вашу персональную нумерологическую матрицу и гороскопы.

*Технологии:*
• Python + python‑telegram‑bot 21.x
• Groq AI (необязательно)
• BeautifulSoup для парсинга

Нажмите /start и следуйте инструкциям."""
        await update.message.reply_text(about_text, parse_mode="Markdown")
        await self.show_main_keyboard(update, None)

    async def show_main_keyboard(self, update: Update, _: CallbackContext):
        kb = [
            [KeyboardButton("🔮 Полная матрица"), KeyboardButton("🌟 Гороскоп на сегодня")],
            [KeyboardButton("📊 Только матрица 3x3"), KeyboardButton("ℹ️ О боте")],
        ]
        await update.message.reply_text("Выберите действие:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

    async def handle_text(self, update: Update, _: CallbackContext):
        txt = update.message.text
        if txt == "🔮 Полная матрица":
            await self.full_matrix(update, None)
        elif txt == "🌟 Гороскоп на сегодня":
            await self.daily_horoscope(update, None)
        elif txt == "📊 Только матрица 3x3":
            await self.only_matrix(update, None)
        elif txt == "ℹ️ О боте":
            await self.about(update, None)
        else:
            await update.message.reply_text("Используйте кнопки или /start")

    async def error_handler(self, update: Update, ctx: CallbackContext):
        logger.error(f"Error: {ctx.error}")
        try:
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте снова.")
        except Exception:
            pass


# ------------------------------------------------------------------
#  ФУНКЦИЯ ПОСТРОЕНИЕ APPLICATION (СИНХРОННО)
# ------------------------------------------------------------------
def build_application() -> Application:
    app = Application.builder().token(Config.BOT_TOKEN).build()
    bot = NumerologyBot()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", bot.start)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_date)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_gender)],
        },
        fallbacks=[CommandHandler("start", bot.start)],
    )
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    app.add_error_handler(bot.error_handler)

    return app


# ------------------------------------------------------------------
#  BOT В ИЗОБРАЖЕНИИ (thread)
# ------------------------------------------------------------------
def run_bot_in_thread() -> None:
    """Запускает бота в отдельном потоке."""
    app = build_application()
    # run_polling блокирует поток, поэтому ничего не делаем после этого
    app.run_polling(allowed_updates=Update.ALL_TYPES)


# ------------------------------------------------------------------
#  HEALTH‑CHECK через aiohttp
# ------------------------------------------------------------------
async def health_app() -> None:
    web_app = web.Application()
    web_app.router.add_get("/", lambda _: web.Response(text="Bot is running"))
    web_app.router.add_get("/health", lambda _: web.Response(text="Bot is running"))
    await web._run_app(web_app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))


# ------------------------------------------------------------------
#  ENTRYPOINT
# ------------------------------------------------------------------
def main() -> None:
    # 1️⃣ Бот в отдельном потоке
    threading.Thread(target=run_bot_in_thread, daemon=True).start()
    # 2️⃣ Сервер health‑check в основном потоке
    asyncio.run(health_app())


if __name__ == "__main__":
    main()
