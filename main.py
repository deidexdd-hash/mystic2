import os
import logging
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
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

# Состояния для ConversationHandler
CHOOSING_GENDER, ENTERING_DATE = range(2)

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
            # Пользователь уже есть - показываем главное меню
            keyboard = [
                ['📊 Моя Матрица', '📖 Интерпретации'],
                ['🔮 Гороскоп на сегодня', '❓ Помощь'],
                ['🔄 Пересчитать матрицу']
            ]
            await update.message.reply_text(
                f"С возвращением, {user_name}! 👋\n\n"
                f"Ваши данные сохранены:\n"
                f"📅 Дата: {existing_user.get('date', 'не указана')}\n"
                f"⚧ Пол: {existing_user.get('gender', 'не указан')}\n"
                f"✨ Знак: {existing_user.get('zodiac', 'не указан')}\n\n"
                f"Выберите действие:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        else:
            # Новый пользователь - приветствие и начало
            welcome_text = (
                f"✨ Привет, {user_name}! ✨\n\n"
                f"Я — *Мистический Нумеролог* 🔮\n\n"
                f"Я помогу тебе:\n"
                f"📊 Рассчитать психоматрицу Пифагора\n"
                f"📖 Узнать значения всех чисел с учетом пола\n"
                f"🎯 Определить личную и родовую задачи\n"
                f"🔮 Получить гороскоп на сегодня\n\n"
                f"Давай начнем! 👇"
            )
            keyboard = [[InlineKeyboardButton("🚀 Узнать свою судьбу", callback_data="start_calculation")]]
            await update.message.reply_text(
                welcome_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик inline-кнопок"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "start_calculation":
            await self.request_gender(query, context)
        elif query.data.startswith("gender_"):
            gender = "мужской" if query.data == "gender_male" else "женский"
            uid = query.from_user.id
            
            if uid not in user_store:
                user_store[uid] = {}
            user_store[uid]["gender"] = gender
            
            # Эмодзи для визуализации выбора
            gender_emoji = "👨" if gender == "мужской" else "👩"
            await query.edit_message_text(
                f"{gender_emoji} Выбран пол: *{gender}*\n\n"
                f"Теперь введите дату рождения в формате: *ДД.ММ.ГГГГ*\n"
                f"Например: 15.05.1992",
                parse_mode="Markdown"
            )
        elif query.data == "show_matrix":
            await self.show_matrix_callback(query, context)
        elif query.data == "show_interpretations":
            await self.show_interpretations_callback(query, context)
        elif query.data == "show_horoscope":
            await self.daily_horoscope_callback(query, context)
        elif query.data == "recalculate":
            await self.request_gender(query, context)
        elif query.data == "help":
            await self.show_help(query, context)

    async def request_gender(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Запрос пола через inline-кнопки"""
        keyboard = [
            [
                InlineKeyboardButton("👨 Мужской", callback_data="gender_male"),
                InlineKeyboardButton("👩 Женский", callback_data="gender_female")
            ]
        ]
        
        text = (
            "🎭 Укажите ваш пол:\n\n"
            "Это важно для точной интерпретации некоторых аспектов матрицы."
        )
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Центральный обработчик текстовых сообщений."""
        text = update.message.text
        uid = update.effective_user.id

        # Главное меню - кнопки
        if text == "📊 Моя Матрица":
            await self.show_matrix(update, context)
            return
        
        if text == "📖 Интерпретации":
            await self.show_interpretations(update, context)
            return
        
        if text == "🔮 Гороскоп на сегодня":
            await self.daily_horoscope(update, context)
            return
        
        if text == "🔄 Пересчитать матрицу":
            # Показываем inline-кнопки для выбора пола
            keyboard = [
                [
                    InlineKeyboardButton("👨 Мужской", callback_data="gender_male"),
                    InlineKeyboardButton("👩 Женский", callback_data="gender_female")
                ]
            ]
            await update.message.reply_text(
                "🎭 Укажите ваш пол:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        if text == "❓ Помощь":
            await self.show_help_message(update, context)
            return

        # Попытка обработать ввод даты
        if self._is_date_format(text):
            await self.process_birth_date(update, context, text)
            return
        
        # Если не распознали команду
        if not text.startswith('/'):
            await update.message.reply_text(
                "🤔 Не понимаю эту команду.\n"
                "Используйте кнопки меню или нажмите /start для начала.",
                reply_markup=self._get_main_keyboard(uid)
            )

    def _is_date_format(self, text: str) -> bool:
        """Проверка, похоже ли сообщение на дату"""
        try:
            datetime.strptime(text, "%d.%m.%Y")
            return True
        except ValueError:
            return False

    def _get_main_keyboard(self, uid: int):
        """Получение главного меню с кнопками"""
        user = user_store.get(uid)
        
        if user and user.get("matrix"):
            keyboard = [
                ['📊 Моя Матрица', '📖 Интерпретации'],
                ['🔮 Гороскоп на сегодня', '❓ Помощь'],
                ['🔄 Пересчитать матрицу']
            ]
        else:
            keyboard = [['🔄 Рассчитать матрицу']]
        
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    async def process_birth_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE, date_str: str):
        """Обработка введенной даты рождения"""
        uid = update.effective_user.id
        
        try:
            birth_date = datetime.strptime(date_str, "%d.%m.%Y")
            
            # Проверка разумности даты
            current_year = datetime.now().year
            if birth_date.year < 1900 or birth_date.year > current_year:
                await update.message.reply_text(
                    f"⚠️ Некорректный год: {birth_date.year}\n"
                    f"Укажите год между 1900 и {current_year}"
                )
                return
            
            # Проверяем наличие пола
            user = user_store.get(uid, {})
            if not user.get("gender"):
                keyboard = [
                    [
                        InlineKeyboardButton("👨 Мужской", callback_data="gender_male"),
                        InlineKeyboardButton("👩 Женский", callback_data="gender_female")
                    ]
                ]
                await update.message.reply_text(
                    "⚠️ Сначала укажите ваш пол:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
            
            # Показываем процесс расчета
            status_msg = await update.message.reply_text(
                "🔮 *Рассчитываю вашу матрицу...*\n"
                "⏳ Анализирую числа судьбы...",
                parse_mode="Markdown"
            )
            
            # Расчет матрицы
            matrix = self.matrix_calc.calculate_matrix(date_str)
            if not matrix:
                await status_msg.edit_text("❌ Не удалось рассчитать матрицу. Проверьте дату.")
                return

            zodiac = self._get_zodiac(birth_date.day, birth_date.month)
            matrix["zodiac"] = zodiac
            
            # Сохраняем данные
            user_store[uid]["matrix"] = matrix
            user_store[uid]["date"] = date_str
            user_store[uid]["zodiac"] = zodiac
            
            await status_msg.delete()
            
            # Красивое сообщение об успехе
            gender_emoji = "👨" if user.get("gender") == "мужской" else "👩"
            await update.message.reply_text(
                f"✅ *Расчет завершен!*\n\n"
                f"📅 Дата: `{date_str}`\n"
                f"{gender_emoji} Пол: {user.get('gender')}\n"
                f"✨ Знак зодиака: *{zodiac}*\n\n"
                f"🎉 Ваша матрица готова!",
                parse_mode="Markdown",
                reply_markup=self._get_main_keyboard(uid)
            )
            
            # Автоматический показ матрицы
            await self.show_matrix(update, context)

        except ValueError:
            await update.message.reply_text(
                "⚠️ *Неверный формат даты!*\n\n"
                "Используйте формат: *ДД.ММ.ГГГГ*\n"
                "Например: 01.01.1990 или 25.12.2000",
                parse_mode="Markdown"
            )

    async def show_matrix(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вывод психоматрицы с улучшенной сводкой"""
        uid = update.effective_user.id
        user = user_store.get(uid)

        if not user or not user.get("matrix"):
            await update.message.reply_text(
                "⚠️ Сначала рассчитайте матрицу!\n"
                "Нажмите /start для начала."
            )
            return

        matrix = user["matrix"]
        full_array = matrix.get("full_array", [])
        
        # Анализ силы каждой цифры
        def get_count(num):
            return len([x for x in full_array if x == num])
        
        def get_level(count):
            if count == 0: return "❌"
            elif count == 1: return "⚠️"
            elif count in [2,3,4]: return "✅"
            else: return "💪"
        
        counts = {i: get_count(i) for i in range(1, 10)}
        
        # Формируем матрицу с подписями
        matrix_with_labels = (
            f"┏━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓\n"
            f"┃ {' '.join([str(i) for i in full_array if i == 1]) or '—':^7} ┃ {' '.join([str(i) for i in full_array if i == 4]) or '—':^7} ┃ {' '.join([str(i) for i in full_array if i == 7]) or '—':^7} ┃\n"
            f"┃Характер ┃Здоровье ┃  Удача  ┃\n"
            f"┃   {get_level(counts[1])}    ┃   {get_level(counts[4])}    ┃   {get_level(counts[7])}    ┃\n"
            f"┣━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━┫\n"
            f"┃ {' '.join([str(i) for i in full_array if i == 2]) or '—':^7} ┃ {' '.join([str(i) for i in full_array if i == 5]) or '—':^7} ┃ {' '.join([str(i) for i in full_array if i == 8]) or '—':^7} ┃\n"
            f"┃ Энергия ┃ Логика  ┃  Долг   ┃\n"
            f"┃   {get_level(counts[2])}    ┃   {get_level(counts[5])}    ┃   {get_level(counts[8])}    ┃\n"
            f"┣━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━┫\n"
            f"┃ {' '.join([str(i) for i in full_array if i == 3]) or '—':^7} ┃ {' '.join([str(i) for i in full_array if i == 6]) or '—':^7} ┃ {' '.join([str(i) for i in full_array if i == 9]) or '—':^7} ┃\n"
            f"┃Творчест ┃  Труд   ┃ Память  ┃\n"
            f"┃   {get_level(counts[3])}    ┃   {get_level(counts[6])}    ┃   {get_level(counts[9])}    ┃\n"
            f"┗━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━┛"
        )
        
        # Категоризация
        strong = [(i, counts[i]) for i in range(1,10) if counts[i] >= 5]
        good = [(i, counts[i]) for i in range(1,10) if counts[i] in [2,3,4]]
        normal = [(i, counts[i]) for i in range(1,10) if counts[i] == 1]
        weak = [i for i in range(1,10) if counts[i] == 0]
        
        labels = {
            1: "Характер", 2: "Энергия", 3: "Творчество",
            4: "Здоровье", 5: "Логика", 6: "Труд",
            7: "Удача", 8: "Долг", 9: "Память"
        }
        
        # Формируем сводку
        summary = []
        
        if strong:
            summary.append("💪 *Сильные стороны:*")
            for num, count in strong:
                summary.append(f"• {labels[num]} ({count})")
            summary.append("")
        
        if good:
            summary.append("✅ *Хорошо развиты:*")
            for num, count in good:
                summary.append(f"• {labels[num]} ({count})")
            summary.append("")
        
        if normal:
            summary.append("⚠️ *Нормально:*")
            for num, count in normal:
                summary.append(f"• {labels[num]} ({count})")
            summary.append("")
        
        if weak:
            summary.append("❌ *Слабые зоны (требуют развития):*")
            for num in weak:
                summary.append(f"• {labels[num]} - нуждается в развитии")
        
        # Формируем дополнительные числа
        additional = matrix.get("additional", [])
        additional_str = ' → '.join(map(str, additional))
        soul_number = additional[1] if len(additional) > 1 else "?"
        family_number = additional[-1] if additional else "?"
        
        gender_emoji = "👨" if user.get("gender") == "мужской" else "👩"
        
        response = (
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *ВАША ПСИХОМАТРИЦА*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 *Профиль:*\n"
            f"📅 {user['date']} | {gender_emoji} {user.get('gender')} | {user['zodiac']}\n\n"
            f"🔢 *Числа судьбы:*\n"
            f"`{additional_str}`\n"
            f"🎯 Душа: {soul_number} | 👪 Род: {family_number}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"```\n{matrix_with_labels}\n```\n"
            f"*Легенда:* 💪 Очень сильно (5+) | ✅ Хорошо (2-4)\n"
            f"         ⚠️ Норма (1) | ❌ Слабо (нет)\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 *ВАША СВОДКА:*\n\n"
            f"{chr(10).join(summary)}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💡 _Нажмите «Интерпретации» для подробного анализа_"
        )
        
        await update.message.reply_text(response, parse_mode="Markdown")
    
    async def show_matrix_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Вывод матрицы через callback"""
        uid = query.from_user.id
        user = user_store.get(uid)

        if not user or not user.get("matrix"):
            await query.edit_message_text("⚠️ Сначала рассчитайте матрицу!")
            return

        matrix = user["matrix"]
        matrix_table = self.matrix_calc.format_matrix_display(matrix)
        additional = matrix.get("additional", [])
        additional_str = ' → '.join(map(str, additional))
        gender_emoji = "👨" if user.get("gender") == "мужской" else "👩"
        
        response = (
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *ВАША ПСИХОМАТРИЦА*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📅 Дата: `{user['date']}`\n"
            f"{gender_emoji} Пол: {user.get('gender')}\n"
            f"✨ Знак: *{user['zodiac']}*\n\n"
            f"🔢 Доп. числа: `{additional_str}`\n\n"
            f"```\n{matrix_table}\n```"
        )
        
        await query.message.reply_text(response, parse_mode="Markdown")
    
    async def show_interpretations(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вывод интерпретаций матрицы"""
        uid = update.effective_user.id
        user = user_store.get(uid)

        if not user or not user.get("matrix"):
            await update.message.reply_text(
                "⚠️ Сначала рассчитайте матрицу!\n"
                "Нажмите /start для начала."
            )
            return
        
        # Показываем процесс
        status_msg = await update.message.reply_text(
            "📖 *Подготавливаю интерпретации...*",
            parse_mode="Markdown"
        )
        
        gender = user.get("gender", "мужской")
        interpretations = self.matrix_calc.get_interpretations(user["matrix"], gender)
        
        await status_msg.delete()
        
        # Добавляем заголовок
        gender_emoji = "👨" if gender == "мужской" else "👩"
        header = (
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📖 *ИНТЕРПРЕТАЦИИ МАТРИЦЫ*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{gender_emoji} Интерпретации для: *{gender}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        interpretations = header + interpretations
        
        # Разбиваем на части если нужно
        await self._send_long_message(update.message, interpretations)
    
    async def show_interpretations_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Вывод интерпретаций через callback"""
        uid = query.from_user.id
        user = user_store.get(uid)

        if not user or not user.get("matrix"):
            await query.message.reply_text("⚠️ Сначала рассчитайте матрицу!")
            return
        
        gender = user.get("gender", "мужской")
        interpretations = self.matrix_calc.get_interpretations(user["matrix"], gender)
        
        gender_emoji = "👨" if gender == "мужской" else "👩"
        header = f"{gender_emoji} *Интерпретации для: {gender}*\n\n"
        interpretations = header + interpretations
        
        await self._send_long_message(query.message, interpretations)

    async def _send_long_message(self, message, text: str):
        """Отправка длинного сообщения с разбивкой"""
        max_length = 4000
        
        if len(text) <= max_length:
            try:
                await message.reply_text(text, parse_mode="Markdown")
            except Exception as e:
                log.error(f"Ошибка отправки: {e}")
                # Если ошибка Markdown, отправляем без форматирования
                await message.reply_text(text)
            return
        
        # Разбиваем по двойным переносам строк
        parts = text.split('\n\n')
        current_message = []
        current_length = 0
        
        for i, part in enumerate(parts):
            part_length = len(part) + 2
            
            if current_length + part_length > max_length:
                # Отправляем накопленное
                msg_text = '\n\n'.join(current_message)
                try:
                    await message.reply_text(msg_text, parse_mode="Markdown")
                except:
                    await message.reply_text(msg_text)
                
                current_message = [part]
                current_length = part_length
            else:
                current_message.append(part)
                current_length += part_length
        
        # Отправляем остаток
        if current_message:
            msg_text = '\n\n'.join(current_message)
            try:
                await message.reply_text(msg_text, parse_mode="Markdown")
            except:
                await message.reply_text(msg_text)

    async def daily_horoscope(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вывод гороскопа"""
        uid = update.effective_user.id
        user = user_store.get(uid)

        if not user or not user.get("zodiac"):
            await update.message.reply_text(
                "⚠️ Сначала рассчитайте матрицу!\n"
                "Нажмите /start для начала."
            )
            return

        status_msg = await update.message.reply_text(
            "🔮 *Анализирую положение планет...*\n"
            "⏳ Составляю прогноз...",
            parse_mode="Markdown"
        )
        
        try:
            horo_text = await self.horoscope_service.get_daily_horoscope(user)
            await status_msg.delete()
            
            header = (
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔮 *ГОРОСКОП НА СЕГОДНЯ*\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✨ Знак: *{user['zodiac']}*\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
            )
            
            await update.message.reply_text(header + horo_text, parse_mode="Markdown")
        except Exception as e:
            log.error(f"Ошибка гороскопа: {e}")
            await status_msg.edit_text(
                "❌ *Не удалось получить гороскоп*\n\n"
                "Попробуйте позже или проверьте подключение к интернету.",
                parse_mode="Markdown"
            )
    
    async def daily_horoscope_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Вывод гороскопа через callback"""
        uid = query.from_user.id
        user = user_store.get(uid)

        if not user or not user.get("zodiac"):
            await query.message.reply_text("⚠️ Сначала рассчитайте матрицу!")
            return

        await query.message.reply_text("🔮 Получаю гороскоп...")
        
        try:
            horo_text = await self.horoscope_service.get_daily_horoscope(user)
            header = f"✨ *Гороскоп для {user['zodiac']}*\n\n"
            await query.message.reply_text(header + horo_text, parse_mode="Markdown")
        except Exception as e:
            log.error(f"Ошибка гороскопа: {e}")
            await query.message.reply_text("❌ Не удалось получить гороскоп. Попробуйте позже.")

    async def show_help(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Показ помощи через callback"""
        help_text = (
            "📚 *СПРАВКА*\n\n"
            "🔮 *Что такое психоматрица?*\n"
            "Психоматрица (квадрат Пифагора) — древняя система анализа личности по дате рождения.\n\n"
            "📊 *Что показывает матрица?*\n"
            "• Силу характера (1)\n"
            "• Энергетику (2)\n"
            "• Интересы (3)\n"
            "• Здоровье (4)\n"
            "• Логику (5)\n"
            "• Труд (6)\n"
            "• Удачу (7)\n"
            "• Долг (8)\n"
            "• Память (9)\n\n"
            "🎯 *Как пользоваться?*\n"
            "1. Нажмите /start\n"
            "2. Выберите пол\n"
            "3. Введите дату рождения\n"
            "4. Изучите матрицу и интерпретации\n\n"
            "💡 Интерпретации учитывают ваш пол для более точного анализа!"
        )
        await query.message.reply_text(help_text, parse_mode="Markdown")
    
    async def show_help_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ помощи через обычное сообщение"""
        help_text = (
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📚 *СПРАВКА*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔮 *Что такое психоматрица?*\n"
            "Психоматрица (квадрат Пифагора) — древняя система анализа личности по дате рождения.\n\n"
            "📊 *Что означают числа в матрице?*\n"
            "• *1* — Характер, сила воли, эго\n"
            "• *2* — Энергия, жизненная сила\n"
            "• *3* — Интересы, творчество\n"
            "• *4* — Здоровье, физическая сила\n"
            "• *5* — Логика, интуиция\n"
            "• *6* — Труд, мастерство\n"
            "• *7* — Удача, везение\n"
            "• *8* — Долг, ответственность\n"
            "• *9* — Память, ум\n\n"
            "🎯 *Как пользоваться ботом?*\n"
            "1️⃣ Нажмите /start\n"
            "2️⃣ Выберите пол (важно!)\n"
            "3️⃣ Введите дату: ДД.ММ.ГГГГ\n"
            "4️⃣ Изучите результаты\n\n"
            "📖 *Возможности:*\n"
            "• Расчет психоматрицы\n"
            "• Подробные интерпретации\n"
            "• Личные и родовые задачи\n"
            "• Гороскоп на сегодня\n\n"
            "💡 *Совет:* Интерпретации учитывают ваш пол для максимальной точности!\n\n"
            "❓ Возникли вопросы? Напишите /start для перезапуска."
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

    def _get_zodiac(self, day, month):
        """Логика определения знака зодиака"""
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
    """Точка входа"""
    bot_logic = NumerologyBot()
    
    if not Config.BOT_TOKEN:
        log.error("BOT_TOKEN не установлен в переменных окружения!")
        return

    # Инициализация приложения
    application = Application.builder().token(Config.BOT_TOKEN).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", bot_logic.start))
    application.add_handler(CallbackQueryHandler(bot_logic.button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_logic.handle_message))

    # Логика запуска
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
    main()
