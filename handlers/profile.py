"""
handlers/profile.py — /profile command handler.

Displays the player's Hunter profile card.
"""

from __future__ import annotations

import asyncio
import io
import logging
from pyrogram import Client, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton

from channel_db import ChannelDB
from game.captions import build_profile_caption, build_profile_rich
from game.formatting import format_profile, format_not_registered, format_not_registered_rich, format_profile_rich
from game.photo_helper import fetch_user_pfp_image
from game.profile_image import render_profile_image
from game.rich_send import photo_media, reply_rich

logger = logging.getLogger(__name__)


async def handle(client: Client, message: Message) -> None:
    """Handle the /profile command."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db

    hunter = await db.get_hunter(user.id)
    if not hunter:
        await reply_rich(
            message, format_not_registered_rich(),
            fallback=lambda: message.reply_text(format_not_registered(), parse_mode=enums.ParseMode.HTML),
        )
        return

    inventory = await db.get_inventory(user.id)

    # 1. Determine player's real full name (First Name + Last Name)
    first_name = (user.first_name or "").strip()
    last_name = (user.last_name or "").strip()
    full_name = f"{first_name} {last_name}".strip() if last_name else first_name

    # Keep hunter's name in sync if updated on Telegram
    if first_name and (hunter.first_name != first_name or hunter.last_name != last_name):
        hunter.first_name = first_name
        hunter.last_name = last_name
        await db.save_hunter(hunter)

    # 2. Retrieve user's profile photo (PFP) if available via MTProto
    pfp_image = await fetch_user_pfp_image(client, user.id, user_obj=user)

    try:
        # Render the profile card image asynchronously in a worker thread
        photo_buf = await asyncio.to_thread(
            render_profile_image,
            hunter,
            inventory,
            pfp_image,
            full_name,
        )
        caption = build_profile_caption(hunter, inventory, full_name)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Copy Hunter ID", copy_text=CopyTextButton(text=str(hunter.user_id)), style=enums.ButtonStyle.PRIMARY)]
        ])
        await reply_rich(
            message, build_profile_rich(hunter, inventory, full_name),
            reply_markup=keyboard,
            media=[photo_media("profile", photo_buf)],
            fallback=lambda: message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=keyboard,
                show_caption_above_media=True,
            ),
        )
    except Exception as exc:
        logger.error("Failed to render profile image, falling back to text: %s", exc, exc_info=True)
        await reply_rich(
            message, format_profile_rich(hunter, inventory),
            fallback=lambda: message.reply_text(
                format_profile(hunter, inventory),
                parse_mode=enums.ParseMode.HTML,
            ),
        )
