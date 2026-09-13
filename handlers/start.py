"""
handlers/start.py — /start command handler.

Creates a new Hunter profile for the user.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from channel_db import ChannelDB
from game.hunter import create_new_hunter
from game.items import create_starter_weapon
from game.formatting import format_welcome, format_already_registered

logger = logging.getLogger(__name__)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    user = update.effective_user
    if not user:
        return

    db: ChannelDB = context.bot_data["db"]

    # Check if already registered
    existing = await db.get_hunter(user.id)
    if existing:
        await update.message.reply_text(format_already_registered(existing))
        return

    # Create new hunter
    username = user.username or user.first_name or f"Hunter_{user.id}"
    hunter = create_new_hunter(user.id, username)
    starter = create_starter_weapon()

    # Persist to channel
    await db.create_hunter(hunter, starter)

    # Send welcome message
    await update.message.reply_text(format_welcome(hunter))
    logger.info(f"New hunter created: {hunter.hunter_name} (ID: {user.id})")
