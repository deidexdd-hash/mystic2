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

# Хранилище пользователей в памяти
user_store = {}

class NumerologyBot:
    def __init__(self):
        self.matrix_calc = MatrixCalculator()
        self.horoscope_service = HoroscopeService()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        uid = update.effective_user.id
        user_name = update.effective_user.first_name or "друг"
        
        # Главное меню
        keyboard = [
            ['📊 Моя Матрица', '📖 Интерпретации'],
            ['🔮 Гороскоп на сегодня', '🔄 Сбросить данные']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"Привет, {user_name}! ✨\n\nЯ помогу тебе рассчитать твою Матрицу Судьбы и составить персональный гороскоп.\n\n"
            "Введите дату рождения в формате: <b>ДД.ММ.ГГГГ</b>\n"
            "Например: 15.05.1992",
            parse_mode="HTML",
            reply_markup=reply_markup
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
            
            if uid not in user_store:
                user_store[uid] = {}
            user_store[uid]["gender"] = gender
            
            gender_emoji = "👨" if gender == "мужской" else "👩"
            
            # --- ИСПРАВЛЕНИЕ ДУБЛИРОВАНИЯ ---
            if "temp_date" in user_store[uid]:
                saved_date = user_store[uid].pop("temp_date")
                await query.edit_message_text(f"{gender_emoji} Пол выбран: <b>{gender}</b>. Провожу расчет...", parse_mode="HTML")
                # Вызываем расчет для сохраненной даты
                await self.process_birth_date(update, context, saved_date)
            else:
                await query.edit_message_text(
                    f"{gender_emoji} Пол выбран: <b>{gender}</b>.\n\nТеперь введите дату рождения (ДД.ММ.ГГГГ):",
                    parse_mode="HTML"
                )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текста"""
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
            # Считаем, что пользователь ввел дату
            await self.process_birth_date(update, context, text)

    async def process_birth_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE, date_str: str):
        """Расчет матрицы"""
        uid = update.effective_user.id
        # Проверяем, откуда пришел запрос (сообщение или кнопка)
        is_callback = update.callback_query is not None
        msg = update.callback_query.message if is_callback else update.message

        try:
            # Валидация даты
            birth_date_obj = datetime.strptime(date_str, "%d.%m.%Y")
            if not (1900 <= birth_date_obj.year <= 2026):
                await msg.reply_text("Пожалуйста, укажите реальный год рождения (1900-2026).")
                return

            # Проверка пола
            user = user_store.get(uid, {})
            if not user.get("gender"):
                # --- ЗАПОМИНАЕМ ДАТУ ---
                if uid not in user_store: user_store[uid] = {}
                user_store[uid]["temp_date"] = date_str 

                keyboard = [
                    [
                        InlineKeyboardButton("👨 Мужской", callback_data="gender_male"),
                        InlineKeyboardButton("👩 Женский", callback_data="gender_female")
                    ]
                ]
                await msg.reply_text(
                    "Для расчета матрицы выберите ваш пол:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            # Расчет
            status_msg = await msg.reply_text("🔮 Считываю информацию с полей вероятности...")
            
            matrix = self.matrix_calc.calculate_matrix(date_str)
            zodiac = self._get_zodiac(birth_date_obj.day, birth_date_obj.month)
            
            user_store[uid].update({
                "matrix": matrix,
                "date": date_str,
                "zodiac": zodiac
            })

            await status_msg.delete()
            await msg.reply_text(f"✅ Матрица для даты {date_str} успешно рассчитана!")
            
            # Сразу показываем матрицу
            await self.show_matrix_callback(update, context)

        except ValueError:
            if not is_callback: # Чтобы не спамить ошибкой на нажатия кнопок
                await msg.reply_text("Неверный формат даты. Используйте: ДД.ММ.ГГГГ (например, 15.05.1992)")

    async def daily_horoscope(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение гороскопа с защитой от ошибок разметки"""
        uid = update.effective_user.id
        is_callback = update.callback_query is not None
        msg = update.callback_query.message if is_callback else update.message
        
        user = user_store.get(uid)
        if not user or "zodiac" not in user:
            await msg.reply_text("Сначала введите дату рождения, чтобы я узнал ваш знак.")
            return

        # Отправляем новое сообщение вместо редактирования старого (так надежнее)
        status_msg = await msg.reply_text(f"⏳ Составляю прогноз для знака {user['zodiac']}...")
        
        try:
            horo_text = await self.horoscope_service.get_daily_horoscope(user)
            
            # Формируем заголовок (жирным через HTML)
            header = f"✨ <b>Гороскоп на сегодня ({user['zodiac']})</b> ✨\n\n"
            
            # Очищаем текст от < > чтобы HTML не сломался
            safe_body = html.escape(horo_text)
            full_text = header + safe_body

            try:
                # Пытаемся отправить красиво в HTML
                await status_msg.edit_text(full_text, parse_mode="HTML")
            except Exception:
                # Если все равно ошибка (например, слишком длинный текст) — шлем простым текстом
                await status_msg.edit_text(header + horo_text)

        except Exception as e:
            log.error(f"Ошибка гороскопа: {e}")
            # Если редактирование не сработало, просто шлем новое сообщение
            await msg.reply_text("❌ Извините, звезды сегодня капризничают. Попробуйте чуть позже.")

    async def show_matrix_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вывод матрицы"""
        uid = update.effective_user.id
        is_callback = update.callback_query is not None
        msg = update.callback_query.message if is_callback else update.message
        
        user = user_store.get(uid)
        if not user or "matrix" not in user:
            await msg.reply_text("Данные не найдены. Введите дату рождения.")
            return

        # Используем MarkdownV2 только для моноширинного шрифта таблицы
        matrix_display = self.matrix_calc.format_matrix_display(
            user["matrix"], user["date"], user["zodiac"], user["gender"]
        )
        
        keyboard = [[InlineKeyboardButton("📖 Читать интерпретации", callback_data="show_interp")]]
        
        # Экранируем спецсимволы для MarkdownV2 (важно!)
        safe_matrix = matrix_display.replace('-', '\\-').replace('.', '\\.').replace('(', '\\(').replace(')', '\\)')
        
        await msg.reply_text(
            f"```\n{safe_matrix}\n```",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_interpretations_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вывод детальной расшифровки"""
        uid = update.effective_user.id
        is_callback = update.callback_query is not None
        msg = update.callback_query.message if is_callback else update.message
        
        user = user_store.get(uid)
        from interpretations import Interpretations
        interp_gen = Interpretations()
        
        text = interp_gen.get_full_interpretation(user["matrix"], user["gender"])
        
        # Разбиваем на части, если текст длиннее 4000 символов
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts:
                await msg.reply_text(part)
        else:
            await msg.reply_text(text)

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
    if not Config.BOT_TOKEN:
        log.error("BOT_TOKEN не найден!")
        return

    bot_logic = NumerologyBot()
    application = Application.builder().token(Config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", bot_logic.start))
    application.add_handler(CallbackQueryHandler(bot_logic.button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_logic.handle_message))

    log.info("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
