"""
handlers/admin.py — Superadmin & Bot Owner Control Console.

Provides executive administration commands strictly restricted to the bot owner
and authorized superadmins (configured via OWNER_ID / SUPERADMIN_IDS in .env):
- /addgold / /addcoins — Credit gold/coins to self or another hunter
- /addxp / /addep — Grant Hunter XP / EP with automatic level-up & rank progression
- /setgold / /setcoins — Set exact gold balance
- /setlevel — Modify hunter level with stat recalculation & rank checks
- /inspect — Deep-inspection of hunter attributes, raw telemetry & cooldowns
- /admin / /superadmin — Display the Superadmin Directive manual
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import Message

import config
from config import RANKS, RANK_LEVEL_THRESHOLDS, BASE_HP
from game.hunter import add_xp, check_rank_up, xp_for_level
from game.formatting import _stat_bar, _rank_badge
from models import Hunter

logger = logging.getLogger(__name__)


def is_superadmin(user_id: int) -> bool:
    """Check if the given Telegram user ID is an authorized superadmin or bot owner."""
    if not user_id:
        return False
    if config.OWNER_ID and user_id == config.OWNER_ID:
        return True
    return user_id in config.SUPERADMIN_IDS


async def _resolve_hunter_and_int(
    client: Client, message: Message, default_self: bool = True
) -> Tuple[Optional[Hunter], Optional[int], Optional[str]]:
    """
    Intelligently resolve the target Hunter and numeric parameter from message context.
    
    Supported syntaxes:
    - Replied to user message:
        /cmd <number>
    - Direct command with explicit user ID / username:
        /cmd <number> <user_id|@username>
        /cmd <user_id|@username> <number>
    - Command for self:
        /cmd <number>
    """
    user = message.from_user
    if not user:
        return None, None, "User context not found."

    db = client.db
    args = message.command[1:] if len(message.command) > 1 else []
    reply = message.reply_to_message

    target_hunter: Optional[Hunter] = None
    numeric_val: Optional[int] = None

    # Case 1: Message is a reply
    if reply and reply.from_user:
        target_uid = reply.from_user.id
        target_hunter = await db.get_hunter(target_uid)
        if not target_hunter:
            return None, None, f"❌ Target user (ID: {target_uid}) has not awakened as a Hunter yet (/start)."

        if not args:
            return target_hunter, None, None
        try:
            numeric_val = int(args[0])
            return target_hunter, numeric_val, None
        except ValueError:
            return None, None, f"❌ Invalid numeric value '{args[0]}'."

    # Case 2: No reply, parse from args
    if not args:
        if default_self:
            self_hunter = await db.get_hunter(user.id)
            if not self_hunter:
                return None, None, "❌ You must awaken as a Hunter first with /start."
            return self_hunter, None, None
        return None, None, "❌ Missing required arguments."

    # Sub-case: 1 argument provided
    if len(args) == 1:
        # Check if argument is a numeric value (intended for self)
        if args[0].lstrip("-").isdigit():
            numeric_val = int(args[0])
            if default_self:
                self_hunter = await db.get_hunter(user.id)
                if not self_hunter:
                    return None, None, "❌ You must awaken as a Hunter first with /start."
                return self_hunter, numeric_val, None
            return None, numeric_val, None
        
        # Or argument is a username / user_id (for inspect)
        target_identifier = args[0]
        target_hunter = await _find_hunter_by_identifier(db, target_identifier)
        if not target_hunter:
            return None, None, f"❌ Hunter '{target_identifier}' not found in the System database."
        return target_hunter, None, None

    # Sub-case: 2 arguments provided (Amount & Target in either order)
    arg0, arg1 = args[0], args[1]
    
    # 1. Try arg1 as target, arg0 as amount
    h1 = await _find_hunter_by_identifier(db, arg1)
    if h1 and arg0.lstrip("-").isdigit():
        return h1, int(arg0), None

    # 2. Try arg0 as target, arg1 as amount
    h0 = await _find_hunter_by_identifier(db, arg0)
    if h0 and arg1.lstrip("-").isdigit():
        return h0, int(arg1), None

    # 3. If neither resolved in DB, try by digit/string pattern
    if arg0.lstrip("-").isdigit() and not arg1.lstrip("-").isdigit():
        val = int(arg0)
        h = await _find_hunter_by_identifier(db, arg1)
        if not h:
            return None, None, f"❌ Target Hunter '{arg1}' not found."
        return h, val, None

    if arg1.lstrip("-").isdigit() and not arg0.lstrip("-").isdigit():
        val = int(arg1)
        h = await _find_hunter_by_identifier(db, arg0)
        if not h:
            return None, None, f"❌ Target Hunter '{arg0}' not found."
        return h, val, None

    if arg0.lstrip("-").isdigit() and arg1.lstrip("-").isdigit():
        # Default order: <amount> <user_id>
        val = int(arg0)
        h = await _find_hunter_by_identifier(db, arg1)
        if not h:
            return None, None, f"❌ Target Hunter with ID '{arg1}' not found in database."
        return h, val, None

    return None, None, "❌ Syntax: /cmd <amount> [user_id|@username] or reply to a user's message."


async def _find_hunter_by_identifier(db, identifier: str) -> Optional[Hunter]:
    """Find a hunter by numeric user ID or username."""
    clean_id = identifier.strip().lstrip("@")
    if clean_id.isdigit():
        h = await db.get_hunter(int(clean_id))
        if h:
            return h

    # Search cache by username
    all_hunters = await db.get_all_hunters()
    for h in all_hunters:
        if h.username and h.username.lower() == clean_id.lower():
            return h
        if h.hunter_name and h.hunter_name.lower() == clean_id.lower():
            return h

    return None


# ── COMMAND: /admin or /superadmin ───────────────────────────────────────────
async def handle_admin_help(client: Client, message: Message) -> None:
    """Display Superadmin Executive Control Console instructions."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ **Access Denied**: This command is restricted to the Bot Owner & Superadmins.")
        return

    text = (
        "👑 **SYSTEM SUPERADMIN CONSOLE**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "**Executive Hunter Management & Balances**\n\n"
        "⚡ **Gold & Economy Controls:**\n"
        "• `/addgold <amount>` — Add gold to your own treasury\n"
        "• `/addgold <amount> <user_id|@username>` — Credit gold to target Hunter\n"
        "• `/setgold <amount> [target]` — Overwrite exact gold balance\n"
        "*(Aliases: `/addcoins`, `/setcoins`)*\n\n"
        "✨ **XP & Level Progression:**\n"
        "• `/addxp <amount>` — Grant XP to yourself (triggers level & rank ups)\n"
        "• `/addxp <amount> <user_id|@username>` — Grant XP to target Hunter\n"
        "• `/setlevel <level> [target]` — Force set hunter level & stats\n"
        "*(Aliases: `/addep`, `/setep`)*\n\n"
        "🔍 **Diagnostics & Inspection:**\n"
        "• `/inspect [user_id|@username]` — Deep telemetry & raw attributes\n\n"
        "💡 *Tip: You can also simply reply to any user's message with `/addgold 50000` or `/addxp 2500`.*"
    )
    await message.reply_text(text)


