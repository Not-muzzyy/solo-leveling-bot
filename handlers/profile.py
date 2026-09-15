"""
handlers/profile.py — /profile command handler.

Displays the player's Hunter profile card.
"""

from __future__ import annotations

import asyncio
import io
import logging
from PIL import Image
from pyrogram import Client
from pyrogram.types import Message

from channel_db import ChannelDB
from game.formatting import format_profile, format_not_registered
from game.profile_image import render_profile_image

logger = logging.getLogger(__name__)


async def handle(client: Client, message: Message) -> None:
    """Handle the /profile command."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db

    hunter = await db.get_hunter(user.id)
    if not hunter:
        await message.reply_text(format_not_registered())
        return

    inventory = await db.get_inventory(user.id)

    # 1. Determine player's real full name (First Name + Last Name)
    first_name = (user.first_name or "").strip()
    last_name = (user.last_name or "").strip()
    full_name = f"{first_name} {last_name}".strip() if last_name else first_name

    # 2. Retrieve user's profile photo (PFP) if available
    pfp_image = None
    try:
        user_photos = await client.get_user_profile_photos(user.id, limit=1)
        if user_photos and user_photos.total_count > 0 and user_photos.photos:
            largest_photo = user_photos.photos[0][-1]
            photo_file = await client.get_file(largest_photo.file_id)
            photo_bytes = await photo_file.download()
            pfp_image = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
    except Exception as pfp_err:
        logger.debug("Could not fetch user profile photo: %s", pfp_err)
        pfp_image = None

    try:
        # Render the profile card image asynchronously in a worker thread
        photo_buf = await asyncio.to_thread(
            render_profile_image,
            hunter,
            inventory,
            pfp_image,
            full_name,
        )
        caption = f"⚔️ Hunter {hunter.hunter_name} | Rank {hunter.rank} | Lv. {hunter.level}"
        await message.reply_photo(photo=photo_buf, caption=caption)
    except Exception as exc:
        logger.error("Failed to render profile image, falling back to text: %s", exc, exc_info=True)
        await message.reply_text(format_profile(hunter, inventory))
