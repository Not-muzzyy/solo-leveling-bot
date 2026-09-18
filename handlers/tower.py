"""
handlers/tower.py — Demon Castle 100-Floor Tower Handler.

Provides:
- Visual Hallmark Demon Castle Spire Status card
- 1-tap floor ascension duel via /trial or button
- Key management (3 daily entries with midnight UTC reset)
- Boss milestone victories, titles, and artifact drops
"""

from __future__ import annotations

import asyncio
import logging
from pyrogram import Client, enums
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from channel_db import ChannelDB
from game.formatting import format_not_registered, _hp_bar
from game.hunter import add_xp
from game.rich_text import escape_html
from game.captions import build_tower_caption
from game.tower import generate_guardian, simulate_tower_climb
from game.tower_image import render_tower_image
from models import Hunter

logger = logging.getLogger(__name__)


def _tower_keyboard(hunter: Hunter) -> InlineKeyboardMarkup:
    """Build action buttons for Demon Castle."""
    buttons = []
    if hunter.tower_keys > 0 and hunter.tower_floor <= 100:
        buttons.append([
            InlineKeyboardButton(
                f"⚔️ Ascend Floor {hunter.tower_floor} (🔑 1 Key)",
                callback_data="tower_climb",
            )
        ])
    elif hunter.tower_floor > 100:
        buttons.append([
            InlineKeyboardButton("👑 Demon Castle Fully Conquered!", callback_data="tower_noop")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("❌ Daily Keys Depleted (Resets at Midnight UTC)", callback_data="tower_noop")
        ])

    buttons.append([
        InlineKeyboardButton("🎒 Inventory & Potions", callback_data="inv_consumable"),
        InlineKeyboardButton("⚒️ Blacksmith Forge", callback_data="shop_menu"),
    ])
    return InlineKeyboardMarkup(buttons)


async def handle(client: Client, message: Message) -> None:
    """Handle /tower and /trial commands."""
    user = message.from_user
    chat = message.chat
    if not user or not chat:
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await message.reply_text(format_not_registered(), parse_mode=enums.ParseMode.HTML)
        return

    hunter.check_and_reset_daily()
    guardian = generate_guardian(hunter.tower_floor)

    command_text = (message.text or "").strip().lower()

    # If /trial invoked directly, trigger the floor climb!
    if command_text.startswith("/trial"):
        await _execute_climb(client, message, hunter, user.id)
        return

    caption = build_tower_caption(hunter, guardian)

    try:
        photo_buf = await asyncio.to_thread(render_tower_image, hunter, guardian)
        await message.reply_photo(
            photo=photo_buf,
            caption=caption,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=_tower_keyboard(hunter),
        )
    except Exception as e:
        logger.error("Failed to render tower image: %s", e, exc_info=True)
        await message.reply_text(caption, reply_markup=_tower_keyboard(hunter), parse_mode=enums.ParseMode.HTML)