# ── COMMAND: /addgold / /addcoins ─────────────────────────────────────────────
async def handle_add_gold(client: Client, message: Message) -> None:
    """Add gold to self or specified hunter."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ **Access Denied**: This command is restricted to the Bot Owner & Superadmins.")
        return

    target_hunter, amount, err = await _resolve_hunter_and_int(client, message, default_self=True)
    if err:
        await message.reply_text(err)
        return
    if amount is None:
        await message.reply_text("❌ Please specify the amount of gold to add.\nExample: `/addgold 50000`")
        return

    old_gold = target_hunter.gold
    target_hunter.gold = max(0, target_hunter.gold + amount)
    await client.db.save_hunter(target_hunter)

    verb = "Credited" if amount >= 0 else "Deducted"
    abs_amt = abs(amount)

    text = (
        "💰 **SYSTEM TREASURY TRANSACTION**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Hunter:** {target_hunter.hunter_name} (`{target_hunter.user_id}`)\n"
        f"⚡ **Adjustment:** {verb} **{abs_amt:,}** Gold\n"
        f"📊 **Previous Balance:** {old_gold:,} 💰\n"
        f"💎 **New Balance:** **{target_hunter.gold:,}** 💰\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ *Database synchronized successfully.*"
    )
    await message.reply_text(text)
    logger.info(f"Superadmin {user.id} modified gold for {target_hunter.user_id} by {amount} (New: {target_hunter.gold})")


# ── COMMAND: /setgold ────────────────────────────────────────────────────────
async def handle_set_gold(client: Client, message: Message) -> None:
    """Set exact gold amount for self or specified hunter."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ **Access Denied**: This command is restricted to the Bot Owner & Superadmins.")
        return

    target_hunter, amount, err = await _resolve_hunter_and_int(client, message, default_self=True)
    if err:
        await message.reply_text(err)
        return
    if amount is None or amount < 0:
        await message.reply_text("❌ Please specify a valid non-negative gold amount.\nExample: `/setgold 100000`")
        return

    old_gold = target_hunter.gold
    target_hunter.gold = amount
    await client.db.save_hunter(target_hunter)

    text = (
        "💰 **SYSTEM TREASURY OVERWRITE**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Hunter:** {target_hunter.hunter_name} (`{target_hunter.user_id}`)\n"
        f"📊 **Previous Balance:** {old_gold:,} 💰\n"
        f"💎 **New Set Balance:** **{target_hunter.gold:,}** 💰\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ *Database synchronized successfully.*"
    )
    await message.reply_text(text)
    logger.info(f"Superadmin {user.id} set gold for {target_hunter.user_id} to {amount}")


