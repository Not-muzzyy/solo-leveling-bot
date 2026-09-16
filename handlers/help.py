"""
handlers/help.py — /help command handler.

Provides an atmospheric, image-based Operational Manual card (Hallmark standard)
outlining all available commands, gameplay mechanics, rank progression, and drop rates.
In group chats, directs users to open the guide in private chat (PM) to avoid chat clutter.
"""

from __future__ import annotations

import asyncio
import logging

from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from game.help_image import generate_help_image

logger = logging.getLogger(__name__)

HELP_CAPTION = (
    "📖 **SYSTEM OPERATIONAL MANUAL**\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "**Solo Leveling Hunter System // Archives V2.4**\n\n"
    "⚡ **Field Commands & Directives:**\n"
    "• `/hunt` — Slay gate monsters for XP & rare items (15m CD)\n"
    "• `/profile` — Holographic status window & attributes\n"
    "• `/inventory` — Dimensional storage & 1-tap equip\n"
    "• `/shop` — Hunter Exchange Depot (weapons & elixirs)\n"
    "• `/duel` — Challenge rival Hunter (reply in group)\n"
    "• `/claim` — Daily System stipend (24h CD)\n"
    "• `/guild` — Manage your Hunter Guild syndicate\n\n"
    "「 *The System acknowledges those who strive to grow stronger.* 」"
)

HELP_FALLBACK_TEXT = (
    "╔══════════════════════════════╗\n"
    "║    📖 HUNTER SYSTEM GUIDE    ║\n"
    "║      Commands & Mechanics    ║\n"
    "╚══════════════════════════════╝\n\n"
    "⚔️ HUNTER COMMANDS\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "/start — Awaken as a Hunter & claim starter weapon\n"
    "/profile — High-res visual Status Card (Stats, Rank & Loadout)\n"
    "/hunt — Slay Gate monsters & earn loot via visual Combat Card (15m CD)\n"
    "/inventory — Dimensional storage image with 1-tap equip & shop\n"
    "/shop — Visual Exchange Depot: buy weapons, armor & items\n"
    "/leaderboard — Visual System Hall of Fame (Power, Level, Wealth, Kills)\n"
    "/duel — Challenge another Hunter by replying to their message in a group\n"
    "/claim — Daily Hunter allowance (XP + Gold, 24h cooldown)\n"
    "/guild — Manage your Hunter Guild (create, join, members, etc.)\n"
    "/help — Display this operational manual\n\n"
    "🏰 GUILD SYNDICATE\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "/guild create <name> — Create a guild (500💰)\n"
    "/guild join <name> — Join a guild\n"
    "/guild war <name> — Challenge a guild to war\n"
    "/guild info / /guild top — View guild card & leaderboard\n"
    "/gift item <id> / /gift gold <amount> — Gift to guildmates\n"
    "🎁 Guild members get +10% XP on all hunts!\n\n"
    "⭐ HUNTER RANKS\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "E → D → C → B → A → S → SS → SSS → National Level → Monarch\n\n"
    "💎 ITEM RARITIES\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "Common (50%) → Uncommon (25%) → Rare (15%) → Epic (7%) → Legendary (2.5%) → Mythic (0.5%)\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "「 The System acknowledges those who strive to grow stronger. 」"
)


def _help_pm_keyboard() -> InlineKeyboardMarkup:
    """Action buttons for help screen in private chat."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎒 Dimensional Inventory", callback_data="inv_weapon"),
            InlineKeyboardButton("🛒 Hunter Shop", callback_data="shop_menu"),
        ],
        [
            InlineKeyboardButton("🏆 System Leaderboard", callback_data="lb_power"),
        ]
    ])


async def send_help_card_to_chat(client: Client, chat_id: int) -> bool:
    """Generate and transmit the visual Operational Manual card to a chat/user."""
    try:
        photo_buf = await asyncio.to_thread(generate_help_image)
        await client.send_photo(
            chat_id=chat_id,
            photo=photo_buf,
            caption=HELP_CAPTION,
            reply_markup=_help_pm_keyboard(),
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to send visual help card to {chat_id}: {e}; using text fallback.")
        try:
            await client.send_message(
                chat_id=chat_id,
                text=HELP_FALLBACK_TEXT,
                reply_markup=_help_pm_keyboard(),
            )
            return True
        except Exception:
            return False


async def handle(client: Client, message: Message) -> None:
    """Handle the /help command. Directs to PM if called inside a group chat."""
    user = message.from_user
    chat = message.chat
    if not user or not chat:
        return

    is_group = chat.type in ["group", "supergroup"]

    if is_group:
        me = await client.get_me()
        bot_user = me.username or "solo_leveling_hunter_bot"
        pm_url = f"https://t.me/{bot_user}?start=help"

        # Attempt direct visual transmission to user's PM
        direct_sent = await send_help_card_to_chat(client, user.id)

        status_msg = (
            "✨ The Hunter System manual has been dispatched directly to your PM!"
            if direct_sent
            else "🔒 Tap the button below to open the visual Hunter operational manual in PM."
        )

        gc_text = (
            "╔══════════════════════════════╗\n"
            "║   ⚡ SYSTEM NOTIFICATION ⚡   ║\n"
            "║     HUNTER SYSTEM GUIDE      ║\n"
            "╚══════════════════════════════╝\n\n"
            f"👤 Hunter {user.first_name},\n"
            "To prevent chat clutter and keep group channels clear,\n"
            "the visual Hunter System manual opens in Private Messages (PM).\n\n"
            f"{status_msg}"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Open Guide in Bot PM", url=pm_url)]
        ])
        await message.reply_text(gc_text, reply_markup=keyboard)
        return

    # In PM: Send the visual card directly
    try:
        photo_buf = await asyncio.to_thread(generate_help_image)
        await message.reply_photo(
            photo=photo_buf,
            caption=HELP_CAPTION,
            reply_markup=_help_pm_keyboard(),
        )
    except Exception as e:
        logger.warning(f"Failed to reply with help photo: {e}")
        await message.reply_text(HELP_FALLBACK_TEXT, reply_markup=_help_pm_keyboard())