async def _execute_climb(
    client: Client,
    target: Message | CallbackQuery,
    hunter: Hunter,
    user_id: int,
) -> None:
    """Execute the floor duel, update hunter stats, and transmit result card."""
    db: ChannelDB = client.db
    hunter.check_and_reset_daily()

    if hunter.tower_keys <= 0:
        msg = (
            "<b>╭━━━「 🏰 DEMON CASTLE NOTICE 」━━━╮</b>\n\n"
            "❌ <b>Daily Keys Depleted!</b>\n\n"
            "<blockquote>"
            "• You have exhausted all <code>3/3</code> daily Demon Castle Keys.\n"
            "• Keys automatically replenish at <code>00:00 UTC</code>."
            "</blockquote>\n\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
        )
        if isinstance(target, CallbackQuery):
            await target.answer("❌ You have exhausted your 3 daily Demon Castle Keys!", show_alert=True)
        else:
            await target.reply_text(msg, parse_mode=enums.ParseMode.HTML)
        return

    if hunter.tower_floor > 100:
        msg = (
            "<b>╭━━━「 👑 DEMON CASTLE CONQUERED 」━━━╮</b>\n\n"
            "🏆 <b>Apex Monarch Achievement!</b>\n\n"
            "<blockquote>"
            "• You have already conquered all <code>100 Floors</code> of the Demon Castle!\n"
            "• The Spire has bowed to your supreme dominance."
            "</blockquote>\n\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
        )
        if isinstance(target, CallbackQuery):
            await target.answer("👑 You have already conquered all 100 floors of the Demon Castle!", show_alert=True)
        else:
            await target.reply_text(msg, parse_mode=enums.ParseMode.HTML)
        return

    # Expend key
    hunter.tower_keys -= 1
    result = simulate_tower_climb(hunter, hunter.tower_floor)

    # Deduct damage taken
    hunter.hp = max(1, hunter.hp - result.damage_taken)

    notice = ""
    if result.victory:
        cleared_floor = hunter.tower_floor
        hunter.tower_floor += 1
        hunter.tower_highest_floor = max(hunter.tower_highest_floor, cleared_floor)
        hunter.gold += result.gold_gained

        leveled_up, new_rank = add_xp(hunter, result.xp_gained)
        result.leveled_up = leveled_up
        result.new_rank = new_rank

        if result.title_unlocked:
            hunter.title = result.title_unlocked

        if result.item_drop:
            inventory = await db.get_inventory(user_id)
            if inventory:
                inventory.add_item(result.item_drop)

        notice = f"CONQUERED FLOOR {cleared_floor}! (+{result.gold_gained} G, +{result.xp_gained} XP)"
        if result.title_unlocked:
            notice += f" | New Title: {result.title_unlocked}"
    else:
        # Defeat
        notice = f"DEFEATED ON FLOOR {hunter.tower_floor}! (-{result.damage_taken} HP)"

    await db.save_all(user_id)

    # Prepare updated guardian and image
    next_guardian = generate_guardian(min(100, hunter.tower_floor))
    caption = build_tower_caption(hunter, next_guardian, result, notice)

    try:
        photo_buf = await asyncio.to_thread(render_tower_image, hunter, next_guardian, notice)
        if isinstance(target, CallbackQuery) and target.message and target.message.photo:
            await target.answer("Ascension battle concluded!", show_alert=False)
            await target.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_tower_keyboard(hunter),
            )
        elif isinstance(target, CallbackQuery):
            await target.answer("Ascension battle concluded!", show_alert=False)
            await target.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_tower_keyboard(hunter),
            )
        else:
            await target.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_tower_keyboard(hunter),
            )
    except Exception as e:
        logger.error("Failed to render tower result: %s", e, exc_info=True)
        if isinstance(target, CallbackQuery):
            await target.edit_message_text(caption, reply_markup=_tower_keyboard(hunter), parse_mode=enums.ParseMode.HTML)
        else:
            await target.reply_text(caption, reply_markup=_tower_keyboard(hunter), parse_mode=enums.ParseMode.HTML)


async def callback(client: Client, query: CallbackQuery) -> None:
    """Handle tower inline button callbacks."""
    user = query.from_user
    if not user:
        await query.answer()
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await query.answer("You are not a registered Hunter!", show_alert=True)
        return

    if query.data == "tower_climb":
        await _execute_climb(client, query, hunter, user.id)
    elif query.data in ["tower_menu", "tower_refresh"]:
        await query.answer("Accessing Demon Castle Spire...")
        guardian = generate_guardian(min(100, hunter.tower_floor))
        caption = build_tower_caption(hunter, guardian)
        photo_buf = await asyncio.to_thread(render_tower_image, hunter, guardian)
        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_tower_keyboard(hunter),
            )
        elif query.message:
            await query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=_tower_keyboard(hunter),
                parse_mode=enums.ParseMode.HTML,
            )
    elif query.data == "tower_noop":
        await query.answer("Daily keys depleted. Resets at midnight UTC.", show_alert=True)
