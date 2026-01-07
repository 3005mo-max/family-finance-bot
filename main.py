 import os
import re
import sqlite3
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "finance.db")

HELP_TEXT = (
    "Касса запущена ✅\n\n"
    "Как писать:\n"
    "  + 3000 [коммент]  — Олег внёс деньги\n"
    "  - 420 [коммент]   — расход (коммуналка/налоги и т.д.)\n\n"
    "Команды:\n"
    "  баланс\n"
    "  последние [N]\n"
    "  сброс\n"
)

def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            sign TEXT NOT NULL,   -- '+' или '-'
            amount REAL NOT NULL,
            comment TEXT
        )
    """)
    conn.commit()
    return conn

def add_op(chat_id: int, sign: str, amount: float, comment: str = ""):
    conn = db_connect()
    conn.execute(
        "INSERT INTO ops (ts, chat_id, sign, amount, comment) VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(timespec="seconds"), chat_id, sign, amount, comment.strip()),
    )
    conn.commit()
    conn.close()

def get_balance(chat_id: int):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(amount),0) FROM ops WHERE chat_id=? AND sign='+'", (chat_id,))
    plus_sum = float(cur.fetchone()[0] or 0)
    cur.execute("SELECT COALESCE(SUM(amount),0) FROM ops WHERE chat_id=? AND sign='-'", (chat_id,))
    minus_sum = float(cur.fetchone()[0] or 0)
    conn.close()
    balance = plus_sum - minus_sum
    return plus_sum, minus_sum, balance

def get_last(chat_id: int, n: int = 10):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT ts, sign, amount, comment FROM ops WHERE chat_id=? ORDER BY id DESC LIMIT ?",
        (chat_id, n),
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def reset_chat(chat_id: int):
    conn = db_connect()
    conn.execute("DELETE FROM ops WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()

def parse_amount(s: str) -> float:
    return float(s.replace(",", "."))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat_id
    text = update.message.text.strip()
    low = text.lower()

    if low == "баланс":
        plus_sum, minus_sum, balance = get_balance(chat_id)
        if balance >= 0:
            msg = (
                f"Внесено Олегом: {plus_sum:.2f}\n"
                f"Расходы: {minus_sum:.2f}\n"
                f"Остаток кассы (деньги Олега у тебя): {balance:.2f}\n"
                f"Долг Олега: 0.00"
            )
        else:
            debt = -balance
            msg = (
                f"Внесено Олегом: {plus_sum:.2f}\n"
                f"Расходы: {minus_sum:.2f}\n"
                f"Остаток кассы: {balance:.2f}\n"
                f"Долг Олега перед тобой (ты доплатил своими): {debt:.2f}"
            )
        await update.message.reply_text(msg)
        return

    m = re.match(r"^последние(?:\s+(\d+))?$", low)
    if m:
        n = int(m.group(1) or 10)
        rows = get_last(chat_id, n)
        if not rows:
            await update.message.reply_text("Пока операций нет.")
            return
        lines = []
        for ts, sign, amount, comment in rows:
            comm = f" — {comment}" if comment else ""
            lines.append(f"{sign}{amount:.2f}{comm}")
        await update.message.reply_text("Последние операции:\n" + "\n".join(lines))
        return

    if low == "сброс":
        reset_chat(chat_id)
        await update.message.reply_text("Готово. Касса обнулена ✅")
        return

    m = re.match(r"^([+-])\s*([0-9]+(?:[.,][0-9]+)?)\s*(.*)$", text)
    if m:
        sign = m.group(1)
        amount = parse_amount(m.group(2))
        comment = m.group(3) or ""
        add_op(chat_id, sign, amount, comment)

        if sign == "+":
            await update.message.reply_text(f"✅ Принято: +{amount:.2f}" + (f" — {comment}" if comment else ""))
        else:
            await update.message.reply_text(f"✅ Принято: -{amount:.2f}" + (f" — {comment}" if comment else ""))
        return

    await update.message.reply_text(
        "Не понял.\nПримеры:\n"
        "+ 3000 депозит\n"
        "- 420 luz\n"
        "баланс\n"
        "последние 20\n"
        "сброс"
    )

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()