# ── COMMAND: /addxp / /addep ──────────────────────────────────────────────────
async def handle_add_xp(client: Client, message: Message) -> None:
    """Grant XP/EP to self or specified hunter with progression handling."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ **Access Denied**: This command is restricted to the Bot Owner & Superadmins.")
        return

    target_hunter, amount, err = await _resolve_hunter_and_int(client, message, default_self=True)
    if err:
        await message.reply_text(err)
        return
    if amount is None or amount <= 0:
        await message.reply_text("❌ Please specify a positive XP amount to add.\nExample: `/addxp 5000`")
        return

    old_level = target_hunter.level
    old_rank = target_hunter.rank
    old_power = target_hunter.power

    leveled_up, new_rank = add_xp(target_hunter, amount)
    await client.db.save_hunter(target_hunter)

    level_notice = ""
    if leveled_up:
        level_notice = f"\n🆙 **LEVEL UP!** Lv {old_level} ➜ **Lv {target_hunter.level}**"
    if new_rank:
        level_notice += f"\n🌟 **RANK PROMOTION!** Rank {old_rank} ➜ **Rank {new_rank}**"

    text = (
        "✨ **SYSTEM ENERGY INFUSION (XP / EP)**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Hunter:** {target_hunter.hunter_name} (`{target_hunter.user_id}`)\n"
        f"⚡ **XP Injected:** +**{amount:,}** XP\n"
        f"📊 **Current Progress:** {target_hunter.xp} / {target_hunter.xp_needed} XP\n"
        f"🏅 **Rank & Level:** [{target_hunter.rank}] Lv **{target_hunter.level}**\n"
        f"⚔️ **Combat Power:** {old_power} ➜ **{target_hunter.power}**"
        f"{level_notice}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ *Database synchronized successfully.*"
    )
    await message.reply_text(text)
    logger.info(f"Superadmin {user.id} granted {amount} XP to {target_hunter.user_id} (New Lv: {target_hunter.level})")


# ── COMMAND: /setlevel ───────────────────────────────────────────────────────
async def handle_set_level(client: Client, message: Message) -> None:
    """Force set hunter level with stat recalculation and rank checks."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ **Access Denied**: This command is restricted to the Bot Owner & Superadmins.")
        return

    target_hunter, new_lvl, err = await _resolve_hunter_and_int(client, message, default_self=True)
    if err:
        await message.reply_text(err)
        return
    if new_lvl is None or new_lvl < 1 or new_lvl > 500:
        await message.reply_text("❌ Please specify a valid level between 1 and 500.\nExample: `/setlevel 50`")
        return

    old_lvl = target_hunter.level
    target_hunter.level = new_lvl
    target_hunter.xp = 0
    target_hunter.xp_needed = xp_for_level(new_lvl)

    # Scale base attributes proportionally if level changed
    diff = new_lvl - old_lvl
    if diff != 0:
        stat_delta = max(0, diff * 2)
        target_hunter.str_stat = max(5, target_hunter.str_stat + stat_delta)
        target_hunter.agi = max(5, target_hunter.agi + stat_delta)
        target_hunter.vit = max(5, target_hunter.vit + stat_delta)
        target_hunter.int_stat = max(5, target_hunter.int_stat + stat_delta)
        target_hunter.per = max(5, target_hunter.per + stat_delta)

    target_hunter.max_hp = BASE_HP + (target_hunter.vit * 5)
    target_hunter.hp = target_hunter.max_hp
    target_hunter.recalculate_power()
    check_rank_up(target_hunter)

    await client.db.save_hunter(target_hunter)

    text = (
        "👑 **SYSTEM LEVEL OVERRIDE**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Hunter:** {target_hunter.hunter_name} (`{target_hunter.user_id}`)\n"
        f"📊 **Level Adjustment:** Lv {old_lvl} ➜ **Lv {target_hunter.level}**\n"
        f"🏅 **Rank:** {target_hunter.rank}\n"
        f"❤️ **Max HP:** {target_hunter.max_hp} | ⚔️ **Power:** {target_hunter.power}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ *Database synchronized successfully.*"
    )
    await message.reply_text(text)
    logger.info(f"Superadmin {user.id} set level for {target_hunter.user_id} to {new_lvl}")


