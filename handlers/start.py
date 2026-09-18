"""
handlers/start.py — /start command handler.

Creates a new Hunter profile for the user.
"""

from __future__ import annotations

import asyncio
import logging

from pyrogram import Client, enums
from pyrogram.types import Message

from channel_db import ChannelDB
from game.captions import (
    build_shop_caption,
    build_inventory_caption,
    build_start_welcome_caption,
    build_start_existing_caption,
)
from game.font_manager import clean_and_normalize_name
from game.hunter import create_new_hunter
from game.items import create_starter_weapon
from game.formatting import format_welcome, format_already_registered, format_inventory
from game.inventory_image import render_inventory_image
from game.rich_text import escape_html
from handlers.inventory import _inventory_keyboard

logger = logging.getLogger(__name__)


async def handle(client: Client, message: Message) -> None:
    """Handle the /start command, supporting deep-links such as /start inventory."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db
    args = message.command[1:] if len(message.command) > 1 else []
    is_inventory_deeplink = bool(args and args[0].lower() == "inventory")
    is_help_deeplink = bool(args and args[0].lower() == "help")
    is_shop_deeplink = bool(args and args[0].lower() == "shop")
    is_redeem_deeplink = bool(args and args[0].lower().startswith("redeem"))

    # Check if already registered
    existing = await db.get_hunter(user.id)
    if existing:
        fn = clean_and_normalize_name(user.first_name)
        ln = clean_and_normalize_name(user.last_name)
        if fn and (existing.first_name != fn or existing.last_name != ln):
            existing.first_name = fn
            existing.last_name = ln
            await db.save_hunter(user.id)

        if is_redeem_deeplink:
            from handlers.redeem import handle_redeem
            sub = args[0]
            if "_" in sub:
                code_part = sub.split("_", 1)[1].strip()
                message.command = ["redeem", code_part]
            else:
                message.command = ["redeem"]
            await handle_redeem(client, message)
            return

        if is_help_deeplink:
            from handlers.help import handle as handle_help
            await handle_help(client, message)
            return
        if args and args[0].lower() in ["forge", "craft"]:
            from handlers.forge import handle as handle_forge
            await handle_forge(client, message)
            return
        if args and args[0].lower() in ["tower", "trial"]:
            from handlers.tower import handle as handle_tower
            await handle_tower(client, message)
            return
        if args and args[0].lower() in ["daily", "quest"]:
            from handlers.quest import handle_daily as handle_quest
            await handle_quest(client, message)
            return
        if args and args[0].lower() in ["stats", "addstat"]:
            from handlers.quest import handle_stats
            await handle_stats(client, message)
            return
        if is_shop_deeplink:
            from game.shop_image import render_shop_image
            from handlers.inventory import _shop_category_keyboard
            caption = build_shop_caption(existing, "menu")
            try:
                photo_buf = await asyncio.to_thread(render_shop_image, existing, "menu")
                await message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=_shop_category_keyboard(),
                )
            except Exception:
                await message.reply_text(
                    caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=_shop_category_keyboard(),
                )
            return
        if is_inventory_deeplink:
            inventory = await db.get_inventory(user.id)
            caption = build_inventory_caption(existing, inventory, "weapon")
            try:
                photo_buf = await asyncio.to_thread(render_inventory_image, existing, inventory, "weapon")
                await message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=_inventory_keyboard(inventory, "weapon"),
                )
            except Exception:
                text = format_inventory(inventory, existing, "weapon")
                await message.reply_text(
                    text,
                    reply_markup=_inventory_keyboard(inventory, "weapon"),
                    parse_mode=enums.ParseMode.HTML,
                )
            return
        await message.reply_text(format_already_registered(existing), parse_mode=enums.ParseMode.HTML)
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
    await message.reply_text(format_welcome(hunter), parse_mode=enums.ParseMode.HTML)
    logger.info(f"New hunter created: {hunter.hunter_name} (ID: {user.id})")

    # If awakened via redeem deep-link, immediately trigger redemption
    if is_redeem_deeplink:
        from handlers.redeem import handle_redeem
        sub = args[0]
        if "_" in sub:
            code_part = sub.split("_", 1)[1].strip()
            message.command = ["redeem", code_part]
        else:
            message.command = ["redeem"]
        await handle_redeem(client, message)
        return

    # If awakened via help deep-link, immediately show the visual Hunter Guide
    if is_help_deeplink:
        from handlers.help import handle as handle_help
        await handle_help(client, message)
        return

    # If awakened via shop deep-link, immediately show the Hunter Shop
    if is_shop_deeplink:
        from game.shop_image import render_shop_image
        from handlers.inventory import _shop_category_keyboard
        caption = build_shop_caption(hunter, "menu")
        try:
            photo_buf = await asyncio.to_thread(render_shop_image, hunter, "menu")
            await message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_shop_category_keyboard(),
            )
        except Exception:
            await message.reply_text(
                caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_shop_category_keyboard(),
            )
        return

    # If awakened via inventory deep-link, immediately show their starter inventory
    if is_inventory_deeplink:
        inv = await db.get_inventory(user.id)
        caption = build_inventory_caption(hunter, inv, "weapon")
        try:
            photo_buf = await asyncio.to_thread(render_inventory_image, hunter, inv, "weapon")
            await message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_inventory_keyboard(inv, "weapon"),
            )
        except Exception:
            text = format_inventory(inv, hunter, "weapon")
            await message.reply_text(
                text,
                reply_markup=_inventory_keyboard(inv, "weapon"),
                parse_mode=enums.ParseMode.HTML,
            )
