"""
handlers/help.py — /help command handler.

Shows all available commands, gameplay mechanics, ranks, and item rarities.
Directs users to open the guide in private chat (PM) when invoked from a group chat.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes


HELP_TEXT = (
    "╔══════════════════════════════╗\n"
    "║    📖 HUNTER SYSTEM GUIDE    ║\n"
    "║      Commands & Mechanics    ║\n"
    "╚══════════════════════════════╝\n"
    "\n"
    "⚔️ HUNTER COMMANDS\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "/start — Awaken as a Hunter & claim starter weapon\n"
    "/profile — High-res visual Status Card (Stats, Rank & Loadout)\n"
    "/hunt — Slay Gate monsters & earn loot via visual Combat Card (15m cooldown)\n"
    "/inventory — Dimensional storage image with 1-tap equip & shop\n"
    "/shop — Visual Exchange Depot: buy weapons, armor & items\n"
    "/claim — Daily Hunter allowance (XP + Gold, 24h cooldown)\n"
    "/help — Display this operational manual\n"
    "\n"
    "🎮 CORE GAMEPLAY LOOP\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "1️⃣ Awaken with /start to receive your Hunter license & starter blade\n"
    "2️⃣ Slay gate monsters with /hunt to earn XP, Gold & rare drops\n"
    "3️⃣ Collect daily rewards via /claim to boost progression\n"
    "4️⃣ Manage gear in /inventory — 1-tap equip weapons, armor & rings\n"
    "5️⃣ Buy advanced equipment and consumables from the 🛒 Hunter Shop\n"
    "6️⃣ Show off your power & stats card with /profile\n"
    "\n"
    "🔒 PRIVACY & GROUP NOTICES\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "• In group chats, /inventory, /shop and /help provide secure buttons to\n"
    "  open your storage, shop and guides in Bot PM to keep group chats clean.\n"
    "\n"
    "⭐ HUNTER RANKS (ASCENDING)\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🅴 E → 🅳 D → 🅲 C → 🅱️ B → 🅰️ A\n"
    "→ ⭐ S → 🌟 SS → 💫 SSS → 🔱 National → 👑 Monarch\n"
    "\n"
    "💎 ITEM RARITIES\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚪ Common (50%) → 🟢 Uncommon (25%) → 🔵 Rare (15%)\n"
    "→ 🟣 Epic (7%) → 🟡 Legendary (2.5%) → 🔴 Mythic (0.5%)\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "「 The System acknowledges those who strive to grow stronger. 」"
)


def _help_pm_keyboard() -> InlineKeyboardMarkup:
    """Action buttons for help screen in private chat."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎒 Dimensional Inventory", callback_data="inv_weapon"),
            InlineKeyboardButton("🛒 Hunter Shop", callback_data="shop_menu"),
        ]
    ])


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command. Directs to PM if called inside a group chat."""
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    is_group = chat.type in ["group", "supergroup"]

    if is_group:
        bot_user = context.bot.username
        if not bot_user:
            try:
                me = await context.bot.get_me()
                bot_user = me.username
            except Exception:
                bot_user = "solo_leveling_hunter_bot"

        pm_url = f"https://t.me/{bot_user}?start=help"

        # Attempt direct transmission to user's PM if they previously interacted in PM
        direct_sent = False
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=HELP_TEXT,
                reply_markup=_help_pm_keyboard(),
            )
            direct_sent = True
        except Exception:
            direct_sent = False

        status_msg = (
            "✨ The Hunter System manual has been dispatched directly to your PM!"
            if direct_sent
            else "🔒 Tap the button below to read the Hunter operational manual in PM."
        )

        gc_text = (
            "╔══════════════════════════════╗\n"
            "║   ⚡ SYSTEM NOTIFICATION ⚡   ║\n"
            "║     HUNTER SYSTEM GUIDE      ║\n"
            "╚══════════════════════════════╝\n\n"
            f"👤 Hunter {user.first_name},\n"
            "To prevent chat clutter and keep the group clean,\n"
            "the Hunter System manual opens in Private Messages (PM).\n\n"
            f"{status_msg}"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Open Guide in Bot PM", url=pm_url)]
        ])
        await update.message.reply_text(gc_text, reply_markup=keyboard)
        return

    # Private Chat (PM) — send full guide with quick action buttons
    await update.message.reply_text(HELP_TEXT, reply_markup=_help_pm_keyboard())
