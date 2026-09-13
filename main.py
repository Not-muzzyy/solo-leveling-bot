"""
main.py — Solo Leveling Hunter RPG Bot entry point.

Wires up all handlers and initializes the Telegram channel database.
"""

import logging

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from config import BOT_TOKEN, DATA_CHANNEL_ID
from channel_db import ChannelDB
from handlers import start, profile, hunt, inventory, equip, help, claim

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application) -> None:
    """Initialize the channel database and populate cache on startup."""
    logger.info("Initializing Solo Leveling Bot...")

    db = ChannelDB(application.bot, DATA_CHANNEL_ID)
    await db.initialize()
    application.bot_data["db"] = db

    logger.info("Bot initialized and ready!")


def main() -> None:
    """Build and run the bot application."""
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        print("❌ ERROR: Set your BOT_TOKEN in the .env file!")
        print("   1. Talk to @BotFather on Telegram")
        print("   2. Create a bot with /newbot")
        print("   3. Copy the token to .env")
        return

    if not DATA_CHANNEL_ID or DATA_CHANNEL_ID == 0:
        print("❌ ERROR: Set your DATA_CHANNEL_ID in the .env file!")
        print("   1. Create a private Telegram channel")
        print("   2. Add the bot as admin")
        print("   3. Get the channel ID (format: -100xxxxxxxxxx)")
        print("   4. Paste it in .env as DATA_CHANNEL_ID")
        return

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # ── Command Handlers ──────────────────────────────────
    app.add_handler(CommandHandler("start", start.handle))
    app.add_handler(CommandHandler("profile", profile.handle))
    app.add_handler(CommandHandler("hunt", hunt.handle))
    app.add_handler(CommandHandler("inventory", inventory.handle))
    app.add_handler(CommandHandler("equip", equip.handle))
    app.add_handler(CommandHandler("help", help.handle))
    app.add_handler(CommandHandler("claim", claim.handle))

    # ── Inline Button Callbacks ───────────────────────────
    app.add_handler(CallbackQueryHandler(equip.button_callback, pattern="^equip_"))
    app.add_handler(CallbackQueryHandler(inventory.tab_callback, pattern="^inv_"))
    app.add_handler(CallbackQueryHandler(inventory.tab_callback, pattern="^shop_"))
    app.add_handler(CallbackQueryHandler(inventory.buy_callback, pattern="^buy_"))

    # ── Run ───────────────────────────────────────────────
    logger.info("Starting bot polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
