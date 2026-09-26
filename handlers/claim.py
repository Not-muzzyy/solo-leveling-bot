"""
handlers/claim.py — /claim command handler.

Daily login reward — one claim per 24 hours. Gives XP and Gold
scaled to the hunter's level.
"""

from __future__ import annotations

import logging

from pyrogram import Client, enums
from pyrogram.types import Message

from channel_db import ChannelDB
from game.economy import GameActionError, claim_daily_reward
from game.formatting import format_not_registered, format_not_registered_rich
from game.captions import build_claim_caption, build_claim_rich
from game.rich_send import reply_rich
from game.miniapp import send_miniapp_entry

logger = logging.getLogger(__name__)

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


def _format_cooldown_rich(remaining: int):
    """Rich twin of _format_cooldown (same copy, block structure)."""
    from game.rich_message import RichDoc, code, heading, quote
    hours = remaining // 3600
    minutes = (remaining % 3600) // 60
    return RichDoc(
        heading(1, "[ SYSTEM DAILY ALLOCATION // 보급품 대기 ]"),
        quote(
            "You have already collected your daily ration from the System.<br>"
            f"⏱️ <b>Next ration ready in:</b> {code(f'{hours}h {minutes:02d}m')}<br>"
            "• Return after the cooldown expires to claim your next ration.",
            expandable=True,
        ),
    )


async def handle(client: Client, message: Message) -> None:
    """Handle the /claim command — daily reward."""
    user = message.from_user
    if not user:
        return

    if await send_miniapp_entry(
        message,
        section="claim",
        title="[ SYSTEM DAILY ALLOCATION ]",
        description="Open the Hunter System Mini App to collect your daily Gold and XP.",
        button_label="◈ Open Daily Allocation",
    ):
        return

    db: ChannelDB = client.db

    try:
        result = await claim_daily_reward(db, user.id)
    except GameActionError as exc:
        if exc.code == "hunter_not_found":
            await reply_rich(
                message, format_not_registered_rich(),
                fallback=lambda: message.reply_text(format_not_registered(), parse_mode=enums.ParseMode.HTML),
            )
        else:
            await message.reply_text(exc.message)
            logger.error("Daily claim failed for %s: %s", user.id, exc)
        return

    hunter = result.hunter
    if not result.claimed:
        await reply_rich(
            message, _format_cooldown_rich(result.remaining_seconds),
            fallback=lambda: message.reply_text(_format_cooldown(result.remaining_seconds), parse_mode=enums.ParseMode.HTML),
        )
        return

    gold_reward = result.gold_reward
    xp_reward = result.xp_reward
    leveled_up = result.leveled_up
    new_rank = result.new_rank

    # Build message using centralized rich text template
    msg_text = build_claim_caption(
        hunter,
        gold_reward,
        xp_reward,
        streak=1,
        leveled_up=leveled_up,
        new_rank=new_rank,
    )

    await reply_rich(
        message,
        build_claim_rich(
            hunter,
            gold_reward,
            xp_reward,
            streak=1,
            leveled_up=leveled_up,
            new_rank=new_rank,
        ),
        fallback=lambda: message.reply_text(msg_text, parse_mode=enums.ParseMode.HTML),
    )
    logger.info(f"Daily claim by {hunter.hunter_name}: +{xp_reward} XP, +{gold_reward} Gold")
