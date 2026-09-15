"""
handlers/guild_war.py — Guild War command handler.

Manages guild-vs-guild wars: challenge, accept, battle resolution, rewards.

Flow:
  /guild war <guild_name>  — Challenge another guild (owner only)
  [Accept War] / [Decline War] — Inline buttons on challenge card
  War auto-resolves: all members fight 1v1, most wins = guild wins
"""

from __future__ import annotations

import asyncio
import logging
import time
from pyrogram import Client
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from pyrogram.errors import BadRequest

from channel_db import ChannelDB
from config import (
    GUILD_MAX_MEMBERS,
    GUILD_WAR_GOLD_REWARD,
    GUILD_WAR_BASE_XP,
    GUILD_WAR_WIN_BONUS_XP,
    GUILD_WAR_WIN_SCORE,
    GUILD_WAR_LOSS_SCORE,
    GUILD_WAR_XP_PENALTY,
)
from models import Guild, Hunter, Inventory
from game.hunter import add_xp
from game.duel import simulate_duel
from game.font_manager import clean_and_normalize_name
from game.guild_war_image import (
    render_war_challenge_card,
    render_war_status_card,
    render_war_result_card,
)

logger = logging.getLogger(__name__)

# ── In-memory war state (single active war at a time) ──────
_active_war: dict | None = None


def _reset_war() -> None:
    global _active_war
    _active_war = None


def _get_war() -> dict | None:
    return _active_war


def _init_war(
    challenger_guild: Guild,
    defender_guild: Guild,
    challengers: list[Hunter],
    defenders: list[Hunter],
) -> dict:
    global _active_war

    # Sort by power descending for fair matching
    challengers.sort(key=lambda h: -h.power)
    defenders.sort(key=lambda h: -h.power)

    # Create matchups: pair by index, min of both guild sizes
    num_matches = min(len(challengers), len(defenders))
    matchups = []
    for i in range(num_matches):
        matchups.append((challengers[i].user_id, defenders[i].user_id, None))

    _active_war = {
        "challenger_guild_id": challenger_guild.guild_id,
        "defender_guild_id": defender_guild.guild_id,
        "challenger_guild_name": challenger_guild.name,
        "defender_guild_name": defender_guild.name,
        "status": "active",
        "challengers": {h.user_id: h for h in challengers},
        "defenders": {h.user_id: h for h in defenders},
        "matchups": matchups,
        "current_match": 0,
        "challenger_wins": 0,
        "defender_wins": 0,
        "started_at": time.time(),
        "message_chat_id": None,
        "message_id": None,
    }
    return _active_war


def _war_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ Accept War", callback_data="war_accept"),
         InlineKeyboardButton("❌ Decline", callback_data="war_decline")],
    ])


