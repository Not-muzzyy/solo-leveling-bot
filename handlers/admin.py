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

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
from typing import Optional, Tuple

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client, filters, enums
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from config import RANKS, RANK_LEVEL_THRESHOLDS, BASE_HP
from game.hunter import add_xp, check_rank_up, xp_for_level
from game.formatting import _stat_bar, _rank_badge
from game.rich_text import escape_html
from game.shop import get_shop_item, create_item_from_shop, SHOP_ITEMS
from models import Hunter, RedeemCode, Item

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
            return None, None, f"❌ Target user (ID: <code>{target_uid}</code>) has not awakened as a Hunter yet (<code>/start</code>)."

        if not args:
            return target_hunter, None, None
        try:
            numeric_val = int(args[0])
            return target_hunter, numeric_val, None
        except ValueError:
            return None, None, f"❌ Invalid numeric value '<code>{escape_html(args[0])}</code>'."

    # Case 2: No reply, parse from args
    if not args:
        if default_self:
            self_hunter = await db.get_hunter(user.id)
            if not self_hunter:
                return None, None, "❌ You must awaken as a Hunter first with <code>/start</code>."
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
                    return None, None, "❌ You must awaken as a Hunter first with <code>/start</code>."
                return self_hunter, numeric_val, None
            return None, numeric_val, None
        
        # Or argument is a username / user_id (for inspect)
        target_identifier = args[0]
        target_hunter = await _find_hunter_by_identifier(db, target_identifier)
        if not target_hunter:
            return None, None, f"❌ Hunter '<code>{escape_html(target_identifier)}</code>' not found in the System database."
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
            return None, None, f"❌ Target Hunter '<code>{escape_html(arg1)}</code>' not found."
        return h, val, None

    if arg1.lstrip("-").isdigit() and not arg0.lstrip("-").isdigit():
        val = int(arg1)
        h = await _find_hunter_by_identifier(db, arg0)
        if not h:
            return None, None, f"❌ Target Hunter '<code>{escape_html(arg0)}</code>' not found."
        return h, val, None

    if arg0.lstrip("-").isdigit() and arg1.lstrip("-").isdigit():
        # Default order: <amount> <user_id>
        val = int(arg0)
        h = await _find_hunter_by_identifier(db, arg1)
        if not h:
            return None, None, f"❌ Target Hunter with ID '<code>{escape_html(arg1)}</code>' not found in database."
        return h, val, None

    return None, None, "❌ Syntax: <code>/cmd &lt;amount&gt; [user_id|@username]</code> or reply to a user's message."


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
        await message.reply_text("⛔ <b>Access Denied</b>: This command is restricted to the Bot Owner & Superadmins.", parse_mode=enums.ParseMode.HTML)
        return

    text = (
        "<b>[ SYSTEM CONTROL // SUPERADMIN CONSOLE ]</b>\n"
        "<b>관리자 제어 // 최고 관리자 터미널</b>\n\n"
        "<i>Executive Hunter Management & Balances</i>\n\n"
        "<blockquote expandable>"
        "⚡ <b>Gold & Economy Controls:</b>\n"
        "• <code>/addgold &lt;amount&gt;</code> — Add gold to your own treasury\n"
        "• <code>/addgold &lt;amount&gt; &lt;user_id|@username&gt;</code> — Credit gold to target Hunter\n"
        "• <code>/setgold &lt;amount&gt; [target]</code> — Overwrite exact gold balance\n"
        "<i>(Aliases: <code>/addcoins</code>, <code>/setcoins</code>)</i>\n"
        "</blockquote>\n\n"
        "<blockquote expandable>"
        "✨ <b>XP & Level Progression:</b>\n"
        "• <code>/addxp &lt;amount&gt;</code> — Grant XP to yourself (triggers level & rank ups)\n"
        "• <code>/addxp &lt;amount&gt; &lt;user_id|@username&gt;</code> — Grant XP to target Hunter\n"
        "• <code>/setlevel &lt;level&gt; [target]</code> — Force set hunter level & stats\n"
        "<i>(Aliases: <code>/addep</code>, <code>/setep</code>)</i>\n"
        "</blockquote>\n\n"
        "<blockquote expandable>"
        "🎁 <b>Promo & Gift Code System:</b>\n"
        "• <code>/createcode gold &lt;CODE&gt; &lt;amount&gt; [max_uses]</code> — Forge gold gift code\n"
        "• <code>/createcode item &lt;CODE&gt; &lt;shop_key&gt; [max_uses]</code> — Forge item code\n"
        "• <code>/createcode custom &lt;CODE&gt; &lt;type&gt; &lt;rarity&gt; &lt;name&gt; &lt;atk&gt; &lt;def&gt; &lt;hp&gt; [max_uses]</code>\n"
        "• <code>/createcode xp &lt;CODE&gt; &lt;amount&gt; [max_uses]</code> — Forge XP promo code\n"
        "• <code>/listcodes</code> (or <code>/codes</code>) — View all promo codes & telemetry\n"
        "• <code>/deletecode &lt;CODE&gt;</code> — Purge / revoke a promo code\n"
        "</blockquote>\n\n"
        "<blockquote expandable>"
        "🔍 <b>Diagnostics & Inspection:</b>\n"
        "• <code>/inspect [user_id|@username]</code> — Deep telemetry & raw attributes\n"
        "</blockquote>\n\n"
        "<blockquote expandable>"
        "🚀 <b>Lifecycle & Remote Updates:</b>\n"
        "• <code>/update</code> — Check remote git commits, changed files & code lines\n"
        "• <code>/restart</code> — Pull latest commits & reboot bot process\n"
        "• <code>/stop</code> (or <code>/shutdown</code>) — Terminate & kill bot process\n"
        "</blockquote>\n\n"
        "<blockquote>💡 <i>Tip: Reply to any message with <code>/addgold 50000</code> or <code>/addxp 2500</code>.</i></blockquote>"
    )
    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)


