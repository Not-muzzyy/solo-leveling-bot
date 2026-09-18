"""
handlers/hunt.py — /hunt command handler.

Main progression command with 15-minute cooldown.
"""

from __future__ import annotations

import asyncio
import logging
import time

from pyrogram import Client, enums
from pyrogram.types import Message

from channel_db import ChannelDB
from config import HUNT_COOLDOWN_SECONDS, GUILD_XP_BONUS, DAILY_HUNT_LIMIT
from game.combat import generate_monster, simulate_hunt
from game.hunter import add_xp
from game.hunt_image import render_hunt_image
from game.captions import build_hunt_caption
from game.formatting import (
    format_hunt_result,
    format_cooldown,
    format_not_registered,
)
from game.rich_text import escape_html

logger = logging.getLogger(__name__)

# In-memory cooldown tracker: user_id → timestamp of last hunt (fallback cache)
_cooldowns: dict[int, float] = {}


def _check_cooldown(hunter: Hunter, user_id: int) -> int | None:
    """
    Check if hunter is on cooldown using persistent timestamp and in-memory cache.
    Returns remaining seconds if on cooldown, None if ready.
    """
    now = time.time()
    last_hunt = max(hunter.last_hunt_time or 0.0, _cooldowns.get(user_id, 0.0))
    if last_hunt <= 0:
        return None

    elapsed = now - last_hunt
    remaining = HUNT_COOLDOWN_SECONDS - elapsed

    if remaining <= 0:
        return None

    return int(remaining)


async def handle(client: Client, message: Message) -> None:
    """Handle the /hunt command with 1-minute cooldown and 20 daily uses cap."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db

    # Check registration
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await message.reply_text(format_not_registered(), parse_mode=enums.ParseMode.HTML)
        return

    # Check and reset daily counter if UTC date changed
    hunter.check_and_reset_daily()

    # Enforce 20 daily hunts limit
    h_name = escape_html(hunter.hunter_name)
    if hunter.daily_hunts >= DAILY_HUNT_LIMIT:
        await message.reply_text(
            "<b>╭━━━「 ⚔️ DAILY HUNT CAPACITY EXHAUSTED 」━━━╮</b>\n\n"
            f"👤 <b>Hunter:</b> {h_name}\n"
            f"📊 <b>Daily Quota:</b> <code>{hunter.daily_hunts} / {DAILY_HUNT_LIMIT}</code> Hunts Completed\n\n"
            "<blockquote>"
            "The dimensional rifts in this sector are closed for the day.\n"
            "Your hunt quota resets automatically at midnight UTC.\n\n"
            "💡 <i>Tip: Venture into uncharted territory with <code>/explore</code> (3x daily)!</i>"
            "</blockquote>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # Check cooldown (1 minute)
    remaining = _check_cooldown(hunter, user.id)
    if remaining is not None:
        await message.reply_text(format_cooldown(remaining), parse_mode=enums.ParseMode.HTML)
        return

    # Set cooldown and increment daily hunts
    now = time.time()
    _cooldowns[user.id] = now
    hunter.last_hunt_time = now
    hunter.daily_hunts += 1
    hunter.total_hunts += 1

    # Daily quest tracking: hunts completed
    hunter.daily_quest_hunts += 1

    # Generate monster based on hunter level/rank
    monster = generate_monster(hunter.level)

    # Simulate combat
    result = simulate_hunt(hunter, monster)

    # Check if hunter has guild XP bonus
    guild = await db.get_user_guild(user.id)
    if guild and result.victory:
        result.xp_gained = int(result.xp_gained * (1 + GUILD_XP_BONUS))

    # Apply outcome to hunter
    if result.victory:
        hunter.victories += 1
        hunter.gold += result.gold_gained
        hunter.hp = max(1, hunter.hp - result.damage_taken)

        # Level up checks
        leveled_up, new_rank = add_xp(hunter, result.xp_gained)
        result.leveled_up = leveled_up
        result.new_rank = new_rank

        # Item drop
        if result.item_drop:
            inventory = await db.get_inventory(user.id)
            inventory.add_item(result.item_drop)
    else:
        hunter.defeats += 1
        hunter.gold = max(0, hunter.gold - result.gold_lost)
        hunter.hp = max(1, hunter.hp - max(20, result.damage_taken))

        # Small consolation XP
        add_xp(hunter, result.xp_gained)

    # Save to channel
    await db.save_all(user.id)

    # Send battle result image (Victory or Defeat) with rich Hallmark caption
    try:
        photo_buf = await asyncio.to_thread(render_hunt_image, hunter, result)
        caption = build_hunt_caption(hunter, result)
        await message.reply_photo(
            photo=photo_buf,
            caption=caption,
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception as exc:
        logger.error("Failed to render hunt image, falling back to text: %s", exc, exc_info=True)
        await message.reply_text(
            format_hunt_result(result),
            parse_mode=enums.ParseMode.HTML,
        )
