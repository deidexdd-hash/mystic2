import os
import logging
import html
from datetime import datetime

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
        """Создает главное меню кнопок"""
        keyboard = [
            ['📊 Моя Матрица', '📖 Интерпретации'],
            ['🔮 Гороскоп на сегодня', '🔄 Сбросить данные']
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        uid = update.effective_user.id
        user_name = update.effective_user.first_name or "друг"
        
        await update.message.reply_text(
            f"Привет, {user_name}! ✨\n\nЯ помогу тебе рассчитать твою Матрицу Судьбы и составить персональный гороскоп.\n\n"
            "Введите дату рождения в формате: <b>ДД.ММ.ГГГГ</b>\n"
            "Например: 15.05.1992",
            parse_mode="HTML",
            reply_markup=self.get_main_keyboard()
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка Inline-кнопок"""
        query = update.callback_query
        await query.answer()
        uid = query.from_user.id

        if query.data == "show_matrix":
            await self.show_matrix_callback(update, context)
        
        elif query.data == "show_interp":
            await self.show_interpretations_callback(update, context)

        elif query.data == "get_horoscope":
            await self.daily_horoscope(update, context)

        elif query.data.startswith("gender_"):
            gender = "мужской" if query.data == "gender_male" else "женский"
            if uid not in user_store: user_store[uid] = {}
            user_store[uid]["gender"] = gender
            
            # Если была введена дата ДО выбора пола
            if "temp_date" in user_store[uid]:
                saved_date = user_store[uid].pop("temp_date")
                await query.edit_message_text(f"✅ Пол: <b>{gender}</b>. Считаю матрицу для <b>{saved_date}</b>...", parse_mode="HTML")
                await self.process_birth_date(update, context, saved_date)
            else:
                await query.edit_message_text(f"✅ Пол выбран: <b>{gender}</b>. Теперь введите дату рождения (ДД.ММ.ГГГГ):", parse_mode="HTML")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текста из главного меню или ввод даты"""
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
            await update.message.reply_text("Данные сброшены. Введите новую дату рождения (ДД.ММ.ГГГГ):")
        else:
            await self.process_birth_date(update, context, text)

    async def process_birth_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE, date_str: str):
        """Логика расчета и сохранения данных"""
        uid = update.effective_user.id
        # Проверяем, откуда вызываем (кнопка или сообщение)
        msg = update.callback_query.message if update.callback_query else update.message

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
                await msg.reply_text("Пожалуйста, выберите ваш пол для расчета:", reply_markup=InlineKeyboardMarkup(keyboard))
                return

            # Расчет
            matrix = self.matrix_calc.calculate_matrix(date_str)
            zodiac = self._get_zodiac(birth_date_obj.day, birth_date_obj.month)
            
            user_store[uid].update({
                "matrix": matrix,
                "date": date_str,
                "zodiac": zodiac
            })

            await msg.reply_text(
                f"🎉 Расчет готов!",
                reply_markup=self.get_main_keyboard()
            )
            # Показываем результат
            await self.show_matrix_callback(update, context)

        except ValueError:
            if not update.callback_query:
                await msg.reply_text("Неверный формат даты. Введите ДД.ММ.ГГГГ (например: 15.05.1992)")

    async def show_matrix_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вывод таблицы матрицы"""
        uid = update.effective_user.id
        msg = update.callback_query.message if update.callback_query else update.message
        
        user = user_store.get(uid)
        if not user or "matrix" not in user:
            await msg.reply_text("Сначала введите дату рождения.")
            return

        matrix_display = self.matrix_calc.format_matrix_display(
            user["matrix"], user["date"], user["zodiac"], user["gender"]
        )
        
        # Экранирование для MarkdownV2
        safe_matrix = matrix_display.replace('-', '\\-').replace('.', '\\.').replace('(', '\\(').replace(')', '\\)')
        
        keyboard = [[InlineKeyboardButton("📖 Читать расшифровку", callback_data="show_interp")]]
        await msg.reply_text(
            f"📊 <b>Ваша Матрица Судьбы:</b>\n\n<code>{safe_matrix}</code>",
            parse_mode="HTML", # Используем HTML + тег code для моноширинности (так надежнее)
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_interpretations_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вывод детальных интерпретаций"""
        uid = update.effective_user.id
        msg = update.callback_query.message if update.callback_query else update.message
        
        user = user_store.get(uid)
        if not user or "matrix" not in user:
            await msg.reply_text("Сначала рассчитайте матрицу.")
            return

        from interpretations import Interpretations
        interp_gen = Interpretations()
        text = interp_gen.get_full_interpretation(user["matrix"], user["gender"])
        
        # Разбивка текста
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                await msg.reply_text(text[i:i+4000])
        else:
            await msg.reply_text(text)

    async def daily_horoscope(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Гороскоп через HTML (безопасный режим)"""
        uid = update.effective_user.id
        msg = update.callback_query.message if update.callback_query else update.message
        user = user_store.get(uid)
        
        if not user or "zodiac" not in user:
            await msg.reply_text("Сначала введите дату рождения.")
            return

        status_msg = await msg.reply_text(f"⏳ Составляю прогноз для {user['zodiac']}...")
        
        try:
            horo_text = await self.horoscope_service.get_daily_horoscope(user)
            header = f"✨ <b>Гороскоп ({user['zodiac']})</b> ✨\n\n"
            safe_body = html.escape(horo_text)
            
            try:
                await status_msg.edit_text(header + safe_body, parse_mode="HTML")
            except:
                await status_msg.edit_text(header + horo_text)
        except Exception as e:
            log.error(f"Ошибка: {e}")
            await msg.reply_text("❌ Ошибка при получении прогноза.")

    def _get_zodiac(self, day: int, month: int) -> str:
        zodiacs = [
            (21, 3, "♈ Овен"), (21, 4, "♉ Телец"), (22, 5, "♊ Близнецы"),
            (22, 6, "♋ Рак"), (23, 7, "♌ Лев"), (24, 8, "♍ Дева"),
            (24, 9, "♎ Весы"), (24, 10, "♏ Скорпион"), (23, 11, "♐ Стрелец"),
            (22, 12, "♑ Козерог"), (21, 1, "♒ Водолей"), (20, 2, "♓ Рыбы")
        ]
        for d, m, name in reversed(zodiacs):
            if (month == m and day >= d) or month > m:
                return name
        return "♑ Козерог"

def main():
    if not Config.BOT_TOKEN: return
    bot_logic = NumerologyBot()
    application = Application.builder().token(Config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", bot_logic.start))
    application.add_handler(CallbackQueryHandler(bot_logic.button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_logic.handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()
