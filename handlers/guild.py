"""
handlers/guild.py — /guild command handler.

Manages Hunter Guilds — social grouping with up to 15 members.
Commands:
  /guild create <name>  — Create a guild (1 per user, costs 500 gold)
  /guild join <name>    — Join an existing guild
  /guild leave          — Leave your current guild
  /guild info [name]    — View guild card (yours or by name)
  /guild members        — List members of your guild
  /guild kick @user     — Owner kicks a member
  /guild disband        — Owner deletes the guild
  /guild edit <desc>    — Owner edits guild description
"""

from __future__ import annotations

import asyncio
import logging
import time
from pyrogram import Client
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from channel_db import ChannelDB
from config import GUILD_MAX_MEMBERS
from models import Guild
from game.formatting import format_not_registered
from game.font_manager import clean_and_normalize_name
from game.guild_image import render_guild_image

logger = logging.getLogger(__name__)


def _format_guild_info(guild: Guild, db_guild_stats: dict | None = None) -> str:
    """Format guild info as text."""
    lines = [
        "╔══════════════════════════════╗",
        "║   🏰 HUNTER GUILD            ║",
        "╚══════════════════════════════╝",
        "",
        f"🏰 {guild.name}",
        f"📝 {guild.description or 'No description set.'}",
        f"👑 Owner: #{guild.owner_id}",
        f"👥 Members: {len(guild.members)}/{GUILD_MAX_MEMBERS}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)


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
        await message.reply_text(format_not_registered())
        return

    # ── /guild (no args) — show help ──────────────────────
    if not sub:
        text = (
            "╔══════════════════════════════╗\n"
            "║   🏰 HUNTER GUILD SYSTEM     ║\n"
            "╚══════════════════════════════╝\n\n"
            "⚔️ GUILD COMMANDS\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "/guild create <name> — Create a guild (500💰)\n"
            "/guild join <name> — Join a guild\n"
            "/guild leave — Leave your guild\n"
            "/guild info — View your guild card\n"
            "/guild members — List guild members\n"
            "/guild kick — Kick a member (owner only)\n"
            "/guild disband — Delete your guild (owner only)\n"
            "/guild edit <desc> — Edit description (owner only)\n\n"
            f"👥 Max members: {GUILD_MAX_MEMBERS}\n"
            "🎁 Guild members get +10% XP on hunts!\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "「 A Hunter grows stronger with allies at their side. 」"
        )
        await message.reply_text(text)
        return

    # ── /guild create <name> ──────────────────────────────
    if sub == "create":
        if len(args) < 2:
            await message.reply_text("Usage: /guild create <name>\nExample: /guild create Shadow Legion")
            return

        guild_name = " ".join(args[1:]).strip()
        if len(guild_name) < 2 or len(guild_name) > 30:
            await message.reply_text("Guild name must be 2-30 characters long.")
            return

        if hunter.guild_id:
            await message.reply_text("⚠️ You already belong to a guild! Leave it first with /guild leave.")
            return

        if await db.guild_name_exists(guild_name):
            await message.reply_text(f"❌ A guild named **{guild_name}** already exists!", parse_mode="markdown")
            return

        # Check gold
        if hunter.gold < 500:
            await message.reply_text(f"❌ Creating a guild costs 500💰. You have {hunter.gold:,}💰.")
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

        await message.reply_text(
            f"🏰 **{guild_name}** has been established!\n\n"
            f"👑 Owner: {hunter.display_full_name}\n"
            f"👥 Members: 1/{GUILD_MAX_MEMBERS}\n\n"
            f"Use /guild info to view your guild.",
            parse_mode="markdown",
        )
        logger.info(f"Guild created: {guild_name} by {hunter.hunter_name}")
        return

    # ── /guild join <name> ────────────────────────────────
    if sub == "join":
        if len(args) < 2:
            await message.reply_text("Usage: /guild join <name>\nExample: /guild join Shadow Legion")
            return

        guild_name = " ".join(args[1:]).strip()

        if hunter.guild_id:
            await message.reply_text("⚠️ You already belong to a guild! Leave it first with /guild leave.")
            return

        guild = await db.get_guild_by_name(guild_name)
        if not guild:
            await message.reply_text(f"❌ No guild named **{guild_name}** found.", parse_mode="markdown")
            return

        if len(guild.members) >= GUILD_MAX_MEMBERS:
            await message.reply_text(f"❌ **{guild.name}** is full! ({len(guild.members)}/{GUILD_MAX_MEMBERS})")
            return

        success = await db.add_guild_member(guild.guild_id, user.id)
        if success:
            await message.reply_text(
                f"🏰 You have joined **{guild.name}**!\n\n"
                f"👥 Members: {len(guild.members)}/{GUILD_MAX_MEMBERS}\n"
                f"🎁 You now receive +10% XP on hunts!",
                parse_mode="markdown",
            )
        else:
            await message.reply_text("❌ Failed to join guild. Try again.")
        return

    # ── /guild leave ──────────────────────────────────────
    if sub == "leave":
        guild = await db.get_user_guild(user.id)
        if not guild:
            await message.reply_text("⚠️ You don't belong to any guild.")
            return

        if guild.owner_id == user.id:
            await message.reply_text("⚠️ You are the guild owner! Use /guild disband to delete it, or transfer ownership first.")
            return

        await db.remove_guild_member(guild.guild_id, user.id)
        await message.reply_text(f"🚪 You have left **{guild.name}**.", parse_mode="markdown")
        return

    # ── /guild info [name] ────────────────────────────────
    if sub == "info":
        if len(args) >= 2:
            # Look up by name
            guild_name = " ".join(args[1:]).strip()
            guild = await db.get_guild_by_name(guild_name)
        else:
            # Show user's own guild
            guild = await db.get_user_guild(user.id)

        if not guild:
            await message.reply_text("⚠️ No guild found. Create one with /guild create <name>")
            return

        # Load all member hunters
        member_hunters = []
        for uid in guild.members:
            h = await db.get_hunter(uid)
            if h:
                member_hunters.append(h)

        total_power = sum(h.power for h in member_hunters)

        try:
            photo_buf = await asyncio.to_thread(
                render_guild_image, guild, member_hunters, total_power
            )
            caption = f"🏰 {guild.name} — {len(guild.members)}/{GUILD_MAX_MEMBERS} members"
            await message.reply_photo(photo=photo_buf, caption=caption)
        except Exception as exc:
            logger.error("Failed to render guild image: %s", exc, exc_info=True)
            # Fallback to text
            member_lines = []
            for h in sorted(member_hunters, key=lambda x: (x.user_id != guild.owner_id, -x.power)):
                rank_emoji = {
                    "E": "🅴", "D": "🅳", "C": "🅲", "B": "🅱️", "A": "🅰️",
                    "S": "⭐", "SS": "🌟", "SSS": "💫", "National Level": "🔱", "Monarch": "👑"
                }.get(h.rank, "")
                role = "👑" if h.user_id == guild.owner_id else "⚔️"
                member_lines.append(f"{role} {h.display_full_name} — Lv.{h.level} {rank_emoji}{h.rank}")

            member_text = "\n".join(member_lines) if member_lines else "No members found."
            text = (
                "╔══════════════════════════════╗\n"
                "║   🏰 GUILD INFO              ║\n"
                "╚══════════════════════════════╝\n\n"
                f"🏰 {guild.name}\n"
                f"📝 {guild.description or 'No description set.'}\n"
                f"👥 Members: {len(guild.members)}/{GUILD_MAX_MEMBERS}\n"
                f"💪 Total Power: {total_power:,}\n"
                f"🎁 XP Bonus: +10% for all members\n"
                "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📋 MEMBERS:\n{member_text}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            )
            await message.reply_text(text)
        return

    # ── /guild members ────────────────────────────────────
    if sub == "members":
        guild = await db.get_user_guild(user.id)
        if not guild:
            await message.reply_text("⚠️ You don't belong to any guild.")
            return

        member_lines = []
        for uid in guild.members:
            h = await db.get_hunter(uid)
            if h:
                rank_emoji = {
                    "E": "🅴", "D": "🅳", "C": "🅲", "B": "🅱️", "A": "🅰️",
                    "S": "⭐", "SS": "🌟", "SSS": "💫", "National Level": "🔱", "Monarch": "👑"
                }.get(h.rank, "")
                role = "👑 Owner" if uid == guild.owner_id else "⚔️ Member"
                member_lines.append(f"{role} — {h.display_full_name} | Lv.{h.level} {rank_emoji}{h.rank} | ⚡{h.power}")

        text = (
            f"🏰 {guild.name} — Members ({len(guild.members)}/{GUILD_MAX_MEMBERS})\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(member_lines) +
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await message.reply_text(text)
        return

    # ── /guild kick <user> ────────────────────────────────
    if sub == "kick":
        guild = await db.get_user_guild(user.id)
        if not guild:
            await message.reply_text("⚠️ You don't belong to any guild.")
            return

        if guild.owner_id != user.id:
            await message.reply_text("⚠️ Only the guild owner can kick members.")
            return

        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.reply_text("⚠️ Reply to a member's message to kick them.")
            return

        target = message.reply_to_message.from_user
        if target.id == user.id:
            await message.reply_text("⚠️ You can't kick yourself. Use /guild disband instead.")
            return

        if target.id not in guild.members:
            await message.reply_text(f"⚠️ {target.first_name} is not in your guild.")
            return

        await db.remove_guild_member(guild.guild_id, target.id)
        await message.reply_text(f"👢 {target.first_name} has been kicked from **{guild.name}**.", parse_mode="markdown")
        return

    # ── /guild disband ────────────────────────────────────
    if sub == "disband":
        guild = await db.get_user_guild(user.id)
        if not guild:
            await message.reply_text("⚠️ You don't belong to any guild.")
            return

        if guild.owner_id != user.id:
            await message.reply_text("⚠️ Only the guild owner can disband the guild.")
            return

        guild_name = guild.name
        await db.delete_guild(guild.guild_id)
        await message.reply_text(f"🏰 **{guild_name}** has been disbanded.", parse_mode="markdown")
        return

    # ── /guild edit <desc> ────────────────────────────────
    if sub == "edit":
        guild = await db.get_user_guild(user.id)
        if not guild:
            await message.reply_text("⚠️ You don't belong to any guild.")
            return

        if guild.owner_id != user.id:
            await message.reply_text("⚠️ Only the guild owner can edit the description.")
            return

        desc = " ".join(args[1:]).strip()
        if not desc:
            await message.reply_text("Usage: /guild edit <description>")
            return

        if len(desc) > 200:
            await message.reply_text("Description must be 200 characters or less.")
            return

        guild.description = desc
        await db.save_guild(guild.guild_id)
        await message.reply_text(f"📝 Guild description updated:\n\n{desc}")
        return

    # Unknown subcommand
    await message.reply_text("Unknown guild command. Use /guild to see available commands.")
