"""
handlers/guild.py — /guild, /gift, and /guild top command handlers.

Manages Hunter Guilds — social grouping with up to 15 members.
Commands:
  /guild create <name>  — Create a guild (1 per user, costs 500 gold)
  /guild join <name>    — Join an existing guild
  /guild leave          — Leave your current guild
  /guild info [name]    — View guild card (yours or by name)
  /guild members        — List members of your guild
  /guild top            — Top 10 guilds leaderboard with category tabs
  /guild kick @user     — Owner kicks a member
  /guild disband        — Owner deletes the guild
  /guild edit <desc>    — Owner edits guild description
  /gift item <id> @user — Gift an item to a guildmate
  /gift gold <amount> @user — Gift gold to a guildmate
"""

from __future__ import annotations

import asyncio
import logging
import time
from pyrogram import Client, enums
from pyrogram.enums import ParseMode
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from pyrogram.errors import BadRequest

from channel_db import ChannelDB
from config import GUILD_MAX_MEMBERS
from models import Guild
from game.formatting import format_not_registered, format_not_registered_rich
from game.font_manager import clean_and_normalize_name
from game.guild_image import render_guild_image
from game.guild_leaderboard_image import render_guild_leaderboard_image
from game.rich_text import escape_html
from game.rich_message import RichDoc, heading, paragraph, quote
from game.rich_send import edit_rich, photo_media, reply_rich
from game.captions import build_guild_caption, build_guild_rich, build_guild_leaderboard_rich
from handlers import guild_war

logger = logging.getLogger(__name__)


def _format_guild_info(guild: Guild, db_guild_stats: dict | None = None) -> str:
    """Format guild info as text."""
    g_name = escape_html(guild.name)
    desc = escape_html(guild.description or "No description recorded.")
    return (
        f"<b>[ GUILD DIRECTORY // {g_name.upper()} ]</b>\n"
        "<b>길드 정보 // 길드 상세</b>\n\n"
        f"🏰 <b>Syndicate:</b> <b>{g_name}</b> (ID: <code>#{guild.guild_id}</code>)\n"
        f"👥 <b>Roster:</b> <code>{len(guild.members)}/{GUILD_MAX_MEMBERS}</code>\n"
        f"👑 <b>Sovereign:</b> <code>#{guild.owner_id}</code>\n\n"
        "<blockquote expandable>"
        f"📝 <b>Guild Creed:</b> <i>{desc}</i>\n"
        "• Active Syndicate Perk: 🎁 <b>+10% EXP on all Hunts</b>\n"
        "</blockquote>"
    )


def _format_guild_info_rich(guild: Guild, db_guild_stats: dict | None = None) -> RichDoc:
    """Rich twin of _format_guild_info (same copy, block structure)."""
    g_name = escape_html(guild.name)
    desc = escape_html(guild.description or "No description recorded.")
    return RichDoc(
        heading(1, f"[ GUILD DIRECTORY // {g_name.upper()} ]"),
        paragraph("<b>길드 정보 // 길드 상세</b>"),
        paragraph(
            f"🏰 <b>Syndicate:</b> <b>{g_name}</b> (ID: <code>#{escape_html(str(guild.guild_id))}</code>)\n"
            f"👥 <b>Roster:</b> <code>{len(guild.members)}/{GUILD_MAX_MEMBERS}</code>\n"
            f"👑 <b>Sovereign:</b> <code>#{guild.owner_id}</code>"
        ),
        quote(
            f"📝 <b>Guild Creed:</b> <i>{desc}</i>\n"
            "• Active Syndicate Perk: 🎁 <b>+10% EXP on all Hunts</b>",
            expandable=True,
        ),
    )


def _guild_view_keyboard(
    user_id: int,
    target_guild: Guild,
    viewer_guild: Optional[Guild],
    all_guilds: list[Guild] | None = None,
) -> InlineKeyboardMarkup:
    """Construct dynamic Hallmark action buttons for the visual Guild Card."""
    buttons = []
    gid = target_guild.guild_id

    # Row 1: Contextual Membership Actions
    if viewer_guild and viewer_guild.guild_id == gid:
        if viewer_guild.owner_id == user_id:
            buttons.append([
                InlineKeyboardButton("👑 Guild Sovereign", callback_data="gnoop"),
                InlineKeyboardButton("👥 Members", callback_data=f"gmembers_{gid}"),
            ])
            buttons.append([
                InlineKeyboardButton("⚔️ Challenge War", callback_data=f"gwar_{gid}", style=enums.ButtonStyle.PRIMARY),
                InlineKeyboardButton("🏆 Guild Leaderboard", callback_data="glb_power", style=enums.ButtonStyle.PRIMARY),
            ])
        else:
            buttons.append([
                InlineKeyboardButton("🚪 Leave Guild", callback_data=f"gleave_{gid}", style=enums.ButtonStyle.DANGER),
                InlineKeyboardButton("👥 Members", callback_data=f"gmembers_{gid}"),
            ])
            buttons.append([
                InlineKeyboardButton("🏆 Guild Leaderboard", callback_data="glb_power", style=enums.ButtonStyle.PRIMARY),
            ])
    elif viewer_guild:
        # Viewer belongs to a different guild
        buttons.append([
            InlineKeyboardButton(f"⚠️ In Guild: {viewer_guild.name}", callback_data="gnoop_switch"),
            InlineKeyboardButton("🏆 Guild Leaderboard", callback_data="glb_power", style=enums.ButtonStyle.PRIMARY),
        ])
    else:
        # Viewer is guildless -> PROMINENT JOIN BUTTON!
        buttons.append([
            InlineKeyboardButton(f"⚔️ Join {target_guild.name}", callback_data=f"gjoin_{gid}", style=enums.ButtonStyle.PRIMARY),
        ])
        buttons.append([
            InlineKeyboardButton("🏆 Guild Leaderboard", callback_data="glb_power", style=enums.ButtonStyle.PRIMARY),
        ])

    # Row 2 (Optional): Navigation when browsing directory
    if all_guilds and len(all_guilds) > 1:
        idx = 0
        for i, g in enumerate(all_guilds):
            if g.guild_id == gid:
                idx = i
                break
        prev_gid = all_guilds[(idx - 1) % len(all_guilds)].guild_id
        next_gid = all_guilds[(idx + 1) % len(all_guilds)].guild_id
        buttons.append([
            InlineKeyboardButton("◀️ Previous", callback_data=f"gview_{prev_gid}"),
            InlineKeyboardButton(f"🏰 {idx + 1}/{len(all_guilds)}", callback_data="gnoop"),
            InlineKeyboardButton("Next ▶️", callback_data=f"gview_{next_gid}"),
        ])

    return InlineKeyboardMarkup(buttons)


