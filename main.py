import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from matrix_calculator import MatrixCalculator

TOKEN = "YOUR_BOT_TOKEN"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

calc = MatrixCalculator()


# ===== helpers =====
def gender_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👨 Мужчина", callback_data="gender_men"),
            InlineKeyboardButton("👩 Женщина", callback_data="gender_women"),
        ]
    ])


# ===== handlers =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "Привет ✨\n\n"
        "Я рассчитаю твою Матрицу судьбы.\n\n"
        "Для начала выбери пол:",
        reply_markup=gender_keyboard()
    )


async def gender_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    gender = query.data.replace("gender_", "")
    context.user_data["gender"] = gender

    await query.message.reply_text(
        "Отлично.\n\n"
        "Теперь введи дату рождения в формате:\n"
        "`YYYY-MM-DD`\n\n"
        "Например: `1994-03-04`",
        parse_mode="Markdown"
    )


async def birth_date_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gender = context.user_data.get("gender")
    if not gender:
        await update.message.reply_text(
            "Сначала нужно выбрать пол 👇",
            reply_markup=gender_keyboard()
        )
        return

    date_text = update.message.text.strip()

    try:
        data = calc.calculate_matrix(date_text, gender)
    except Exception:
        await update.message.reply_text(
            "Дата введена неверно ❌\n"
            "Используй формат: `YYYY-MM-DD`",
            parse_mode="Markdown"
        )
        return

    # ===== message building =====
    matrix = data["matrix"]

    matrix_view = calc.format_matrix_display(data)

    text = (
        "✨ *Твоя матрица судьбы*\n\n"
        f"`{matrix_view}`\n\n"
    )

    for i in range(1, 10):
        cell = matrix[str(i)]
        if cell["value"] != f"{i}0":
            text += (
                f"*{i} → {cell['value']}*\n"
                f"{cell['text']}\n\n"
            )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )

    # сохраняем second / fourth для следующего шага
    context.user_data["additional"] = data["additional"]

    await update.message.reply_text(
        "Хочешь узнать:\n"
        "🧠 *Личную задачу Души*\n"
        "🧬 *Родовую задачу (ЧРП)*\n\n"
        "Напиши: `задачи`",
        parse_mode="Markdown"
    )


async def tasks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    additional = context.user_data.get("additional")
    gender = context.user_data.get("gender")

    if not additional or not gender:
        await update.message.reply_text(
            "Сначала рассчитай матрицу через /start"
        )
        return

    # second и fourth
    second = str(additional[1])
    fourth = str(additional[-1])

    from interpretations import Interpretations
    interp = Interpretations()

    soul_task = interp.get_task(second, gender)
    family_task = interp.get_task(fourth, gender)

    text = (
        "🧠 *Личная задача Души*\n"
        f"{soul_task or '—'}\n\n"
        "🧬 *Родовая задача (ЧРП)*\n"
        f"{family_task or '—'}"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ===== main =====
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(gender_selected, pattern="^gender_"))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^\d{4}-\d{2}-\d{2}$"), birth_date_received))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"(?i)^задачи$"), tasks_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
