"""
handlers/duel.py — /duel command and callback query handlers.

Manages PvP hunter duels in group chats via message replies.
Features:
- Group-only enforcement (PM directs user to group chats)
- Message-reply validation (must reply to another hunter's message)
- Target validation (no bots, no self-duels, both hunters registered)
- Inline challenge buttons: [ ⚔️ Accept Duel ] and [ ❌ Decline ]
- Opponent-only authorization check
- Real-time profile photo retrieval
- Pure combat simulation factoring in equipped gear
- High-definition duel card image rendering and telegram dispatch
- Persistent hunter record and reward saves to ChannelDB.
"""

from __future__ import annotations

import asyncio
import logging
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

from channel_db import ChannelDB
from game.formatting import format_not_registered
from game.duel import simulate_duel
from game.duel_image import render_duel_card
from game.photo_helper import fetch_user_pfp_bytes

logger = logging.getLogger(__name__)


async def handle(client: Client, message: Message) -> None:
    """Handle the /duel command."""
    user = message.from_user
    chat = message.chat

    if not user or not chat:
        return

    # 1. Enforce Group Chat Only (No Duels in PM)
    if chat.type == "private":
        await message.reply_text(
            "⚔️ <b>HUNTER PVP ARENA</b>\n\n"
            "Duels can only be initiated in <b>Group Chats</b>!\n\n"
            "To challenge a rival Hunter, reply to any of their messages in a group with <code>/duel</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    # 2. Enforce Reply-To-Message Requirement
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply_text(
            "⚠️ <b>Challenge Target Required!</b>\n\n"
            "To challenge another Hunter to a duel, <b>reply</b> to one of their messages in this group with <code>/duel</code>!",
            parse_mode=ParseMode.HTML,
        )
        return

    opponent_user = message.reply_to_message.from_user

    # 3. Disallow Bot Challenges
    if opponent_user.is_bot:
        await message.reply_text(
            "🤖 <b>Automaton Target Invalid!</b>\n\n"
            "You cannot challenge a System Automaton / Bot to a duel!",
            parse_mode=ParseMode.HTML,
        )
        return

    # 4. Disallow Self-Duels
    if opponent_user.id == user.id:
        await message.reply_text(
            "⚔️ <b>Self-Challenge Prohibited!</b>\n\n"
            "You cannot duel yourself. Reply to a worthy rival Hunter's message to issue a challenge!",
            parse_mode=ParseMode.HTML,
        )
        return

    db: ChannelDB = client.db

    # 5. Check Registration of Challenger
    challenger_hunter = await db.get_hunter(user.id)
    if not challenger_hunter:
        await message.reply_text(format_not_registered())
        return

    # 6. Check Registration of Opponent
    opponent_hunter = await db.get_hunter(opponent_user.id)
    if not opponent_hunter:
        opp_name = opponent_user.first_name or "Target"
        await message.reply_text(
            f"⚠️ <b>Target Not Awakened!</b>\n\n"
            f"<b>{opp_name}</b> has not awakened as a Hunter yet. They must start their journey with /start first!",
            parse_mode=ParseMode.HTML,
        )
        return

    # 7. Send Duel Challenge Invitation with Interactive Keyboard
    c_name = challenger_hunter.display_full_name
    o_name = opponent_hunter.display_full_name

    text = (
        "╔══════════════════════════════════╗\n"
        "║   ⚔️ <b>HUNTER DUEL CHALLENGE</b> ⚔️   ║\n"
        "╚══════════════════════════════════╝\n\n"
        f"💥 <b>{c_name}</b> [Rank {challenger_hunter.rank} • Lv. {challenger_hunter.level}]\n"
        f"has challenged\n"
        f"🎯 <b>{o_name}</b> [Rank {opponent_hunter.rank} • Lv. {opponent_hunter.level}]\n"
        "to an official Arena PvP Duel!\n\n"
        f"<i>Only {o_name} can accept or decline this challenge.</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚔️ Accept Duel", callback_data=f"duel_accept_{user.id}_{opponent_user.id}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"duel_decline_{user.id}_{opponent_user.id}"),
        ]
    ])

    await message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def callback(client: Client, query: CallbackQuery) -> None:
    """Handle duel acceptance or decline button callbacks."""
    if not query or not query.data:
        return

    data = query.data
    if not data.startswith("duel_"):
        return

    parts = data.split("_")
    if len(parts) != 4:
        return

    action = parts[1]  # "accept" or "decline"
    challenger_id = int(parts[2])
    opponent_id = int(parts[3])

    clicker_id = query.from_user.id

    # 1. Strictly Authorize Only the Challenged Opponent
    if clicker_id != opponent_id:
        await query.answer("❌ Only the challenged Hunter can accept or decline this duel!", show_alert=True)
        return

    db: ChannelDB = client.db
    challenger = await db.get_hunter(challenger_id)
    opponent = await db.get_hunter(opponent_id)

    c_name = challenger.display_full_name if challenger else f"Hunter #{challenger_id}"
    o_name = opponent.display_full_name if opponent else f"Hunter #{opponent_id}"

    # 2. Handle Decline
    if action == "decline":
        await query.answer("Duel challenge declined.")
        await query.edit_message_text(
            f"🏳️ <b>DUEL DECLINED</b>\n\n"
            f"<b>{o_name}</b> has declined the duel challenge from <b>{c_name}</b>.",
            parse_mode=ParseMode.HTML,
        )
        return

    # 3. Handle Accept
    if action == "accept":
        await query.answer("⚔️ Duel accepted! Entering Arena...")
        await query.edit_message_text(
            "⚔️ <b>DUEL IN PROGRESS...</b>\n\n"
            f"<b>{c_name}</b> and <b>{o_name}</b> have entered the Arena!\n"
            "The System is computing combat resolution...",
            parse_mode=ParseMode.HTML,
        )

        if not challenger or not opponent:
            await query.message.reply_text("⚠️ Could not load hunter profiles. Duel aborted.")
            return

        c_inv = await db.get_inventory(challenger_id)
        o_inv = await db.get_inventory(opponent_id)

        # 4. Retrieve Profile Photos (if available) via MTProto
        c_pfp_bytes = await fetch_user_pfp_bytes(client, challenger_id)
        o_pfp_bytes = await fetch_user_pfp_bytes(client, opponent_id)

        # 5. Simulate Combat
        result = simulate_duel(challenger, c_inv, opponent, o_inv)

        # 6. Persist Updated Hunter Data
        await db.save_hunter(challenger_id)
        await db.save_hunter(opponent_id)

        # 7. Render Duel Resolution Card & Dispatch
        try:
            photo_buf = await asyncio.to_thread(
                render_duel_card,
                result,
                challenger_pfp=c_pfp_bytes,
                opponent_pfp=o_pfp_bytes,
                challenger_inv=c_inv,
                opponent_inv=o_inv,
            )

            winner_name = result.winner.display_full_name
            loser_name = result.loser.display_full_name
            caption = (
                f"⚔️ <b>PVP ARENA DUEL RESOLUTION</b>\n\n"
                f"👑 <b>Victor:</b> {winner_name} (+{result.winner_xp_gained} XP, +{result.winner_gold_gained} G)\n"
                f"💀 <b>Defeated:</b> {loser_name} (+{result.loser_xp_gained} XP)"
            )
            if result.winner_leveled_up and result.winner_new_level:
                caption += f"\n⭐ <b>{winner_name}</b> leveled up to <b>Lv. {result.winner_new_level}</b>!"

            await query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            logger.error("Failed to render duel card: %s", exc, exc_info=True)
            await query.message.reply_text(
                f"⚔️ <b>PVP ARENA DUEL RESOLUTION</b>\n\n"
                f"👑 <b>Victor:</b> {result.winner.display_full_name}\n"
                f"💀 <b>Defeated:</b> {result.loser.display_full_name}\n\n"
                f"💥 Challenger Damage: {result.challenger_damage_dealt:,}\n"
                f"💥 Opponent Damage: {result.opponent_damage_dealt:,}\n"
                f"🎁 Spoils: +{result.winner_xp_gained} XP, +{result.winner_gold_gained} Gold",
                parse_mode=ParseMode.HTML,
            )
