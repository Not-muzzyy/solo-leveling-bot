"""
handlers/hunt.py — /hunt command handler.

Main progression command with 15-minute cooldown.
"""

from __future__ import annotations

import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

from channel_db import ChannelDB
from config import HUNT_COOLDOWN_SECONDS
from game.combat import generate_monster, simulate_hunt
from game.hunter import add_xp
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


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /hunt command."""
    user = update.effective_user
    if not user:
        return

    db: ChannelDB = context.bot_data["db"]

    # Check registration
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await update.message.reply_text(format_not_registered())
        return

    # Check cooldown
    remaining = _check_cooldown(user.id)
    if remaining is not None:
        await update.message.reply_text(format_cooldown(remaining))
        return

    # Set cooldown
    _cooldowns[user.id] = time.time()

    # Generate monster and simulate
    monster = generate_monster(hunter.level)
    result = simulate_hunt(hunter, monster)

    # Apply results to hunter
    hunter.total_hunts += 1

    if result.victory:
        hunter.victories += 1
        hunter.gold += result.gold_gained

        # Add XP and check for level/rank up
        leveled_up, new_rank = add_xp(hunter, result.xp_gained)
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

    # Send result
    await update.message.reply_text(format_hunt_result(result))
