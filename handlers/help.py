"""
handlers/help.py — /help command handler.

Shows all available commands, gameplay mechanics, ranks, and item rarities.
"""

from __future__ import annotations

from telegram import Update
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
    "/hunt — Battle Gate monsters via animated GIF (15m cooldown)\n"
    "/inventory — Dimensional storage image with 1-tap equip & shop\n"
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
    "🔒 GROUP CHAT NOTICE\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "• In group chats, /inventory provides an instant button to open\n"
    "  your Dimensional Storage in Bot PM to keep group chats clean.\n"
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


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command."""
    await update.message.reply_text(HELP_TEXT)
