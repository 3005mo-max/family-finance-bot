import os
import asyncio
import aiosqlite
from datetime import datetime, date
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "finance.db")


HELP_TEXT = (
    "💰 Family Finance Bot\n\n"
    "Команды:\n"
    "• /start — проверка\n"
    "• /help — справка\n"
    "• /expense <сумма> <категория> [комментарий]\n"
    "   пример: /expense 12.5 food кофе\n"
    "• /income <сумма> <категория> [комментарий]\n"
    "   пример: /income 1500 salary аванс\n"
    "• /balance — баланс за всё время\n"
    "• /today — итоги за сегодня\n"
    "• /month — итоги за текущий месяц\n"
    "• /last [N] — последние N операций (по умолчанию 10)\n"
)


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _month_prefix() -> str:
    # UTC-месяц; если хочешь "по Барселоне", потом сделаем TZ
    return date.today().strftime("%Y-%m")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tx (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                kind TEXT NOT NULL,          -- 'income' | 'expense'
                amount REAL NOT NULL,        -- положительное число
                category TEXT NOT NULL,
                note TEXT
            )
            """
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tx_user_ts ON tx(user_id, ts)")
        await db.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен и работает ✅\n\n" + HELP_TEXT)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


def parse_amount(s: str) -> float:
    s = s.replace(",", ".").strip()
    val = float(s)
    if val <= 0:
        raise ValueError("amount must be > 0")
    return val


async def add_tx(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str):
    msg = update.message
    if not msg:
        return

    user_id = msg.from_user.id
    chat_id = msg.chat_id

    args = context.args
    if len(args) < 2:
        await msg.reply_text(
            "Неверный формат.\n"
            f"Пример: /{kind} 12.5 food кофе"
        )
        return

    try:
        amount = parse_amount(args[0])
    except Exception:
        await msg.reply_text("Сумма не распознана. Пример: 12.5 или 12,5")
        return

    category = args[1].strip().lower()
    note = " ".join(args[2:]).strip() if len(args) > 2 else None

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO tx (ts, user_id, chat_id, kind, amount, category, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now_iso(), user_id, chat_id, kind, amount, category, note),
        )
        await db.commit()

    sign = "➖" if kind == "expense" else "➕"
    await msg.reply_text(
        f"{sign} Записал: {kind} {amount:.2f} | {category}"
        + (f" | {note}" if note else "")
    )


async def expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_tx(update, context, "expense")


async def income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_tx(update, context, "income")


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    user_id = msg.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN kind='income' THEN amount ELSE 0 END), 0) AS inc,
              COALESCE(SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END), 0) AS exp
            FROM tx
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = await cur.fetchone()

    inc, exp = row[0], row[1]
    net = inc - exp
    await msg.reply_text(
        f"📊 Баланс за всё время:\n"
        f"➕ Доходы: {inc:.2f}\n"
        f"➖ Расходы: {exp:.2f}\n"
        f"✅ Итог: {net:.2f}"
    )


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    user_id = msg.from_user.id
    today_prefix = date.today().strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN kind='income' THEN amount ELSE 0 END), 0) AS inc,
              COALESCE(SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END), 0) AS exp
            FROM tx
            WHERE user_id = ? AND ts LIKE ?
            """,
            (user_id, f"{today_prefix}%"),
        )
        row = await cur.fetchone()

    inc, exp = row[0], row[1]
    net = inc - exp
    await msg.reply_text(
        f"📅 Сегодня ({today_prefix}):\n"
        f"➕ Доходы: {inc:.2f}\n"
        f"➖ Расходы: {exp:.2f}\n"
        f"✅ Итог: {net:.2f}"
    )


async def month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    user_id = msg.from_user.id
    mp = _month_prefix()

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN kind='income' THEN amount ELSE 0 END), 0) AS inc,
              COALESCE(SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END), 0) AS exp
            FROM tx
            WHERE user_id = ? AND ts LIKE ?
            """,
            (user_id, f"{mp}%"),
        )
        row = await cur.fetchone()

    inc, exp = row[0], row[1]
    net = inc - exp
    await msg.reply_text(
        f"🗓️ Текущий месяц ({mp}):\n"
        f"➕ Доходы: {inc:.2f}\n"
        f"➖ Расходы: {exp:.2f}\n"
        f"✅ Итог: {net:.2f}"
    )


async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    user_id = msg.from_user.id
    n = 10
    if context.args:
        try:
            n = max(1, min(50, int(context.args[0])))
        except Exception:
            n = 10

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT ts, kind, amount, category, COALESCE(note,'')
            FROM tx
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, n),
        )
        rows = await cur.fetchall()

    if not rows:
        await msg.reply_text("Пока нет операций.")
        return

    lines = []
    for ts, kind, amount, category, note in rows:
        sign = "➖" if kind == "expense" else "➕"
        tail = f" — {note}" if note else ""
        lines.append(f"{sign} {amount:.2f} [{category}] {ts}{tail}")

    await msg.reply_text("🧾 Последние операции:\n" + "\n".join(lines))


async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    await init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("expense", expense))
    app.add_handler(CommandHandler("income", income))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("month", month))
    app.add_handler(CommandHandler("last", last))

    await app.run_polling(close_loop=False)


if __name__ == "__main__":
    asyncio.run(main())