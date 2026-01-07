import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ["BOT_TOKEN"]  # чтобы сразу падало, если токена нет

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен и работает ✅")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    # ВАЖНО: run_polling вызываем БЕЗ await и БЕЗ asyncio.run
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()