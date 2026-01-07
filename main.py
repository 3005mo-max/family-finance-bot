import os
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("family-finance-bot")

TOKEN = os.getenv("BOT_TOKEN")

# Простое хранилище в памяти (пока без базы)
STATE = {
    "income": 0.0,
    "expense": 0.0,
    "ops": []  # список операций
}

def _parse_amount(text: str) -> float:
    # поддержка "100", "100.5", "100,5"
    t = text.replace(",", ".").strip()
    return float(t)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот запущен и работает ✅\n\n"
        "Команды:\n"
        "/income <сумма> [коммент] — добавить доход\n"
        "/expense <сумма> [коммент] — добавить расход\n"
        "/balance — показать баланс\n"
        "/last [N] — последние операции (по умолчанию 10)\n"
        "/reset — обнулить всё (осторожно)"
    )

async def income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Пример: /income 2500 зарплата")

    try:
        amount = _parse_amount(context.args[0])
    except Exception:
        return await update.message.reply_text("Сумма не распознана. Пример: /income 2500 зарплата")

    comment = " ".join(context.args[1:]).strip()
    STATE["income"] += amount
    STATE["ops"].append(("income", amount, comment, datetime.now().isoformat(timespec="seconds")))
    await update.message.reply_text(f"Доход +{amount:.2f} ✅{(' — ' + comment) if comment else ''}")

async def expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Пример: /expense 320 продукты")

    try:
        amount = _parse_amount(context.args[0])
    except Exception:
        return await update.message.reply_text("Сумма не распознана. Пример: /expense 320 продукты")

    comment = " ".join(context.args[1:]).strip()
    STATE["expense"] += amount
    STATE["ops"].append(("expense", amount, comment, datetime.now().isoformat(timespec="seconds")))
    await update.message.reply_text(f"Расход -{amount:.2f} ✅{(' — ' + comment) if comment else ''}")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc = STATE["income"]
    exp = STATE["expense"]
    bal = inc - exp
    await update.message.reply_text(
        "Баланс:\n"
        f"Доходы: {inc:.2f}\n"
        f"Расходы: {exp:.2f}\n"
        f"Итого: {bal:.2f}"
    )

async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    n = 10
    if context.args:
        try:
            n = int(context.args[0])
        except Exception:
            n = 10

    ops = STATE["ops"][-n:]
    if not ops:
        return await update.message.reply_text("Операций пока нет.")

    lines = []
    for typ, amount, comment, ts in ops:
        sign = "+" if typ == "income" else "-"
        lines.append(f"{ts} | {typ} {sign}{amount:.2f}" + (f" | {comment}" if comment else ""))

    await update.message.reply_text("Последние операции:\n" + "\n".join(lines))

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    STATE["income"] = 0.0
    STATE["expense"] = 0.0
    STATE["ops"].clear()
    await update.message.reply_text("Всё обнулено ✅")

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled error: %s", context.error)

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set in environment variables")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("income", income))
    app.add_handler(CommandHandler("expense", expense))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("last", last))
    app.add_handler(CommandHandler("reset", reset))

    app.add_error_handler(on_error)

    # Важно: НЕ asyncio.run, Railway нормально держит процесс так
    app.run_polling()

if __name__ == "__main__":
    main()