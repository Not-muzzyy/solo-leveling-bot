"""
handlers/shop.py — /shop command handler.

Allows hunters to access the System Exchange Depot (Hunter Shop) to purchase
weapons, armor, accessories, consumables, and materials.
Directs users to open the shop in private chat (PM) when invoked from a group chat.
"""

from __future__ import annotations

import asyncio
import logging
from pyrogram import Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from channel_db import ChannelDB
from game.captions import build_shop_caption, build_shop_rich
from game.formatting import format_not_registered, format_not_registered_rich
from game.rich_message import RichDoc, heading, paragraph, quote
from game.rich_send import photo_media, reply_rich, send_rich
from game.rich_text import escape_html
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
            u_name = escape_html(user.first_name or "Hunter")
            gc_text = (
                "<blockquote>⚡ <b>SYSTEM NOTIFICATION — HUNTER SHOP</b>\n\n"
                f"👤 <b>{u_name}</b>, you are not an awakened Hunter yet!\n\n"
                "Awaken first in Bot PM to gain access to the Hunter Shop.</blockquote>"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ Awaken in Bot PM", url=pm_url)]
            ])
            await reply_rich(
                message,
                RichDoc(
                    heading(1, "⚡ SYSTEM NOTIFICATION — HUNTER SHOP"),
                    quote(
                        f"👤 <b>{u_name}</b>, you are not an awakened Hunter yet!<br><br>"
                        "Awaken first in Bot PM to gain access to the Hunter Shop.",
                        expandable=False,
                    ),
                ),
                reply_markup=keyboard,
                fallback=lambda: message.reply_text(gc_text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML),
            )
            return

        h_name = escape_html(hunter.hunter_name)
        # Attempt direct transmission to PM
        direct_sent = False
        try:
            photo_buf = await asyncio.to_thread(render_shop_image, hunter, "menu")
            caption = build_shop_caption(hunter, "menu")
            await send_rich(
                client, user.id, build_shop_rich(hunter, "menu", photo_first=True),
                reply_markup=_shop_category_keyboard(),
                media=[photo_media("shop", photo_buf)],
                fallback=lambda: client.send_photo(
                    chat_id=user.id,
                    photo=photo_buf,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=_shop_category_keyboard(),
                ),
            )
            direct_sent = True
        except Exception:
            direct_sent = False

        status_msg = (
            "✨ <i>The Hunter Shop has also been dispatched directly to your PM!</i>"
            if direct_sent
            else "🔒 <i>Tap the button below to browse and purchase items in Bot PM.</i>"
        )

        gc_text = (
            "<blockquote>⚡ <b>SYSTEM NOTIFICATION — HUNTER SHOP</b>\n\n"
            f"👤 <b>Hunter:</b> {h_name} ┊ 🏅 Rank <b>{hunter.rank}</b>\n"
            f"💰 <b>Treasury:</b> <code>{hunter.gold:,} G</code>\n\n"
            "⚠️ <i>To protect transactions and keep group chats clean, the Hunter Shop opens in Private Chat (PM).</i>\n\n"
            f"{status_msg}</blockquote>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Open Hunter Shop in Bot PM", url=pm_url)]
        ])
        await reply_rich(
            message,
            RichDoc(
                heading(1, "⚡ SYSTEM NOTIFICATION — HUNTER SHOP"),
                paragraph(
                    f"👤 <b>Hunter:</b> {h_name} ┊ 🏅 Rank <b>{escape_html(hunter.rank)}</b><br>"
                    f"💰 <b>Treasury:</b> <code>{escape_html(f'{hunter.gold:,} G')}</code>"
                ),
                quote(
                    "⚠️ <i>To protect transactions and keep group chats clean, the Hunter Shop opens in Private Chat (PM).</i>",
                    expandable=False,
                ),
                paragraph(status_msg),
            ),
            reply_markup=keyboard,
            fallback=lambda: message.reply_text(gc_text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML),
        )
        return

    # 2. Private Chat (PM) — render visual shop hub card
    if not hunter:
        await reply_rich(
            message, format_not_registered_rich(),
            fallback=lambda: message.reply_text(format_not_registered(), parse_mode=enums.ParseMode.HTML),
        )
        return

    caption = build_shop_caption(hunter, "menu")

    try:
        photo_buf = await asyncio.to_thread(render_shop_image, hunter, "menu")
        await reply_rich(
            message, build_shop_rich(hunter, "menu", photo_first=True),
            reply_markup=_shop_category_keyboard(),
            media=[photo_media("shop", photo_buf)],
            fallback=lambda: message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_shop_category_keyboard(),
            ),
        )
    except Exception as exc:
        logger.error("Failed to render shop image, falling back to text: %s", exc, exc_info=True)
        await reply_rich(
            message, build_shop_rich(hunter, "menu"),
            reply_markup=_shop_category_keyboard(),
            fallback=lambda: message.reply_text(
                caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_shop_category_keyboard(),
            ),
        )
