"""
handlers/claim.py — /claim command handler.

Daily login reward — one claim per 24 hours. Gives XP and Gold
scaled to the hunter's level.
"""

from __future__ import annotations

import logging
import random
import time

from pyrogram import Client, enums
from pyrogram.types import Message

from channel_db import ChannelDB
from game.hunter import add_xp
from game.formatting import format_not_registered
from game.rich_text import escape_html
from game.captions import build_claim_caption

logger = logging.getLogger(__name__)

# 24-hour cooldown in seconds
CLAIM_COOLDOWN_SECONDS = 86400

# In-memory cooldown cache: user_id → timestamp (persisted truth lives on Hunter.last_claim_time)
_claim_cooldowns: dict[int, float] = {}


def _check_cooldown(hunter: Hunter, user_id: int) -> int | None:
    """Returns remaining seconds if on cooldown, None if ready.

    Uses the persisted hunter timestamp (survives restarts) with the
    in-memory dict as a fast fallback cache — same pattern as hunt.
    """
    now = time.time()
    last_claim = max(hunter.last_claim_time or 0.0, _claim_cooldowns.get(user_id, 0.0))
    if last_claim <= 0:
        return None
    remaining = CLAIM_COOLDOWN_SECONDS - (now - last_claim)
    return int(remaining) if remaining > 0 else None


def _format_cooldown(remaining: int) -> str:
    """Format the claim cooldown message."""
    hours = remaining // 3600
    minutes = (remaining % 3600) // 60
    return (
        "<b>[ SYSTEM DAILY ALLOCATION // 보급품 대기 ]</b>\n\n"
        "<blockquote expandable>"
        "You have already collected your daily ration from the System.\n"
        f"⏱️ <b>Next ration ready in:</b> <code>{hours}h {minutes:02d}m</code>\n"
        "• Return after the cooldown expires to claim your next ration.\n"
        "</blockquote>"
    )


async def handle(client: Client, message: Message) -> None:
    """Handle the /claim command — daily reward."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db

    hunter = await db.get_hunter(user.id)
    if not hunter:
        await message.reply_text(format_not_registered(), parse_mode=enums.ParseMode.HTML)
        return

    # Check 24h cooldown (persisted on the hunter)
    remaining = _check_cooldown(hunter, user.id)
    if remaining is not None:
        await message.reply_text(_format_cooldown(remaining), parse_mode=enums.ParseMode.HTML)
        return

    # Set cooldown — both in-memory cache and persisted field
    now = time.time()
    _claim_cooldowns[user.id] = now
    hunter.last_claim_time = now

    # Calculate rewards scaled to level
    base_gold = 50 + (hunter.level * 10)
    base_xp = 30 + (hunter.level * 8)
    gold_reward = base_gold + random.randint(-10, 20)
    xp_reward = base_xp + random.randint(-5, 15)

    # Apply rewards
    hunter.gold += gold_reward
    leveled_up, new_rank = add_xp(hunter, xp_reward)

    # Save
    await db.save_hunter(user.id)

    # Build message using centralized rich text template
    msg_text = build_claim_caption(
        hunter,
        gold_reward,
        xp_reward,
        streak=1,
        leveled_up=leveled_up,
        new_rank=new_rank,
    )

    await message.reply_text(msg_text, parse_mode=enums.ParseMode.HTML)
    logger.info(f"Daily claim by {hunter.hunter_name}: +{xp_reward} XP, +{gold_reward} Gold")
