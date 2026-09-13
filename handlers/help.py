"""
handlers/help.py — /help command handler.

Shows all available commands and how to play.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


HELP_TEXT = (
    "━━━━━━━━━━━━━━━━━━\n"
    "📖 HUNTER SYSTEM — GUIDE\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "\n"
    "⚔️ COMMANDS\n"
    "\n"
    "/start — Awaken as a new Hunter\n"
    "/profile — View your Hunter profile\n"
    "/hunt — Fight a monster (15min cooldown)\n"
    "/inventory — Browse your items\n"
    "/equip — Change your equipped gear\n"
    "/claim — Daily reward (XP + Gold)\n"
    "/help — Show this guide\n"
    "\n"
    "━━━ HOW TO PLAY ━━━\n"
    "\n"
    "1️⃣ Use /start to create your Hunter\n"
    "2️⃣ Use /hunt to fight monsters and earn XP, Gold & Loot\n"
    "3️⃣ Use /inventory to see what you've collected\n"
    "4️⃣ Use /equip to gear up with better weapons & armor\n"
    "5️⃣ Use /profile to show off your stats\n"
    "\n"
    "━━━ RANKS ━━━\n"
    "\n"
    "🅴 E → 🅳 D → 🅲 C → 🅱️ B → 🅰️ A\n"
    "→ ⭐ S → 🌟 SS → 💫 SSS → 🔱 National → 👑 Monarch\n"
    "\n"
    "━━━ ITEM RARITIES ━━━\n"
    "\n"
    "⚪ Common → 🟢 Uncommon → 🔵 Rare\n"
    "→ 🟣 Epic → 🟡 Legendary → 🔴 Mythic\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "「 The System watches over all Hunters. 」"
)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command."""
    await update.message.reply_text(HELP_TEXT)
