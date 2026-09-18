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

from pyrogram import Client, filters, enums
from pyrogram.types import Message

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
        "<b>╭━━━「 👑 SYSTEM SUPERADMIN CONSOLE 」━━━╮</b>\n\n"
        "<i>Executive Hunter Management & Balances</i>\n\n"
        "<blockquote>"
        "⚡ <b>Gold & Economy Controls:</b>\n"
        "• <code>/addgold &lt;amount&gt;</code> — Add gold to your own treasury\n"
        "• <code>/addgold &lt;amount&gt; &lt;user_id|@username&gt;</code> — Credit gold to target Hunter\n"
        "• <code>/setgold &lt;amount&gt; [target]</code> — Overwrite exact gold balance\n"
        "<i>(Aliases: <code>/addcoins</code>, <code>/setcoins</code>)</i>\n"
        "</blockquote>\n\n"
        "<blockquote>"
        "✨ <b>XP & Level Progression:</b>\n"
        "• <code>/addxp &lt;amount&gt;</code> — Grant XP to yourself (triggers level & rank ups)\n"
        "• <code>/addxp &lt;amount&gt; &lt;user_id|@username&gt;</code> — Grant XP to target Hunter\n"
        "• <code>/setlevel &lt;level&gt; [target]</code> — Force set hunter level & stats\n"
        "<i>(Aliases: <code>/addep</code>, <code>/setep</code>)</i>\n"
        "</blockquote>\n\n"
        "<blockquote>"
        "🎁 <b>Promo & Gift Code System:</b>\n"
        "• <code>/createcode gold &lt;CODE&gt; &lt;amount&gt; [max_uses]</code> — Forge gold gift code\n"
        "• <code>/createcode item &lt;CODE&gt; &lt;shop_key&gt; [max_uses]</code> — Forge item code\n"
        "• <code>/createcode custom &lt;CODE&gt; &lt;type&gt; &lt;rarity&gt; &lt;name&gt; &lt;atk&gt; &lt;def&gt; &lt;hp&gt; [max_uses]</code>\n"
        "• <code>/createcode xp &lt;CODE&gt; &lt;amount&gt; [max_uses]</code> — Forge XP promo code\n"
        "• <code>/listcodes</code> (or <code>/codes</code>) — View all promo codes & telemetry\n"
        "• <code>/deletecode &lt;CODE&gt;</code> — Purge / revoke a promo code\n"
        "</blockquote>\n\n"
        "<blockquote>"
        "🔍 <b>Diagnostics & Inspection:</b>\n"
        "• <code>/inspect [user_id|@username]</code> — Deep telemetry & raw attributes\n"
        "</blockquote>\n\n"
        "<blockquote>💡 <i>Tip: Reply to any message with <code>/addgold 50000</code> or <code>/addxp 2500</code>.</i></blockquote>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
        "<b>╭━━━「 💰 TREASURY TRANSACTION 」━━━╮</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} (<code>{target_hunter.user_id}</code>)\n"
        f"⚡ <b>Adjustment:</b> {verb} <b>{abs_amt:,}</b> Gold\n\n"
        "<blockquote>"
        f"• Previous Balance: <code>{old_gold:,}</code> 💰\n"
        f"• New Balance: <b>{target_hunter.gold:,}</b> 💰\n"
        "</blockquote>\n\n"
        "<i>✅ Database synchronized successfully.</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
        "<b>╭━━━「 💰 TREASURY OVERWRITE 」━━━╮</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} (<code>{target_hunter.user_id}</code>)\n\n"
        "<blockquote>"
        f"• Previous Balance: <code>{old_gold:,}</code> 💰\n"
        f"• Set Balance: <b>{target_hunter.gold:,}</b> 💰\n"
        "</blockquote>\n\n"
        "<i>✅ Database synchronized successfully.</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
        "<b>╭━━━「 ✨ ENERGY INFUSION (XP) 」━━━╮</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} (<code>{target_hunter.user_id}</code>)\n"
        f"⚡ <b>XP Injected:</b> +<b>{amount:,}</b> XP\n\n"
        "<blockquote>"
        f"• Progress: <code>{target_hunter.xp} / {target_hunter.xp_needed} XP</code>\n"
        f"• Rank & Level: [<code>{target_hunter.rank}</code>] Lv <b>{target_hunter.level}</b>\n"
        f"• Combat Power: <code>{old_power}</code> ➜ <b>{target_hunter.power}</b>"
        f"{level_notice}\n"
        "</blockquote>\n\n"
        "<i>✅ Database synchronized successfully.</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
        "<b>╭━━━「 👑 LEVEL OVERRIDE 」━━━╮</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} (<code>{target_hunter.user_id}</code>)\n\n"
        "<blockquote>"
        f"• Level Adjustment: Lv {old_lvl} ➜ <b>Lv {target_hunter.level}</b>\n"
        f"• Rank: <code>{target_hunter.rank}</code>\n"
        f"• Max HP: <code>{target_hunter.max_hp}</code> ┊ Combat Power: <b>{target_hunter.power}</b>\n"
        "</blockquote>\n\n"
        "<i>✅ Database synchronized successfully.</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
        "<b>╭━━━「 🔍 HUNTER TELEMETRY DOSSIER 」━━━╮</b>\n\n"
        f"👤 <b>Name:</b> {h_name}\n"
        f"🆔 <b>User ID:</b> <code>{target_hunter.user_id}</code> ┊ 🏷 <b>Username:</b> @{u_name}\n"
        f"🏅 <b>Rank:</b> [<code>{target_hunter.rank}</code>] ┊ <b>Level:</b> Lv <b>{target_hunter.level}</b>\n\n"
        "<blockquote>"
        f"• XP: <code>{target_hunter.xp:,} / {target_hunter.xp_needed:,}</code>\n"
        f"• Treasury: 💰 <code>{target_hunter.gold:,} G</code>\n"
        f"• Combat Power: ⚡ <b>{target_hunter.power:,}</b>\n"
        f"• Vitality: ❤️ <code>{target_hunter.hp} / {target_hunter.max_hp}</code>\n"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>📊 Core Attributes:</b>\n"
        f"• STR: <code>{target_hunter.str_stat}</code> ┊ AGI: <code>{target_hunter.agi}</code>\n"
        f"• VIT: <code>{target_hunter.vit}</code> ┊ INT: <code>{target_hunter.int_stat}</code> ┊ PER: <code>{target_hunter.per}</code>\n"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>🎒 Association Records:</b>\n"
        f"• Inventory: <code>{inv_count}</code> items (<code>{equipped}</code> equipped)\n"
        f"• Guild ID: <code>{g_id}</code>\n"
        f"• Duels: <code>{target_hunter.duel_wins}W - {target_hunter.duel_losses}L</code>\n"
        f"• Hunts: <code>{target_hunter.victories}W - {target_hunter.defeats}L</code> (Total: <code>{target_hunter.total_hunts}</code>)\n"
        "</blockquote>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
            "<b>╭━━━「 🎁 SYSTEM CODE FORGE DIRECTIVE 」━━━╮</b>\n\n"
            "<i>Create Promo &amp; Gift Codes for Hunters</i>\n\n"
            "<blockquote>"
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
            "<blockquote>💡 <i>Tip: Set max_uses to 0 for unlimited uses.</i></blockquote>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
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
            "<b>╭━━━「 ✅ SYSTEM CODE FORGED 」━━━╮</b>\n\n"
            f"🔑 <b>Code:</b> <code>{esc_code}</code>\n"
            f"💰 <b>Reward:</b> +{amount:,} Gold\n\n"
            "<blockquote>"
            f"• Claim Capacity: <code>{escape_html(limit_text)}</code>\n"
            f"• Creator ID: <code>{user.id}</code>\n"
            "</blockquote>\n\n"
            f"<i>Hunters may now claim via <code>/redeem {esc_code}</code></i>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
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
            "<b>╭━━━「 ✅ ARTIFACT CODE FORGED 」━━━╮</b>\n\n"
            f"🔑 <b>Code:</b> <code>{esc_code}</code>\n"
            f"🎒 <b>Artifact:</b> {esc_iname} [<code>{item_obj.rarity}</code>]\n\n"
            "<blockquote>"
            f"• Attributes: <i>{esc_stats}</i>\n"
            f"• Claim Capacity: <code>{escape_html(limit_text)}</code>\n"
            f"• Creator ID: <code>{user.id}</code>\n"
            "</blockquote>\n\n"
            f"<i>Hunters may now claim via <code>/redeem {esc_code}</code></i>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
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
            "<b>╭━━━「 ✅ CUSTOM ARTIFACT CODE FORGED 」━━━╮</b>\n\n"
            f"🔑 <b>Code:</b> <code>{esc_code}</code>\n"
            f"🎒 <b>Artifact:</b> {esc_iname} [<code>{item_obj.rarity}</code>]\n"
            f"📊 <b>Type:</b> {escape_html(item_obj.type.capitalize())}\n\n"
            "<blockquote>"
            f"• Attributes: <i>{esc_stats}</i>\n"
            f"• Claim Capacity: <code>{escape_html(limit_text)}</code>\n"
            f"• Creator ID: <code>{user.id}</code>\n"
            "</blockquote>\n\n"
            f"<i>Hunters may now claim via <code>/redeem {esc_code}</code></i>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
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
            "<b>╭━━━「 ✅ SYSTEM XP CODE FORGED 」━━━╮</b>\n\n"
            f"🔑 <b>Code:</b> <code>{esc_code}</code>\n"
            f"✨ <b>Reward:</b> +{amount:,} XP\n\n"
            "<blockquote>"
            f"• Claim Capacity: <code>{escape_html(limit_text)}</code>\n"
            f"• Creator ID: <code>{user.id}</code>\n"
            "</blockquote>\n\n"
            f"<i>Hunters may now claim via <code>/redeem {esc_code}</code></i>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
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
            "<b>╭━━━「 📭 CODE REGISTRY EMPTY 」━━━╮</b>\n\n"
            "<i>No promotional redeem codes currently registered.</i>\n\n"
            "<blockquote>"
            "• Use <code>/createcode</code> to generate a new gift code."
            "</blockquote>\n\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    lines = [
        "<b>╭━━━「 🎁 PROMO CODE REGISTRY 」━━━╮</b>",
        "",
        "<blockquote>",
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
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
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
            "<b>╭━━━「 🗑️ CODE REVOKED 」━━━╮</b>\n\n"
            f"Redemption key <code>{escape_html(code_str)}</code> was successfully purged from the System.\n\n"
            "<blockquote>"
            "Hunters can no longer redeem this code."
            "</blockquote>\n\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        logger.info(f"Superadmin {user.id} deleted redeem code {code_str}")
    else:
        await message.reply_text(
            f"❌ Code <code>{escape_html(code_str)}</code> was not found in the System registry.",
            parse_mode=enums.ParseMode.HTML,
        )

