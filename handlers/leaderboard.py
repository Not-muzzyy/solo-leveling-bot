"""
handlers/leaderboard.py — /leaderboard command handler.

Displays top hunters across multiple categories (Combat Power, Hunter Level,
Wealth, Dungeon Victories) on a dynamic Solo Leveling System HUD card.
Strictly displays the hunter's real First Name and Last Name (never @username).
Provides live category switching via inline keyboard callbacks (lb_<category>).
"""

from __future__ import annotations

import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from channel_db import ChannelDB
from game.font_manager import clean_and_normalize_name
from game.leaderboard_image import render_leaderboard_image
from models import Hunter

logger = logging.getLogger(__name__)

CATEGORY_TITLES = {
    "power": "Combat Power",
    "level": "Hunter Level",
    "wealth": "Gold Wealth",
    "victories": "Dungeon Victories",
}


def _leaderboard_keyboard(active_cat: str = "power") -> InlineKeyboardMarkup:
    """Inline tabs to switch between leaderboard categories."""
    def btn_label(cat: str, icon: str, name: str) -> str:
        return f"[ {icon} {name} ]" if cat == active_cat else f"{icon} {name}"

    buttons = [
        [
            InlineKeyboardButton(btn_label("power", "⚡", "Power"), callback_data="lb_power"),
            InlineKeyboardButton(btn_label("level", "🏆", "Level"), callback_data="lb_level"),
        ],
        [
            InlineKeyboardButton(btn_label("wealth", "💰", "Wealth"), callback_data="lb_wealth"),
            InlineKeyboardButton(btn_label("victories", "⚔️", "Victories"), callback_data="lb_victories"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def _sort_hunters(hunters: list[Hunter], category: str) -> list[Hunter]:
    """Sort hunters list based on the selected leaderboard category."""
    if category == "level":
        return sorted(hunters, key=lambda h: (h.level, h.xp, h.combat_power), reverse=True)
    elif category == "wealth":
        return sorted(hunters, key=lambda h: (h.gold, h.combat_power, h.level), reverse=True)
    elif category == "victories":
        return sorted(hunters, key=lambda h: (h.victories, h.combat_power, h.level), reverse=True)
    else:  # "power" (default)
        return sorted(hunters, key=lambda h: (h.combat_power, h.level, h.gold), reverse=True)


async def _resolve_missing_names(
    context: ContextTypes.DEFAULT_TYPE,
    db: ChannelDB,
    hunters: list[Hunter],
) -> None:
    """Resolve and cache real First Name & Last Name for top hunters missing them."""
    for h in hunters:
        if not h.first_name:
            try:
                chat = await context.bot.get_chat(h.user_id)
                if chat and (chat.first_name or chat.last_name):
                    h.first_name = clean_and_normalize_name(chat.first_name)
                    h.last_name = clean_and_normalize_name(chat.last_name)
                    await db.save_hunter(h.user_id)
            except Exception as exc:
                logger.debug("Failed to fetch chat for user_id=%s: %s", h.user_id, exc)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /leaderboard command."""
    user = update.effective_user
    if not user:
        return

    db: ChannelDB = context.bot_data["db"]

    # Ensure caller's hunter profile has latest Telegram first & last name
    req_hunter = await db.get_hunter(user.id)
    if req_hunter:
        clean_fn = clean_and_normalize_name(user.first_name)
        clean_ln = clean_and_normalize_name(user.last_name)
        dirty = False
        if clean_fn and req_hunter.first_name != clean_fn:
            req_hunter.first_name = clean_fn
            dirty = True
        if req_hunter.last_name != clean_ln:
            req_hunter.last_name = clean_ln
            dirty = True
        if dirty:
            await db.save_hunter(user.id)

    all_hunters = await db.get_all_hunters()
    if not all_hunters:
        await update.message.reply_text(
            "╔══════════════════════════════╗\n"
            "║   ⚡ SYSTEM NOTIFICATION ⚡   ║\n"
            "║      HUNTER LEADERBOARD      ║\n"
            "╚══════════════════════════════╝\n\n"
            "No hunters have awakened yet!\n"
            "Use /start to awaken and begin your hunter journey."
        )
        return

    category = "power"
    sorted_hunters = _sort_hunters(all_hunters, category)

    # Resolve names for top 10 hunters
    await _resolve_missing_names(context, db, sorted_hunters[:10])

    try:
        photo_buf = await asyncio.to_thread(
            render_leaderboard_image,
            sorted_hunters,
            category=category,
            requesting_user_id=user.id,
        )
        cat_name = CATEGORY_TITLES.get(category, "Combat Power")
        caption = f"🏆 System Leaderboard — Top Hunters [{cat_name}]"
        await update.message.reply_photo(
            photo=photo_buf,
            caption=caption,
            reply_markup=_leaderboard_keyboard(category),
        )
    except Exception as exc:
        logger.error("Failed to render leaderboard image: %s", exc, exc_info=True)
        await update.message.reply_text("❌ System Error: Failed to render leaderboard. Please try again later.")


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle lb_<category> tab switching callbacks."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    data = query.data or ""
    if not data.startswith("lb_"):
        return

    category = data[3:]
    if category not in CATEGORY_TITLES:
        category = "power"

    user = update.effective_user
    user_id = user.id if user else 0
    db: ChannelDB = context.bot_data["db"]

    all_hunters = await db.get_all_hunters()
    if not all_hunters:
        return

    sorted_hunters = _sort_hunters(all_hunters, category)
    await _resolve_missing_names(context, db, sorted_hunters[:10])

    try:
        photo_buf = await asyncio.to_thread(
            render_leaderboard_image,
            sorted_hunters,
            category=category,
            requesting_user_id=user_id,
        )
        cat_name = CATEGORY_TITLES.get(category, "Combat Power")
        caption = f"🏆 System Leaderboard — Top Hunters [{cat_name}]"

        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption),
                reply_markup=_leaderboard_keyboard(category),
            )
        elif query.message:
            await query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=_leaderboard_keyboard(category),
            )
    except BadRequest as br_err:
        if "Message is not modified" not in str(br_err):
            logger.warning("BadRequest during leaderboard update: %s", br_err)
    except Exception as exc:
        logger.error("Failed to update leaderboard tab: %s", exc, exc_info=True)
