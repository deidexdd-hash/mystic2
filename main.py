import os
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

# Хранилище пользователей в памяти
user_store = {}

class NumerologyBot:
    def __init__(self):
        self.matrix_calc = MatrixCalculator()
        self.horoscope_service = HoroscopeService()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start: приветствие и запрос данных."""
        uid = update.effective_user.id
        user_name = update.effective_user.first_name or "друг"
        
        # Проверяем, есть ли уже данные пользователя
        existing_user = user_store.get(uid)
        
        if existing_user and existing_user.get("matrix"):
            keyboard = [
                ['📊 Моя Матрица', '📖 Интерпретации'],
                ['🔮 Гороскоп на сегодня', '🔄 Сбросить данные']
            ]
            from telegram import ReplyKeyboardMarkup
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                f"С возвращением, {user_name}! Что посчитаем сегодня?",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"Привет, {user_name}! ✨\n\nЯ помогу тебе рассчитать твою Матрицу Судьбы и составить персональный гороскоп.\n\n"
                "Для начала введите вашу дату рождения в формате: *ДД.ММ.ГГГГ*\n"
                "Например: 15.05.1992",
                parse_mode="Markdown"
            )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на Inline-кнопки"""
        query = update.callback_query
        await query.answer()
        uid = query.from_user.id

        if query.data == "show_matrix":
            await self.show_matrix_callback(query, context)
        
        elif query.data == "show_interp":
            await self.show_interpretations_callback(query, context)

        elif query.data == "get_horoscope":
            await self.daily_horoscope_callback(query, context)

        elif query.data.startswith("gender_"):
            gender = "мужской" if query.data == "gender_male" else "женский"
            
            if uid not in user_store:
                user_store[uid] = {}
            user_store[uid]["gender"] = gender
            
            gender_emoji = "👨" if gender == "мужской" else "👩"
            
            # ПРОВЕРКА ДУБЛИРОВАНИЯ: если дата уже была введена ранее
            if "temp_date" in user_store[uid]:
                saved_date = user_store[uid].pop("temp_date")
                await query.edit_message_text(
                    f"{gender_emoji} Пол выбран: *{gender}*\n📅 Провожу расчет для даты: *{saved_date}*...",
                    parse_mode="Markdown"
                )
                # Вызываем процесс обработки даты напрямую
                await self.process_birth_date(query, context, saved_date)
            else:
                await query.edit_message_text(
                    f"{gender_emoji} Пол выбран: *{gender}*.\n\nТеперь введите вашу дату рождения (ДД.ММ.ГГГГ):",
                    parse_mode="Markdown"
                )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Основной обработчик текстовых сообщений"""
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
            # Пытаемся распарсить дату
            await self.process_birth_date(update, context, text)

    async def process_birth_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE, date_str: str):
        """Логика расчета матрицы"""
        uid = update.effective_user.id
        # Определяем, откуда пришел вызов (сообщение или кнопка)
        msg_obj = update.message if update.message else update.callback_query.message
        
        try:
            # Проверка формата даты
            birth_date_obj = datetime.strptime(date_str, "%d.%m.%Y")
            if not (1900 <= birth_date_obj.year <= 2026):
                await msg_obj.reply_text("Пожалуйста, введите корректный год (от 1900 до 2026).")
                return

            # Проверяем наличие пола
            user = user_store.get(uid, {})
            if not user.get("gender"):
                if uid not in user_store: user_store[uid] = {}
                user_store[uid]["temp_date"] = date_str  # Сохраняем дату, чтобы не запрашивать дважды
                
                keyboard = [
                    [
                        InlineKeyboardButton("👨 Мужской", callback_data="gender_male"),
                        InlineKeyboardButton("👩 Женский", callback_data="gender_female")
                    ]
                ]
                await msg_obj.reply_text(
                    "Для точного расчета выберите ваш пол:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            # Если пол есть, считаем
            status_msg = await msg_obj.reply_text("🔮 Звезды выстраиваются в ряд... Считаю вашу матрицу...")
            
            matrix = self.matrix_calc.calculate_matrix(date_str)
            zodiac = self._get_zodiac(birth_date_obj.day, birth_date_obj.month)
            
            user_store[uid].update({
                "matrix": matrix,
                "date": date_str,
                "zodiac": zodiac
            })

            from telegram import ReplyKeyboardMarkup
            keyboard = [['📊 Моя Матрица', '📖 Интерпретации'], ['🔮 Гороскоп на сегодня', '🔄 Сбросить данные']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await status_msg.delete()
            await msg_obj.reply_text(
                f"✅ Расчет готов для даты {date_str}!\nВоспользуйтесь меню ниже для просмотра.",
                reply_markup=reply_markup
            )
            await self.show_matrix_callback(update, context)

        except ValueError:
            if not update.callback_query: # Не отвечаем на ошибки, если это был автоматический вызов
                await msg_obj.reply_text("Неверный формат даты. Используйте: ДД.ММ.ГГГГ (например, 15.05.1992)")

    async def show_matrix_callback(self, update_or_query, context):
        """Отображение таблицы матрицы"""
        is_query = hasattr(update_or_query, "callback_query") or hasattr(update_or_query, "data")
        uid = update_or_query.from_user.id if is_query else update_or_query.effective_user.id
        msg = update_or_query.message if is_query else update_or_query.message
        
        user = user_store.get(uid)
        if not user or "matrix" not in user:
            await msg.reply_text("Сначала введите дату рождения.")
            return

        matrix_text = self.matrix_calc.format_matrix_display(user["matrix"], user["date"], user["zodiac"], user["gender"])
        
        keyboard = [[InlineKeyboardButton("📖 Читать интерпретации", callback_data="show_interp")]]
        await msg.reply_text(f"```{matrix_text}```", parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_interpretations_callback(self, update_or_query, context):
        uid = update_or_query.from_user.id if hasattr(update_or_query, "data") else update_or_query.effective_user.id
        msg = update_or_query.message if hasattr(update_or_query, "data") else update_or_query.message
        
        user = user_store.get(uid)
        from interpretations import Interpretations
        interp_gen = Interpretations()
        text = interp_gen.get_full_interpretation(user["matrix"], user["gender"])
        
        # Разбивка длинного текста
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                await msg.reply_text(text[i:i+4000], parse_mode="Markdown")
        else:
            await msg.reply_text(text, parse_mode="Markdown")

    async def daily_horoscope(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = user_store.get(uid)
        
        if not user or "zodiac" not in user:
            await update.message.reply_text("Пожалуйста, сначала введите дату рождения, чтобы я узнал ваш знак зодиака.")
            return

        status_msg = await update.message.reply_text(f"⏳ Составляю прогноз для знака {user['zodiac']}...")
        
        try:
            horo_text = await self.horoscope_service.get_daily_horoscope(user)
            header = f"✨ *Гороскоп на сегодня* ({user['zodiac']}) ✨\n\n"
            
            # ПРАВКА: Безопасная отправка Markdown
            try:
                await status_msg.edit_text(header + horo_text, parse_mode="Markdown")
            except Exception:
                await status_msg.edit_text(header + horo_text) # Если падает — шлем без разметки

        except Exception as e:
            log.error(f"Ошибка гороскопа: {e}")
            await update.message.reply_text("❌ Извините, сейчас звезды скрыты за тучами. Попробуйте позже.")

    async def daily_horoscope_callback(self, query, context):
        uid = query.from_user.id
        user = user_store.get(uid)
        await query.message.reply_text(f"⏳ Составляю прогноз для {user['zodiac']}...")
        horo_text = await self.horoscope_service.get_daily_horoscope(user)
        header = f"✨ *Гороскоп на сегодня* ({user['zodiac']}) ✨\n\n"
        
        try:
            await query.message.reply_text(header + horo_text, parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(header + horo_text)

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
    bot_logic = NumerologyBot()
    if not Config.BOT_TOKEN:
        log.error("BOT_TOKEN не установлен!")
        return

    application = Application.builder().token(Config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", bot_logic.start))
    application.add_handler(CallbackQueryHandler(bot_logic.button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_logic.handle_message))

    # Запуск
    application.run_polling()

if __name__ == '__main__':
    main()
