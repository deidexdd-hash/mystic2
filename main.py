# main.py
import asyncio
import logging
import os
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
# 3️⃣ КЛАСС БОТА
# --------------------------------------------------------------------
class NumerologyBot:
    def __init__(self):
        self.matrix_calc = MatrixCalculator()
        self.interpretations = Interpretations()
        self.horoscope_service = HoroscopeService()
        self.store: dict[int, dict] = {}

    # --------------------- /start ---------------------
    async def start(self, update: Update, ctx: CallbackContext) -> int:
        await update.message.reply_text(
            "👋 Добро пожаловать в бот нумерологии!\n\n"
            "Введите дату рождения в формате ДД.MM.ГГГГ, например 15.05.1990"
        )
        return DATE

    # --------------------- DATE ---------------------
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

    # --------------------- GENDER ---------------------
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

    # --------------------- ПОЛНАЯ МАТРИЦА ---------------------
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

    # --------------------- ГОРСКОП ---------------------
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

    # --------------------- ТОЛЬКО МАТРИЦА 3x3 ---------------------
    async def only_matrix(self, update: Update, _: CallbackContext):
        uid = update.effective_user.id
        user = self.store.get(uid)
        if not user:
            await update.message.reply_text("❌ Сначала введите данные через /start")
            return

        mat = user["matrix"]
        add = ".".join(map(str, mat["additional"]))
        txt = f"""
📊 *ВАША МАТРИЦА* 📊

*Дата:* {mat['date']}
*Знак:* {mat['zodiac']}
*Доп. числа:* {add}

{self.matrix_calc.format_matrix_display(mat)}

*Расшифровка:*
1️⃣: {len([x for x in mat['full_array'] if x == 1])} шт.
2️⃣: {len([x for x in mat['full_array'] if x == 2])} шт.
3️⃣: {len([x for x in mat['full_array'] if x == 3])} шт.
4️⃣: {len([x for x in mat['full_array'] if x == 4])} шт.
5️⃣: {len([x for x in mat['full_array'] if x == 5])} шт.
6️⃣: {len([x for x in mat['full_array'] if x == 6])} шт.
7️⃣: {len([x for x in mat['full_array'] if x == 7])} шт.
8️⃣: {len([x for x in mat['full_array'] if x == 8])} шт.