async def handle_view(client: Client, message: Message, target_query: str = "") -> None:
    """Handle /guild view and /guild info commands with Hallmark visual rendering."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db
    viewer_guild = await db.get_user_guild(user.id)
    all_guilds = await db.get_all_guilds()

    guild = None
    if target_query:
        guild = await db.get_guild_by_name(target_query)
        if not guild:
            q_esc = escape_html(target_query)
            await reply_rich(
                message,
                RichDoc(paragraph(f"❌ No Hunter Guild matching <b>{q_esc}</b> was found in the System Registry.")),
                fallback=lambda: message.reply_text(
                    f"❌ No Hunter Guild matching <b>{q_esc}</b> was found in the System Registry.",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return
    elif viewer_guild:
        guild = viewer_guild
    elif all_guilds:
        # Viewer has no guild and specified no query: show first / top guild
        guild = all_guilds[0]
    else:
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ SYSTEM DIRECTIVE // GUILD REGISTRY ]"),
                paragraph("<b>시스템 안내 // 길드 목록 없음</b>"),
                paragraph("<i>No Hunter Guilds have been established yet in the System!</i>"),
                quote(
                    "• Be the pioneer and establish the first Guild:\n"
                    "👉 <code>/guild create &lt;name&gt;</code> (Cost: <code>500 Gold</code>)",
                    expandable=True,
                ),
            ),
            fallback=lambda: message.reply_text(
                "<b>[ SYSTEM DIRECTIVE // GUILD REGISTRY ]</b>\n"
                "<b>시스템 안내 // 길드 목록 없음</b>\n\n"
                "<i>No Hunter Guilds have been established yet in the System!</i>\n\n"
                "<blockquote expandable>"
                "• Be the pioneer and establish the first Guild:\n"
                "👉 <code>/guild create &lt;name&gt;</code> (Cost: <code>500 Gold</code>)\n"
                "</blockquote>",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    # Load member hunters
    member_hunters = []
    for uid in guild.members:
        h = await db.get_hunter(uid)
        if h:
            member_hunters.append(h)

    total_power = sum(h.power for h in member_hunters)
    keyboard = _guild_view_keyboard(user.id, guild, viewer_guild, all_guilds)
    caption = build_guild_caption(guild, len(member_hunters), total_power, GUILD_MAX_MEMBERS)

    try:
        photo_buf = await asyncio.to_thread(
            render_guild_image, guild, member_hunters, total_power
        )
        await reply_rich(
            message,
            build_guild_rich(guild, len(member_hunters), total_power, GUILD_MAX_MEMBERS, photo_first=False),
            reply_markup=keyboard,
            media=[photo_media("guild", photo_buf)],
            fallback=lambda: message.reply_photo(photo=photo_buf, caption=caption, reply_markup=keyboard, parse_mode=ParseMode.HTML, show_caption_above_media=True),
        )
    except Exception as exc:
        logger.error("Failed to render hallmark guild image: %s", exc, exc_info=True)
        # Fallback to text
        await reply_rich(
            message,
            _format_guild_info_rich(guild),
            reply_markup=keyboard,
            fallback=lambda: message.reply_text(
                _format_guild_info(guild),
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            ),
        )


async def handle(client: Client, message: Message) -> None:
    """Handle the /guild command."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db
    args = message.command[1:] if len(message.command) > 1 else []
    sub = args[0].lower() if args else ""

    hunter = await db.get_hunter(user.id)
    if not hunter:
        await reply_rich(
            message, format_not_registered_rich(),
            fallback=lambda: message.reply_text(format_not_registered()),
        )
        return

    # ── /guild (no args) — show help ──────────────────────
    if not sub:
        text = (
            "<b>[ SYSTEM DIRECTIVE // GUILD DIRECTORY ]</b>\n"
            "<b>시스템 안내 // 헌터 길드 본부</b>\n\n"
            "<blockquote expandable>"
            "<b>⚔️ Syndicate Directives:</b>\n"
            "• <code>/guild view [name]</code> — View guild card & join\n"
            "• <code>/guild create &lt;name&gt;</code> — Establish guild (<code>500 Gold</code>)\n"
            "• <code>/guild join &lt;name&gt;</code> — Pledge allegiance to a guild\n"
            "• <code>/guild leave</code> — Depart current guild\n"
            "• <code>/guild members</code> — Inspect guild roster\n"
            "• <code>/guild top</code> — Top 10 guilds leaderboard\n"
            "• <code>/guild war &lt;name&gt;</code> — Challenge rival guild to war\n"
            "• <code>/guild kick</code> — Expel member (reply in group)\n"
            "• <code>/guild disband</code> — Dissolve guild (owner only)\n"
            "• <code>/guild edit &lt;desc&gt;</code> — Update syndicate creed\n"
            "</blockquote>\n\n"
            "<blockquote expandable>"
            "<b>🎁 Gifting Protocols:</b>\n"
            "• <code>/gift gold &lt;amount&gt; @user</code> — Gift gold to guildmate\n"
            "• <code>/gift item &lt;id&gt; @user</code> — Gift equipment to guildmate\n"
            "</blockquote>\n\n"
            "<i>Syndicate members receive 🎁 <b>+10% EXP</b> on all dungeon hunts!</i>"
        )
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ SYSTEM DIRECTIVE // GUILD DIRECTORY ]"),
                paragraph("<b>시스템 안내 // 헌터 길드 본부</b>"),
                quote(
                    "<b>⚔️ Syndicate Directives:</b>\n"
                    "• <code>/guild view [name]</code> — View guild card & join\n"
                    "• <code>/guild create &lt;name&gt;</code> — Establish guild (<code>500 Gold</code>)\n"
                    "• <code>/guild join &lt;name&gt;</code> — Pledge allegiance to a guild\n"
                    "• <code>/guild leave</code> — Depart current guild\n"
                    "• <code>/guild members</code> — Inspect guild roster\n"
                    "• <code>/guild top</code> — Top 10 guilds leaderboard\n"
                    "• <code>/guild war &lt;name&gt;</code> — Challenge rival guild to war\n"
                    "• <code>/guild kick</code> — Expel member (reply in group)\n"
                    "• <code>/guild disband</code> — Dissolve guild (owner only)\n"
                    "• <code>/guild edit &lt;desc&gt;</code> — Update syndicate creed",
                    expandable=True,
                ),
                quote(
                    "<b>🎁 Gifting Protocols:</b>\n"
                    "• <code>/gift gold &lt;amount&gt; @user</code> — Gift gold to guildmate\n"
                    "• <code>/gift item &lt;id&gt; @user</code> — Gift equipment to guildmate",
                    expandable=True,
                ),
                paragraph("<i>Syndicate members receive 🎁 <b>+10% EXP</b> on all dungeon hunts!</i>"),
            ),
            fallback=lambda: message.reply_text(text, parse_mode=ParseMode.HTML),
        )
        return

    # ── /guild create <name> ──────────────────────────────
    if sub == "create":
        if len(args) < 2:
            await reply_rich(
                message,
                RichDoc(
                    heading(1, "[ SYSTEM NOTICE // GUILD ESTABLISHMENT ]"),
                    paragraph("<b>시스템 안내 // 길드 창설 지침</b>"),
                    paragraph("⚠️ <b>Syntax:</b> <code>/guild create &lt;name&gt;</code>\n<i>Example:</i> <code>/guild create Shadow Legion</code>"),
                ),
                fallback=lambda: message.reply_text(
                    "<b>[ SYSTEM NOTICE // GUILD ESTABLISHMENT ]</b>\n"
                    "<b>시스템 안내 // 길드 창설 지침</b>\n\n"
                    "⚠️ <b>Syntax:</b> <code>/guild create &lt;name&gt;</code>\n"
                    "<i>Example:</i> <code>/guild create Shadow Legion</code>",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        guild_name = " ".join(args[1:]).strip()
        if len(guild_name.split()) < 1 or len(guild_name.split()) > 4:
            await reply_rich(
                message,
                RichDoc(paragraph("❌ <b>Invalid Name:</b> Guild name must be 1 to 4 words.")),
                fallback=lambda: message.reply_text(
                    "❌ <b>Invalid Name:</b> Guild name must be 1 to 4 words.",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        if hunter.guild_id:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ <b>Already Pledged:</b> You already belong to a guild! Depart first via <code>/guild leave</code>.")),
                fallback=lambda: message.reply_text(
                    "⚠️ <b>Already Pledged:</b> You already belong to a guild! Depart first via <code>/guild leave</code>.",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        if await db.guild_name_exists(guild_name):
            await reply_rich(
                message,
                RichDoc(paragraph(f"❌ <b>Name Conflict:</b> A guild named <b>{escape_html(guild_name)}</b> already exists!")),
                fallback=lambda: message.reply_text(
                    f"❌ <b>Name Conflict:</b> A guild named <b>{escape_html(guild_name)}</b> already exists!",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        # Check gold
        if hunter.gold < 500:
            await reply_rich(
                message,
                RichDoc(paragraph(f"❌ <b>Insufficient Treasury:</b> Creating a guild costs <code>500 Gold</code>. You have <code>{hunter.gold:,} Gold</code>.")),
                fallback=lambda: message.reply_text(
                    f"❌ <b>Insufficient Treasury:</b> Creating a guild costs <code>500 Gold</code>. You have <code>{hunter.gold:,} Gold</code>.",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        # Create the guild
        hunter.gold -= 500
        guild = Guild(
            guild_id=user.id,
            name=guild_name,
            owner_id=user.id,
            members=[user.id],
            description="",
            created_at=time.time(),
        )
        hunter.guild_id = guild.guild_id
        await db.create_guild(guild)
        await db.save_hunter(user.id)

        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ SYSTEM NOTIFICATION // GUILD CHARTER ESTABLISHED ]"),
                paragraph("<b>길드 창설 // 시스템 인가 완료</b>"),
                paragraph(f"🎉 <b>{escape_html(guild_name)}</b> is officially recognized!"),
                quote(
                    f"👑 <b>Founder / Sovereign:</b> <b>{escape_html(hunter.display_full_name)}</b>\n"
                    f"👥 <b>Initial Roster:</b> <code>1/{GUILD_MAX_MEMBERS}</code>\n"
                    "• Perk Active: 🎁 <b>+10% Hunt EXP</b> unlocked for all members",
                    expandable=True,
                ),
                paragraph("<i>Use <code>/guild info</code> to review your visual syndicate card.</i>"),
            ),
            fallback=lambda: message.reply_text(
                "<b>[ SYSTEM NOTIFICATION // GUILD CHARTER ESTABLISHED ]</b>\n"
                "<b>길드 창설 // 시스템 인가 완료</b>\n\n"
                f"🎉 <b>{escape_html(guild_name)}</b> is officially recognized!\n\n"
                "<blockquote expandable>"
                f"👑 <b>Founder / Sovereign:</b> <b>{escape_html(hunter.display_full_name)}</b>\n"
                f"👥 <b>Initial Roster:</b> <code>1/{GUILD_MAX_MEMBERS}</code>\n"
                "• Perk Active: 🎁 <b>+10% Hunt EXP</b> unlocked for all members\n"
                "</blockquote>\n\n"
                "<i>Use <code>/guild info</code> to review your visual syndicate card.</i>",
                parse_mode=ParseMode.HTML,
            ),
        )
        logger.info(f"Guild created: {guild_name} by {hunter.hunter_name}")
        return

    # ── /guild join <name> ────────────────────────────────
    if sub == "join":
        if len(args) < 2:
            await reply_rich(
                message,
                RichDoc(
                    heading(1, "[ SYSTEM NOTICE // JOIN SYNDICATE ]"),
                    paragraph("<b>시스템 안내 // 길드 가입 지침</b>"),
                    paragraph("⚠️ <b>Syntax:</b> <code>/guild join &lt;name&gt;</code>\n<i>Example:</i> <code>/guild join Shadow Legion</code>"),
                ),
                fallback=lambda: message.reply_text(
                    "<b>[ SYSTEM NOTICE // JOIN SYNDICATE ]</b>\n"
                    "<b>시스템 안내 // 길드 가입 지침</b>\n\n"
                    "⚠️ <b>Syntax:</b> <code>/guild join &lt;name&gt;</code>\n"
                    "<i>Example:</i> <code>/guild join Shadow Legion</code>",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        guild_name = " ".join(args[1:]).strip()

        if hunter.guild_id:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ <b>Already Pledged:</b> You already belong to a guild! Depart first via <code>/guild leave</code>.")),
                fallback=lambda: message.reply_text(
                    "⚠️ <b>Already Pledged:</b> You already belong to a guild! Depart first via <code>/guild leave</code>.",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        guild = await db.get_guild_by_name(guild_name)
        if not guild:
            await reply_rich(
                message,
                RichDoc(paragraph(f"❌ <b>Not Found:</b> No guild named <b>{escape_html(guild_name)}</b> exists.")),
                fallback=lambda: message.reply_text(
                    f"❌ <b>Not Found:</b> No guild named <b>{escape_html(guild_name)}</b> exists.",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        if len(guild.members) >= GUILD_MAX_MEMBERS:
            await reply_rich(
                message,
                RichDoc(paragraph(f"❌ <b>Roster Full:</b> <b>{escape_html(guild.name)}</b> has reached capacity (<code>{len(guild.members)}/{GUILD_MAX_MEMBERS}</code>).")),
                fallback=lambda: message.reply_text(
                    f"❌ <b>Roster Full:</b> <b>{escape_html(guild.name)}</b> has reached capacity (<code>{len(guild.members)}/{GUILD_MAX_MEMBERS}</code>).",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        success = await db.add_guild_member(guild.guild_id, user.id)
        if success:
            await reply_rich(
                message,
                RichDoc(
                    heading(1, "[ SYSTEM NOTIFICATION // GUILD PLEDGE ACCEPTED ]"),
                    paragraph("<b>길드 가입 // 연맹 맹세 수락</b>"),
                    paragraph(f"🎉 Welcome to <b>{escape_html(guild.name)}</b>!"),
                    quote(
                        f"👥 <b>Updated Roster:</b> <code>{len(guild.members)}/{GUILD_MAX_MEMBERS}</code>\n"
                        "🎁 <b>Active Buff:</b> <code>+10% EXP</code> applied to all dungeon hunts!",
                        expandable=True,
                    ),
                ),
                fallback=lambda: message.reply_text(
                    "<b>[ SYSTEM NOTIFICATION // GUILD PLEDGE ACCEPTED ]</b>\n"
                    "<b>길드 가입 // 연맹 맹세 수락</b>\n\n"
                    f"🎉 Welcome to <b>{escape_html(guild.name)}</b>!\n\n"
                    "<blockquote expandable>"
                    f"👥 <b>Updated Roster:</b> <code>{len(guild.members)}/{GUILD_MAX_MEMBERS}</code>\n"
                    "🎁 <b>Active Buff:</b> <code>+10% EXP</code> applied to all dungeon hunts!\n"
                    "</blockquote>",
                    parse_mode=ParseMode.HTML,
                ),
            )
        else:
            await reply_rich(
                message,
                RichDoc(paragraph("❌ Failed to join guild. Please try again.")),
                fallback=lambda: message.reply_text(
                    "❌ Failed to join guild. Please try again.",
                    parse_mode=ParseMode.HTML,
                ),
            )
        return

    # ── /guild leave ──────────────────────────────────────
    if sub == "leave":
        guild = await db.get_user_guild(user.id)
        if not guild:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ You do not belong to any Hunter Guild.")),
                fallback=lambda: message.reply_text("⚠️ You do not belong to any Hunter Guild.", parse_mode=ParseMode.HTML),
            )
            return

        if guild.owner_id == user.id:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ <b>Sovereign Restriction:</b> You are the guild owner! Use <code>/guild disband</code> to dissolve the guild.")),
                fallback=lambda: message.reply_text(
                    "⚠️ <b>Sovereign Restriction:</b> You are the guild owner! Use <code>/guild disband</code> to dissolve the guild.",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        await db.remove_guild_member(guild.guild_id, user.id)
        await reply_rich(
            message,
            RichDoc(paragraph(f"🚪 <b>Allegiance Severed:</b> You have departed from <b>{escape_html(guild.name)}</b>.")),
            fallback=lambda: message.reply_text(
                f"🚪 <b>Allegiance Severed:</b> You have departed from <b>{escape_html(guild.name)}</b>.",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    # ── /guild view / /guild info [name/id] ───────────────
    if sub in ("view", "info"):
        target_query = " ".join(args[1:]).strip() if len(args) > 1 else ""
        await handle_view(client, message, target_query)
        return

    # ── /guild members ────────────────────────────────────
    if sub == "members":
        guild = await db.get_user_guild(user.id)
        if not guild:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ You do not belong to any Hunter Guild.")),
                fallback=lambda: message.reply_text("⚠️ You do not belong to any Hunter Guild.", parse_mode=ParseMode.HTML),
            )
            return

        member_lines = []
        for uid in guild.members:
            h = await db.get_hunter(uid)
            if h:
                role = "👑 Owner" if uid == guild.owner_id else "⚔️ Member"
                member_lines.append(f"• {role}: <b>{escape_html(h.display_full_name)}</b> [Rank <b>{h.rank}</b> | Lv.<code>{h.level}</code> | ⚡<code>{h.power:,}</code>]")

        text = (
            f"<b>[ GUILD ROSTER // {escape_html(guild.name.upper())} ]</b>\n"
            "<b>길드 명단 // 소속 헌터 목록</b>\n\n"
            f"🏰 <b>Syndicate:</b> <b>{escape_html(guild.name)}</b> (<code>{len(guild.members)}/{GUILD_MAX_MEMBERS}</code>)\n\n"
            "<blockquote expandable>"
            + "\n".join(member_lines) +
            "\n</blockquote>"
        )
        await reply_rich(
            message,
            RichDoc(
                heading(1, f"[ GUILD ROSTER // {escape_html(guild.name.upper())} ]"),
                paragraph("<b>길드 명단 // 소속 헌터 목록</b>"),
                paragraph(f"🏰 <b>Syndicate:</b> <b>{escape_html(guild.name)}</b> (<code>{len(guild.members)}/{GUILD_MAX_MEMBERS}</code>)"),
                quote("\n".join(member_lines), expandable=True),
            ),
            fallback=lambda: message.reply_text(text, parse_mode=ParseMode.HTML),
        )
        return

    # ── /guild kick <user> ────────────────────────────────
    if sub == "kick":
        guild = await db.get_user_guild(user.id)
        if not guild:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ You do not belong to any Hunter Guild.")),
                fallback=lambda: message.reply_text("⚠️ You do not belong to any Hunter Guild.", parse_mode=ParseMode.HTML),
            )
            return

        if guild.owner_id != user.id:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ Only the Guild Sovereign can expel members.")),
                fallback=lambda: message.reply_text("⚠️ Only the Guild Sovereign can expel members.", parse_mode=ParseMode.HTML),
            )
            return

        if not message.reply_to_message or not message.reply_to_message.from_user:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ Reply to a member's message in this group to expel them.")),
                fallback=lambda: message.reply_text("⚠️ Reply to a member's message in this group to expel them.", parse_mode=ParseMode.HTML),
            )
            return

        target = message.reply_to_message.from_user
        if target.id == user.id:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ You cannot expel yourself. Use <code>/guild disband</code> instead.")),
                fallback=lambda: message.reply_text("⚠️ You cannot expel yourself. Use <code>/guild disband</code> instead.", parse_mode=ParseMode.HTML),
            )
            return

        if target.id not in guild.members:
            await reply_rich(
                message,
                RichDoc(paragraph(f"⚠️ {escape_html(target.first_name)} is not enrolled in your guild.")),
                fallback=lambda: message.reply_text(f"⚠️ {escape_html(target.first_name)} is not enrolled in your guild.", parse_mode=ParseMode.HTML),
            )
            return

        await db.remove_guild_member(guild.guild_id, target.id)
        await reply_rich(
            message,
            RichDoc(paragraph(f"👢 <b>Member Expelled:</b> <b>{escape_html(target.first_name)}</b> was removed from <b>{escape_html(guild.name)}</b>.")),
            fallback=lambda: message.reply_text(
                f"👢 <b>Member Expelled:</b> <b>{escape_html(target.first_name)}</b> was removed from <b>{escape_html(guild.name)}</b>.",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    # ── /guild disband ────────────────────────────────────
    if sub == "disband":
        guild = await db.get_user_guild(user.id)
        if not guild:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ You do not belong to any Hunter Guild.")),
                fallback=lambda: message.reply_text("⚠️ You do not belong to any Hunter Guild.", parse_mode=ParseMode.HTML),
            )
            return

        if guild.owner_id != user.id:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ Only the Guild Sovereign can disband the guild.")),
                fallback=lambda: message.reply_text("⚠️ Only the Guild Sovereign can disband the guild.", parse_mode=ParseMode.HTML),
            )
            return

        guild_name = guild.name
        await db.delete_guild(guild.guild_id)
        await reply_rich(
            message,
            RichDoc(paragraph(f"🏰 <b>Syndicate Dissolved:</b> <b>{escape_html(guild_name)}</b> has been permanently disbanded.")),
            fallback=lambda: message.reply_text(
                f"🏰 <b>Syndicate Dissolved:</b> <b>{escape_html(guild_name)}</b> has been permanently disbanded.",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    # ── /guild edit <desc> ────────────────────────────────
    if sub == "edit":
        guild = await db.get_user_guild(user.id)
        if not guild:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ You do not belong to any Hunter Guild.")),
                fallback=lambda: message.reply_text("⚠️ You do not belong to any Hunter Guild.", parse_mode=ParseMode.HTML),
            )
            return

        if guild.owner_id != user.id:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ Only the Guild Sovereign can edit the description.")),
                fallback=lambda: message.reply_text("⚠️ Only the Guild Sovereign can edit the description.", parse_mode=ParseMode.HTML),
            )
            return

        desc = " ".join(args[1:]).strip()
        if not desc:
            await reply_rich(
                message,
                RichDoc(paragraph("Usage: <code>/guild edit &lt;description&gt;</code>")),
                fallback=lambda: message.reply_text("Usage: <code>/guild edit &lt;description&gt;</code>", parse_mode=ParseMode.HTML),
            )
            return

        if len(desc) > 200:
            await reply_rich(
                message,
                RichDoc(paragraph("❌ Description must be 200 characters or fewer.")),
                fallback=lambda: message.reply_text("❌ Description must be 200 characters or fewer.", parse_mode=ParseMode.HTML),
            )
            return

        guild.description = desc
        await db.save_guild(guild.guild_id)
        await reply_rich(
            message,
            RichDoc(paragraph(f"📝 <b>Guild Creed Updated:</b>\n\n<i>{escape_html(desc)}</i>")),
            fallback=lambda: message.reply_text(
                f"📝 <b>Guild Creed Updated:</b>\n\n<i>{escape_html(desc)}</i>",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    # ── /guild top — guild leaderboard ────────────────────
    if sub == "top":
        await handle_top(client, message)
        return

    # ── /guild war — guild war system ─────────────────────
    if sub == "war":
        await guild_war.handle_war(client, message)
        return

    # Unknown subcommand
    await reply_rich(
        message,
        RichDoc(paragraph("❌ Unknown guild command. Use <code>/guild</code> to see available directives.")),
        fallback=lambda: message.reply_text(
            "❌ Unknown guild command. Use <code>/guild</code> to see available directives.",
            parse_mode=ParseMode.HTML,
        ),
    )


# ═══════════════════════════════════════════════════════════════
# /gift command — guild-only item and gold gifting
# ═══════════════════════════════════════════════════════════════

def _resolve_recipient(message: Message, args: list[str]) -> tuple[int | None, str | None]:
    """
    Resolve recipient from reply-to-message or @username in args.
    Returns (user_id, error_message_or_None).
    """
    # Method 1: reply to a message
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        if target.is_bot:
            return None, "⚠️ You can't gift items to bots."
        return target.id, None

    # Method 2: @username in args — find last arg that looks like @username
    for arg in reversed(args):
        if arg.startswith("@"):
            return None, f"⚠️ Reply to {arg}'s message instead, or use their Telegram ID."

    return None, "⚠️ Reply to a guildmate's message or specify their @username."


async def handle_gift(client: Client, message: Message) -> None:
    """Handle the /gift command — gift items or gold to guildmates."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db
    args = message.command[1:] if len(message.command) > 1 else []

    sender = await db.get_hunter(user.id)
    if not sender:
        await reply_rich(
            message, format_not_registered_rich(),
            fallback=lambda: message.reply_text(format_not_registered(), parse_mode=ParseMode.HTML),
        )
        return

    if not args:
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ GUILD PROTOCOL // GIFT DISPATCH ]"),
                paragraph("<b>길드 지원 // 물품 및 자금 지원</b>"),
                paragraph("<i>Distribute treasury or equipment directly to your guildmates!</i>"),
                quote(
                    "<b>Directives:</b>\n"
                    "• <code>/gift item &lt;id&gt; @user</code> — Gift unequipped gear\n"
                    "• <code>/gift gold &lt;amount&gt; @user</code> — Gift treasury gold\n\n"
                    "💡 <i>Tip: Reply directly to a guildmate's message with</i> <code>/gift item &lt;id&gt;</code>.",
                    expandable=True,
                ),
            ),
            fallback=lambda: message.reply_text(
                "<b>[ GUILD PROTOCOL // GIFT DISPATCH ]</b>\n"
                "<b>길드 지원 // 물품 및 자금 지원</b>\n\n"
                "<i>Distribute treasury or equipment directly to your guildmates!</i>\n\n"
                "<blockquote expandable>"
                "<b>Directives:</b>\n"
                "• <code>/gift item &lt;id&gt; @user</code> — Gift unequipped gear\n"
                "• <code>/gift gold &lt;amount&gt; @user</code> — Gift treasury gold\n\n"
                "💡 <i>Tip: Reply directly to a guildmate's message with</i> <code>/gift item &lt;id&gt;</code>.\n"
                "</blockquote>",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    gift_type = args[0].lower()
    if gift_type not in ("item", "gold"):
        await reply_rich(
            message,
            RichDoc(paragraph("⚠️ <b>Usage:</b> <code>/gift item &lt;id&gt;</code> or <code>/gift gold &lt;amount&gt;</code>")),
            fallback=lambda: message.reply_text(
                "⚠️ <b>Usage:</b> <code>/gift item &lt;id&gt;</code> or <code>/gift gold &lt;amount&gt;</code>",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    # Verify sender is in a guild
    sender_guild = await db.get_user_guild(user.id)
    if not sender_guild:
        await reply_rich(
            message,
            RichDoc(paragraph("⚠️ You must be enrolled in a Hunter Guild to gift items or gold.")),
            fallback=lambda: message.reply_text(
                "⚠️ You must be enrolled in a Hunter Guild to gift items or gold.",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    # ── /gift gold <amount> ──────────────────────────────
    if gift_type == "gold":
        if len(args) < 2:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ <b>Usage:</b> <code>/gift gold &lt;amount&gt; @user</code>")),
                fallback=lambda: message.reply_text(
                    "⚠️ <b>Usage:</b> <code>/gift gold &lt;amount&gt; @user</code>",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        try:
            amount = int(args[1])
        except ValueError:
            await reply_rich(
                message,
                RichDoc(paragraph("❌ Invalid gold amount. Use a positive integer.")),
                fallback=lambda: message.reply_text("❌ Invalid gold amount. Use a positive integer.", parse_mode=ParseMode.HTML),
            )
            return

        if amount <= 0:
            await reply_rich(
                message,
                RichDoc(paragraph("❌ Gold amount must be greater than zero.")),
                fallback=lambda: message.reply_text("❌ Gold amount must be greater than zero.", parse_mode=ParseMode.HTML),
            )
            return

        if sender.gold < amount:
            await reply_rich(
                message,
                RichDoc(paragraph(f"❌ <b>Insufficient Treasury:</b> You only possess <code>{sender.gold:,} Gold</code>.")),
                fallback=lambda: message.reply_text(
                    f"❌ <b>Insufficient Treasury:</b> You only possess <code>{sender.gold:,} Gold</code>.",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        recipient_id, err = _resolve_recipient(message, args)
        if err:
            await reply_rich(
                message,
                RichDoc(paragraph(escape_html(err))),
                fallback=lambda: message.reply_text(err, parse_mode=ParseMode.HTML),
            )
            return

        if recipient_id == user.id:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ You cannot gift gold to yourself.")),
                fallback=lambda: message.reply_text("⚠️ You cannot gift gold to yourself.", parse_mode=ParseMode.HTML),
            )
            return

        # Verify recipient is in same guild
        if recipient_id not in sender_guild.members:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ That hunter is not enrolled in your guild.")),
                fallback=lambda: message.reply_text("⚠️ That hunter is not enrolled in your guild.", parse_mode=ParseMode.HTML),
            )
            return

        recipient = await db.get_hunter(recipient_id)
        if not recipient:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ That hunter has not awakened in the System yet.")),
                fallback=lambda: message.reply_text("⚠️ That hunter has not awakened in the System yet.", parse_mode=ParseMode.HTML),
            )
            return

        # Transfer gold
        sender.gold -= amount
        recipient.gold += amount
        await db.save_hunter(user.id)
        await db.save_hunter(recipient_id)

        s_name = escape_html(sender.display_full_name)
        r_name = escape_html(recipient.display_full_name)
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ GUILD PROTOCOL // TREASURY TRANSFER ]"),
                paragraph("<b>길드 금고 // 자금 이체 완료</b>"),
                paragraph(f"💰 <b>{s_name}</b> transferred <code>{amount:,} Gold</code> to <b>{r_name}</b>!"),
                quote(
                    f"• Sender Vault: <code>{sender.gold:,} Gold</code>\n"
                    f"• Recipient Vault: <code>{recipient.gold:,} Gold</code>",
                    expandable=True,
                ),
            ),
            fallback=lambda: message.reply_text(
                "<b>[ GUILD PROTOCOL // TREASURY TRANSFER ]</b>\n"
                "<b>길드 금고 // 자금 이체 완료</b>\n\n"
                f"💰 <b>{s_name}</b> transferred <code>{amount:,} Gold</code> to <b>{r_name}</b>!\n\n"
                "<blockquote expandable>"
                f"• Sender Vault: <code>{sender.gold:,} Gold</code>\n"
                f"• Recipient Vault: <code>{recipient.gold:,} Gold</code>\n"
                "</blockquote>",
                parse_mode=ParseMode.HTML,
            ),
        )
        logger.info(f"Gold gift: {sender.hunter_name} -> {recipient.hunter_name}: {amount} gold")
        return

    # ── /gift item <id> ──────────────────────────────────
    if gift_type == "item":
        if len(args) < 2:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ <b>Usage:</b> <code>/gift item &lt;id&gt; @user</code>")),
                fallback=lambda: message.reply_text(
                    "⚠️ <b>Usage:</b> <code>/gift item &lt;id&gt; @user</code>",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return

        try:
            item_id = int(args[1])
        except ValueError:
            await reply_rich(
                message,
                RichDoc(paragraph("❌ Invalid item ID. Use a valid number.")),
                fallback=lambda: message.reply_text("❌ Invalid item ID. Use a valid number.", parse_mode=ParseMode.HTML),
            )
            return

        recipient_id, err = _resolve_recipient(message, args)
        if err:
            await reply_rich(
                message,
                RichDoc(paragraph(escape_html(err))),
                fallback=lambda: message.reply_text(err, parse_mode=ParseMode.HTML),
            )
            return

        if recipient_id == user.id:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ You cannot gift items to yourself.")),
                fallback=lambda: message.reply_text("⚠️ You cannot gift items to yourself.", parse_mode=ParseMode.HTML),
            )
            return

        # Verify recipient is in same guild
        if recipient_id not in sender_guild.members:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ That hunter is not enrolled in your guild.")),
                fallback=lambda: message.reply_text("⚠️ That hunter is not enrolled in your guild.", parse_mode=ParseMode.HTML),
            )
            return

        recipient = await db.get_hunter(recipient_id)
        if not recipient:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ That hunter has not awakened in the System yet.")),
                fallback=lambda: message.reply_text("⚠️ That hunter has not awakened in the System yet.", parse_mode=ParseMode.HTML),
            )
            return

        # Check sender has the item
        sender_inv = await db.get_inventory(user.id)
        item = sender_inv.get_item(item_id)
        if not item:
            await reply_rich(
                message,
                RichDoc(paragraph(f"❌ No item with ID <code>{item_id}</code> found in your inventory.")),
                fallback=lambda: message.reply_text(f"❌ No item with ID <code>{item_id}</code> found in your inventory.", parse_mode=ParseMode.HTML),
            )
            return

        if item.is_equipped:
            await reply_rich(
                message,
                RichDoc(paragraph("⚠️ Unequip the artifact first before gifting it!")),
                fallback=lambda: message.reply_text("⚠️ Unequip the artifact first before gifting it!", parse_mode=ParseMode.HTML),
            )
            return

        # Remove from sender, add to receiver
        removed = sender_inv.remove_item(item_id)
        if not removed:
            await reply_rich(
                message,
                RichDoc(paragraph("❌ Failed to transfer item from inventory.")),
                fallback=lambda: message.reply_text("❌ Failed to transfer item from inventory.", parse_mode=ParseMode.HTML),
            )
            return

        recipient_inv = await db.get_inventory(recipient_id)
        recipient_inv.add_item(removed)

        # Save both inventories
        await db.save_hunter(user.id)
        await db.save_inventory(user.id)
        await db.save_inventory(recipient_id)

        rarity_emoji = {
            "Common": "⚪", "Uncommon": "🟢", "Rare": "🔵",
            "Epic": "🟣", "Legendary": "🟡", "Mythic": "🔴",
        }.get(removed.rarity, "⚪")

        s_name = escape_html(sender.display_full_name)
        r_name = escape_html(recipient.display_full_name)
        it_name = escape_html(removed.name)
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ GUILD PROTOCOL // ARTIFACT TRANSFER ]"),
                paragraph("<b>길드 보관소 // 장비 전달 완료</b>"),
                paragraph(f"🎁 <b>{s_name}</b> transferred <b>{rarity_emoji} {it_name}</b> to <b>{r_name}</b>!"),
                quote(
                    f"• Artifact: <code>[{escape_html(removed.rarity)}]</code> <b>{it_name}</b>\n"
                    f"• Stats: <code>{escape_html(removed.stat_summary())}</code>\n"
                    f"• Slot: <b>{escape_html(removed.type.title())}</b>",
                    expandable=True,
                ),
            ),
            fallback=lambda: message.reply_text(
                "<b>[ GUILD PROTOCOL // ARTIFACT TRANSFER ]</b>\n"
                "<b>길드 보관소 // 장비 전달 완료</b>\n\n"
                f"🎁 <b>{s_name}</b> transferred <b>{rarity_emoji} {it_name}</b> to <b>{r_name}</b>!\n\n"
                "<blockquote expandable>"
                f"• Artifact: <code>[{escape_html(removed.rarity)}]</code> <b>{it_name}</b>\n"
                f"• Stats: <code>{escape_html(removed.stat_summary())}</code>\n"
                f"• Slot: <b>{escape_html(removed.type.title())}</b>\n"
                "</blockquote>",
                parse_mode=ParseMode.HTML,
            ),
        )
        logger.info(f"Item gift: {sender.hunter_name} -> {recipient.hunter_name}: {removed.name} (ID {removed.id})")
        return


# ═══════════════════════════════════════════════════════════════
# /guild top — guild leaderboard with category tabs
# ═══════════════════════════════════════════════════════════════

GLB_CATEGORY_TITLES = {
    "power": "Total Power",
    "level": "Avg Level",
    "wealth": "Total Gold",
    "members": "Members",
}


def _glb_keyboard(active_cat: str = "power") -> InlineKeyboardMarkup:
    """Inline tabs to switch between guild leaderboard categories."""
    def make_btn(cat: str, icon: str, name: str) -> InlineKeyboardButton:
        is_active = (cat == active_cat)
        label = f"[ {icon} {name} ]" if is_active else f"{icon} {name}"
        style = enums.ButtonStyle.PRIMARY if is_active else enums.ButtonStyle.DEFAULT
        return InlineKeyboardButton(label, callback_data=f"glb_{cat}", style=style)

    return InlineKeyboardMarkup([
        [
            make_btn("power", "⚡", "Power"),
            make_btn("level", "🏆", "Level"),
        ],
        [
            make_btn("wealth", "💰", "Gold"),
            make_btn("members", "👥", "Members"),
        ],
    ])


async def _compute_guilds_data(db: ChannelDB, guilds: list[Guild]) -> list[dict]:
    """Compute aggregate stats for each guild and return sorted list of dicts."""
    result = []
    for guild in guilds:
        member_hunters = []
        for uid in guild.members:
            h = await db.get_hunter(uid)
            if h:
                member_hunters.append(h)

        if not member_hunters:
            continue

        total_power = sum(h.power for h in member_hunters)
        avg_level = sum(h.level for h in member_hunters) / len(member_hunters)
        total_gold = sum(h.gold for h in member_hunters)
        member_count = len(member_hunters)

        # Resolve owner name
        owner_hunter = await db.get_hunter(guild.owner_id)
        owner_name = owner_hunter.display_full_name if owner_hunter else "Unknown"

        result.append({
            "guild_id": guild.guild_id,
            "name": guild.name,
            "owner_name": owner_name,
            "member_count": member_count,
            "total_power": total_power,
            "avg_level": avg_level,
            "total_gold": total_gold,
        })

    return result


def _sort_guilds_data(guilds_data: list[dict], category: str) -> list[dict]:
    """Sort guild aggregate data by category (descending)."""
    if category == "level":
        return sorted(guilds_data, key=lambda g: (g["avg_level"], g["total_power"], g["member_count"]), reverse=True)
    elif category == "wealth":
        return sorted(guilds_data, key=lambda g: (g["total_gold"], g["total_power"], g["avg_level"]), reverse=True)
    elif category == "members":
        return sorted(guilds_data, key=lambda g: (g["member_count"], g["total_power"], g["avg_level"]), reverse=True)
    else:  # power
        return sorted(guilds_data, key=lambda g: (g["total_power"], g["avg_level"], g["total_gold"]), reverse=True)


async def handle_top(client: Client, message: Message) -> None:
    """Handle the /guild top command — show top 10 guilds leaderboard."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db

    all_guilds = await db.get_all_guilds()
    if not all_guilds:
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ GUILD LEADERBOARD // SYNDICATE STANDINGS ]"),
                paragraph("<b>길드 순위 // 연맹 랭킹 목록 없음</b>"),
                paragraph("<i>No guilds have been established yet in the System!</i>"),
                quote("• Use <code>/guild create &lt;name&gt;</code> to establish the first Guild.", expandable=True),
            ),
            fallback=lambda: message.reply_text(
                "<b>[ GUILD LEADERBOARD // SYNDICATE STANDINGS ]</b>\n"
                "<b>길드 순위 // 연맹 랭킹 목록 없음</b>\n\n"
                "<i>No guilds have been established yet in the System!</i>\n\n"
                "<blockquote expandable>"
                "• Use <code>/guild create &lt;name&gt;</code> to establish the first Guild.\n"
                "</blockquote>",
                parse_mode=ParseMode.HTML,
            ),
        )
        return

    category = "power"
    guilds_data = await _compute_guilds_data(db, all_guilds)
    sorted_guilds = _sort_guilds_data(guilds_data, category)

    # Find viewer's guild
    viewer_guild = await db.get_user_guild(user.id)
    viewer_guild_id = viewer_guild.guild_id if viewer_guild else None

    try:
        photo_buf = await asyncio.to_thread(
            render_guild_leaderboard_image,
            sorted_guilds,
            category=category,
            viewer_guild_id=viewer_guild_id,
        )
        cat_name = GLB_CATEGORY_TITLES.get(category, "Total Power")
        caption = (
            f"<b>[ GUILD LEADERBOARD // {cat_name.upper()} ]</b>\n"
            "<b>길드 순위 // 연맹 랭킹 차트</b>\n\n"
            f"📊 <b>Category:</b> <code>{escape_html(cat_name)}</code>\n\n"
            "<blockquote expandable>"
            "<b>Guild Standings Matrix:</b>\n"
            "• Visual rankings displayed on the Syndicate HUD card above.\n"
            "• Switch ranking criteria using the controls below.\n"
            "</blockquote>"
        )
        await reply_rich(
            message,
            build_guild_leaderboard_rich(cat_name, photo_first=False),
            reply_markup=_glb_keyboard(category),
            media=[photo_media("guild", photo_buf)],
            fallback=lambda: message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=_glb_keyboard(category),
                parse_mode=ParseMode.HTML,
                show_caption_above_media=True,
            ),
        )
    except Exception as exc:
        logger.error("Failed to render guild leaderboard image: %s", exc, exc_info=True)
        await reply_rich(
            message,
            RichDoc(paragraph("❌ System Error: Failed to render guild leaderboard. Please try again later.")),
            fallback=lambda: message.reply_text(
                "❌ System Error: Failed to render guild leaderboard. Please try again later.",
                parse_mode=ParseMode.HTML,
            ),
        )


async def guild_leaderboard_callback(client: Client, query: CallbackQuery) -> None:
    """Handle glb_<category> tab switching callbacks for guild leaderboard."""
    if not query:
        return

    await query.answer()
    data = query.data or ""
    if not data.startswith("glb_"):
        return

    category = data[4:]
    if category not in GLB_CATEGORY_TITLES:
        category = "power"

    user = query.from_user
    user_id = user.id if user else 0
    db: ChannelDB = client.db

    all_guilds = await db.get_all_guilds()
    if not all_guilds:
        return

    guilds_data = await _compute_guilds_data(db, all_guilds)
    sorted_guilds = _sort_guilds_data(guilds_data, category)

    # Find viewer's guild
    viewer_guild = await db.get_user_guild(user_id)
    viewer_guild_id = viewer_guild.guild_id if viewer_guild else None

    try:
        photo_buf = await asyncio.to_thread(
            render_guild_leaderboard_image,
            sorted_guilds,
            category=category,
            viewer_guild_id=viewer_guild_id,
        )
        cat_name = GLB_CATEGORY_TITLES.get(category, "Total Power")
        caption = (
            f"<b>[ GUILD LEADERBOARD // {cat_name.upper()} ]</b>\n"
            "<b>길드 순위 // 연맹 랭킹 차트</b>\n\n"
            f"📊 <b>Category:</b> <code>{escape_html(cat_name)}</code>\n\n"
            "<blockquote expandable>"
            "<b>Guild Standings Matrix:</b>\n"
            "• Visual rankings displayed on the Syndicate HUD card above.\n"
            "• Switch ranking criteria using the controls below.\n"
            "</blockquote>"
        )

        if query.message and query.message.photo:
            await edit_rich(
                client, query.message.chat.id, query.message.id,
                build_guild_leaderboard_rich(cat_name, photo_first=False),
                reply_markup=_glb_keyboard(category),
                media=[photo_media("guild", photo_buf)],
                fallback=lambda: query.edit_message_media(
                    media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=_glb_keyboard(category),
                ),
            )
        elif query.message:
            await reply_rich(
                query.message,
                build_guild_leaderboard_rich(cat_name, photo_first=False),
                reply_markup=_glb_keyboard(category),
                media=[photo_media("guild", photo_buf)],
                fallback=lambda: query.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    reply_markup=_glb_keyboard(category),
                    parse_mode=ParseMode.HTML,
                    show_caption_above_media=True,
                ),
            )
    except BadRequest as br_err:
        if "Message is not modified" not in str(br_err):
            logger.warning("BadRequest during guild leaderboard update: %s", br_err)
    except Exception as exc:
        logger.error("Failed to update guild leaderboard tab: %s", exc, exc_info=True)


async def guild_interaction_callback(client: Client, query: CallbackQuery) -> None:
    """Handle interactive guild action buttons (gjoin_, gleave_, gview_, gmembers_, gnoop)."""
    if not query:
        return

    data = query.data or ""
    user = query.from_user
    if not user:
        return

    db: ChannelDB = client.db

    if data == "gnoop":
        await query.answer("👑 Guild Sovereign & Founder.", show_alert=False)
        return

    if data == "gnoop_switch":
        await query.answer(
            "⚠️ You already belong to a Guild!\nYou must leave your current guild (/guild leave) before joining another.",
            show_alert=True,
        )
        return

    # ── gmembers_{guild_id} ──
    if data.startswith("gmembers_"):
        try:
            gid = int(data[9:])
        except ValueError:
            return
        g = await db.get_guild_by_id(gid)
        if not g:
            await query.answer("❌ Guild not found.", show_alert=True)
            return

        lines = [f"🏰 {g.name} — Members ({len(g.members)}/{GUILD_MAX_MEMBERS}):"]
        for uid in g.members:
            h = await db.get_hunter(uid)
            if h:
                role = "👑" if uid == g.owner_id else "⚔️"
                lines.append(f"{role} {h.display_full_name} [Lv.{h.level} {h.rank}-Rank] ⚡{h.power:,}")
        roster_text = "\n".join(lines[:12])
        if len(lines) > 12:
            roster_text += f"\n...and {len(lines) - 12} more"
        if len(roster_text) > 190:
            roster_text = roster_text[:187] + "..."
        await query.answer(roster_text, show_alert=True)
        return

    # ── gview_{guild_id} ──
    if data.startswith("gview_"):
        await query.answer()
        try:
            gid = int(data[6:])
        except ValueError:
            return
        target_guild = await db.get_guild_by_id(gid)
        if not target_guild:
            return

        viewer_guild = await db.get_user_guild(user.id)
        all_guilds = await db.get_all_guilds()

        member_hunters = []
        for uid in target_guild.members:
            h = await db.get_hunter(uid)
            if h:
                member_hunters.append(h)
        total_power = sum(h.power for h in member_hunters)

        photo_buf = await asyncio.to_thread(
            render_guild_image, target_guild, member_hunters, total_power
        )
        caption = build_guild_caption(target_guild, len(member_hunters), total_power, GUILD_MAX_MEMBERS)
        keyboard = _guild_view_keyboard(user.id, target_guild, viewer_guild, all_guilds)
        try:
            if query.message and query.message.photo:
                await edit_rich(
                    client, query.message.chat.id, query.message.id,
                    build_guild_rich(target_guild, len(member_hunters), total_power, GUILD_MAX_MEMBERS, photo_first=False),
                    reply_markup=keyboard,
                    media=[photo_media("guild", photo_buf)],
                    fallback=lambda: query.edit_message_media(
                        media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=ParseMode.HTML),
                        reply_markup=keyboard,
                    ),
                )
        except BadRequest as e:
            if "not modified" not in str(e).lower():
                logger.warning(f"Failed to edit guild view: {e}")
        return

    # ── gjoin_{guild_id} ──
    if data.startswith("gjoin_"):
        hunter = await db.get_hunter(user.id)
        if not hunter:
            await query.answer("⚠️ Register first with /start!", show_alert=True)
            return

        try:
            gid = int(data[6:])
        except ValueError:
            return

        target_guild = await db.get_guild_by_id(gid)
        if not target_guild:
            await query.answer("❌ Guild no longer exists.", show_alert=True)
            return

        if hunter.guild_id:
            await query.answer("⚠️ You already belong to a guild! Leave it first with /guild leave.", show_alert=True)
            return

        if len(target_guild.members) >= GUILD_MAX_MEMBERS:
            await query.answer(f"❌ {target_guild.name} is full ({len(target_guild.members)}/{GUILD_MAX_MEMBERS})!", show_alert=True)
            return

        success = await db.add_guild_member(target_guild.guild_id, user.id)
        if success:
            await query.answer(
                f"🎉 Welcome to {target_guild.name}!\nYou have received the +10% XP Buff on all hunts!",
                show_alert=True,
            )
            # Refresh card in-place
            viewer_guild = target_guild
            all_guilds = await db.get_all_guilds()
            member_hunters = []
            for uid in target_guild.members:
                h = await db.get_hunter(uid)
                if h:
                    member_hunters.append(h)
            total_power = sum(h.power for h in member_hunters)

            photo_buf = await asyncio.to_thread(
                render_guild_image, target_guild, member_hunters, total_power
            )
            caption = build_guild_caption(target_guild, len(member_hunters), total_power, GUILD_MAX_MEMBERS)
            keyboard = _guild_view_keyboard(user.id, target_guild, viewer_guild, all_guilds)
            try:
                if query.message and query.message.photo:
                    await edit_rich(
                        client, query.message.chat.id, query.message.id,
                        build_guild_rich(target_guild, len(member_hunters), total_power, GUILD_MAX_MEMBERS, photo_first=False),
                        reply_markup=keyboard,
                        media=[photo_media("guild", photo_buf)],
                        fallback=lambda: query.edit_message_media(
                            media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=ParseMode.HTML),
                            reply_markup=keyboard,
                        ),
                    )
            except Exception as e:
                logger.warning(f"In-place media edit error after join: {e}")
        else:
            await query.answer("❌ Failed to join guild. Please try again.", show_alert=True)
        return

    # ── gleave_{guild_id} ──
    if data.startswith("gleave_"):
        try:
            gid = int(data[7:])
        except ValueError:
            return

        target_guild = await db.get_guild_by_id(gid)
        if not target_guild:
            await query.answer("❌ Guild not found.", show_alert=True)
            return

        if target_guild.owner_id == user.id:
            await query.answer("⚠️ Guild Sovereign cannot leave. Use /guild disband or transfer ownership.", show_alert=True)
            return

        if user.id not in target_guild.members:
            await query.answer("⚠️ You are not a member of this guild.", show_alert=True)
            return

        await db.remove_guild_member(target_guild.guild_id, user.id)
        await query.answer(f"🚪 You have departed from {target_guild.name}.", show_alert=True)

        # Refresh card in-place
        all_guilds = await db.get_all_guilds()
        member_hunters = []
        for uid in target_guild.members:
            h = await db.get_hunter(uid)
            if h:
                member_hunters.append(h)
        total_power = sum(h.power for h in member_hunters)

        photo_buf = await asyncio.to_thread(
            render_guild_image, target_guild, member_hunters, total_power
        )
        caption = build_guild_caption(target_guild, len(member_hunters), total_power, GUILD_MAX_MEMBERS)
        keyboard = _guild_view_keyboard(user.id, target_guild, None, all_guilds)
        try:
            if query.message and query.message.photo:
                await edit_rich(
                    client, query.message.chat.id, query.message.id,
                    build_guild_rich(target_guild, len(member_hunters), total_power, GUILD_MAX_MEMBERS, photo_first=False),
                    reply_markup=keyboard,
                    media=[photo_media("guild", photo_buf)],
                    fallback=lambda: query.edit_message_media(
                        media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=ParseMode.HTML),
                        reply_markup=keyboard,
                    ),
                )
        except Exception as e:
            logger.warning(f"In-place media edit error after leave: {e}")
        return