# ── COMMAND: /addgold / /addcoins ─────────────────────────────────────────────
async def handle_add_gold(client: Client, message: Message) -> None:
    """Add gold to self or specified hunter."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ <b>Access Denied</b>: This command is restricted to the Bot Owner & Superadmins.", parse_mode=enums.ParseMode.HTML)
        return

    target_hunter, amount, err = await _resolve_hunter_and_int(client, message, default_self=True)
    if err:
        await message.reply_text(err, parse_mode=enums.ParseMode.HTML)
        return
    if amount is None:
        await message.reply_text("❌ Please specify the amount of gold to add.\nExample: <code>/addgold 50000</code>", parse_mode=enums.ParseMode.HTML)
        return

    old_gold = target_hunter.gold
    target_hunter.gold = max(0, target_hunter.gold + amount)
    await client.db.save_hunter(target_hunter)

    verb = "Credited" if amount >= 0 else "Deducted"
    abs_amt = abs(amount)
    h_name = escape_html(target_hunter.hunter_name)

    text = (
        "<b>[ SYSTEM NOTIFICATION // TREASURY TRANSACTION ]</b>\n"
        "<b>자금 조정 // 국고 잔액 변경</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} (<code>{target_hunter.user_id}</code>)\n"
        f"⚡ <b>Adjustment:</b> {verb} <b>{abs_amt:,}</b> Gold\n\n"
        "<blockquote expandable>"
        f"• Previous Balance: <code>{old_gold:,}</code> 💰\n"
        f"• New Balance: <b>{target_hunter.gold:,}</b> 💰\n"
        "</blockquote>\n\n"
        "<i>✅ Database synchronized successfully.</i>"
    )
    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
    logger.info(f"Superadmin {user.id} modified gold for {target_hunter.user_id} by {amount} (New: {target_hunter.gold})")


# ── COMMAND: /setgold ────────────────────────────────────────────────────────
async def handle_set_gold(client: Client, message: Message) -> None:
    """Set exact gold amount for self or specified hunter."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ <b>Access Denied</b>: This command is restricted to the Bot Owner & Superadmins.", parse_mode=enums.ParseMode.HTML)
        return

    target_hunter, amount, err = await _resolve_hunter_and_int(client, message, default_self=True)
    if err:
        await message.reply_text(err, parse_mode=enums.ParseMode.HTML)
        return
    if amount is None or amount < 0:
        await message.reply_text("❌ Please specify a valid non-negative gold amount.\nExample: <code>/setgold 100000</code>", parse_mode=enums.ParseMode.HTML)
        return

    old_gold = target_hunter.gold
    target_hunter.gold = amount
    await client.db.save_hunter(target_hunter)

    h_name = escape_html(target_hunter.hunter_name)
    text = (
        "<b>[ SYSTEM NOTIFICATION // TREASURY OVERWRITE ]</b>\n"
        "<b>자금 재설정 // 국고 강제 조정</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} (<code>{target_hunter.user_id}</code>)\n\n"
        "<blockquote expandable>"
        f"• Previous Balance: <code>{old_gold:,}</code> 💰\n"
        f"• Set Balance: <b>{target_hunter.gold:,}</b> 💰\n"
        "</blockquote>\n\n"
        "<i>✅ Database synchronized successfully.</i>"
    )
    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
    logger.info(f"Superadmin {user.id} set gold for {target_hunter.user_id} to {amount}")


