"""
main.py — Solo Leveling Hunter RPG Bot entry point.

Wires up all handlers and initializes the Telegram channel database.
"""

import logging

from pyrogram import Client, filters

from config import BOT_TOKEN, API_ID, API_HASH, DATA_CHANNEL_ID
from channel_db import ChannelDB
from handlers import start, profile, hunt, inventory, help, claim, shop, leaderboard, duel, guild, guild_war, admin

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Client ────────────────────────────────────────────────
app = Client(
    "solo_leveling_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# ── Lifecycle ─────────────────────────────────────────────
@app.on_start()
async def on_start(client):
    """Initialize the channel database and populate cache on startup."""
    logger.info("Initializing Solo Leveling Bot...")

    db = ChannelDB(client, DATA_CHANNEL_ID)
    client.db = db  # ponytail: attach DB to client for handler access
    await db.initialize()

    logger.info("Bot initialized and ready!")


@app.on_stop()
async def on_stop(client):
    logger.info("Bot shutting down...")


# ── Command Handlers ──────────────────────────────────────
app.on_message(filters.command("start"))(start.handle)
app.on_message(filters.command("profile"))(profile.handle)
app.on_message(filters.command("hunt"))(hunt.handle)
app.on_message(filters.command(["inventory", "equip"]))(inventory.handle)
app.on_message(filters.command("shop"))(shop.handle)
app.on_message(filters.command("leaderboard"))(leaderboard.handle)
app.on_message(filters.command("duel"))(duel.handle)
app.on_message(filters.command("help"))(help.handle)
app.on_message(filters.command("claim"))(claim.handle)
app.on_message(filters.command("guild"))(guild.handle)
app.on_message(filters.command("gift"))(guild.handle_gift)

# ── Superadmin / Owner Command Handlers ───────────────────
app.on_message(filters.command(["admin", "superadmin"]))(admin.handle_admin_help)
app.on_message(filters.command(["addgold", "addcoins"]))(admin.handle_add_gold)
app.on_message(filters.command(["setgold", "setcoins"]))(admin.handle_set_gold)
app.on_message(filters.command(["addxp", "addep"]))(admin.handle_add_xp)
app.on_message(filters.command("setlevel"))(admin.handle_set_level)
app.on_message(filters.command("inspect"))(admin.handle_inspect)

# ── Inline Button Callbacks ───────────────────────────────
app.on_callback_query(filters.regex(r"^equip_"))(inventory.equip_callback)
app.on_callback_query(filters.regex(r"^inv_"))(inventory.tab_callback)
app.on_callback_query(filters.regex(r"^shop_"))(inventory.tab_callback)
app.on_callback_query(filters.regex(r"^buy_"))(inventory.buy_callback)
app.on_callback_query(filters.regex(r"^lb_"))(leaderboard.callback)
app.on_callback_query(filters.regex(r"^glb_"))(guild.guild_leaderboard_callback)
app.on_callback_query(filters.regex(r"^war_"))(guild_war.war_callback)
app.on_callback_query(filters.regex(r"^duel_"))(duel.callback)


# ── Run ───────────────────────────────────────────────────
if __name__ == "__main__":
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        print("ERROR: Set your BOT_TOKEN in the .env file!")
        print("   1. Talk to @BotFather on Telegram")
        print("   2. Create a bot with /newbot")
        print("   3. Copy the token to .env")
        raise SystemExit(1)

    if not API_ID or API_ID == 0:
        print("ERROR: Set your API_ID in the .env file!")
        print("   1. Go to https://my.telegram.org")
        print("   2. Create an application")
        print("   3. Copy API_ID and API_HASH to .env")
        raise SystemExit(1)

    if not DATA_CHANNEL_ID or DATA_CHANNEL_ID == 0:
        print("ERROR: Set your DATA_CHANNEL_ID in the .env file!")
        print("   1. Create a private Telegram channel")
        print("   2. Add the bot as admin")
        print("   3. Get the channel ID (format: -100xxxxxxxxxx)")
        print("   4. Paste it in .env as DATA_CHANNEL_ID")
        raise SystemExit(1)

    logger.info("Starting bot polling...")
    app.run()
