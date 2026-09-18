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
        "<b>╭━━━「 ⏳ DAILY STIPEND COOLDOWN 」━━━╮</b>\n\n"
        "<blockquote>"
        "You have already collected your daily ration from the System.\n"
        f"⏱️ <b>Next ration ready in:</b> <code>{hours}h {minutes:02d}m</code>"
        "</blockquote>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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

    # Check 24h cooldown
    remaining = _check_cooldown(user.id)
    if remaining is not None:
        await message.reply_text(_format_cooldown(remaining), parse_mode=enums.ParseMode.HTML)
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
    h_name = escape_html(hunter.hunter_name)
    extra_lines = []
    if leveled_up:
        extra_lines.append(f"⚡ <b>LEVEL UP!</b> Reached <b>Level {hunter.level}</b>")
    if new_rank:
        extra_lines.append(f"🔥 <b>RANK ADVANCEMENT!</b> Awakened as <b>[{escape_html(new_rank)}] Hunter</b>")

    extra_block = ""
    if extra_lines:
        extra_block = f"\n<blockquote>{' '.join(extra_lines)}</blockquote>\n"

    msg_text = (
        "<b>╭━━━「 💰 DAILY SYSTEM STIPEND 」━━━╮</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} [Rank <b>{hunter.rank}</b>]\n\n"
        "<blockquote>"
        "<b>✅ Daily Ration Dispatched:</b>\n"
        f"• EXP Bounty: ✨ <code>+{xp_reward:,} XP</code>\n"
        f"• Treasury Bonus: 💰 <code>+{gold_reward:,} G</code>\n"
        f"• Total Vault: 💰 <code>{hunter.gold:,} G</code>\n"
        f"• Current EXP: <code>{hunter.xp:,} / {hunter.xp_needed:,} XP</code>\n"
        "</blockquote>\n"
        f"{extra_block}\n"
        "<blockquote><i>「 Return tomorrow for your next allocation, Hunter. 」</i></blockquote>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )

    await message.reply_text(msg_text, parse_mode=enums.ParseMode.HTML)
    logger.info(f"Daily claim by {hunter.hunter_name}: +{xp_reward} XP, +{gold_reward} Gold")