# ── COMMAND: /addxp / /addep ──────────────────────────────────────────────────
async def handle_add_xp(client: Client, message: Message) -> None:
    """Grant XP/EP to self or specified hunter with progression handling."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ <b>Access Denied</b>: This command is restricted to the Bot Owner & Superadmins.", parse_mode=enums.ParseMode.HTML)
        return

    target_hunter, amount, err = await _resolve_hunter_and_int(client, message, default_self=True)
    if err:
        await message.reply_text(err, parse_mode=enums.ParseMode.HTML)
        return
    if amount is None or amount <= 0:
        await message.reply_text("❌ Please specify a positive XP amount to add.\nExample: <code>/addxp 5000</code>", parse_mode=enums.ParseMode.HTML)
        return

    old_level = target_hunter.level
    old_rank = target_hunter.rank
    old_power = target_hunter.power

    leveled_up, new_rank = add_xp(target_hunter, amount)
    await client.db.save_hunter(target_hunter)

    level_notice = ""
    if leveled_up:
        level_notice = f"\n• 🆙 <b>LEVEL UP!</b> Lv {old_level} ➜ <b>Lv {target_hunter.level}</b>"
    if new_rank:
        level_notice += f"\n• 🌟 <b>RANK PROMOTION!</b> Rank {old_rank} ➜ <b>Rank {new_rank}</b>"

    h_name = escape_html(target_hunter.hunter_name)
    text = (
        "<b>[ SYSTEM NOTIFICATION // ENERGY INFUSION ]</b>\n"
        "<b>마력 주입 // 경험치 직접 지급</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} (<code>{target_hunter.user_id}</code>)\n"
        f"⚡ <b>XP Injected:</b> +<b>{amount:,}</b> XP\n\n"
        "<blockquote expandable>"
        f"• Progress: <code>{target_hunter.xp} / {target_hunter.xp_needed} XP</code>\n"
        f"• Rank & Level: [<code>{target_hunter.rank}</code>] Lv <b>{target_hunter.level}</b>\n"
        f"• Combat Power: <code>{old_power}</code> ➜ <b>{target_hunter.power}</b>"
        f"{level_notice}\n"
        "</blockquote>\n\n"
        "<i>✅ Database synchronized successfully.</i>"
    )
    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
    logger.info(f"Superadmin {user.id} granted {amount} XP to {target_hunter.user_id} (New Lv: {target_hunter.level})")


# ── COMMAND: /setlevel ───────────────────────────────────────────────────────
async def handle_set_level(client: Client, message: Message) -> None:
    """Force set hunter level with stat recalculation and rank checks."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ <b>Access Denied</b>: This command is restricted to the Bot Owner & Superadmins.", parse_mode=enums.ParseMode.HTML)
        return

    target_hunter, new_lvl, err = await _resolve_hunter_and_int(client, message, default_self=True)
    if err:
        await message.reply_text(err, parse_mode=enums.ParseMode.HTML)
        return
    if new_lvl is None or new_lvl < 1 or new_lvl > 500:
        await message.reply_text("❌ Please specify a valid level between 1 and 500.\nExample: <code>/setlevel 50</code>", parse_mode=enums.ParseMode.HTML)
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

    h_name = escape_html(target_hunter.hunter_name)
    text = (
        "<b>[ SYSTEM NOTIFICATION // LEVEL OVERRIDE ]</b>\n"
        "<b>레벨 재설정 // 헌터 등급 강제 조정</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} (<code>{target_hunter.user_id}</code>)\n\n"
        "<blockquote expandable>"
        f"• Level Adjustment: Lv {old_lvl} ➜ <b>Lv {target_hunter.level}</b>\n"
        f"• Rank: <code>{target_hunter.rank}</code>\n"
        f"• Max HP: <code>{target_hunter.max_hp}</code> ┊ Combat Power: <b>{target_hunter.power}</b>\n"
        "</blockquote>\n\n"
        "<i>✅ Database synchronized successfully.</i>"
    )
    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
    logger.info(f"Superadmin {user.id} set level for {target_hunter.user_id} to {new_lvl}")


