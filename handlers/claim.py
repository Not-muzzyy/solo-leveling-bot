"""
handlers/claim.py — /claim command handler.

Daily login reward — one claim per 24 hours. Gives XP and Gold
scaled to the hunter's level.
"""

from __future__ import annotations

import logging
import random
import time

from pyrogram import Client
from pyrogram.types import Message

from channel_db import ChannelDB
from game.hunter import add_xp
from game.formatting import format_not_registered

logger = logging.getLogger(__name__)

# 24-hour cooldown in seconds
CLAIM_COOLDOWN_SECONDS = 86400

# In-memory cooldown tracker: user_id → timestamp of last claim
_claim_cooldowns: dict[int, float] = {}


def _check_cooldown(user_id: int) -> int | None:
    """Returns remaining seconds if on cooldown, None if ready."""
    last_claim = _claim_cooldowns.get(user_id)
    if last_claim is None:
        return None

    elapsed = time.time() - last_claim
    remaining = CLAIM_COOLDOWN_SECONDS - elapsed

    if remaining <= 0:
        return None

    return int(remaining)


def _format_cooldown(remaining: int) -> str:
    """Format the claim cooldown message."""
    hours = remaining // 3600
    minutes = (remaining % 3600) // 60
    return (
        f"⏳ You have already claimed your daily reward!\n"
        f"\n"
        f"⏱️ Next claim in: {hours}h {minutes:02d}m"
    )


async def handle(client: Client, message: Message) -> None:
    """Handle the /claim command — daily reward."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db

    hunter = await db.get_hunter(user.id)
    if not hunter:
        await message.reply_text(format_not_registered())
        return

    # Check 24h cooldown
    remaining = _check_cooldown(user.id)
    if remaining is not None:
        await message.reply_text(_format_cooldown(remaining))
        return

    # Set cooldown
    _claim_cooldowns[user.id] = time.time()

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

    # Build message
    lines = [
        "🎁 DAILY REWARD CLAIMED",
        "",
        "━━━━━━━━━━━━━━━━━━",
        f"✨ XP: +{xp_reward}",
        f"💰 Gold: +{gold_reward}",
        "━━━━━━━━━━━━━━━━━━",
    ]

    if leveled_up:
        lines.append("")
        lines.append(f"⚡ LEVEL UP! → Level {hunter.level}")

    if new_rank:
        lines.append(f"🔥 RANK UP! → {new_rank}")

    lines.append("")
    lines.append(f"💰 Total Gold: {hunter.gold}")
    lines.append(f"✨ XP: {hunter.xp}/{hunter.xp_needed}")
    lines.append("")
    lines.append("「 Come back tomorrow for more, Hunter. 」")

    await message.reply_text("\n".join(lines))
    logger.info(f"Daily claim by {hunter.hunter_name}: +{xp_reward} XP, +{gold_reward} Gold")
