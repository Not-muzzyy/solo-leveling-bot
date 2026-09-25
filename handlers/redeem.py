"""
handlers/redeem.py — System Promo & Gift Code Redemption Terminal.

Allows registered Hunters to redeem System gift codes for:
- Gold currency injections
- Dimensional Artifacts (Weapons, Armor, Accessories)
- Direct Hunter XP boosts

Enforces strict one-time-per-hunter redemption and max claim capacity limits.
"""

from __future__ import annotations

import logging
from typing import Optional

from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from game.hunter import add_xp, check_rank_up
from game.rich_text import escape_html
from game.rich_message import RichDoc, heading, paragraph, quote
from game.rich_send import reply_rich, send_rich
from models import Item, Inventory, Hunter

logger = logging.getLogger(__name__)


async def handle_redeem(client: Client, message: Message) -> None:
    """Handle /redeem <CODE> commands from hunters. Strictly restricted to bot DM."""
    user = message.from_user
    chat = message.chat
    if not user or not chat:
        return

    # Strictly enforce that /redeem operates only in the bot's direct messages (DM)
    chat_type_str = str(getattr(chat, "type", "")).lower()
    if "private" not in chat_type_str:
        me = await client.get_me()
        bot_user = me.username or "solo_leveling_hunter_bot"
        args = message.command[1:] if len(message.command) > 1 else []

        deleted_public_code = False
        if args:
            code_candidate = args[0].strip()
            pm_url = f"https://t.me/{bot_user}?start=redeem_{code_candidate}"
            # Attempt to delete the message to protect the user's promo code from being sniped
            try:
                await message.delete()
                deleted_public_code = True
            except Exception:
                pass
        else:
            pm_url = f"https://t.me/{bot_user}?start=redeem"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎁 Open Bot DM & Redeem", url=pm_url, style=enums.ButtonStyle.PRIMARY)]
        ])

        warning_subtext = (
            "🛡️ <i>Your message was removed to prevent other hunters from intercepting your secret code!</i>"
            if deleted_public_code else
            "⚠️ <i>Never enter redemption keys in public groups to prevent other hunters from stealing your reward!</i>"
        )

        classic_text = (
            "<b>[ SYSTEM DIRECTIVE // CONFIDENTIAL TRANSMISSION ]</b>\n"
            "<b>기밀 전송 // 개인 통신망 전용</b>\n\n"
            "The <code>/redeem</code> terminal is strictly confidential and <b>only works in the Bot's Direct Messages (DM)</b>.\n\n"
            f"<blockquote expandable>{warning_subtext}</blockquote>\n\n"
            "👉 <i>Tap the button below to redeem your reward safely in private chat:</i>"
        )
        await send_rich(
            client, chat.id,
            RichDoc(
                heading(1, "[ SYSTEM DIRECTIVE // CONFIDENTIAL TRANSMISSION ]"),
                paragraph("<b>기밀 전송 // 개인 통신망 전용</b>"),
                paragraph("The <code>/redeem</code> terminal is strictly confidential and <b>only works in the Bot's Direct Messages (DM)</b>."),
                quote(warning_subtext, expandable=True),
                paragraph("👉 <i>Tap the button below to redeem your reward safely in private chat:</i>"),
            ),
            reply_markup=keyboard,
            fallback=lambda: client.send_message(
                chat_id=chat.id,
                text=classic_text,
                reply_markup=keyboard,
                parse_mode=enums.ParseMode.HTML,
            ),
        )
        return

    db = client.db
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ SYSTEM NOTICE // UNREGISTERED ENTITY ]"),
                paragraph("<b>시스템 경고 // 미각성자 접근 제한</b>"),
                quote(
                    "You have not awakened as a Hunter yet.<br>"
                    "Use <code>/start</code> to awaken and initialize your Hunter License!",
                    expandable=True,
                ),
            ),
            fallback=lambda: message.reply_text(
                "<b>[ SYSTEM NOTICE // UNREGISTERED ENTITY ]</b>\n"
                "<b>시스템 경고 // 미각성자 접근 제한</b>\n\n"
                "<blockquote expandable>"
                "You have not awakened as a Hunter yet.\n"
                "Use <code>/start</code> to awaken and initialize your Hunter License!\n"
                "</blockquote>",
                parse_mode=enums.ParseMode.HTML,
            ),
        )
        return

    args = message.command[1:] if len(message.command) > 1 else []
    if not args:
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ SYSTEM PROTOCOL // REDEMPTION TERMINAL ]"),
                paragraph("<b>코드 교환 // 보상 수령 터미널</b>"),
                quote(
                    "Enter a secret System promo code to receive dimensional supplies, rare artifacts, or gold.<br><br>"
                    "<b>Command Syntax:</b><br>"
                    "<code>/redeem &lt;CODE&gt;</code><br><br>"
                    "<b>Examples:</b><br>"
                    "• <code>/redeem WELCOME1000</code><br>"
                    "• <code>/redeem SHADOWBLADE</code>",
                    expandable=True,
                ),
                quote("「 The System rewards those who remain vigilant. 」", expandable=False),
            ),
            fallback=lambda: message.reply_text(
                "<b>[ SYSTEM PROTOCOL // REDEMPTION TERMINAL ]</b>\n"
                "<b>코드 교환 // 보상 수령 터미널</b>\n\n"
                "<blockquote expandable>"
                "Enter a secret System promo code to receive dimensional supplies, rare artifacts, or gold.\n\n"
                "<b>Command Syntax:</b>\n"
                "<code>/redeem &lt;CODE&gt;</code>\n\n"
                "<b>Examples:</b>\n"
                "• <code>/redeem WELCOME1000</code>\n"
                "• <code>/redeem SHADOWBLADE</code>\n"
                "</blockquote>\n\n"
                "<blockquote><i>「 The System rewards those who remain vigilant. 」</i></blockquote>",
                parse_mode=enums.ParseMode.HTML,
            ),
        )
        return

    code_str = args[0].strip().upper()

    # Atomically attempt to claim the code in the database
    success, err_msg, code_obj = await db.claim_redeem_code(code_str, user.id)
    if not success:
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ SYSTEM ERROR // REDEMPTION FAILED ]"),
                paragraph("<b>교환 오류 // 코드 인식 실패</b>"),
                quote(escape_html(err_msg), expandable=True),
            ),
            fallback=lambda: message.reply_text(
                "<b>[ SYSTEM ERROR // REDEMPTION FAILED ]</b>\n"
                "<b>교환 오류 // 코드 인식 실패</b>\n\n"
                f"<blockquote expandable>{escape_html(err_msg)}</blockquote>",
                parse_mode=enums.ParseMode.HTML,
            ),
        )
        return

    h_name = escape_html(hunter.hunter_name)
    c_code = escape_html(code_obj.code)

    # Process rewards according to reward type
    if code_obj.reward_type == "gold":
        gold_amount = int(code_obj.reward_value)
        hunter.gold += gold_amount
        await db.save_hunter(hunter)

        text = (
            "<b>[ SYSTEM REWARD // CLAIM GRANTED ]</b>\n"
            "<b>시스템 보상 // 지급 완료</b>\n\n"
            f"👤 <b>Hunter:</b> {h_name} (<code>{hunter.user_id}</code>)\n"
            f"🔑 <b>Code:</b> <code>{c_code}</code>\n\n"
            "<blockquote expandable>"
            f"💰 <b>Reward:</b> <code>+{gold_amount:,} Gold</code>\n"
            f"🪙 <b>New Vault Balance:</b> <b>{hunter.gold:,} G</b>\n\n"
            "<i>Gold has been deposited directly into your dimensional vault.</i>\n"
            "</blockquote>"
        )
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ SYSTEM REWARD // CLAIM GRANTED ]"),
                paragraph("<b>시스템 보상 // 지급 완료</b>"),
                paragraph(f"👤 <b>Hunter:</b> {h_name} (<code>{hunter.user_id}</code>)<br>🔑 <b>Code:</b> <code>{c_code}</code>"),
                quote(
                    f"💰 <b>Reward:</b> <code>+{gold_amount:,} Gold</code><br>"
                    f"🪙 <b>New Vault Balance:</b> <b>{hunter.gold:,} G</b><br><br>"
                    "<i>Gold has been deposited directly into your dimensional vault.</i>",
                    expandable=True,
                ),
            ),
            fallback=lambda: message.reply_text(text, parse_mode=enums.ParseMode.HTML),
        )
        logger.info(f"Hunter {hunter.user_id} redeemed gold code {code_str} (+{gold_amount}g)")
        return

    elif code_obj.reward_type == "item":
        inv = await db.get_inventory(hunter.user_id)
        if not inv:
            inv = Inventory(user_id=hunter.user_id)

        # Deserialize item template if stored as dict
        raw_val = code_obj.reward_value
        if isinstance(raw_val, dict):
            item_template = Item.from_dict(raw_val)
        elif isinstance(raw_val, Item):
            item_template = raw_val
        else:
            await reply_rich(
                message, RichDoc(paragraph("❌ Internal System Error: Corrupted item data.")),
                fallback=lambda: message.reply_text("❌ Internal System Error: Corrupted item data.", parse_mode=enums.ParseMode.HTML),
            )
            return

        # Create a fresh copy for the hunter's inventory
        new_item = Item(
            id=0,
            name=item_template.name,
            type=item_template.type,
            rarity=item_template.rarity,
            atk_bonus=item_template.atk_bonus,
            def_bonus=item_template.def_bonus,
            hp_bonus=item_template.hp_bonus,
            spd_bonus=item_template.spd_bonus,
            is_equipped=False,
        )
        added_item = inv.add_item(new_item)
        await db.save_inventory(inv)

        stats_str = escape_html(added_item.stat_summary())
        item_name = escape_html(added_item.name)
        text = (
            "<b>[ SYSTEM REWARD // ARTIFACT RECEIVED ]</b>\n"
            "<b>시스템 보상 // 아티팩트 지급</b>\n\n"
            f"👤 <b>Hunter:</b> {h_name} (<code>{hunter.user_id}</code>)\n"
            f"🔑 <b>Code:</b> <code>{c_code}</code>\n\n"
            "<blockquote expandable>"
            "<b>🎒 Dimensional Artifact Received:</b>\n"
            f"• <b>{item_name}</b> [<code>{added_item.rarity}</code>]\n"
            f"• <b>Type:</b> {escape_html(added_item.type.capitalize())}\n"
            f"• <b>Stats:</b> <i>{stats_str}</i>\n"
            f"• <b>Slot:</b> #{added_item.id}\n"
            "</blockquote>\n\n"
            "<blockquote>💡 <i>Use <code>/inventory</code> to inspect and equip your new gear.</i></blockquote>"
        )
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ SYSTEM REWARD // ARTIFACT RECEIVED ]"),
                paragraph("<b>시스템 보상 // 아티팩트 지급</b>"),
                paragraph(f"👤 <b>Hunter:</b> {h_name} (<code>{hunter.user_id}</code>)<br>🔑 <b>Code:</b> <code>{c_code}</code>"),
                quote(
                    "<b>🎒 Dimensional Artifact Received:</b><br>"
                    f"• <b>{item_name}</b> [<code>{added_item.rarity}</code>]<br>"
                    f"• <b>Type:</b> {escape_html(added_item.type.capitalize())}<br>"
                    f"• <b>Stats:</b> <i>{stats_str}</i><br>"
                    f"• <b>Slot:</b> #{added_item.id}",
                    expandable=True,
                ),
                quote("💡 <i>Use <code>/inventory</code> to inspect and equip your new gear.</i>", expandable=False),
            ),
            fallback=lambda: message.reply_text(text, parse_mode=enums.ParseMode.HTML),
        )
        logger.info(f"Hunter {hunter.user_id} redeemed item code {code_str} ({added_item.name})")
        return

    elif code_obj.reward_type == "xp":
        xp_amount = int(code_obj.reward_value)
        leveled_up, new_level = add_xp(hunter, xp_amount)
        ranked_up, new_rank = check_rank_up(hunter)
        await db.save_hunter(hunter)

        ascend_lines = []
        if leveled_up:
            ascend_lines.append(f"⚡ <b>LEVEL UP!</b> You reached <b>Level {new_level}</b>!")
        if ranked_up:
            ascend_lines.append(f"👑 <b>RANK UP!</b> Awakened as <b>[{new_rank}] Hunter</b>!")

        ascend_block = ""
        if ascend_lines:
            ascend_block = f"\n<blockquote>{' '.join(ascend_lines)}</blockquote>\n"

        text = (
            "<b>[ SYSTEM REWARD // XP INFUSION ]</b>\n"
            "<b>시스템 보상 // 마력 주입 완료</b>\n\n"
            f"👤 <b>Hunter:</b> {h_name} (<code>{hunter.user_id}</code>)\n"
            f"🔑 <b>Code:</b> <code>{c_code}</code>\n\n"
            "<blockquote expandable>"
            f"✨ <b>Reward:</b> <code>+{xp_amount:,} XP</code>\n"
            f"📊 <b>Current EXP:</b> <code>{hunter.xp:,} / {hunter.xp_needed:,}</code> (Lv <code>{hunter.level}</code>)\n"
            "</blockquote>\n"
            f"{ascend_block}\n"
            "<blockquote><i>「 The Monarch's energy flows through your veins. 」</i></blockquote>"
        )
        xp_blocks = [
            heading(1, "[ SYSTEM REWARD // XP INFUSION ]"),
            paragraph("<b>시스템 보상 // 마력 주입 완료</b>"),
            paragraph(f"👤 <b>Hunter:</b> {h_name} (<code>{hunter.user_id}</code>)<br>🔑 <b>Code:</b> <code>{c_code}</code>"),
            quote(
                f"✨ <b>Reward:</b> <code>+{xp_amount:,} XP</code><br>"
                f"📊 <b>Current EXP:</b> <code>{hunter.xp:,} / {hunter.xp_needed:,}</code> (Lv <code>{hunter.level}</code>)",
                expandable=True,
            ),
        ]
        if ascend_lines:
            xp_blocks.append(quote(" ".join(ascend_lines), expandable=False))
        xp_blocks.append(quote("「 The Monarch's energy flows through your veins. 」", expandable=False))
        await reply_rich(
            message, RichDoc(*xp_blocks),
            fallback=lambda: message.reply_text(text, parse_mode=enums.ParseMode.HTML),
        )
        logger.info(f"Hunter {hunter.user_id} redeemed XP code {code_str} (+{xp_amount}xp)")
        return

    else:
        await reply_rich(
            message, RichDoc(paragraph("❌ System error: Unknown reward type.")),
            fallback=lambda: message.reply_text("❌ System error: Unknown reward type.", parse_mode=enums.ParseMode.HTML),
        )
