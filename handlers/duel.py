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
from game.rich_text import escape_html
from game.captions import build_duel_challenge_caption, build_duel_result_caption
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
            "<b>╭━━━「 ⚔️ HUNTER PVP ARENA 」━━━╮</b>\n\n"
            "⚠️ <b>Arena Protocol: Group Directives Only</b>\n\n"
            "<blockquote>"
            "• Duels can only be initiated inside <b>Group Chats</b>!\n"
            "• To challenge a rival, reply to any of their messages with <code>/duel</code>."
            "</blockquote>\n\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    # 2. Enforce Reply-To-Message Requirement
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply_text(
            "<b>╭━━━「 ⚔️ TARGET SPECIFICATION REQUIRED 」━━━╮</b>\n\n"
            "⚠️ <b>Direct reply required to issue a challenge!</b>\n\n"
            "<blockquote>"
            "• <b>Reply</b> to a rival Hunter's message in this group with <code>/duel</code>."
            "</blockquote>\n\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    opponent_user = message.reply_to_message.from_user

    # 3. Disallow Bot Challenges
    if opponent_user.is_bot:
        await message.reply_text(
            "<b>╭━━━「 🤖 INVALID COMBAT TARGET 」━━━╮</b>\n\n"
            "❌ <b>Target is a System Automaton!</b>\n\n"
            "<blockquote>"
            "• You cannot challenge non-awakened automata / bots to a duel."
            "</blockquote>\n\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    # 4. Disallow Self-Duels
    if opponent_user.id == user.id:
        await message.reply_text(
            "<b>╭━━━「 ⚔️ SELF-COMBAT PROHIBITED 」━━━╮</b>\n\n"
            "❌ <b>Internal mana clash disallowed!</b>\n\n"
            "<blockquote>"
            "• Reply to a worthy rival Hunter's message to issue an Arena challenge."
            "</blockquote>\n\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    db: ChannelDB = client.db

    # 5. Check Registration of Challenger
    challenger_hunter = await db.get_hunter(user.id)
    if not challenger_hunter:
        await message.reply_text(format_not_registered(), parse_mode=ParseMode.HTML)
        return

    # 6. Check Registration of Opponent
    opponent_hunter = await db.get_hunter(opponent_user.id)
    if not opponent_hunter:
        opp_name = escape_html(opponent_user.first_name or "Target")
        await message.reply_text(
            "<b>╭━━━「 ⚠️ OPPONENT NOT AWAKENED 」━━━╮</b>\n\n"
            f"❌ <b>{opp_name} has not awakened!</b>\n\n"
            "<blockquote>"
            "• They have not registered with the System yet.\n"
            "• They must awaken via <code>/start</code> first before entering PvP."
            "</blockquote>\n\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    # 7. Send Duel Challenge Invitation with Interactive Keyboard
    text = build_duel_challenge_caption(challenger_hunter, opponent_hunter)

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

    c_name = escape_html(challenger.display_full_name if challenger else f"Hunter #{challenger_id}")
    o_name = escape_html(opponent.display_full_name if opponent else f"Hunter #{opponent_id}")

    # 2. Handle Decline
    if action == "decline":
        await query.answer("Duel challenge declined.")
        await query.edit_message_text(
            "<b>╭━━━「 🏳️ DUEL DECLINED 」━━━╮</b>\n\n"
            f"<b>{o_name}</b> declined the duel challenge from <b>{c_name}</b>.\n\n"
            "<blockquote><i>Combat avoided. Peace maintained in the district.</i></blockquote>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    # 3. Handle Accept
    if action == "accept":
        await query.answer("⚔️ Duel accepted! Entering Arena...")
        await query.edit_message_text(
            "<b>╭━━━「 ⚔️ ARENA GATES OPENING 」━━━╮</b>\n\n"
            f"<b>{c_name}</b> and <b>{o_name}</b> have stepped into the Arena!\n\n"
            "<blockquote><i>The System is computing combat matrix resolution...</i></blockquote>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
            parse_mode=ParseMode.HTML,
        )

        if not challenger or not opponent:
            await query.message.reply_text(
                "⚠️ Could not load hunter profiles. Duel aborted.",
                parse_mode=ParseMode.HTML,
            )
            return

        c_inv = await db.get_inventory(challenger_id)
        o_inv = await db.get_inventory(opponent_id)

        # 4. Retrieve Profile Photos (if available) via MTProto
        c_pfp_bytes = await fetch_user_pfp_bytes(client, challenger_id)
        o_pfp_bytes = await fetch_user_pfp_bytes(client, opponent_id)

        # 5. Simulate Combat
        result = simulate_duel(challenger, c_inv, opponent, o_inv)

        # Track daily quest duel completion
        challenger.daily_quest_duel += 1
        opponent.daily_quest_duel += 1

        # 6. Persist Updated Hunter Data
        await db.save_hunter(challenger_id)
        await db.save_hunter(opponent_id)

        # 7. Render Duel Resolution Card & Dispatch
        caption = build_duel_result_caption(result)
        try:
            photo_buf = await asyncio.to_thread(
                render_duel_card,
                result,
                challenger_pfp=c_pfp_bytes,
                opponent_pfp=o_pfp_bytes,
                challenger_inv=c_inv,
                opponent_inv=o_inv,
            )

            await query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            logger.error("Failed to render duel card: %s", exc, exc_info=True)
            await query.message.reply_text(
                caption,
                parse_mode=ParseMode.HTML,
            )

