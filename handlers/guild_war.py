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
import json
import logging
import time
from pyrogram import Client, enums
from pyrogram.enums import ParseMode
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from pyrogram.errors import BadRequest, RPCError

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
from game.formatting import format_not_registered, format_not_registered_rich
from game.rich_text import escape_html
from game.rich_message import RichDoc, heading, paragraph, photo_block, quote
from game.rich_send import edit_rich, photo_media, reply_rich, send_rich
from game.captions import (
    build_war_challenge_caption,
    build_war_status_caption,
    build_war_challenge_rich,
    build_war_status_rich,
)
from game.guild_war_image import (
    render_war_challenge_card,
    render_war_status_card,
    render_war_result_card,
)

logger = logging.getLogger(__name__)

# ── In-memory war state (single active war at a time) ──────
_active_war: dict | None = None
_resumed_tasks: set[asyncio.Task] = set()


def _resume_task_done(task: asyncio.Task) -> None:
    _resumed_tasks.discard(task)
    if not task.cancelled() and task.exception() is not None:
        logger.error(f"Resumed guild war task failed: {task.exception()}")

PENDING_WAR_EXPIRY_SECONDS = 1800   # ponytail: defender gets 30 min to answer
ACTIVE_WAR_EXPIRY_SECONDS = 7200    # ponytail: 2 h to fight all duels


def _war_expired(war: dict) -> bool:
    if war.get("status") == "pending":
        return time.time() - war.get("created_at", 0) > PENDING_WAR_EXPIRY_SECONDS
    if war.get("status") == "active":
        return time.time() - war.get("started_at", 0) > ACTIVE_WAR_EXPIRY_SECONDS
    return True


def _serialize_war(war: dict) -> dict:
    """JSON-safe copy of war state — Hunter objects reduced to user ids."""
    drop = ("challengers", "defenders", "challenger_members", "defender_members")
    out = {k: v for k, v in war.items() if k not in drop}
    if "challenger_members" in war:
        out["challenger_member_ids"] = [h.user_id for h in war["challenger_members"]]
        out["defender_member_ids"] = [h.user_id for h in war["defender_members"]]
    if "challengers" in war:
        out["challenger_ids"] = list(war["challengers"].keys())
        out["defender_ids"] = list(war["defenders"].keys())
    if "matchups" in war:
        out["matchups"] = [list(m) for m in war["matchups"]]
    return out


async def _persist_war(db: ChannelDB) -> None:
    """Write war state to its channel message; clear the message when no war is active."""
    if _active_war is None:
        if db._war_msg_id:
            try:
                await db.bot.delete_messages(db.channel_id, db._war_msg_id)
            except Exception:
                pass
            await db.set_war_msg_id(None)
        return

    payload = json.dumps({"type": "guild_war", **_serialize_war(_active_war)}, separators=(",", ":"))
    if db._war_msg_id:
        try:
            await db.bot.edit_message_text(
                chat_id=db.channel_id, message_id=db._war_msg_id, text=payload
            )
            return
        except RPCError as e:
            if "not modified" in str(e).lower():
                return
            logger.warning(f"War state message invalid, re-posting: {e}")
    msg = await db.bot.send_message(chat_id=db.channel_id, text=payload)
    await db.set_war_msg_id(msg.id)