# ── COMMAND: /inspect ────────────────────────────────────────────────────────
async def handle_inspect(client: Client, message: Message) -> None:
    """Deep inspection of hunter attributes and raw database record."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ **Access Denied**: This command is restricted to the Bot Owner & Superadmins.")
        return

    db = client.db
    reply = message.reply_to_message
    args = message.command[1:] if len(message.command) > 1 else []

    target_hunter = None
    if reply and reply.from_user:
        target_hunter = await db.get_hunter(reply.from_user.id)
    elif args:
        target_hunter = await _find_hunter_by_identifier(db, args[0])
    else:
        target_hunter = await db.get_hunter(user.id)

    if not target_hunter:
        ident = args[0] if args else "Target"
        await message.reply_text(f"❌ Hunter '{ident}' not found in the System database.")
        return

    inv = await client.db.get_inventory(target_hunter.user_id)
    inv_count = len(inv.items) if inv else 0
    equipped = sum(1 for it in inv.items if it.is_equipped) if inv else 0

    text = (
        f"🔍 **HUNTER TELEMETRY DOSSIER**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Name:** {target_hunter.hunter_name}\n"
        f"🆔 **User ID:** `{target_hunter.user_id}`\n"
        f"🏷 **Username:** @{target_hunter.username or 'None'}\n"
        f"🏅 **Rank:** [{target_hunter.rank}] | **Level:** Lv {target_hunter.level}\n"
        f"✨ **XP:** {target_hunter.xp:,} / {target_hunter.xp_needed:,}\n"
        f"💰 **Gold:** {target_hunter.gold:,} 💰\n"
        f"⚔️ **Combat Power:** {target_hunter.power:,}\n"
        f"❤️ **HP:** {target_hunter.hp} / {target_hunter.max_hp}\n\n"
        f"📊 **Base Attributes:**\n"
        f"• STR: {target_hunter.str_stat} ┊ AGI: {target_hunter.agi}\n"
        f"• VIT: {target_hunter.vit} ┊ INT: {target_hunter.int_stat} ┊ PER: {target_hunter.per}\n\n"
        f"🎒 **Inventory:** {inv_count} items ({equipped} equipped)\n"
        f"🏰 **Guild ID:** {target_hunter.guild_id or 'None'}\n"
        f"⚔️ **Duels:** {target_hunter.duel_wins}W - {target_hunter.duel_losses}L\n"
        f"👹 **Gate Hunts:** {target_hunter.victories}W - {target_hunter.defeats}L (Total: {target_hunter.total_hunts})\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await message.reply_text(text)
