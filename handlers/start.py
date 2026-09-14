"""
handlers/start.py — /start command handler.

Creates a new Hunter profile for the user.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from channel_db import ChannelDB
from game.font_manager import clean_and_normalize_name
from game.hunter import create_new_hunter
from game.items import create_starter_weapon
from game.formatting import format_welcome, format_already_registered, format_inventory
from game.inventory_image import render_inventory_image
from handlers.inventory import _inventory_keyboard

logger = logging.getLogger(__name__)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command, supporting deep-links such as /start inventory."""
    user = update.effective_user
    if not user:
        return

    db: ChannelDB = context.bot_data["db"]
    is_inventory_deeplink = bool(
        context.args and context.args[0].lower() == "inventory"
    )
    is_help_deeplink = bool(
        context.args and context.args[0].lower() == "help"
    )
    is_shop_deeplink = bool(
        context.args and context.args[0].lower() == "shop"
    )

    # Check if already registered
    existing = await db.get_hunter(user.id)
    if existing:
        fn = clean_and_normalize_name(user.first_name)
        ln = clean_and_normalize_name(user.last_name)
        if fn and (existing.first_name != fn or existing.last_name != ln):
            existing.first_name = fn
            existing.last_name = ln
            await db.save_hunter(user.id)

        if is_help_deeplink:
            from handlers.help import HELP_TEXT, _help_pm_keyboard
            await update.message.reply_text(HELP_TEXT, reply_markup=_help_pm_keyboard())
            return
        if is_shop_deeplink:
            from game.shop_image import render_shop_image
            from handlers.inventory import _shop_category_keyboard
            caption = (
                f"🛒 Hunter Shop — System Exchange Depot\n"
                f"👤 Hunter: {existing.hunter_name} [Rank {existing.rank}] ┊ 💰 Available Treasury: {existing.gold:,} G\n\n"
                "Select a department below to browse items:"
            )
            try:
                photo_buf = await asyncio.to_thread(render_shop_image, existing, "menu")
                await update.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    reply_markup=_shop_category_keyboard(),
                )
            except Exception:
                await update.message.reply_text(
                    f"🛒 Hunter Shop — Available Treasury: {existing.gold:,} G",
                    reply_markup=_shop_category_keyboard(),
                )
            return
        if is_inventory_deeplink:
            inventory = await db.get_inventory(user.id)
            caption = f"🎒 Dimensional Inventory — ⚔️ Weapons\n👤 Hunter: {existing.hunter_name} [Rank {existing.rank}] ┊ 💰 Gold: {existing.gold:,} G"
            try:
                photo_buf = await asyncio.to_thread(render_inventory_image, existing, inventory, "weapon")
                await update.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    reply_markup=_inventory_keyboard(inventory, "weapon"),
                )
            except Exception:
                text = format_inventory(inventory, existing, "weapon")
                await update.message.reply_text(
                    text, reply_markup=_inventory_keyboard(inventory, "weapon")
                )
            return
        await update.message.reply_text(format_already_registered(existing))
        return

    # Create new hunter
    fn = clean_and_normalize_name(user.first_name)
    ln = clean_and_normalize_name(user.last_name)
    username = user.username or fn or f"Hunter_{user.id}"
    hunter = create_new_hunter(user.id, username, first_name=fn, last_name=ln)
    starter = create_starter_weapon()

    # Persist to channel
    await db.create_hunter(hunter, starter)

    # Send welcome message
    await update.message.reply_text(format_welcome(hunter))
    logger.info(f"New hunter created: {hunter.hunter_name} (ID: {user.id})")

    # If awakened via help deep-link, immediately show the Hunter Guide
    if is_help_deeplink:
        from handlers.help import HELP_TEXT, _help_pm_keyboard
        await update.message.reply_text(HELP_TEXT, reply_markup=_help_pm_keyboard())
        return

    # If awakened via shop deep-link, immediately show the Hunter Shop
    if is_shop_deeplink:
        from game.shop_image import render_shop_image
        from handlers.inventory import _shop_category_keyboard
        caption = (
            f"🛒 Hunter Shop — System Exchange Depot\n"
            f"👤 Hunter: {hunter.hunter_name} [Rank {hunter.rank}] ┊ 💰 Available Treasury: {hunter.gold:,} G\n\n"
            "Select a department below to browse items:"
        )
        try:
            photo_buf = await asyncio.to_thread(render_shop_image, hunter, "menu")
            await update.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=_shop_category_keyboard(),
            )
        except Exception:
            await update.message.reply_text(
                f"🛒 Hunter Shop — Available Treasury: {hunter.gold:,} G",
                reply_markup=_shop_category_keyboard(),
            )
        return

    # If awakened via inventory deep-link, immediately show their starter inventory
    if is_inventory_deeplink:
        inv = await db.get_inventory(user.id)
        caption = f"🎒 Dimensional Inventory — ⚔️ Weapons\n👤 Hunter: {hunter.hunter_name} [Rank {hunter.rank}] ┊ 💰 Gold: {hunter.gold:,} G"
        try:
            photo_buf = await asyncio.to_thread(render_inventory_image, hunter, inv, "weapon")
            await update.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=_inventory_keyboard(inv, "weapon"),
            )
        except Exception:
            text = format_inventory(inv, hunter, "weapon")
            await update.message.reply_text(
                text, reply_markup=_inventory_keyboard(inv, "weapon")
            )