async def restore_war(client: Client) -> None:
    """Load persisted war state after DB init; resume active wars, clear expired ones."""
    global _active_war
    db: ChannelDB = client.db
    if not db._war_msg_id:
        return
    try:
        msg = await db.bot.get_messages(db.channel_id, db._war_msg_id)
        if not msg or not msg.text or '"type":"guild_war"' not in msg.text:
            await db.set_war_msg_id(None)
            return
        data = json.loads(msg.text)
        if _war_expired(data):
            await _persist_war(db)  # _active_war is None → deletes message, clears index slot
            logger.info("Persisted guild war expired before restart; cleared.")
            return

        if data.get("status") == "pending":
            c_ids = data.pop("challenger_member_ids", [])
            d_ids = data.pop("defender_member_ids", [])
            data["challenger_members"] = [h for u in c_ids if (h := await db.get_hunter(u))]
            data["defender_members"] = [h for u in d_ids if (h := await db.get_hunter(u))]
            if not data["challenger_members"] or not data["defender_members"]:
                await _persist_war(db)
                return
            _active_war = data
            logger.info(
                f"Restored pending war: {data['challenger_guild_name']} vs {data['defender_guild_name']}"
            )
            return

        # Active war: rebuild rosters and resume remaining matchups
        c_ids = data.pop("challenger_ids", [])
        d_ids = data.pop("defender_ids", [])
        data["challengers"] = {u: h for u in c_ids if (h := await db.get_hunter(u))}
        data["defenders"] = {u: h for u in d_ids if (h := await db.get_hunter(u))}
        data["matchups"] = [tuple(m) for m in data.get("matchups", [])]
        if not (await db.get_guild(data["challenger_guild_id"])) or not (
            await db.get_guild(data["defender_guild_id"])
        ):
            await _persist_war(db)
            return
        _active_war = data
        logger.info(
            f"Resuming guild war: {data['challenger_guild_name']} vs {data['defender_guild_name']}"
        )
        task = asyncio.create_task(_run_war_battles(client, db, data))
        _resumed_tasks.add(task)
        task.add_done_callback(_resume_task_done)
    except Exception as exc:
        logger.error(f"Failed to restore guild war state: {exc}", exc_info=True)


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
        [InlineKeyboardButton("⚔️ Accept War", callback_data="war_accept", style=enums.ButtonStyle.PRIMARY),
         InlineKeyboardButton("❌ Decline", callback_data="war_decline", style=enums.ButtonStyle.DANGER)],
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
        await reply_rich(
            message, format_not_registered_rich(),
            fallback=lambda: message.reply_text(format_not_registered(), parse_mode=ParseMode.HTML),
        )
        return

    # Check for active war (clear expired state first)
    war = _get_war()
    if war and _war_expired(war):
        logger.info("Expired war state cleared")
        _reset_war()
        war = None
    if war and war["status"] == "active":
        # Show war status
        await _show_war_status(client, message, db, war)
        return
    if war and war["status"] == "pending":
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ SYSTEM NOTICE // WAR PROTOCOL PENDING ]"),
                paragraph("<b>전쟁 프로토콜 // 대기 중인 도전 과제</b>"),
                paragraph("<i>A syndicate war challenge is currently awaiting resolution.</i>"),
            ),
            fallback=lambda: message.reply_text(
                "<b>[ SYSTEM NOTICE // WAR PROTOCOL PENDING ]</b>\n"
                "<b>전쟁 프로토콜 // 대기 중인 도전 과제</b>\n\n"
                "<i>A syndicate war challenge is currently awaiting resolution.</i>",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    # /guild war (no args) — show help
    if not args:
        text = (
            "<b>[ SYSTEM DIRECTIVE // GUILD WARFARE ]</b>\n"
            "<b>길드 전쟁 // 연맹 간 총력전</b>\n\n"
            "<i>Challenge another Hunter Syndicate to official clan warfare!</i>\n\n"
            "<blockquote expandable>"
            "<b>Declaration Directive:</b>\n"
            "• <code>/guild war &lt;guild_name&gt;</code> — Challenge a rival guild\n\n"
            "<b>Combat Structure:</b>\n"
            "1. Guild Sovereign issues the war declaration\n"
            "2. Opposing Sovereign accepts or declines the challenge\n"
            "3. Roster members clash in 1v1 ladder duels\n"
            "4. Syndicate with the most victories claims the spoils!\n\n"
            f"🎁 <b>Spoils:</b> <code>+{GUILD_WAR_GOLD_REWARD:,} Gold</code>/fighter, <code>+{GUILD_WAR_WIN_SCORE} War Score</code>, bonus EXP\n"
            f"💀 <b>Defeat:</b> <code>-{GUILD_WAR_LOSS_SCORE} War Score</code>, <code>-{GUILD_WAR_XP_PENALTY} EXP</code>\n"
            "</blockquote>"
        )
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ SYSTEM DIRECTIVE // GUILD WARFARE ]"),
                paragraph("<b>길드 전쟁 // 연맹 간 총력전</b>"),
                paragraph("<i>Challenge another Hunter Syndicate to official clan warfare!</i>"),
                quote(
                    "<b>Declaration Directive:</b>\n"
                    "• <code>/guild war &lt;guild_name&gt;</code> — Challenge a rival guild\n\n"
                    "<b>Combat Structure:</b>\n"
                    "1. Guild Sovereign issues the war declaration\n"
                    "2. Opposing Sovereign accepts or declines the challenge\n"
                    "3. Roster members clash in 1v1 ladder duels\n"
                    "4. Syndicate with the most victories claims the spoils!\n\n"
                    f"🎁 <b>Spoils:</b> <code>+{GUILD_WAR_GOLD_REWARD:,} Gold</code>/fighter, <code>+{GUILD_WAR_WIN_SCORE} War Score</code>, bonus EXP\n"
                    f"💀 <b>Defeat:</b> <code>-{GUILD_WAR_LOSS_SCORE} War Score</code>, <code>-{GUILD_WAR_XP_PENALTY} EXP</code>",
                    expandable=True,
                ),
            ),
            fallback=lambda: message.reply_text(text, parse_mode=ParseMode.HTML),
        )
        return

    # ── Challenge another guild ──
    # Verify user is a guild owner
    sender_guild = await db.get_user_guild(user.id)
    if not sender_guild:
        await reply_rich(
            message,
            RichDoc(paragraph("⚠️ <b>Enrollment Required:</b> You must belong to a guild to declare war. Establish one via <code>/guild create</code>.")),
            fallback=lambda: message.reply_text(
                "⚠️ <b>Enrollment Required:</b> You must belong to a guild to declare war. Establish one via <code>/guild create</code>.",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    if sender_guild.owner_id != user.id:
        await reply_rich(
            message,
            RichDoc(paragraph("⚠️ <b>Authority Denied:</b> Only the Guild Sovereign can issue a formal war declaration!")),
            fallback=lambda: message.reply_text(
                "⚠️ <b>Authority Denied:</b> Only the Guild Sovereign can issue a formal war declaration!",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    # Find target guild
    target_name = " ".join(args).strip()
    target_guild = await db.get_guild_by_name(target_name)
    if not target_guild:
        t_name = escape_html(target_name)
        await reply_rich(
            message,
            RichDoc(paragraph(f"❌ <b>Target Syndicate Missing:</b> No guild named <b>{t_name}</b> exists in System records.")),
            fallback=lambda: message.reply_text(
                f"❌ <b>Target Syndicate Missing:</b> No guild named <b>{t_name}</b> exists in System records.",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    if target_guild.guild_id == sender_guild.guild_id:
        await reply_rich(
            message,
            RichDoc(paragraph("⚠️ <b>Internal Conflict Forbidden:</b> You cannot declare war upon your own guild!")),
            fallback=lambda: message.reply_text(
                "⚠️ <b>Internal Conflict Forbidden:</b> You cannot declare war upon your own guild!",
                parse_mode=ParseMode.HTML,
            ),
        )
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
        await reply_rich(
            message,
            RichDoc(paragraph("❌ Both syndicates require active members to initiate a guild war.")),
            fallback=lambda: message.reply_text(
                "❌ Both syndicates require active members to initiate a guild war.",
                parse_mode=ParseMode.HTML,
            ),
        )
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
        "created_at": time.time(),
    }

    caption = build_war_challenge_caption(
        sender_guild.name,
        target_guild.name,
        challenger_power,
        defender_power,
    )

    # Send challenge card
    sent = None
    try:
        photo_buf = await asyncio.to_thread(
            render_war_challenge_card,
            sender_guild, challenger_members,
            target_guild, defender_members,
            challenger_power, defender_power,
        )
        sent = await reply_rich(
            message,
            build_war_challenge_rich(
                sender_guild.name, target_guild.name,
                challenger_power, defender_power,
                photo_first=False,
            ),
            reply_markup=_war_keyboard(),
            media=[photo_media("war", photo_buf)],
            fallback=lambda: message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=_war_keyboard(),
                parse_mode=ParseMode.HTML,
                show_caption_above_media=True,
            ),
        )
    except Exception as exc:
        logger.error("Failed to render war challenge card: %s", exc, exc_info=True)
        sent = await reply_rich(
            message,
            build_war_challenge_rich(sender_guild.name, target_guild.name, challenger_power, defender_power),
            reply_markup=_war_keyboard(),
            fallback=lambda: message.reply_text(
                caption,
                reply_markup=_war_keyboard(),
                parse_mode=ParseMode.HTML,
            ),
        )
    if sent and _active_war:
        _active_war["message_chat_id"] = sent.chat.id
        _active_war["message_id"] = sent.id
    await _persist_war(db)

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
    if war and _war_expired(war):
        _reset_war()
        war = None

    if not war or war["status"] != "pending":
        await edit_rich(
            client, query.message.chat.id, query.message.id,
            RichDoc(paragraph("⚠️ This war challenge has expired or been resolved.")),
            fallback=lambda: query.edit_message_text(
                "⚠️ This war challenge has expired or been resolved.",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    # Only target guild owner can accept/decline
    if user.id != war["defender_guild_id"]:
        await query.answer("⚠️ Only the target guild owner can respond!", show_alert=True)
        return

    if query.data == "war_decline":
        _reset_war()
        await _persist_war(db)
        def_name = escape_html(war['defender_guild_name'])
        await edit_rich(
            client, query.message.chat.id, query.message.id,
            RichDoc(
                heading(1, "[ SYSTEM NOTIFICATION // WAR CHALLENGE DECLINED ]"),
                paragraph("<b>전쟁 거부 // 평화 협정 체결</b>"),
                paragraph(f"❌ <b>{def_name}</b> declined the war challenge."),
                quote("<i>Their leader chose diplomacy over bloodshed.</i>", expandable=True),
            ),
            fallback=lambda: query.edit_message_text(
                "<b>[ SYSTEM NOTIFICATION // WAR CHALLENGE DECLINED ]</b>\n"
                "<b>전쟁 거부 // 평화 협정 체결</b>\n\n"
                f"❌ <b>{def_name}</b> declined the war challenge.\n\n"
                "<blockquote expandable><i>Their leader chose diplomacy over bloodshed.</i></blockquote>",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    if query.data == "war_accept":
        # Accept — start the war
        defender_guild = await db.get_guild(war["defender_guild_id"])
        challenger_guild = await db.get_guild(war["challenger_guild_id"])

        if not defender_guild or not challenger_guild:
            _reset_war()
            await edit_rich(
                client, query.message.chat.id, query.message.id,
                RichDoc(paragraph("❌ One of the guilds no longer exists. War cancelled.")),
                fallback=lambda: query.edit_message_text(
                    "❌ One of the guilds no longer exists. War cancelled.",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        # Initiate the war
        active_war = _init_war(
            challenger_guild, defender_guild,
            war["challenger_members"], war["defender_members"],
        )
        active_war["message_chat_id"] = war.get("message_chat_id")
        active_war["message_id"] = war.get("message_id")
        await _persist_war(db)

        # Send initial status card
        ch_name = escape_html(war['challenger_guild_name'])
        def_name = escape_html(war['defender_guild_name'])
        caption = (
            "<b>[ SYSTEM NOTIFICATION // GUILD WAR INITIATED ]</b>\n"
            "<b>전쟁 개시 // 1:1 결투 개전</b>\n\n"
            f"🏰 <b>{ch_name}</b> vs <b>{def_name}</b>\n\n"
            "<blockquote expandable>"
            f"• Scheduled Clashes: <code>{len(active_war['matchups'])}</code> 1v1 Duels\n"
            "• All duel outcomes will determine the victorious syndicate.\n"
            "</blockquote>"
        )
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
            if query.message and query.message.photo:
                await edit_rich(
                    client, query.message.chat.id, query.message.id,
                    build_war_status_rich(
                        war['challenger_guild_name'], war['defender_guild_name'],
                        0, 0, 0, len(active_war["matchups"]),
                        photo_first=False,
                    ),
                    media=[photo_media("war", photo_buf)],
                    fallback=lambda: query.edit_message_media(
                        media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=ParseMode.HTML),
                        reply_markup=None,
                    ),
                )
        except Exception as exc:
            logger.error("Failed to render war status: %s", exc, exc_info=True)
            await edit_rich(
                client, query.message.chat.id, query.message.id,
                RichDoc(
                    heading(1, "[ SYSTEM NOTIFICATION // GUILD WAR INITIATED ]"),
                    paragraph("<b>전쟁 개시 // 1:1 결투 개전</b>"),
                    paragraph(f"🏰 <b>{ch_name}</b> vs <b>{def_name}</b>"),
                    quote(
                        f"• Scheduled Clashes: <code>{len(active_war['matchups'])}</code> 1v1 Duels\n"
                        "• All duel outcomes will determine the victorious syndicate.",
                        expandable=True,
                    ),
                ),
                fallback=lambda: query.edit_message_text(
                    caption,
                    parse_mode=ParseMode.HTML,
                ),
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

    for i, (c_uid, d_uid, winner) in enumerate(war["matchups"]):
        if winner is not None:
            continue  # resolved before a restart — never re-fight (no double rewards)
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
        await _persist_war(db)

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

    w_name = escape_html(winner_guild.name)
    l_name = escape_html(loser_guild.name)
    result_text = (
        f"<b>[ GUILD WAR VICTORY // {w_name.upper()} ]</b>\n"
        "<b>전쟁 종결 // 최종 승리 길드</b>\n\n"
        f"👑 <b>Victor Syndicate:</b> <b>{w_name}</b>\n"
        f"💀 <b>Defeated Syndicate:</b> <b>{l_name}</b>\n\n"
        "<blockquote expandable>"
        f"• Final Standing: <code>{c_wins} — {d_wins}</code>\n"
        f"• Winner Spoils: 💰 <code>+{GUILD_WAR_GOLD_REWARD:,} Gold</code>, ✨ <code>+{GUILD_WAR_BASE_XP + GUILD_WAR_WIN_BONUS_XP:,} XP</code>/fighter\n"
        f"• Defeat Penalty: 💀 <code>-{GUILD_WAR_XP_PENALTY:,} XP</code>/member\n"
        f"• War Score: <b>{w_name}</b> <code>+{GUILD_WAR_WIN_SCORE}</code> ┊ <b>{l_name}</b> <code>-{GUILD_WAR_LOSS_SCORE}</code>\n"
        "</blockquote>"
    )

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

        chat_id = war.get("message_chat_id")
        msg_id = war.get("message_id")

        if chat_id and msg_id:
            try:
                await edit_rich(
                    client, chat_id, msg_id,
                    RichDoc(photo_block("war"), paragraph(f"⚔️ <b>WAR COMPLETE — {w_name} WINS!</b>")),
                    media=[photo_media("war", photo_buf)],
                    fallback=lambda: client.edit_message_media(
                        chat_id=chat_id,
                        message_id=msg_id,
                        media=InputMediaPhoto(media=photo_buf, caption=f"⚔️ <b>WAR COMPLETE — {w_name} WINS!</b>", parse_mode=ParseMode.HTML),
                    ),
                )
            except Exception:
                pass
    except Exception as exc:
        logger.error("Failed to render war result card: %s", exc, exc_info=True)

    # Try to send result to the chat where war was started
    if war.get("message_chat_id"):
        try:
            await send_rich(
                client, war["message_chat_id"],
                RichDoc(
                    heading(1, f"[ GUILD WAR VICTORY // {w_name.upper()} ]"),
                    paragraph("<b>전쟁 종결 // 최종 승리 길드</b>"),
                    paragraph(
                        f"👑 <b>Victor Syndicate:</b> <b>{w_name}</b>\n"
                        f"💀 <b>Defeated Syndicate:</b> <b>{l_name}</b>"
                    ),
                    quote(
                        f"• Final Standing: <code>{c_wins} — {d_wins}</code>\n"
                        f"• Winner Spoils: 💰 <code>+{GUILD_WAR_GOLD_REWARD:,} Gold</code>, ✨ <code>+{GUILD_WAR_BASE_XP + GUILD_WAR_WIN_BONUS_XP:,} XP</code>/fighter\n"
                        f"• Defeat Penalty: 💀 <code>-{GUILD_WAR_XP_PENALTY:,} XP</code>/member\n"
                        f"• War Score: <b>{w_name}</b> <code>+{GUILD_WAR_WIN_SCORE}</code> ┊ <b>{l_name}</b> <code>-{GUILD_WAR_LOSS_SCORE}</code>",
                        expandable=True,
                    ),
                ),
                fallback=lambda: client.send_message(
                    chat_id=war["message_chat_id"],
                    text=result_text,
                    parse_mode=ParseMode.HTML,
                ),
            )
        except Exception:
            pass

    logger.info(f"War complete: {winner_guild.name} wins ({c_wins}-{d_wins})")
    _reset_war()
    await _persist_war(db)


async def _show_war_status(client: Client, message: Message, db: ChannelDB, war: dict) -> None:
    """Show current war status."""
    c_wins = war["challenger_wins"]
    d_wins = war["defender_wins"]
    current = war["current_match"]
    total = len(war["matchups"])

    c_guild = await db.get_guild(war["challenger_guild_id"])
    d_guild = await db.get_guild(war["defender_guild_id"])

    if not c_guild or not d_guild:
        await reply_rich(
            message,
            RichDoc(paragraph("⚠️ War state is invalid.")),
            fallback=lambda: message.reply_text("⚠️ War state is invalid.", parse_mode=ParseMode.HTML),
        )
        return

    caption = build_war_status_caption(
        c_guild.name,
        d_guild.name,
        c_wins,
        d_wins,
        current,
        total,
    )
    try:
        photo_buf = await asyncio.to_thread(
            render_war_status_card,
            c_guild, d_guild,
            c_wins, d_wins,
            war["matchups"], current, total,
            list(war["challengers"].values()),
            list(war["defenders"].values()),
        )
        await reply_rich(
            message,
            build_war_status_rich(
                c_guild.name, d_guild.name,
                c_wins, d_wins, current, total,
                photo_first=True,
            ),
            media=[photo_media("war", photo_buf)],
            fallback=lambda: message.reply_photo(photo=photo_buf, caption=caption, parse_mode=ParseMode.HTML),
        )
    except Exception as exc:
        logger.error("Failed to render war status: %s", exc, exc_info=True)
        await reply_rich(
            message,
            build_war_status_rich(c_guild.name, d_guild.name, c_wins, d_wins, current, total),
            fallback=lambda: message.reply_text(
                caption,
                parse_mode=ParseMode.HTML,
            ),
        )