# ── COMMAND: /inspect ────────────────────────────────────────────────────────
async def handle_inspect(client: Client, message: Message) -> None:
    """Deep inspection of hunter attributes and raw database record."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ <b>Access Denied</b>: This command is restricted to the Bot Owner & Superadmins.", parse_mode=enums.ParseMode.HTML)
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
        ident = escape_html(args[0]) if args else "Target"
        await message.reply_text(f"❌ Hunter '<code>{ident}</code>' not found in the System database.", parse_mode=enums.ParseMode.HTML)
        return

    inv = await client.db.get_inventory(target_hunter.user_id)
    inv_count = len(inv.items) if inv else 0
    equipped = sum(1 for it in inv.items if it.is_equipped) if inv else 0

    h_name = escape_html(target_hunter.hunter_name)
    u_name = escape_html(target_hunter.username or 'None')
    g_id = escape_html(target_hunter.guild_id or 'None')

    text = (
        "<b>[ SYSTEM DOSSIER // HUNTER TELEMETRY ]</b>\n"
        "<b>헌터 정보 // 상세 데이터 열람</b>\n\n"
        f"👤 <b>Name:</b> {h_name}\n"
        f"🆔 <b>User ID:</b> <code>{target_hunter.user_id}</code> ┊ 🏷 <b>Username:</b> @{u_name}\n"
        f"🏅 <b>Rank:</b> [<code>{target_hunter.rank}</code>] ┊ <b>Level:</b> Lv <b>{target_hunter.level}</b>\n\n"
        "<blockquote expandable>"
        f"• XP: <code>{target_hunter.xp:,} / {target_hunter.xp_needed:,}</code>\n"
        f"• Treasury: 💰 <code>{target_hunter.gold:,} G</code>\n"
        f"• Combat Power: ⚡ <b>{target_hunter.power:,}</b>\n"
        f"• Vitality: ❤️ <code>{target_hunter.hp} / {target_hunter.max_hp}</code>\n"
        "</blockquote>\n\n"
        "<blockquote expandable>"
        "<b>📊 Core Attributes:</b>\n"
        f"• STR: <code>{target_hunter.str_stat}</code> ┊ AGI: <code>{target_hunter.agi}</code>\n"
        f"• VIT: <code>{target_hunter.vit}</code> ┊ INT: <code>{target_hunter.int_stat}</code> ┊ PER: <code>{target_hunter.per}</code>\n"
        "</blockquote>\n\n"
        "<blockquote expandable>"
        "<b>🎒 Association Records:</b>\n"
        f"• Inventory: <code>{inv_count}</code> items (<code>{equipped}</code> equipped)\n"
        f"• Guild ID: <code>{g_id}</code>\n"
        f"• Duels: <code>{target_hunter.duel_wins}W - {target_hunter.duel_losses}L</code>\n"
        f"• Hunts: <code>{target_hunter.victories}W - {target_hunter.defeats}L</code> (Total: <code>{target_hunter.total_hunts}</code>)\n"
        "</blockquote>"
    )
    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)


# ── COMMAND: /createcode ──────────────────────────────────────────────────────
async def handle_create_code(client: Client, message: Message) -> None:
    """Create a new promotional redeem code granting Gold, Items, or XP."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ <b>Access Denied</b>: This command is restricted to the Bot Owner & Superadmins.", parse_mode=enums.ParseMode.HTML)
        return

    db = client.db
    args = message.command[1:] if len(message.command) > 1 else []
    if len(args) < 3:
        await message.reply_text(
            "<b>[ SYSTEM DIRECTIVE // CODE FORGE ]</b>\n"
            "<b>코드 생성 // 프로모션 코드 제작 지침</b>\n\n"
            "<i>Create Promo &amp; Gift Codes for Hunters</i>\n\n"
            "<blockquote expandable>"
            "⚡ <b>Supported Syntaxes:</b>\n"
            "1. <b>Gold Code:</b>\n"
            "   <code>/createcode gold &lt;CODE&gt; &lt;amount&gt; [max_uses]</code>\n"
            "   <i>Example:</i> <code>/createcode gold LEVELUP 10000 50</code>\n\n"
            "2. <b>Item Code (from Shop Catalog):</b>\n"
            "   <code>/createcode item &lt;CODE&gt; &lt;shop_key&gt; [max_uses]</code>\n"
            "   <i>Example:</i> <code>/createcode item FREEBLADE knight_killer 20</code>\n\n"
            "3. <b>Custom Item Code:</b>\n"
            "   <code>/createcode custom &lt;CODE&gt; &lt;type&gt; &lt;rarity&gt; &lt;name&gt; &lt;atk&gt; &lt;def&gt; &lt;hp&gt; [max_uses]</code>\n\n"
            "4. <b>XP Code:</b>\n"
            "   <code>/createcode xp &lt;CODE&gt; &lt;amount&gt; [max_uses]</code>\n"
            "   <i>Example:</i> <code>/createcode xp FASTXP 2500 100</code>\n"
            "</blockquote>\n\n"
            "<blockquote>💡 <i>Tip: Set max_uses to 0 for unlimited uses.</i></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    subcmd = args[0].lower()
    code_str = args[1].strip().upper()

    # 1. Gold Code: /createcode gold <CODE> <amount> [max_uses]
    if subcmd == "gold":
        if not args[2].isdigit() and not (args[2].startswith("-") and args[2][1:].isdigit()):
            await message.reply_text("❌ Gold amount must be a valid integer.", parse_mode=enums.ParseMode.HTML)
            return
        amount = int(args[2])
        if amount <= 0:
            await message.reply_text("❌ Gold amount must be greater than 0.", parse_mode=enums.ParseMode.HTML)
            return

        max_uses = 1
        if len(args) >= 4 and args[3].isdigit():
            max_uses = int(args[3])

        code_obj = RedeemCode(
            code=code_str,
            reward_type="gold",
            reward_value=amount,
            max_uses=max_uses,
            created_by=user.id,
            description=f"{amount:,} Gold",
        )
        await db.create_redeem_code(code_obj)

        limit_text = f"{max_uses} Hunters" if max_uses > 0 else "Unlimited"
        esc_code = escape_html(code_obj.code)
        await message.reply_text(
            "<b>[ SYSTEM NOTIFICATION // CODE FORGED ]</b>\n"
            "<b>코드 생성 완료 // 골드 코드 인가</b>\n\n"
            f"🔑 <b>Code:</b> <code>{esc_code}</code>\n"
            f"💰 <b>Reward:</b> +{amount:,} Gold\n\n"
            "<blockquote expandable>"
            f"• Claim Capacity: <code>{escape_html(limit_text)}</code>\n"
            f"• Creator ID: <code>{user.id}</code>\n"
            "</blockquote>\n\n"
            f"<i>Hunters may now claim via <code>/redeem {esc_code}</code></i>",
            parse_mode=enums.ParseMode.HTML,
        )
        logger.info(f"Superadmin {user.id} created gold code {code_obj.code} (+{amount}g, limit: {max_uses})")
        return

    # 2. Item Code (Shop Preset): /createcode item <CODE> <shop_key> [max_uses]
    elif subcmd == "item":
        shop_key = args[2].lower()
        shop_entry = get_shop_item(shop_key)
        if not shop_entry:
            keys = [i["key"] for i in SHOP_ITEMS[:10]]
            await message.reply_text(
                f"❌ Shop item '<code>{escape_html(shop_key)}</code>' not found.\n"
                f"Available examples: <code>{escape_html(', '.join(keys))}</code>\n"
                "Or use <code>/createcode custom</code> to build a unique artifact.",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        max_uses = 1
        if len(args) >= 4 and args[3].isdigit():
            max_uses = int(args[3])

        item_obj = create_item_from_shop(shop_entry)
        code_obj = RedeemCode(
            code=code_str,
            reward_type="item",
            reward_value=item_obj.to_dict(),
            max_uses=max_uses,
            created_by=user.id,
            description=f"{item_obj.name} [{item_obj.rarity}]",
        )
        await db.create_redeem_code(code_obj)

        limit_text = f"{max_uses} Hunters" if max_uses > 0 else "Unlimited"
        esc_code = escape_html(code_obj.code)
        esc_iname = escape_html(item_obj.name)
        esc_stats = escape_html(item_obj.stat_summary())
        await message.reply_text(
            "<b>[ SYSTEM NOTIFICATION // ARTIFACT CODE FORGED ]</b>\n"
            "<b>코드 생성 완료 // 장비 코드 인가</b>\n\n"
            f"🔑 <b>Code:</b> <code>{esc_code}</code>\n"
            f"🎒 <b>Artifact:</b> {esc_iname} [<code>{item_obj.rarity}</code>]\n\n"
            "<blockquote expandable>"
            f"• Attributes: <i>{esc_stats}</i>\n"
            f"• Claim Capacity: <code>{escape_html(limit_text)}</code>\n"
            f"• Creator ID: <code>{user.id}</code>\n"
            "</blockquote>\n\n"
            f"<i>Hunters may now claim via <code>/redeem {esc_code}</code></i>",
            parse_mode=enums.ParseMode.HTML,
        )
        logger.info(f"Superadmin {user.id} created item code {code_obj.code} ({item_obj.name}, limit: {max_uses})")
        return

    # 3. Custom Item Code: /createcode custom <CODE> <weapon|armor|accessory> <rarity> <name> <atk> <def> <hp> [max_uses]
    elif subcmd == "custom":
        if len(args) < 8:
            await message.reply_text(
                "❌ <b>Syntax:</b> <code>/createcode custom &lt;CODE&gt; &lt;type&gt; &lt;rarity&gt; &lt;name&gt; &lt;atk&gt; &lt;def&gt; &lt;hp&gt; [max_uses]</code>\n"
                "<i>Example:</i> <code>/createcode custom GODSWORD weapon Mythic Shadow_Monarch_Blade 250 50 150 10</code>",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        item_type = args[2].lower()
        if item_type not in ("weapon", "armor", "accessory"):
            await message.reply_text("❌ Type must be 'weapon', 'armor', or 'accessory'.", parse_mode=enums.ParseMode.HTML)
            return

        rarity = args[3].capitalize()
        name = args[4].replace("_", " ")
        try:
            atk = int(args[5])
            defn = int(args[6])
            hp = int(args[7])
        except ValueError:
            await message.reply_text("❌ ATK, DEF, and HP bonuses must be numbers.", parse_mode=enums.ParseMode.HTML)
            return

        max_uses = 1
        if len(args) >= 9 and args[8].isdigit():
            max_uses = int(args[8])

        item_obj = Item(
            id=0,
            name=name,
            type=item_type,
            rarity=rarity,
            atk_bonus=atk,
            def_bonus=defn,
            hp_bonus=hp,
            spd_bonus=0,
        )
        code_obj = RedeemCode(
            code=code_str,
            reward_type="item",
            reward_value=item_obj.to_dict(),
            max_uses=max_uses,
            created_by=user.id,
            description=f"{item_obj.name} [{item_obj.rarity}]",
        )
        await db.create_redeem_code(code_obj)

        limit_text = f"{max_uses} Hunters" if max_uses > 0 else "Unlimited"
        esc_code = escape_html(code_obj.code)
        esc_iname = escape_html(item_obj.name)
        esc_stats = escape_html(item_obj.stat_summary())
        await message.reply_text(
            "<b>[ SYSTEM NOTIFICATION // CUSTOM ARTIFACT CODE FORGED ]</b>\n"
            "<b>코드 생성 완료 // 특수 장비 코드 인가</b>\n\n"
            f"🔑 <b>Code:</b> <code>{esc_code}</code>\n"
            f"🎒 <b>Artifact:</b> {esc_iname} [<code>{item_obj.rarity}</code>]\n"
            f"📊 <b>Type:</b> {escape_html(item_obj.type.capitalize())}\n\n"
            "<blockquote expandable>"
            f"• Attributes: <i>{esc_stats}</i>\n"
            f"• Claim Capacity: <code>{escape_html(limit_text)}</code>\n"
            f"• Creator ID: <code>{user.id}</code>\n"
            "</blockquote>\n\n"
            f"<i>Hunters may now claim via <code>/redeem {esc_code}</code></i>",
            parse_mode=enums.ParseMode.HTML,
        )
        logger.info(f"Superadmin {user.id} created custom item code {code_obj.code} ({item_obj.name}, limit: {max_uses})")
        return

    # 4. XP Code: /createcode xp <CODE> <amount> [max_uses]
    elif subcmd == "xp":
        if not args[2].isdigit():
            await message.reply_text("❌ XP amount must be a positive integer.", parse_mode=enums.ParseMode.HTML)
            return
        amount = int(args[2])
        if amount <= 0:
            await message.reply_text("❌ XP amount must be greater than 0.", parse_mode=enums.ParseMode.HTML)
            return

        max_uses = 1
        if len(args) >= 4 and args[3].isdigit():
            max_uses = int(args[3])

        code_obj = RedeemCode(
            code=code_str,
            reward_type="xp",
            reward_value=amount,
            max_uses=max_uses,
            created_by=user.id,
            description=f"{amount:,} XP",
        )
        await db.create_redeem_code(code_obj)

        limit_text = f"{max_uses} Hunters" if max_uses > 0 else "Unlimited"
        esc_code = escape_html(code_obj.code)
        await message.reply_text(
            "<b>[ SYSTEM NOTIFICATION // XP CODE FORGED ]</b>\n"
            "<b>코드 생성 완료 // 경험치 코드 인가</b>\n\n"
            f"🔑 <b>Code:</b> <code>{esc_code}</code>\n"
            f"✨ <b>Reward:</b> +{amount:,} XP\n\n"
            "<blockquote expandable>"
            f"• Claim Capacity: <code>{escape_html(limit_text)}</code>\n"
            f"• Creator ID: <code>{user.id}</code>\n"
            "</blockquote>\n\n"
            f"<i>Hunters may now claim via <code>/redeem {esc_code}</code></i>",
            parse_mode=enums.ParseMode.HTML,
        )
        logger.info(f"Superadmin {user.id} created XP code {code_obj.code} (+{amount}xp, limit: {max_uses})")
        return

    else:
        await message.reply_text("❌ Invalid code type. Supported types: <code>gold</code>, <code>item</code>, <code>custom</code>, <code>xp</code>.", parse_mode=enums.ParseMode.HTML)


# ── COMMAND: /listcodes / /codes ──────────────────────────────────────────────
async def handle_list_codes(client: Client, message: Message) -> None:
    """List all registered System promo codes with claim statistics."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ <b>Access Denied</b>: This command is restricted to the Bot Owner & Superadmins.", parse_mode=enums.ParseMode.HTML)
        return

    db = client.db
    all_codes = await db.get_all_redeem_codes()
    if not all_codes:
        await message.reply_text(
            "<b>[ SYSTEM DIRECTIVE // CODE REGISTRY EMPTY ]</b>\n"
            "<b>코드 목록 // 등록된 코드 없음</b>\n\n"
            "<i>No promotional redeem codes currently registered.</i>\n\n"
            "<blockquote expandable>"
            "• Use <code>/createcode</code> to generate a new gift code.\n"
            "</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    lines = [
        "<b>[ SYSTEM DIRECTIVE // PROMO CODE REGISTRY ]</b>",
        "<b>코드 등록소 // 활성 프로모션 목록</b>",
        "",
        "<blockquote expandable>",
    ]
    for c in sorted(all_codes, key=lambda x: x.created_at, reverse=True):
        claimed_count = len(c.claimed_by)
        limit_str = str(c.max_uses) if c.max_uses > 0 else "∞"
        status_tag = "🔴 [DEPLETED]" if c.is_depleted else "🟢 [ACTIVE]"

        if c.reward_type == "gold":
            reward_str = f"💰 {int(c.reward_value):,} Gold"
        elif c.reward_type == "xp":
            reward_str = f"✨ {int(c.reward_value):,} XP"
        elif c.reward_type == "item":
            desc = c.description or "Artifact"
            reward_str = f"🎒 {desc}"
        else:
            reward_str = f"🎁 {c.reward_type}"

        lines.append(
            f"• <code>{escape_html(c.code)}</code> {status_tag}\n"
            f"  └ {escape_html(reward_str)} ┊ <code>{claimed_count}/{limit_str}</code> used"
        )

    lines.extend([
        "</blockquote>",
        "",
        "<blockquote>💡 <i>Use <code>/deletecode &lt;CODE&gt;</code> to deactivate any code.</i></blockquote>",
    ])
    await message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML)


# ── COMMAND: /deletecode ──────────────────────────────────────────────────────
async def handle_delete_code(client: Client, message: Message) -> None:
    """Revoke and delete a promotional redeem code."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ <b>Access Denied</b>: This command is restricted to the Bot Owner & Superadmins.", parse_mode=enums.ParseMode.HTML)
        return

    db = client.db
    args = message.command[1:] if len(message.command) > 1 else []
    if not args:
        await message.reply_text(
            "❌ <b>Syntax:</b> <code>/deletecode &lt;CODE&gt;</code>\n<i>Example:</i> <code>/deletecode WELCOME100</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    code_str = args[0].strip().upper()
    deleted = await db.delete_redeem_code(code_str)
    if deleted:
        await message.reply_text(
            "<b>[ SYSTEM NOTIFICATION // CODE REVOKED ]</b>\n"
            "<b>코드 삭제 // 프로모션 코드 폐기 완료</b>\n\n"
            f"Redemption key <code>{escape_html(code_str)}</code> was successfully purged from the System.\n\n"
            "<blockquote expandable>"
            "Hunters can no longer redeem this code.\n"
            "</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        logger.info(f"Superadmin {user.id} deleted redeem code {code_str}")
    else:
        await message.reply_text(
            f"❌ Code <code>{escape_html(code_str)}</code> was not found in the System registry.",
            parse_mode=enums.ParseMode.HTML,
        )


# ── GIT REPOSITORY & LIFECYCLE HELPERS ───────────────────────────────────────

RESTART_STATE_FILE = os.path.join(os.getcwd(), ".restart_state.json")


def _run_git(*args: str) -> tuple[int, str, str]:
    """Execute a git command synchronously in a worker thread."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=35,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return -1, "", str(exc)


async def _run_git_async(*args: str) -> tuple[int, str, str]:
    """Execute a git command asynchronously without blocking the event loop."""
    return await asyncio.to_thread(_run_git, *args)


async def _get_git_branch() -> str:
    """Determine the active git branch name."""
    ret, stdout, _ = await _run_git_async("rev-parse", "--abbrev-ref", "HEAD")
    return stdout if ret == 0 and stdout else "main"


async def _get_upstream_ref(branch: str) -> str:
    """Determine the remote tracking upstream branch."""
    ret, stdout, _ = await _run_git_async("rev-parse", "--abbrev-ref", "@{u}")
    if ret == 0 and stdout:
        return stdout
    return f"origin/{branch}"


async def _execute_restart(client: Client, chat_id: int, message_id: int, pull_first: bool = True) -> None:
    """
    Persist restart metadata, optionally pull updates, spawn fresh process, and exit cleanly.
    """
    _, current_commit, _ = await _run_git_async("rev-parse", "--short", "HEAD")
    branch = await _get_git_branch()

    pull_summary = ""
    if pull_first:
        ret, stdout, stderr = await _run_git_async("pull")
        pull_summary = stdout if ret == 0 else f"Error: {stderr}"
        logger.info(f"Pre-restart git pull output: {pull_summary}")

    restart_data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "timestamp": time.time(),
        "branch": branch,
        "prev_commit": current_commit or "unknown",
        "pull_summary": pull_summary[:300] if pull_summary else "",
    }

    try:
        with open(RESTART_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(restart_data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write restart state: {e}")

    # Brief pause to allow Telegram networks and disk buffers to flush
    await asyncio.sleep(0.5)

    # Re-launch current script with same python executable & arguments
    script_path = os.path.abspath(sys.argv[0])
    args = [sys.executable, script_path] + sys.argv[1:]
    logger.info(f"Spawning restart process: {args}")

    try:
        subprocess.Popen(args, cwd=os.getcwd())
    except Exception as exc:
        logger.error(f"Failed to spawn new process during restart: {exc}")
        return

    # Terminate current process immediately to release sessions and sockets
    os._exit(0)


# ── COMMAND: /update ──────────────────────────────────────────────────────────
async def handle_update(client: Client, message: Message) -> None:
    """
    Check remote git origin for incoming commits.
    Displays:
    - Commit names / titles
    - Changed files list
    - Code total lines ONLY in number (+insertions, -deletions, total lines)
    """
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ <b>Access Denied</b>: This command is restricted to the Bot Owner & Superadmins.", parse_mode=enums.ParseMode.HTML)
        return

    status_msg = await message.reply_text(
        "<b>[ SYSTEM TELEMETRY // CHECKING UPDATES ]</b>\n"
        "<b>업데이트 확인 // 원격 저장소 조회</b>\n\n"
        "<i>Contacting remote repository origin...</i>\n\n"
        "<blockquote expandable>• Fetching git refs from origin...</blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )

    branch = await _get_git_branch()
    upstream = await _get_upstream_ref(branch)

    # 1. Fetch remote origin
    ret, _, stderr = await _run_git_async("fetch", "origin")
    if ret != 0:
        await status_msg.edit_text(
            "<b>[ SYSTEM ERROR // UPDATE CHECK FAILED ]</b>\n"
            "<b>조회 실패 // 원격 연결 오류</b>\n\n"
            "❌ Failed to reach remote git origin.\n\n"
            f"<blockquote expandable><code>{escape_html(stderr or 'Unknown network/git error')}</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # 2. Check commit difference between HEAD and upstream
    ret, count_str, _ = await _run_git_async("rev-list", "--count", f"HEAD..{upstream}")
    commit_count = int(count_str) if (ret == 0 and count_str.isdigit()) else 0

    if commit_count <= 0:
        # System is already synchronized
        _, current_hash, _ = await _run_git_async("rev-parse", "--short", "HEAD")
        _, commit_msg, _ = await _run_git_async("log", "-1", "--format=%s")
        _, author, _ = await _run_git_async("log", "-1", "--format=%an")

        text = (
            "<b>[ SYSTEM TELEMETRY // SYSTEM UP TO DATE ]</b>\n"
            "<b>시스템 상태 // 최신 버전 유지 중</b>\n\n"
            "<i>The Solo Leveling Hunter System is synchronized with remote origin.</i>\n\n"
            "<blockquote expandable>"
            f"• <b>Branch:</b> <code>{escape_html(branch)}</code>\n"
            f"• <b>Active Commit:</b> <code>{escape_html(current_hash)}</code>\n"
            f"• <b>Latest Change:</b> {escape_html(commit_msg)}\n"
            f"• <b>Author:</b> {escape_html(author)}\n"
            "• <b>Status:</b> 🟢 No pending remote commits found.\n"
            "</blockquote>\n\n"
            "<blockquote>💡 <i>Use <code>/restart</code> anytime to reboot the bot process.</i></blockquote>"
        )
        await status_msg.edit_text(text, parse_mode=enums.ParseMode.HTML)
        return

    # 3. Incoming commits found! Extract details:
    # A. Commit names & titles
    ret, log_out, _ = await _run_git_async("log", f"HEAD..{upstream}", "--format=%h - %s (%an)", f"-n{min(commit_count, 10)}")
    commit_lines = [line.strip() for line in log_out.split("\n") if line.strip()]
    commits_formatted = []
    for c in commit_lines:
        parts = c.split(" - ", 1)
        if len(parts) == 2:
            h, rest = parts[0], parts[1]
            commits_formatted.append(f"• <code>{escape_html(h)}</code>: {escape_html(rest)}")
        else:
            commits_formatted.append(f"• {escape_html(c)}")
    if commit_count > 10:
        commits_formatted.append(f"• <i>... and {commit_count - 10} more commits</i>")
    commits_block = "\n".join(commits_formatted)

    # B. Changed files
    ret, files_out, _ = await _run_git_async("diff", "--name-only", f"HEAD..{upstream}")
    file_lines = [line.strip() for line in files_out.split("\n") if line.strip()]
    files_formatted = [f"• <code>{escape_html(f)}</code>" for f in file_lines[:10]]
    if len(file_lines) > 10:
        files_formatted.append(f"• <i>... and {len(file_lines) - 10} more files</i>")
    files_block = "\n".join(files_formatted) if files_formatted else "• <i>No file list available</i>"

    # C. Code total lines only in number
    ret, stat_out, _ = await _run_git_async("diff", "--shortstat", f"HEAD..{upstream}")
    ins_m = re.search(r"(\d+)\s+insertion", stat_out)
    del_m = re.search(r"(\d+)\s+deletion", stat_out)
    files_m = re.search(r"(\d+)\s+file", stat_out)

    files_count = int(files_m.group(1)) if files_m else len(file_lines)
    insertions = int(ins_m.group(1)) if ins_m else 0
    deletions = int(del_m.group(1)) if del_m else 0
    total_lines = insertions + deletions

    text = (
        "<b>[ SYSTEM TELEMETRY // UPDATE AVAILABLE ]</b>\n"
        "<b>업데이트 감지 // 신규 패치 대기</b>\n\n"
        f"<i>{commit_count} new commit{'s' if commit_count != 1 else ''} detected on <code>{escape_html(upstream)}</code>!</i>\n\n"
        "<blockquote expandable>"
        f"<b>📦 Incoming Commits ({commit_count}):</b>\n"
        f"{commits_block}\n"
        "</blockquote>\n\n"
        "<blockquote expandable>"
        f"<b>📂 Changed Files ({files_count}):</b>\n"
        f"{files_block}\n"
        "</blockquote>\n\n"
        "<blockquote expandable>"
        "<b>📊 Code Total Lines:</b>\n"
        f"• Insertions: <b>+{insertions:,}</b>\n"
        f"• Deletions: <b>-{deletions:,}</b>\n"
        f"• Total Lines Changed: <b>{total_lines:,}</b>\n"
        "</blockquote>\n\n"
        "<blockquote>💡 <i>Tap <b>[ 🔄 Pull & Restart ]</b> below or run <code>/restart</code> to apply.</i></blockquote>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Pull & Restart", callback_data="admin_restart", style=enums.ButtonStyle.PRIMARY)]
    ])
    await status_msg.edit_text(text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)


# ── COMMAND: /restart ────────────────────────────────────────────────────────
async def handle_restart(client: Client, message: Message) -> None:
    """Reboot the bot process, pulling latest commits if requested or available."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ <b>Access Denied</b>: This command is restricted to the Bot Owner & Superadmins.", parse_mode=enums.ParseMode.HTML)
        return

    status_msg = await message.reply_text(
        "<b>[ SYSTEM NOTIFICATION // REBOOT SEQUENCE INITIATED ]</b>\n"
        "<b>시스템 재부팅 // 재가동 시퀀스 시작</b>\n\n"
        "<i>Initiating automated reboot sequence...</i>\n\n"
        "<blockquote expandable>"
        "• <b>Step 1:</b> Pulling remote code changes...\n"
        "• <b>Step 2:</b> Saving telemetry state...\n"
        "• <b>Step 3:</b> Spawning fresh process...\n"
        "</blockquote>\n\n"
        "<blockquote>⏳ <i>Stand by... This message will update once online.</i></blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )

    await _execute_restart(client, message.chat.id, status_msg.id, pull_first=True)


# ── CALLBACK: admin_restart ──────────────────────────────────────────────────
async def handle_restart_callback(client: Client, query: CallbackQuery) -> None:
    """Handle the inline button callback [ 🔄 Pull & Restart ]."""
    user = query.from_user
    if not user or not is_superadmin(user.id):
        await query.answer("⛔ Access Denied: Superadmin only.", show_alert=True)
        return

    await query.answer("Initiating System restart...", show_alert=False)

    await query.edit_message_text(
        "<b>[ SYSTEM NOTIFICATION // REBOOT SEQUENCE INITIATED ]</b>\n"
        "<b>시스템 재부팅 // 재가동 시퀀스 시작</b>\n\n"
        "<i>Applying updates and restarting System...</i>\n\n"
        "<blockquote expandable>"
        "• <b>Step 1:</b> Pulling remote commits from origin...\n"
        "• <b>Step 2:</b> Preserving state telemetry...\n"
        "• <b>Step 3:</b> Launching new engine instance...\n"
        "</blockquote>\n\n"
        "<blockquote>⏳ <i>Stand by... This message will update once online.</i></blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )

    chat_id = query.message.chat.id
    message_id = query.message.id
    await _execute_restart(client, chat_id, message_id, pull_first=True)


# ── COMMAND: /stop / /shutdown / /kill ────────────────────────────────────────
async def handle_stop(client: Client, message: Message) -> None:
    """Terminate and kill the bot process as commanded by the Superadmin."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("⛔ <b>Access Denied</b>: This command is restricted to the Bot Owner & Superadmins.", parse_mode=enums.ParseMode.HTML)
        return

    name = escape_html(user.first_name or "Sovereign")
    await message.reply_text(
        "<b>[ SYSTEM DIRECTIVE // EMERGENCY SHUTDOWN ]</b>\n"
        "<b>시스템 정지 // 엔진 가동 중단</b>\n\n"
        "<i>Terminating Hunter System engine as commanded...</i>\n\n"
        "<blockquote expandable>"
        "• <b>Status:</b> Offline 🔴\n"
        f"• <b>Authorized By:</b> {name}\n"
        "• <b>Action:</b> Process terminated (task killed)\n"
        "</blockquote>\n\n"
        "<blockquote>💤 <i>System power disconnected. All sessions safely released.</i></blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )

    logger.info(f"Stop command issued by Superadmin {user.id} ({user.first_name}). Terminating process...")

    # Allow network buffer time to deliver the final message
    await asyncio.sleep(0.5)

    os._exit(0)

