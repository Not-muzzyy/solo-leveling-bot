"""
game/photo_helper.py — Telegram Profile Picture (PFP) retrieval utility for Kurigram MTProto.

Provides robust, multi-tier photo fetching for users and chats:
1. Direct check on user_obj.photo (ChatPhoto)
2. client.get_chat(user_id) for fresh chat photo info
3. client.get_chat_photos(user_id, limit=1) generator fallback
4. In-memory download and conversion to PIL Image (RGBA) or raw bytes.
"""

from __future__ import annotations

import io
import logging
from typing import Optional
from PIL import Image
from pyrogram import Client
from pyrogram.types import User

logger = logging.getLogger(__name__)


async def fetch_user_pfp_bytes(
    client: Client,
    user_id: int,
    user_obj: Optional[User] = None,
) -> Optional[bytes]:
    """
    Fetch a user's Telegram profile photo and return the raw image bytes.
    Returns None if the user has no photo, if privacy restricts it, or on download failure.
    """
    try:
        file_id: Optional[str] = None

        # 1. Check if user_obj already has a photo attached
        if user_obj and getattr(user_obj, "photo", None):
            photo = user_obj.photo
            file_id = getattr(photo, "big_file_id", None) or getattr(photo, "small_file_id", None)

        # 2. Try fetching chat profile for fresh photo
        if not file_id:
            try:
                chat = await client.get_chat(user_id)
                if chat and getattr(chat, "photo", None):
                    photo = chat.photo
                    file_id = getattr(photo, "big_file_id", None) or getattr(photo, "small_file_id", None)
            except Exception as chat_err:
                logger.debug("Could not get_chat for user %s photo: %s", user_id, chat_err)

        # 3. Fallback: iterate chat photos generator
        if not file_id:
            try:
                async for p in client.get_chat_photos(user_id, limit=1):
                    file_id = getattr(p, "file_id", None) or getattr(p, "big_file_id", None)
                    if file_id:
                        break
            except Exception as photos_err:
                logger.debug("Could not get_chat_photos for user %s: %s", user_id, photos_err)

        if not file_id:
            return None

        # 4. Download media in-memory
        media_buf = await client.download_media(file_id, in_memory=True)
        if not media_buf:
            return None

        if hasattr(media_buf, "getvalue"):
            return media_buf.getvalue()
        elif hasattr(media_buf, "getbuffer"):
            return bytes(media_buf.getbuffer())
        elif isinstance(media_buf, bytes):
            return media_buf

        return None
    except Exception as exc:
        logger.debug("Error fetching pfp bytes for user %s: %s", user_id, exc)
        return None


async def fetch_user_pfp_image(
    client: Client,
    user_id: int,
    user_obj: Optional[User] = None,
) -> Optional[Image.Image]:
    """
    Fetch a user's Telegram profile photo and return it as a PIL Image in RGBA format.
    Returns None if no photo is available.
    """
    raw_bytes = await fetch_user_pfp_bytes(client, user_id, user_obj=user_obj)
    if not raw_bytes:
        return None

    try:
        img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
        return img
    except Exception as exc:
        logger.debug("Could not decode PFP image bytes for user %s: %s", user_id, exc)
        return None
