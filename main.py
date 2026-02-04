import asyncio
import logging
import os
import json
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

# ----------------- локальные модули -----------------
from config import Config
from matrix_calculator import MatrixCalculator
from interpretations import Interpretations
from horoscope_service import HoroscopeService

# --------------------------------------------------------------------
# 1️⃣ LOGGING
# --------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# --------------------------------------------------------------------
# 2️⃣ СОСТОЯНИЯ ДИАЛОГА
# --------------------------------------------------------------------
DATE, GENDER = range(2)

# --------------------------------------------------------------------
# 3️⃣ КЛАСС БОТА (Без изменений)
# --------------------------------------------------------------------
class NumerologyBot:
    def __init__(self):
        self.matrix_calc = MatrixCalculator()
        self.interpretations = Interpretations()
        self.horoscope_service = HoroscopeService()
        self.store: dict[int, dict] = {}

    async def start(self, update: Update, ctx: CallbackContext) -> int:
        await update.message.reply_text(
            "👋 Добро пожаловать в бот нумерологии!\n\n"
            "Введите дату рождения в формате ДД.MM.ГГГГ, например 15.05.1990"
        )
        return DATE

    async def receive_date(self, update: Update, ctx: CallbackContext) -> int:
        txt = update.message.text
        try:
            datetime.strptime(txt, "%d.%m.%Y")
            ctx.user_data["birth_date"] = txt
            kb = [[KeyboardButton("Мужской"), KeyboardButton("Женский")]]
            await update.message.reply_text(
                "✅ Дата принята!\nВыберите ваш пол:",
                reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True),
            )
            return GENDER
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты.\nВведите как ДД.MM.ГГГГ, например 15.05.1990"
            )
            return DATE

    async def receive_gender(self, update: Update, ctx: CallbackContext) -> int:
        gender = update.message.text
        birth_date = ctx.user_data.get("birth_date")
        if gender not in ("Мужской", "Женский"):
            await update.message.reply_text(
                "❌ Пожалуйста, выберите пол из предложенных вариантов."
            )
            return GENDER

        uid = update.effective_user.id
        matrix = self.matrix_calc.calculate_matrix(birth_date, gender)

        self.store[uid] = {
            "birth_date": birth_date,
            "gender": gender,
            "chat_id": update.effective_chat.id,
            "matrix": matrix,
        }

        kb = [
            [
                KeyboardButton("🔮 Полная матрица"),
                KeyboardButton("🌟 Гороскоп на сегодня"),
            ],
            [
                KeyboardButton("📊 Только матрица 3x3"),
                KeyboardButton("ℹ️ О боте"),
            ],
        ]
        await update.message.reply_text(
            f"✅ Данные сохранены:\n"
            f"📅 Дата: {birth_date}\n"
            f"⚧ Пол: {gender}\n"
            f"♈ Знак: {matrix['zodiac']}\n\n"
            "Выберите действие:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        )
        return ConversationHandler.END

    async def full_matrix(self, update: Update, _: CallbackContext):
        uid = update.effective_user.id
        user = self.store.get(uid)
        if not user:
            await update.message.reply_text("❌ Сначала введите данные через /start")
            return

        disp = self.matrix_calc.format_matrix_display(user["matrix"])
        await update.message.reply_text(
            f"📊 *Нумерологическая матрица:*\n\n{disp}",
            parse_mode="Markdown",
        )
        try:
            interp = self.interpretations.generate_full_interpretation(user["matrix"])
            for i in range(0, len(interp), 4096):
                await update.message.reply_text(interp[i : i + 4096], parse_mode="Markdown")
        except Exception as exc:
            log.error(f"Interpretation error: {exc}")
            await update.message.reply_text("⚠️ Интерпретации временно недоступны.")
        await self.show_main_keyboard(update, None)

    async def daily_horoscope(self, update: Update, _: CallbackContext):
        uid = update.effective_user.id
        user = self.store.get(uid)
        if not user:
            await update.message.reply_text("❌ Сначала введите данные через /start")
            return

        proc = await update.message.reply_text("🔮 Генерирую персональный гороскоп…")
        try:
            horo = await self.horoscope_service.get_daily_horoscope(user["matrix"])
            await proc.delete()
            for i in range(0, len(horo), 4096):
                await update.message.reply_text(horo[i : i + 4096], parse_mode="Markdown")
        except Exception as exc:
            await proc.delete()
            log.error(f"Horoscope error: {exc}")
            await update.message.reply_text("❌ Ошибка получения гороскопа.")
        await self.show_main_keyboard(update, None)

    async def only_matrix(self, update: Update, _: CallbackContext):
        uid = update.effective_user.id
        user = self.store.get(uid)
        if not user:
            await update.message.reply_text("❌ Сначала введите данные через /start")
            return

        mat = user["matrix"]
        add = ".".join(map(str, mat["additional"]))
        txt = f"""\n📊 *ВАША МАТРИЦА* 📊

*Дата:* {mat['date']}
*Знак:* {mat['zodiac']}
*Доп. числа:* {add}

{self.matrix_calc.format_matrix_display(mat)}
"""
        await update.message.reply_text(txt, parse_mode="Markdown")
        await self.show_main_keyboard(update, None)

    async def about(self, update: Update, _: CallbackContext):
        txt = """\n🤖 *НУМЕРОЛОГИЧЕСКИЙ БОТ* 🤖

Этот бот рассчитывает вашу персональную нумерологическую матрицу и гороскопы.
"""
        await update.message.reply_text(txt, parse_mode="Markdown")
        await self.show_main_keyboard(update, None)

    async def show_main_keyboard(self, update: Update, _: CallbackContext):
        kb = [
            [
                KeyboardButton("🔮 Полная матрица"),
                KeyboardButton("🌟 Гороскоп на сегодня"),
            ],
            [
                KeyboardButton("📊 Только матрица 3x3"),
                KeyboardButton("ℹ️ О боте"),
            ],
        ]
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        )

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
        log.error(f"Error: {ctx.error}")
        try:
            await update.message.reply_text("❌ Произошла ошибка.")
        except Exception:
            pass


