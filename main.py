"""
main.py — Solo Leveling Hunter RPG Bot entry point.

Wires up all handlers and initializes the Telegram channel database.
"""

import asyncio
import json
import logging
import os
import subprocess
import time

# Ensure event loop exists on Python 3.12+ / 3.14+ before pyrogram imports
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client, filters, enums, utils

# Support modern 64-bit Telegram channel IDs (e.g. -1004250848098)
utils.MIN_CHANNEL_ID = -10099999999999

from config import BOT_TOKEN, API_ID, API_HASH, DATA_CHANNEL_ID, SHADOWS_CHANNEL_ID
from channel_db import ChannelDB
from shadows_db import ShadowsDB
from handlers import (
    start, profile, hunt, inventory, help, claim, shop,
    leaderboard, duel, guild, guild_war, admin, redeem, explore,
    forge, tower, quest, arise
)

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
    parse_mode=enums.ParseMode.HTML,
)


# ── Lifecycle ─────────────────────────────────────────────
async def on_start(client):
    """Initialize the channel database and populate cache on startup."""
    logger.info("Initializing Solo Leveling Bot...")

    db = ChannelDB(client, DATA_CHANNEL_ID)
    client.db = db  # ponytail: attach DB to client for handler access
    await db.initialize()

    # Dedicated Shadows Database Channel
    shadows_db = ShadowsDB(client, SHADOWS_CHANNEL_ID)
    client.shadows_db = shadows_db
    await shadows_db.initialize()

    # Resume any persisted guild war
    try:
        await guild_war.restore_war(client)
    except Exception as exc:
        logger.error(f"Failed to restore guild war state: {exc}")

    # ── Post-Restart Online State Notification (In-Place Edit Only) ──
    state_file = os.path.join(os.getcwd(), ".restart_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                restart_data = json.load(f)

            chat_id = restart_data.get("chat_id")
            message_id = restart_data.get("message_id")
            start_ts = restart_data.get("timestamp", time.time())
            duration = max(0.1, round(time.time() - start_ts, 1))

            # Fetch active commit telemetry
            try:
                proc = subprocess.run(
                    ["git", "log", "-1", "--format=%h - %s (%an)"],
                    cwd=os.getcwd(),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                commit_info = proc.stdout.strip() if proc.returncode == 0 else "Latest Build"
            except Exception:
                commit_info = "Latest Build"

            online_text = (
                "<b>[ SYSTEM NOTIFICATION // REBOOT SEQUENCE COMPLETE ]</b>\n"
                "<b>시스템 재가동 // 정상 가동 개시</b>\n\n"
                "<i>Solo Leveling Hunter System is back online!</i>\n\n"
                "<blockquote expandable>"
                "• <b>Status:</b> Operational & Active ⚡\n"
                f"• <b>Reboot Latency:</b> <code>{duration}s</code>\n"
                f"• <b>Active Build:</b> <code>{commit_info}</code>\n"
                "• <b>Modules:</b> All game systems initialized\n"
                "</blockquote>\n\n"
                "<blockquote>✨ <i>Updates applied successfully. Ready for commands.</i></blockquote>"
            )

            # Strictly edit the existing restart message (never send a new message)
            if chat_id and message_id:
                try:
                    await client.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=online_text,
                        parse_mode=enums.ParseMode.HTML,
                    )
                    logger.info(f"Updated restart notification in chat {chat_id}, message {message_id}")
                except Exception as exc:
                    logger.warning(f"Could not edit restart message {message_id}: {exc}")
        except Exception as e:
            logger.error(f"Error handling post-restart telemetry: {e}")
        finally:
            try:
                if os.path.exists(state_file):
                    os.remove(state_file)
            except Exception:
                pass

    logger.info("Bot initialized and ready!")


async def on_stop(client):
    logger.info("Bot shutting down...")


if hasattr(app, "on_start"):
    app.on_start()(on_start)
if hasattr(app, "on_stop"):
    app.on_stop()(on_stop)


# ── Incoming Message & Callback Logger ─────────────────────
@app.on_message(group=-1)
async def _log_incoming_message(client, message):
    user = message.from_user
    u_info = f"{user.id} (@{user.username or user.first_name})" if user else "Unknown"
    txt = (message.text or message.caption or "<media>")[:80]
    logger.info(f"Incoming message from {u_info}: {txt}")

@app.on_callback_query(group=-1)
async def _log_incoming_callback(client, query):
    user = query.from_user
    u_info = f"{user.id} (@{user.username or user.first_name})" if user else "Unknown"
    logger.info(f"Incoming callback from {u_info}: {query.data}")


# ── Group Message Counter (Dimensional Rifts) ─────────────
@app.on_message(filters.group & ~filters.service, group=1)
async def _group_message_listener(client, message):
    await arise.count_group_message(client, message)


# ── Command Handlers ──────────────────────────────────────
app.on_message(filters.command("start"))(start.handle)
app.on_message(filters.command("profile"))(profile.handle)
app.on_message(filters.command("hunt"))(hunt.handle)
app.on_message(filters.command("explore"))(explore.handle)
app.on_message(filters.command(["inventory", "equip"]))(inventory.handle)
app.on_message(filters.command("shop"))(shop.handle)
app.on_message(filters.command("leaderboard"))(leaderboard.handle)
app.on_message(filters.command("duel"))(duel.handle)
app.on_message(filters.command("help"))(help.handle)
app.on_message(filters.command("claim"))(claim.handle)
app.on_message(filters.command("redeem"))(redeem.handle_redeem)
app.on_message(filters.command("guild"))(guild.handle)
app.on_message(filters.command("gift"))(guild.handle_gift)
app.on_message(filters.command(["use", "potion", "heal"]))(inventory.handle_use)
app.on_message(filters.command(["forge", "craft", "upgrade"]))(forge.handle)
app.on_message(filters.command(["tower", "trial"]))(tower.handle)
app.on_message(filters.command("daily"))(quest.handle_daily)
app.on_message(filters.command(["stats", "addstat"]))(quest.handle_stats)
app.on_message(filters.command("arise"))(arise.handle_arise)
app.on_message(filters.command(["shadows", "shadow", "army"]))(arise.handle_shadows)

# ── Superadmin / Owner Command Handlers ───────────────────
app.on_message(filters.command(["admin", "superadmin"]))(admin.handle_admin_help)
app.on_message(filters.command("update"))(admin.handle_update)
app.on_message(filters.command("restart"))(admin.handle_restart)
app.on_message(filters.command(["stop", "shutdown", "kill"]))(admin.handle_stop)
app.on_message(filters.command(["addgold", "addcoins"]))(admin.handle_add_gold)
app.on_message(filters.command(["setgold", "setcoins"]))(admin.handle_set_gold)
app.on_message(filters.command(["addxp", "addep"]))(admin.handle_add_xp)
app.on_message(filters.command("setlevel"))(admin.handle_set_level)
app.on_message(filters.command("inspect"))(admin.handle_inspect)
app.on_message(filters.command("createcode"))(admin.handle_create_code)
app.on_message(filters.command(["listcodes", "codes"]))(admin.handle_list_codes)
app.on_message(filters.command("deletecode"))(admin.handle_delete_code)
app.on_message(filters.command(["addshadow", "addcharacter"]))(arise.handle_add_shadow)
app.on_message(filters.command("listshadows"))(arise.handle_list_shadows)
app.on_message(filters.command("delshadow"))(arise.handle_del_shadow)
app.on_message(filters.command("spawnshadow"))(arise.handle_spawn_shadow)
app.on_message(filters.command(["shadowstats", "riftstats"]))(arise.handle_shadow_stats)

# ── Inline Button Callbacks ───────────────────────────────
app.on_callback_query(filters.regex(r"^equip_"))(inventory.equip_callback)
app.on_callback_query(filters.regex(r"^use_"))(inventory.use_callback)
app.on_callback_query(filters.regex(r"^inv_"))(inventory.tab_callback)
app.on_callback_query(filters.regex(r"^shop_"))(inventory.tab_callback)
app.on_callback_query(filters.regex(r"^buy_"))(inventory.buy_callback)
app.on_callback_query(filters.regex(r"^admin_restart$"))(admin.handle_restart_callback)
app.on_callback_query(filters.regex(r"^lb_"))(leaderboard.callback)
app.on_callback_query(filters.regex(r"^glb_"))(guild.guild_leaderboard_callback)
app.on_callback_query(filters.regex(r"^(gjoin_|gleave_|gview_|gmembers_|gnoop)"))(guild.guild_interaction_callback)
app.on_callback_query(filters.regex(r"^war_"))(guild_war.war_callback)
app.on_callback_query(filters.regex(r"^duel_"))(duel.callback)
app.on_callback_query(filters.regex(r"^forge_"))(forge.callback)
app.on_callback_query(filters.regex(r"^tower_"))(tower.callback)
app.on_callback_query(filters.regex(r"^(quest_|stats_)"))(quest.callback)
app.on_callback_query(filters.regex(r"^help_"))(help.callback)
app.on_callback_query(filters.regex(r"^shadow_"))(arise.shadows_callback)


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
    if hasattr(app, "on_start"):
        app.run()
    else:
        from pyrogram import idle

        async def _run_bot():
            await app.start()
            await on_start(app)
            await idle()
            await on_stop(app)
            await app.stop()

        app.run(_run_bot())