async def handle_war(client: Client, message: Message) -> None:
    """Handle /guild war [guild_name]."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db
    args = message.command[2:] if len(message.command) > 2 else []

    # Ensure user is registered
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await message.reply_text("⚠️ You must be a Hunter first. Use /start.")
        return

    # Check for active war
    war = _get_war()
    if war and war["status"] == "active":
        # Show war status
        await _show_war_status(client, message, db, war)
        return
    if war and war["status"] == "pending":
        await message.reply_text("⚠️ A war challenge is already pending. Wait for it to resolve.")
        return

    # /guild war (no args) — show help
    if not args:
        text = (
            "╔══════════════════════════════╗\n"
            "║   ⚔️ GUILD WAR SYSTEM        ║\n"
            "╚══════════════════════════════╝\n\n"
            "Challenge another guild to war!\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "/guild war <guild_name> — Challenge a guild\n\n"
            "📜 HOW IT WORKS:\n"
            "1. Guild owner challenges another guild\n"
            "2. Target guild owner accepts or declines\n"
            "3. All members fight 1v1 (strongest vs strongest)\n"
            "4. Most duel wins = guild wins the war!\n\n"
            "🎁 WINNER: +200💰 per member, +war_score, +XP\n"
            "💀 LOSER: -XP, -war_score\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "「 Only the strongest guilds survive. 」"
        )
        await message.reply_text(text)
        return

    # ── Challenge another guild ──
    # Verify user is a guild owner
    sender_guild = await db.get_user_guild(user.id)
    if not sender_guild:
        await message.reply_text("⚠️ You must be in a guild to start a war. Create one with /guild create.")
        return

    if sender_guild.owner_id != user.id:
        await message.reply_text("⚠️ Only the guild owner can declare war!")
        return

    # Find target guild
    target_name = " ".join(args).strip()
    target_guild = await db.get_guild_by_name(target_name)
    if not target_guild:
        await message.reply_text(f"❌ No guild named **{target_name}** found.", parse_mode="markdown")
        return

    if target_guild.guild_id == sender_guild.guild_id:
        await message.reply_text("⚠️ You can't declare war on your own guild!")
        return

    # Load members
    challenger_members = []
    for uid in sender_guild.members:
        h = await db.get_hunter(uid)
        if h:
            challenger_members.append(h)

    defender_members = []
    for uid in target_guild.members:
        h = await db.get_hunter(uid)
        if h:
            defender_members.append(h)

    if not challenger_members or not defender_members:
        await message.reply_text("❌ Both guilds need members to start a war.")
        return

    challenger_power = sum(h.power for h in challenger_members)
    defender_power = sum(h.power for h in defender_members)

    # Store pending war info
    global _active_war
    _active_war = {
        "challenger_guild_id": sender_guild.guild_id,
        "defender_guild_id": target_guild.guild_id,
        "challenger_guild_name": sender_guild.name,
        "defender_guild_name": target_guild.name,
        "status": "pending",
        "challenger_members": challenger_members,
        "defender_members": defender_members,
        "challenger_power": challenger_power,
        "defender_power": defender_power,
    }

    # Send challenge card
    try:
        photo_buf = await asyncio.to_thread(
            render_war_challenge_card,
            sender_guild, challenger_members,
            target_guild, defender_members,
            challenger_power, defender_power,
        )
        caption = (
            f"⚔️ **{sender_guild.name}** declares war on **{target_guild.name}**!\n\n"
            f"👑 Target owner: Reply required to accept/decline."
        )
        await message.reply_photo(
            photo=photo_buf,
            caption=caption,
            reply_markup=_war_keyboard(),
            parse_mode="markdown",
        )
    except Exception as exc:
        logger.error("Failed to render war challenge card: %s", exc, exc_info=True)
        await message.reply_text(
            f"⚔️ **{sender_guild.name}** declares war on **{target_guild.name}**!\n\n"
            f"👑 Target owner: Use /guild war to accept or decline.",
            reply_markup=_war_keyboard(),
            parse_mode="markdown",
        )

    logger.info(f"War challenge: {sender_guild.name} -> {target_guild.name}")


async def war_callback(client: Client, query: CallbackQuery) -> None:
    """Handle war_accept / war_decline callbacks."""
    if not query or not query.data:
        return

    await query.answer()
    user = query.from_user
    if not user:
        return

    db: ChannelDB = client.db
    war = _get_war()

    if not war or war["status"] != "pending":
        await query.edit_message_text("⚠️ This war challenge has expired or been resolved.")
        return

    # Only target guild owner can accept/decline
    if user.id != war["defender_guild_id"]:
        await query.answer("⚠️ Only the target guild owner can respond!", show_alert=True)
        return

    if query.data == "war_decline":
        _reset_war()
        await query.edit_message_text(
            f"❌ **{war['defender_guild_name']}** has declined the war challenge.\n\n"
            f"Their leader chose diplomacy over battle.",
            parse_mode="markdown",
        )
        return

    if query.data == "war_accept":
        # Accept — start the war
        defender_guild = await db.get_guild(war["defender_guild_id"])
        challenger_guild = await db.get_guild(war["challenger_guild_id"])

        if not defender_guild or not challenger_guild:
            _reset_war()
            await query.edit_message_text("❌ One of the guilds no longer exists. War cancelled.")
            return

        # Initiate the war
        active_war = _init_war(
            challenger_guild, defender_guild,
            war["challenger_members"], war["defender_members"],
        )

        # Send initial status card
        try:
            photo_buf = await asyncio.to_thread(
                render_war_status_card,
                challenger_guild, defender_guild,
                0, 0,
                active_war["matchups"], 0,
                len(active_war["matchups"]),
                active_war["challengers"],
                active_war["defenders"],
            )
            caption = (
                f"⚔️ **WAR BEGINS!**\n\n"
                f"🏰 {war['challenger_guild_name']} vs {war['defender_guild_name']}\n"
                f"👥 {len(active_war['matchups'])} battles will determine the winner!"
            )
            if query.message:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=photo_buf, caption=caption),
                    reply_markup=None,
                    parse_mode="markdown",
                )
        except Exception as exc:
            logger.error("Failed to render war status: %s", exc, exc_info=True)
            await query.edit_message_text(
                f"⚔️ **WAR BEGINS!** {war['challenger_guild_name']} vs {war['defender_guild_name']}\n\n"
                f"Starting {len(active_war['matchups'])} battles...",
                parse_mode="markdown",
            )

        logger.info(f"War started: {war['challenger_guild_name']} vs {war['defender_guild_name']}")

        # Run all battles sequentially
        await _run_war_battles(client, db, active_war)


async def _run_war_battles(client: Client, db: ChannelDB, war: dict) -> None:
    """Run all war battles sequentially."""
    challenger_guild = await db.get_guild(war["challenger_guild_id"])
    defender_guild = await db.get_guild(war["defender_guild_id"])

    c_lookup = war["challengers"]
    d_lookup = war["defenders"]

    for i, (c_uid, d_uid, _) in enumerate(war["matchups"]):
        war["current_match"] = i + 1

        c_hunter = c_lookup.get(c_uid)
        d_hunter = d_lookup.get(d_uid)

        if not c_hunter or not d_hunter:
            continue

        # Load inventories for equipment
        c_inv = await db.get_inventory(c_uid)
        d_inv = await db.get_inventory(d_uid)
        if not c_inv:
            c_inv = Inventory(user_id=c_uid)
        if not d_inv:
            d_inv = Inventory(user_id=d_uid)

        # Simulate duel
        result = simulate_duel(c_hunter, c_inv, d_hunter, d_inv)

        # Record winner
        winner_uid = result.winner.user_id
        war["matchups"][i] = (c_uid, d_uid, winner_uid)

        if winner_uid == c_uid:
            war["challenger_wins"] += 1
        else:
            war["defender_wins"] += 1

        # Save updated hunters (duel_wins/duel_losses already updated by simulate_duel)
        await db.save_hunter(c_uid)
        await db.save_hunter(d_uid)

        # Small delay between matches for dramatic effect
        await asyncio.sleep(1.5)

    # War complete — resolve results
    await _resolve_war(client, db, war, challenger_guild, defender_guild)


async def _resolve_war(
    client: Client,
    db: ChannelDB,
    war: dict,
    challenger_guild: Guild,
    defender_guild: Guild,
) -> None:
    """Apply war results: rewards, penalties, war_score updates."""
    c_wins = war["challenger_wins"]
    d_wins = war["defender_wins"]
    winner_is_challenger = c_wins > d_wins

    if winner_is_challenger:
        winner_guild = challenger_guild
        loser_guild = defender_guild
    else:
        winner_guild = defender_guild
        loser_guild = challenger_guild

    # Update guild war stats
    winner_guild.war_score += GUILD_WAR_WIN_SCORE
    winner_guild.war_wins += 1
    loser_guild.war_score = max(0, loser_guild.war_score - GUILD_WAR_LOSS_SCORE)
    loser_guild.war_losses += 1

    await db.save_guild(winner_guild.guild_id)
    await db.save_guild(loser_guild.guild_id)

    # Apply rewards to all fighters
    c_lookup = war["challengers"]
    d_lookup = war["defenders"]

    all_fighters = list(c_lookup.values()) + list(d_lookup.values())
    for h in all_fighters:
        is_winner = (h.user_id in c_lookup and winner_is_challenger) or \
                    (h.user_id in d_lookup and not winner_is_challenger)

        if is_winner:
            h.gold += GUILD_WAR_GOLD_REWARD
            add_xp(h, GUILD_WAR_BASE_XP + GUILD_WAR_WIN_BONUS_XP)
            h.guild_war_wins += 1
        else:
            # Loser: XP penalty (can't go below 0)
            xp_loss = min(h.xp, GUILD_WAR_XP_PENALTY)
            h.xp = max(0, h.xp - xp_loss)
            h.guild_war_losses += 1

        await db.save_hunter(h.user_id)

    # Send result card
    try:
        photo_buf = await asyncio.to_thread(
            render_war_result_card,
            challenger_guild, defender_guild,
            c_wins, d_wins,
            winner_is_challenger,
            list(c_lookup.values()),
            list(d_lookup.values()),
            GUILD_WAR_GOLD_REWARD,
            GUILD_WAR_BASE_XP + GUILD_WAR_WIN_BONUS_XP,
            GUILD_WAR_XP_PENALTY,
        )

        # Find a message to edit or send new
        chat_id = war.get("message_chat_id")
        msg_id = war.get("message_id")

        if chat_id and msg_id:
            try:
                await client.edit_message_media(
                    chat_id=chat_id,
                    message_id=msg_id,
                    media=InputMediaPhoto(media=photo_buf, caption=f"⚔️ WAR COMPLETE — {winner_guild.name} WINS!"),
                )
            except Exception:
                pass
    except Exception as exc:
        logger.error("Failed to render war result card: %s", exc, exc_info=True)

    # Send result as new message
    result_text = (
        f"⚔️ **WAR COMPLETE!**\n\n"
        f"🏆 **{winner_guild.name}** wins!\n\n"
        f"📊 Final Score: {c_wins} — {d_wins}\n\n"
        f"🎁 Winner bonuses applied: +{GUILD_WAR_GOLD_REWARD}💰, +{GUILD_WAR_BASE_XP + GUILD_WAR_WIN_BONUS_XP} XP per fighter\n"
        f"💀 Loser penalties: -{GUILD_WAR_XP_PENALTY} XP per member\n"
        f"📈 War Score: {winner_guild.name} +{GUILD_WAR_WIN_SCORE} | {loser_guild.name} -{GUILD_WAR_LOSS_SCORE}"
    )

    # Try to send result to the chat where war was started
    if war.get("message_chat_id"):
        try:
            await client.send_message(
                chat_id=war["message_chat_id"],
                text=result_text,
                parse_mode="markdown",
            )
        except Exception:
            pass

    logger.info(f"War complete: {winner_guild.name} wins ({c_wins}-{d_wins})")
    _reset_war()


async def _show_war_status(client: Client, message: Message, db: ChannelDB, war: dict) -> None:
    """Show current war status."""
    c_wins = war["challenger_wins"]
    d_wins = war["defender_wins"]
    current = war["current_match"]
    total = len(war["matchups"])

    c_guild = await db.get_guild(war["challenger_guild_id"])
    d_guild = await db.get_guild(war["defender_guild_id"])

    if not c_guild or not d_guild:
        await message.reply_text("⚠️ War state is invalid.")
        return

    try:
        photo_buf = await asyncio.to_thread(
            render_war_status_card,
            c_guild, d_guild,
            c_wins, d_wins,
            war["matchups"], current, total,
            list(war["challengers"].values()),
            list(war["defenders"].values()),
        )
        caption = f"⚔️ WAR IN PROGRESS — {c_guild.name} [{c_wins}] vs [{d_wins}] {d_guild.name}"
        await message.reply_photo(photo=photo_buf, caption=caption)
    except Exception as exc:
        logger.error("Failed to render war status: %s", exc, exc_info=True)
        await message.reply_text(
            f"⚔️ WAR: {c_guild.name} [{c_wins}] vs [{d_wins}] {d_guild.name}\n"
            f"Battle {current}/{total} in progress..."
        )