# --------------------------------------------------------------------
# 4️⃣ СБОРКА APPLICATION
# --------------------------------------------------------------------
def build_application() -> Application:
    app = Application.builder().token(Config.BOT_TOKEN).build()
    bot = NumerologyBot()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", bot.start)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_date)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_gender)],
        },
        fallbacks=[CommandHandler("start", bot.start)],
    )
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    app.add_error_handler(bot.error_handler)
    return app


# --------------------------------------------------------------------
# 5️⃣ MAIN - ИСПРАВЛЕННАЯ ВЕРСИЯ
# --------------------------------------------------------------------
async def main() -> None:
    # 1. Инициализируем приложение бота
    ptb_app = build_application()
    
    # 2. Получаем настройки окружения
    port = int(os.getenv("PORT", 8080))
    external_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if not external_host:
        # Для локального теста, если переменная не задана
        log.warning("RENDER_EXTERNAL_HOSTNAME не задан. Используем локальный режим или упадем.")
    
    webhook_url = f"https://{external_host}/webhook" if external_host else None

    # 3. Инициализация и старт бота (без запуска встроенного сервера)
    await ptb_app.initialize()
    await ptb_app.start()
    
    # Устанавливаем вебхук только если есть внешний хост
    if webhook_url:
        log.info(f"Setting webhook to: {webhook_url}")
        await ptb_app.bot.set_webhook(webhook_url)
    else:
        log.warning("Webhook URL не сформирован, бот не будет получать обновления!")

    # 4. Создаем веб-приложение aiohttp для обработки запросов
    web_app = web.Application()

    # --- Обработчик обновлений от Telegram ---
    async def telegram_webhook(request):
        """Принимает POST запрос от Telegram и передает его в PTB App"""
        if request.content_type == 'application/json':
            json_data = await request.json()
            update = Update.de_json(json_data, ptb_app.bot)
            await ptb_app.process_update(update)
            return web.Response()
        return web.Response(status=403)

    # --- Простой Health Check для Render ---
    async def health_check(request):
        return web.Response(text="Bot is running OK", status=200)

    # Регистрируем маршруты
    web_app.router.add_post("/webhook", telegram_webhook)
    web_app.router.add_get("/health", health_check)
    web_app.router.add_get("/", health_check) # Render иногда пингует корень

    # 5. Запускаем веб-сервер
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    log.info(f"Server started on 0.0.0.0:{port}")

    # Держим цикл живым
    try:
        # Ждем бесконечно, пока не придет сигнал остановки
        stop_event = asyncio.Event()
        await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        # Корректное завершение
        await ptb_app.stop()
        await ptb_app.shutdown()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
