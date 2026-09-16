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
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from pyrogram.errors import BadRequest

from channel_db import ChannelDB
from config import GUILD_MAX_MEMBERS
from models import Guild
from game.formatting import format_not_registered
from game.font_manager import clean_and_normalize_name
from game.guild_image import render_guild_image
from game.guild_leaderboard_image import render_guild_leaderboard_image
from handlers import guild_war

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
            "/guild top — Top 10 guilds leaderboard\n"
            "/guild war <name> — Challenge a guild to war\n"
            "/guild kick — Kick a member (owner only)\n"
            "/guild disband — Delete your guild (owner only)\n"
            "/guild edit <desc> — Edit description (owner only)\n\n"
            "🎁 GIFT COMMANDS\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "/gift item <id> @user — Gift an item to a guildmate\n"
            "/gift gold <amount> @user — Gift gold to a guildmate\n"
            "Or reply to a guildmate's message with /gift item <id>\n\n"
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
        if len(guild_name.split()) < 1 or len(guild_name.split()) > 4:
            await message.reply_text("Guild name must be 1-4 words long.")
            return

        if hunter.guild_id:
            await message.reply_text("⚠️ You already belong to a guild! Leave it first with /guild leave.")
            return

        if await db.guild_name_exists(guild_name):
            await message.reply_text(f"❌ A guild named **{guild_name}** already exists!", parse_mode=ParseMode.MARKDOWN)
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
            parse_mode=ParseMode.MARKDOWN,
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
            await message.reply_text(f"❌ No guild named **{guild_name}** found.", parse_mode=ParseMode.MARKDOWN)
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
                parse_mode=ParseMode.MARKDOWN,
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
        await message.reply_text(f"🚪 You have left **{guild.name}**.", parse_mode=ParseMode.MARKDOWN)
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
        await message.reply_text(f"👢 {target.first_name} has been kicked from **{guild.name}**.", parse_mode=ParseMode.MARKDOWN)
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
        await message.reply_text(f"🏰 **{guild_name}** has been disbanded.", parse_mode=ParseMode.MARKDOWN)
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

    # ── /guild top — guild leaderboard ────────────────────
    if sub == "top":
        await handle_top(client, message)
        return

    # ── /guild war — guild war system ─────────────────────
    if sub == "war":
        await guild_war.handle_war(client, message)
        return

    # Unknown subcommand
    await message.reply_text("Unknown guild command. Use /guild to see available commands.")


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
        await message.reply_text(format_not_registered())
        return

    if not args:
        await message.reply_text(
            "╔══════════════════════════════╗\n"
            "║   🎁 GUILD GIFT SYSTEM       ║\n"
            "╚══════════════════════════════╝\n\n"
            "Gift items and gold to your guildmates!\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "/gift item <id> @user — Gift an item\n"
            "/gift gold <amount> @user — Gift gold\n\n"
            "💡 Tip: Reply to a guildmate's message\n"
            "with /gift item <id> for quick gifting!\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "「 Sharing strength is the mark of a true guild. 」"
        )
        return

    gift_type = args[0].lower()
    if gift_type not in ("item", "gold"):
        await message.reply_text("Usage: /gift item <id> or /gift gold <amount>\nExample: /gift item 3 (reply to recipient)")
        return

    # Verify sender is in a guild
    sender_guild = await db.get_user_guild(user.id)
    if not sender_guild:
        await message.reply_text("⚠️ You must be in a guild to gift. Create one with /guild create.")
        return

    # ── /gift gold <amount> ──────────────────────────────
    if gift_type == "gold":
        if len(args) < 2:
            await message.reply_text("Usage: /gift gold <amount> @user\nExample: /gift gold 500 (reply to recipient)")
            return

        try:
            amount = int(args[1])
        except ValueError:
            await message.reply_text("❌ Invalid gold amount. Use a whole number.")
            return

        if amount <= 0:
            await message.reply_text("❌ Gold amount must be positive.")
            return

        if sender.gold < amount:
            await message.reply_text(f"❌ You don't have enough gold! You have {sender.gold:,}💰.")
            return

        recipient_id, err = _resolve_recipient(message, args)
        if err:
            await message.reply_text(err)
            return

        if recipient_id == user.id:
            await message.reply_text("⚠️ You can't gift gold to yourself.")
            return

        # Verify recipient is in same guild
        if recipient_id not in sender_guild.members:
            await message.reply_text("⚠️ That hunter is not in your guild.")
            return

        recipient = await db.get_hunter(recipient_id)
        if not recipient:
            await message.reply_text("⚠️ That hunter hasn't registered yet.")
            return

        # Transfer gold
        sender.gold -= amount
        recipient.gold += amount
        await db.save_hunter(user.id)
        await db.save_hunter(recipient_id)

        await message.reply_text(
            f"🎁 **{sender.display_full_name}** gifted **{amount:,}💰** to **{recipient.display_full_name}**!\n\n"
            f"Your balance: {sender.gold:,}💰\n"
            f"Their balance: {recipient.gold:,}💰",
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(f"Gold gift: {sender.hunter_name} -> {recipient.hunter_name}: {amount} gold")
        return

    # ── /gift item <id> ──────────────────────────────────
    if gift_type == "item":
        if len(args) < 2:
            await message.reply_text("Usage: /gift item <id> @user\nExample: /gift item 3 (reply to recipient)")
            return

        try:
            item_id = int(args[1])
        except ValueError:
            await message.reply_text("❌ Invalid item ID. Use a number (e.g., /gift item 3).")
            return

        recipient_id, err = _resolve_recipient(message, args)
        if err:
            await message.reply_text(err)
            return

        if recipient_id == user.id:
            await message.reply_text("⚠️ You can't gift items to yourself.")
            return

        # Verify recipient is in same guild
        if recipient_id not in sender_guild.members:
            await message.reply_text("⚠️ That hunter is not in your guild.")
            return

        recipient = await db.get_hunter(recipient_id)
        if not recipient:
            await message.reply_text("⚠️ That hunter hasn't registered yet.")
            return

        # Check sender has the item
        sender_inv = await db.get_inventory(user.id)
        item = sender_inv.get_item(item_id)
        if not item:
            await message.reply_text(f"❌ No item with ID {item_id} found in your inventory.")
            return

        if item.is_equipped:
            await message.reply_text("⚠️ Unequip the item first before gifting it!")
            return

        # Remove from sender, add to receiver
        removed = sender_inv.remove_item(item_id)
        if not removed:
            await message.reply_text("❌ Failed to remove item from inventory.")
            return

        recipient_inv = await db.get_inventory(recipient_id)
        recipient_inv.add_item(removed)

        # Save both inventories
        await db.save_inventory(user.id)
        await db.save_inventory(recipient_id)

        rarity_emoji = {
            "Common": "⚪", "Uncommon": "🟢", "Rare": "🔵",
            "Epic": "🟣", "Legendary": "🟡", "Mythic": "🔴",
        }.get(removed.rarity, "⚪")

        await message.reply_text(
            f"🎁 **{sender.display_full_name}** gifted **{rarity_emoji} {removed.name}** to **{recipient.display_full_name}**!\n\n"
            f"Item: {removed.stat_summary()}\n"
            f"Type: {removed.type.title()} | Rarity: {removed.rarity}",
            parse_mode=ParseMode.MARKDOWN,
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
    def btn_label(cat: str, icon: str, name: str) -> str:
        return f"[ {icon} {name} ]" if cat == active_cat else f"{icon} {name}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(btn_label("power", "⚡", "Power"), callback_data="glb_power"),
            InlineKeyboardButton(btn_label("level", "🏆", "Level"), callback_data="glb_level"),
        ],
        [
            InlineKeyboardButton(btn_label("wealth", "💰", "Gold"), callback_data="glb_wealth"),
            InlineKeyboardButton(btn_label("members", "👥", "Members"), callback_data="glb_members"),
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
        await message.reply_text(
            "╔══════════════════════════════╗\n"
            "║   ⚡ SYSTEM NOTIFICATION ⚡   ║\n"
            "║    GUILD LEADERBOARD         ║\n"
            "╚══════════════════════════════╝\n\n"
            "No guilds have been established yet!\n"
            "Use /guild create <name> to found a guild."
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
        caption = f"🏰 Guild Leaderboard — Top Guilds [{cat_name}]"
        await message.reply_photo(
            photo=photo_buf,
            caption=caption,
            reply_markup=_glb_keyboard(category),
        )
    except Exception as exc:
        logger.error("Failed to render guild leaderboard image: %s", exc, exc_info=True)
        await message.reply_text("❌ System Error: Failed to render guild leaderboard. Please try again later.")


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
        caption = f"🏰 Guild Leaderboard — Top Guilds [{cat_name}]"

        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption),
                reply_markup=_glb_keyboard(category),
            )
        elif query.message:
            await query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=_glb_keyboard(category),
            )
    except BadRequest as br_err:
        if "Message is not modified" not in str(br_err):
            logger.warning("BadRequest during guild leaderboard update: %s", br_err)
    except Exception as exc:
        logger.error("Failed to update guild leaderboard tab: %s", exc, exc_info=True)
