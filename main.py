import os
import logging
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
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
        """Команда /start: приветствие и запрос даты."""
        reply_keyboard = [['Узнать свою судьбу 🔮']]
        await update.message.reply_text(
            "Привет! Я твой персональный нумеролог и астролог.\n"
            "Я рассчитаю твою психоматрицу и составлю агрегированный гороскоп из нескольких источников.\n\n"
            "Нажми на кнопку ниже, чтобы начать!",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        )

    async def request_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запрос даты рождения."""
        await update.message.reply_text(
            "Введите дату вашего рождения в формате: *ДД.ММ.ГГГГ*\n"
            "(Например: 15.05.1992)",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Центральный обработчик текстовых сообщений."""
        text = update.message.text
        uid = update.effective_user.id

        if text == "Узнать свою судьбу 🔮":
            await self.request_date(update, context)
            return

        if text == "📊 Моя Матрица":
            await self.show_matrix(update, context)
            return
        
        if text == "🔮 Гороскоп на сегодня":
            await self.daily_horoscope(update, context)
            return
        
        if text == "📝 Сменить дату":
            await self.request_date(update, context)
            return

        # Попытка обработать ввод даты
        try:
            birth_date = datetime.strptime(text, "%d.%m.%Y")
            
            # Расчет матрицы
            matrix = self.matrix_calc.calculate_matrix(text)
            if not matrix:
                await update.message.reply_text("❌ Не удалось рассчитать матрицу. Проверьте дату.")
                return

            zodiac = self._get_zodiac(birth_date.day, birth_date.month)
            matrix["zodiac"] = zodiac
            
            # Сохраняем данные
            user_store[uid] = {
                "matrix": matrix,
                "date": text,
                "zodiac": zodiac
            }

            reply_keyboard = [
                ['📊 Моя Матрица', '🔮 Гороскоп на сегодня'],
                ['📝 Сменить дату']
            ]
            await update.message.reply_text(
                f"✅ Данные приняты! Ваш знак: *{zodiac}*.",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
            )
            
            # Автоматический показ матрицы после ввода даты
            await self.show_matrix(update, context)

        except ValueError:
            if not text.startswith('/'):
                await update.message.reply_text("⚠️ Введите дату корректно (ДД.ММ.ГГГГ), например: 01.01.1990")

    async def show_matrix(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вывод психоматрицы в моноширинном формате."""
        uid = update.effective_user.id
        user = user_store.get(uid)

        if not user:
            await self.request_date(update, context)
            return

        # Вызываем метод красивой отрисовки из MatrixCalculator
        matrix_table = self.matrix_calc.format_matrix_display(user["matrix"])
        
        response = (
            f"📊 *ВАША ПСИХОМАТРИЦА*\n"
            f"📅 Дата: `{user['date']}`\n"
            f"✨ Знак: *{user['zodiac']}*\n\n"
            f"```\n{matrix_table}\n```\n"
            f"💡 _Каждая ячейка отражает силу ваших врожденных качеств._"
        )
        await update.message.reply_text(response, parse_mode="Markdown")

    async def daily_horoscope(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вывод агрегированного гороскопа."""
        uid = update.effective_user.id
        user = user_store.get(uid)

        if not user:
            await self.request_date(update, context)
            return

        status_msg = await update.message.reply_text("🔮 _Анализирую источники и положение планет..._", parse_mode="Markdown")
        
        try:
            # Вызов AI-сервиса с асинхронным парсингом
            horo_text = await self.horoscope_service.get_daily_horoscope(user)
            await status_msg.delete()
            await update.message.reply_text(horo_text, parse_mode="Markdown")
        except Exception as e:
            log.error(f"Ошибка гороскопа: {e}")
            await status_msg.edit_text(f"❌ Извините, сейчас звезды скрыты за тучами. Попробуйте позже.")

    def _get_zodiac(self, day, month):
        """Логика определения знака зодиака."""
        zodiacs = [
            (21, 3, "Овен"), (21, 4, "Телец"), (22, 5, "Близнецы"),
            (22, 6, "Рак"), (23, 7, "Лев"), (24, 8, "Дева"),
            (24, 9, "Весы"), (24, 10, "Скорпион"), (23, 11, "Стрелец"),
            (22, 12, "Козерог"), (21, 1, "Водолей"), (20, 2, "Рыбы")
        ]
        for d, m, name in reversed(zodiacs):
            if (month == m and day >= d) or month > m:
                return name
        return "Козерог"

def main():
    """Точка входа (синхронная для управления циклом событий внутри PTB)."""
    bot_logic = NumerologyBot()
    
    if not Config.BOT_TOKEN:
        log.error("BOT_TOKEN не установлен в переменных окружения!")
        return

    # Инициализация приложения
    application = Application.builder().token(Config.BOT_TOKEN).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", bot_logic.start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_logic.handle_message))

    # Логика запуска: Webhook для Render или Polling для локальной разработки
    port = int(os.environ.get("PORT", 10000))
    url_path = os.environ.get("RENDER_EXTERNAL_HOSTNAME") 

    if url_path:
        log.info(f"Запуск Webhook: https://{url_path}/webhook")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="webhook",
            webhook_url=f"https://{url_path}/webhook"
        )
    else:
        log.info("Запуск локального Polling...")
        application.run_polling()

if __name__ == '__main__':
    # ВАЖНО: В PTB v20+ не используем asyncio.run() для run_polling/run_webhook
    main()
