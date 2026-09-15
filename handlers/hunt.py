"""
handlers/hunt.py — /hunt command handler.

Main progression command with 15-minute cooldown.
"""

from __future__ import annotations

import asyncio
import logging
import time

from pyrogram import Client
from pyrogram.types import Message

from channel_db import ChannelDB
from config import HUNT_COOLDOWN_SECONDS, GUILD_XP_BONUS
from game.combat import generate_monster, simulate_hunt
from game.hunter import add_xp
from game.hunt_image import render_hunt_image
from game.formatting import (
    format_hunt_result,
    format_cooldown,
    format_not_registered,
)

logger = logging.getLogger(__name__)

# In-memory cooldown tracker: user_id → timestamp of last hunt
_cooldowns: dict[int, float] = {}


def _check_cooldown(user_id: int) -> int | None:
    """
    Check if user is on cooldown.
    Returns remaining seconds if on cooldown, None if ready.
    """
    last_hunt = _cooldowns.get(user_id)
    if last_hunt is None:
        return None

    elapsed = time.time() - last_hunt
    remaining = HUNT_COOLDOWN_SECONDS - elapsed

    if remaining <= 0:
        return None

    return int(remaining)


async def handle(client: Client, message: Message) -> None:
    """Handle the /hunt command."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db

    # Check registration
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await message.reply_text(format_not_registered())
        return

    # Check cooldown
    remaining = _check_cooldown(user.id)
    if remaining is not None:
        await message.reply_text(format_cooldown(remaining))
        return

    # Set cooldown
    _cooldowns[user.id] = time.time()

    # Generate monster and simulate
    monster = generate_monster(hunter.level)
    result = simulate_hunt(hunter, monster)

    # Check for guild XP bonus
    guild_bonus = 0.0
    if hunter.guild_id:
        guild_bonus = GUILD_XP_BONUS

    # Apply results to hunter
    hunter.total_hunts += 1

    if result.victory:
        hunter.victories += 1
        hunter.gold += result.gold_gained

        # Add XP and check for level/rank up
        leveled_up, new_rank = add_xp(hunter, result.xp_gained, bonus=guild_bonus)
        result.leveled_up = leveled_up
        result.new_level = hunter.level if leveled_up else None
        result.ranked_up = new_rank is not None
        result.new_rank = new_rank

        # Add loot to inventory
        if result.item_drop:
            inventory = await db.get_inventory(user.id)
            inventory.add_item(result.item_drop)
    else:
        hunter.defeats += 1
        hunter.gold = max(0, hunter.gold - result.gold_lost)

        # Small consolation XP
        add_xp(hunter, result.xp_gained)

    # Save to channel
    await db.save_all(user.id)

    # Send battle result image (Victory or Defeat)
    try:
        photo_buf = await asyncio.to_thread(render_hunt_image, hunter, result)
        if result.victory:
            caption = f"⚔️ Victory against {result.monster.name} (+{result.xp_gained} XP, +{result.gold_gained} G)"
            if result.item_drop:
                caption += f" | 🎁 Loot: {result.item_drop.name}"
        else:
            caption = f"☠️ Defeated by {result.monster.name} (-{result.gold_lost} G)"

        await message.reply_photo(
            photo=photo_buf,
            caption=caption,
        )
    except Exception as exc:
        logger.error("Failed to render hunt image, falling back to text: %s", exc, exc_info=True)
        await message.reply_text(format_hunt_result(result))
