"""
handlers/shop.py — /shop command handler.

Allows hunters to access the System Exchange Depot (Hunter Shop) to purchase
weapons, armor, accessories, consumables, and materials.
Directs users to open the shop in private chat (PM) when invoked from a group chat.
"""

from __future__ import annotations

import asyncio
import logging
from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from channel_db import ChannelDB
from game.formatting import format_not_registered
from game.shop_image import render_shop_image
from handlers.inventory import _shop_category_keyboard

logger = logging.getLogger(__name__)


async def handle(client: Client, message: Message) -> None:
    """Handle the /shop command. Directs to PM if called inside a group chat."""
    user = message.from_user
    chat = message.chat
    if not user or not chat:
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)

    # 1. Group / Supergroup chat detection
    is_group = chat.type in ["group", "supergroup"]

    if is_group:
        me = await client.get_me()
        bot_user = me.username or "solo_leveling_hunter_bot"
        pm_url = f"https://t.me/{bot_user}?start=shop"

        if not hunter:
            gc_text = (
                "╔══════════════════════════════╗\n"
                "║   ⚡ SYSTEM NOTIFICATION ⚡   ║\n"
                "║       HUNTER SHOP            ║\n"
                "╚══════════════════════════════╝\n\n"
                f"👤 {user.first_name}, you are not an awakened Hunter yet!\n\n"
                "Awaken first in Bot PM to gain access to the Hunter Shop."
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ Awaken in Bot PM", url=pm_url)]
            ])
            await message.reply_text(gc_text, reply_markup=keyboard)
            return

        # Attempt direct transmission to PM
        direct_sent = False
        try:
            photo_buf = await asyncio.to_thread(render_shop_image, hunter, "menu")
            caption = (
                f"🛒 Hunter Shop — System Exchange Depot\n"
                f"👤 Hunter: {hunter.hunter_name} [Rank {hunter.rank}] ┊ 💰 Available Treasury: {hunter.gold:,} G\n\n"
                "Select a department below to browse items:"
            )
            await client.send_photo(
                chat_id=user.id,
                photo=photo_buf,
                caption=caption,
                reply_markup=_shop_category_keyboard(),
            )
            direct_sent = True
        except Exception:
            direct_sent = False

        status_msg = (
            "✨ The Hunter Shop has also been dispatched directly to your PM!"
            if direct_sent
            else "🔒 Tap the button below to browse and purchase items in Bot PM."
        )

        gc_text = (
            "╔══════════════════════════════╗\n"
            "║   ⚡ SYSTEM NOTIFICATION ⚡   ║\n"
            "║       HUNTER SHOP            ║\n"
            "╚══════════════════════════════╝\n\n"
            f"👤 Hunter: {hunter.hunter_name} ┊ 🏅 Rank {hunter.rank}\n"
            f"💰 Treasury: {hunter.gold:,} G\n\n"
            "⚠️ To protect transactions and keep group chats clean,\n"
            "the Hunter Shop opens in Private Chat (PM).\n\n"
            f"{status_msg}"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Open Hunter Shop in Bot PM", url=pm_url)]
        ])
        await message.reply_text(gc_text, reply_markup=keyboard)
        return

    # 2. Private Chat (PM) — render visual shop hub card
    if not hunter:
        await message.reply_text(format_not_registered())
        return

    caption = (
        f"🛒 Hunter Shop — System Exchange Depot\n"
        f"👤 Hunter: {hunter.hunter_name} [Rank {hunter.rank}] ┊ 💰 Available Treasury: {hunter.gold:,} G\n\n"
        "Select a department below to browse items:"
    )

    try:
        photo_buf = await asyncio.to_thread(render_shop_image, hunter, "menu")
        await message.reply_photo(
            photo=photo_buf,
            caption=caption,
            reply_markup=_shop_category_keyboard(),
        )
    except Exception as exc:
        logger.error("Failed to render shop image, falling back to text: %s", exc, exc_info=True)
        text = (
            "🛒 HUNTER SHOP — SYSTEM EXCHANGE DEPOT\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Hunter: {hunter.hunter_name} ┊ 🏅 Rank {hunter.rank}\n"
            f"💰 Available Gold: {hunter.gold:,} G\n\n"
            "Select a category below to browse items:"
        )
        await message.reply_text(text, reply_markup=_shop_category_keyboard())
