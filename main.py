import os
import threading
import logging
import html
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer # Добавлено для веб-сервера

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

from config import Config
from matrix_calculator import MatrixCalculator
from horoscope_service import HoroscopeService

# --- СЕКЦИЯ ДЛЯ RENDER (Health Check) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_health_check():
    # Render передает порт в переменную окружения PORT
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()
# ----------------------------------------

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
log = logging.getLogger(__name__)

# Хранилище пользователей
user_store = {}

class NumerologyBot:
    def __init__(self):
        self.matrix_calc = MatrixCalculator()
        self.horoscope_service = HoroscopeService()

    def get_main_keyboard(self):
        """Главное меню (нижние кнопки)"""
        keyboard = [
            ['📊 Моя Матрица', '📖 Интерпретации'],
            ['🔮 Гороскоп на сегодня', '🔄 Сбросить данные']
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user_name = update.effective_user.first_name or "друг"
        
        await update.message.reply_text(
            f"Привет, {user_name}! ✨\n\nЯ помогу тебе рассчитать твою Матрицу Судьбы.\n"
            "Введите дату рождения в формате: <b>ДД.ММ.ГГГГ</b> (например: 15.05.1992)",
            parse_mode="HTML",
            reply_markup=self.get_main_keyboard()
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        uid = query.from_user.id

        if query.data == "show_matrix":
            await self.show_matrix_callback(update, context)
        elif query.data == "show_interp":
            await self.show_interpretations_callback(update, context)
        elif query.data.startswith("gender_"):
            gender = "мужской" if query.data == "gender_male" else "женский"
            if uid not in user_store: user_store[uid] = {}
            user_store[uid]["gender"] = gender
            
            if "temp_date" in user_store[uid]:
                date = user_store[uid].pop("temp_date")
                await query.edit_message_text(f"✅ Пол: {gender}. Считаю для {date}...")
                await self.process_birth_date(update, context, date)
            else:
                await query.edit_message_text(f"✅ Пол выбран. Теперь введите дату (ДД.ММ.ГГГГ):")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        uid = update.effective_user.id

        if text == '📊 Моя Матрица':
            await self.show_matrix_callback(update, context)
        elif text == '📖 Интерпретации':
            await self.show_interpretations_callback(update, context)
        elif text == '🔮 Гороскоп на сегодня':
            await self.daily_horoscope(update, context)
        elif text == '🔄 Сбросить данные':
            user_store.pop(uid, None)
            await update.message.reply_text("Данные сброшены. Введите новую дату:")
        else:
            await self.process_birth_date(update, context, text)

    async def process_birth_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE, date_str: str):
        uid = update.effective_user.id
        msg = update.effective_message

        try:
            birth_date_obj = datetime.strptime(date_str, "%d.%m.%Y")
            user = user_store.get(uid, {})
            
            if not user.get("gender"):
                if uid not in user_store: user_store[uid] = {}
                user_store[uid]["temp_date"] = date_str
                keyboard = [[
                    InlineKeyboardButton("👨 Мужской", callback_data="gender_male"),
                    InlineKeyboardButton("👩 Женский", callback_data="gender_female")
                ]]
                await msg.reply_text("Выберите ваш пол:", reply_markup=InlineKeyboardMarkup(keyboard))
                return

            matrix = self.matrix_calc.calculate_matrix(date_str)
            zodiac = self._get_zodiac(birth_date_obj.day, birth_date_obj.month)
            
            user_store[uid].update({
                "matrix": matrix, "date": date_str, "zodiac": zodiac
            })

            await msg.reply_text(f"🎉 Матрица для {date_str} готова!", reply_markup=self.get_main_keyboard())
            await self.show_matrix_callback(update, context)

        except ValueError:
            if not update.callback_query:
                await msg.reply_text("⚠️ Ошибка формата. Нужно: ДД.ММ.ГГГГ")

    async def show_matrix_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        msg = update.effective_message
        user = user_store.get(uid)
        
        if not user or "matrix" not in user:
            await msg.reply_text("Сначала введите дату рождения.")
            return

        matrix_table = self.matrix_calc.format_matrix_display(user["matrix"])
        
        info = f"👤 <b>Дата:</b> {user['date']} | {user['zodiac']}\n\n"
        keyboard = [[InlineKeyboardButton("📖 Читать расшифровку", callback_data="show_interp")]]
        
        await msg.reply_text(
            f"{info}<code>{matrix_table}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_interpretations_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        msg = update.effective_message
        user = user_store.get(uid)
        
        if not user or "matrix" not in user:
            await msg.reply_text("Данные не найдены.")
            return

        try:
            text = self.matrix_calc.get_interpretations(user["matrix"], user["gender"])
            
            if len(text) > 4000:
                for i in range(0, len(text), 4000):
                    await msg.reply_text(text[i:i+4000], parse_mode="Markdown")
            else:
                await msg.reply_text(text, parse_mode="Markdown")
        except Exception as e:
            log.error(f"Ошибка вывода расшифровки: {e}")
            await msg.reply_text("❌ Произошла ошибка при формировании расшифровки.")

    async def daily_horoscope(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        msg = update.effective_message
        user = user_store.get(uid)
        
        if not user or "zodiac" not in user:
            await msg.reply_text("Сначала введите дату рождения.")
            return

        status = await msg.reply_text(f"⏳ Считываю прогноз для знака {user['zodiac']}...")
        horo = await self.horoscope_service.get_daily_horoscope(user)
        await status.edit_text(f"✨ <b>Гороскоп ({user['zodiac']})</b>\n\n{html.escape(horo)}", parse_mode="HTML")

    def _get_zodiac(self, day, month):
        zodiacs = [(21, 3, "Овен"), (21, 4, "Телец"), (22, 5, "Близнецы"), (22, 6, "Рак"), (23, 7, "Лев"), (24, 8, "Дева"), (24, 9, "Весы"), (24, 10, "Скорпион"), (23, 11, "Стрелец"), (22, 12, "Козерог"), (21, 1, "Водолей"), (20, 2, "Рыбы")]
        for d, m, name in reversed(zodiacs):
            if (month == m and day >= d) or month > m: return name
        return "Козерог"

def main():
    # 1. Запускаем веб-сервер в фоновом потоке
    threading.Thread(target=run_health_check, daemon=True).start()
    log.info("Health check server started...")

    # 2. Запускаем бота
    app = Application.builder().token(Config.BOT_TOKEN).build()
    bot = NumerologyBot()
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CallbackQueryHandler(bot.button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    log.info("Bot starting polling...")
    app.run_polling()

if __name__ == '__main__':
    main()
