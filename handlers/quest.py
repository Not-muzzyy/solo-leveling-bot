"""
handlers/quest.py — System Daily Quests & Free Stat Allocation Handler.

Provides:
- Visual Hallmark Daily Quest board (/daily)
- Quest reward claiming (+3 Free Stat Points, Gold, XP, Blessed Mystery Gift)
- Free attribute investment (/stats, /addstat)
"""

from __future__ import annotations

import asyncio
import logging
import random
from pyrogram import Client, enums
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from channel_db import ChannelDB
from game.captions import build_quest_caption
from game.formatting import format_not_registered
from game.hunter import add_xp
from game.items import generate_accessory, generate_weapon
from game.quest_image import render_quest_image
from game.rich_text import escape_html
from models import Hunter, Inventory, Item

logger = logging.getLogger(__name__)


def _quest_keyboard(hunter: Hunter) -> InlineKeyboardMarkup:
    """Build action buttons for Daily Quest."""
    buttons = []

    all_done = (
        hunter.daily_quest_hunts >= 5 and
        hunter.daily_quest_explore >= 1 and
        hunter.daily_quest_duel >= 1 and
        hunter.daily_quest_use >= 1
    )

    if not hunter.daily_quest_claimed and all_done:
        buttons.append([
            InlineKeyboardButton("🎁 Claim Daily Quest Rewards (+3 Stat Pts)", callback_data="quest_claim")
        ])
    elif hunter.daily_quest_claimed:
        buttons.append([
            InlineKeyboardButton("✅ Daily Rewards Claimed for Today", callback_data="quest_noop")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("⏳ Physical Conditioning in Progress...", callback_data="quest_noop")
        ])

    if hunter.unspent_stat_points > 0:
        buttons.append([
            InlineKeyboardButton(f"⚡ Allocate {hunter.unspent_stat_points} Unspent Stat Points", callback_data="stats_menu")
        ])

    buttons.append([
        InlineKeyboardButton("⚔️ Hunt Gate", callback_data="inv_weapon"),
        InlineKeyboardButton("🗺️ World Explore", callback_data="inv_consumable"),
    ])

    return InlineKeyboardMarkup(buttons)


def _stats_keyboard(hunter: Hunter) -> InlineKeyboardMarkup:
    """Build attribute investment buttons."""
    buttons = []
    if hunter.unspent_stat_points > 0:
        buttons.append([
            InlineKeyboardButton(f"💪 +1 STR ({hunter.str_stat})", callback_data="stats_add_str_1"),
            InlineKeyboardButton(f"⚡ +1 AGI ({hunter.agi})", callback_data="stats_add_agi_1"),
            InlineKeyboardButton(f"🛡️ +1 VIT ({hunter.vit})", callback_data="stats_add_vit_1"),
        ])
        buttons.append([
            InlineKeyboardButton(f"🔮 +1 INT ({hunter.int_stat})", callback_data="stats_add_int_1"),
            InlineKeyboardButton(f"👁️ +1 PER ({hunter.per})", callback_data="stats_add_per_1"),
        ])
        if hunter.unspent_stat_points >= 3:
            buttons.append([
                InlineKeyboardButton(f"💥 Dump All ({hunter.unspent_stat_points}) into STR", callback_data=f"stats_add_str_{hunter.unspent_stat_points}"),
                InlineKeyboardButton(f"🛡️ Dump All ({hunter.unspent_stat_points}) into VIT", callback_data=f"stats_add_vit_{hunter.unspent_stat_points}"),
            ])

    buttons.append([
        InlineKeyboardButton("📋 Daily Quest Board", callback_data="quest_menu"),
        InlineKeyboardButton("👤 View Profile", callback_data="inv_weapon"),
    ])
    return InlineKeyboardMarkup(buttons)


async def handle_daily(client: Client, message: Message) -> None:
    """Handle /daily command."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await message.reply_text(format_not_registered(), parse_mode=enums.ParseMode.HTML)
        return

    hunter.check_and_reset_daily()
    caption = build_quest_caption(hunter)

    try:
        photo_buf = await asyncio.to_thread(render_quest_image, hunter)
        await message.reply_photo(
            photo=photo_buf,
            caption=caption,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=_quest_keyboard(hunter),
        )
    except Exception as e:
        logger.error("Failed to render daily quest image: %s", e, exc_info=True)
        await message.reply_text(caption, reply_markup=_quest_keyboard(hunter), parse_mode=enums.ParseMode.HTML)


async def handle_stats(client: Client, message: Message) -> None:
    """Handle /stats and /addstat commands."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await message.reply_text(format_not_registered(), parse_mode=enums.ParseMode.HTML)
        return

    args = (message.text or "").split()

    # If /addstat <stat> [amount], e.g. /addstat str 2
    if len(args) > 1:
        stat_name = args[1].lower()
        amount = 1
        if len(args) > 2 and args[2].isdigit():
            amount = max(1, int(args[2]))

        if hunter.unspent_stat_points < amount:
            await message.reply_text(
                f"❌ You only have <code>{hunter.unspent_stat_points}</code> unspent stat points available!\n"
                "Complete your <code>/daily</code> quest to earn more points.",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        stat_map = {
            "str": "str_stat", "strength": "str_stat",
            "agi": "agi", "agility": "agi", "spd": "agi",
            "vit": "vit", "vitality": "vit", "def": "vit",
            "int": "int_stat", "intelligence": "int_stat",
            "per": "per", "perception": "per",
        }

        attr = stat_map.get(stat_name)
        if not attr:
            await message.reply_text(
                "❌ Unknown attribute! Choose: <code>str</code>, <code>agi</code>, <code>vit</code>, <code>int</code>, or <code>per</code>.",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        setattr(hunter, attr, getattr(hunter, attr) + amount)
        hunter.unspent_stat_points -= amount
        hunter.recalculate_power()
        if attr == "vit":
            hunter.max_hp += amount * 5
            hunter.hp = min(hunter.max_hp, hunter.hp + amount * 5)

        await db.save_all(user.id)

        await message.reply_text(
            "<b>╭━━━「 ⚡ ATTRIBUTE ENHANCED 」━━━╮</b>\n\n"
            f"👤 <b>Hunter:</b> {escape_html(hunter.hunter_name)}\n"
            f"✨ Invested <b>+{amount}</b> into <b>{escape_html(stat_name.upper())}</b>!\n\n"
            "<blockquote>"
            f"• Total Combat Power: <code>{hunter.power:,}</code>\n"
            f"• Remaining Unspent Points: <code>{hunter.unspent_stat_points}</code>\n"
            "</blockquote>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # Default /stats menu
    text = (
        "<b>╭━━━「 📊 HUNTER STAT ALLOCATION 」━━━╮</b>\n\n"
        f"👤 <b>Hunter:</b> {escape_html(hunter.hunter_name)} [Rank <b>{hunter.rank}</b>]\n"
        f"⚡ <b>Unallocated Stat Points:</b> <code>{hunter.unspent_stat_points}</code>\n\n"
        "<blockquote>"
        "<b>Current Attributes:</b>\n"
        f"• <b>STR (Strength):</b> <code>{hunter.str_stat}</code>\n"
        f"• <b>AGI (Agility):</b> <code>{hunter.agi}</code>\n"
        f"• <b>VIT (Vitality):</b> <code>{hunter.vit}</code> (Max HP: <code>{hunter.max_hp}</code>)\n"
        f"• <b>INT (Intelligence):</b> <code>{hunter.int_stat}</code>\n"
        f"• <b>PER (Perception):</b> <code>{hunter.per}</code>\n\n"
        f"💪 <b>Combat Power:</b> <code>{hunter.power:,}</code>\n"
        "</blockquote>\n\n"
        "<i>Tap an attribute button below to invest points:</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )
    await message.reply_text(text, reply_markup=_stats_keyboard(hunter), parse_mode=enums.ParseMode.HTML)


async def callback(client: Client, query: CallbackQuery) -> None:
    """Handle quest and stats inline callbacks."""
    user = query.from_user
    if not user:
        await query.answer()
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await query.answer("You are not a registered Hunter!", show_alert=True)
        return

    hunter.check_and_reset_daily()
    data = query.data

    # 1. Claim Daily Quest Rewards
    if data == "quest_claim":
        all_done = (
            hunter.daily_quest_hunts >= 5 and
            hunter.daily_quest_explore >= 1 and
            hunter.daily_quest_duel >= 1 and
            hunter.daily_quest_use >= 1
        )
        if not all_done:
            await query.answer("You have not completed all 4 conditioning tasks yet!", show_alert=True)
            return

        if hunter.daily_quest_claimed:
            await query.answer("Daily rewards already claimed today! Resets at midnight UTC.", show_alert=True)
            return

        hunter.daily_quest_claimed = True
        hunter.unspent_stat_points += 3
        hunter.gold += 600
        add_xp(hunter, 250)

        # Grant random gift item
        inventory = await db.get_inventory(user.id)
        gift_item = None
        if inventory:
            gift_item = generate_accessory(hunter.level, rarity="Rare")
            inventory.add_item(gift_item)

        await db.save_all(user.id)

        gift_msg = f" + [{gift_item.rarity}] {gift_item.name}" if gift_item else ""
        notice = f"CLAIMED: +3 Stat Points, +600 Gold, +250 XP{gift_msg}!"
        await query.answer("🎉 Daily Quest Rewards Claimed! +3 Stat Points awarded.", show_alert=True)

        gift_line = ""
        if gift_item:
            gift_line = f"\n• 🎁 Blessed Gift: [<b>{escape_html(gift_item.rarity)}</b>] <i>{escape_html(gift_item.name)}</i>"

        caption = (
            "<b>╭━━━「 📋 DAILY QUEST COMPLETED 」━━━╮</b>\n\n"
            f"👤 <b>Hunter:</b> <b>{escape_html(hunter.hunter_name)}</b>\n"
            f"⚡ <b>Stat Points Available:</b> <code>{hunter.unspent_stat_points}</code>\n\n"
            "<blockquote>"
            "<b>✨ Rewards Granted:</b>\n"
            "• ⚡ <code>+3</code> Unallocated Stat Points\n"
            f"• 💰 <code>+600 Gold</code> ┊ ✨ <code>+250 XP</code>"
            f"{gift_line}\n"
            "</blockquote>\n\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
        )

        photo_buf = await asyncio.to_thread(render_quest_image, hunter, notice)
        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_quest_keyboard(hunter),
            )
        return

    # 2. Stats allocation callback: "stats_add_str_1"
    if data.startswith("stats_add_"):
        parts = data.replace("stats_add_", "").split("_")
        stat_name = parts[0]
        amount = int(parts[1]) if len(parts) > 1 else 1

        if hunter.unspent_stat_points < amount:
            await query.answer("No stat points available!", show_alert=True)
            return

        stat_map = {"str": "str_stat", "agi": "agi", "vit": "vit", "int": "int_stat", "per": "per"}
        attr = stat_map.get(stat_name)
        if attr:
            setattr(hunter, attr, getattr(hunter, attr) + amount)
            hunter.unspent_stat_points -= amount
            hunter.recalculate_power()
            if attr == "vit":
                hunter.max_hp += amount * 5
                hunter.hp = min(hunter.max_hp, hunter.hp + amount * 5)

            await db.save_all(user.id)
            await query.answer(f"Allocated +{amount} into {stat_name.upper()}! Power: {hunter.power}")

        text = (
            "<b>╭━━━「 📊 HUNTER STAT ALLOCATION 」━━━╮</b>\n\n"
            f"👤 <b>Hunter:</b> {escape_html(hunter.hunter_name)} [Rank <b>{hunter.rank}</b>]\n"
            f"⚡ <b>Unallocated Stat Points:</b> <code>{hunter.unspent_stat_points}</code>\n\n"
            "<blockquote>"
            "<b>Current Attributes:</b>\n"
            f"• <b>STR (Strength):</b> <code>{hunter.str_stat}</code>\n"
            f"• <b>AGI (Agility):</b> <code>{hunter.agi}</code>\n"
            f"• <b>VIT (Vitality):</b> <code>{hunter.vit}</code>  (Max HP: <code>{hunter.max_hp}</code>)\n"
            f"• <b>INT (Intelligence):</b> <code>{hunter.int_stat}</code>\n"
            f"• <b>PER (Perception):</b> <code>{hunter.per}</code>\n\n"
            f"💪 <b>Total Combat Power:</b> <code>{hunter.power:,}</code>\n"
            "</blockquote>\n\n"
            "<i>Tap an attribute button below to invest points:</i>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
        )
        if query.message and query.message.photo:
            await query.message.reply_text(text, reply_markup=_stats_keyboard(hunter), parse_mode=enums.ParseMode.HTML)
        elif query.message:
            await query.edit_message_text(text, reply_markup=_stats_keyboard(hunter), parse_mode=enums.ParseMode.HTML)
        return

    # 3. Stats menu toggle
    if data == "stats_menu":
        await query.answer()
        text = (
            "<b>╭━━━「 📊 HUNTER STAT ALLOCATION 」━━━╮</b>\n\n"
            f"👤 <b>Hunter:</b> {escape_html(hunter.hunter_name)} [Rank <b>{hunter.rank}</b>]\n"
            f"⚡ <b>Unallocated Stat Points:</b> <code>{hunter.unspent_stat_points}</code>\n\n"
            "<blockquote>"
            "<b>Current Attributes:</b>\n"
            f"• <b>STR:</b> <code>{hunter.str_stat}</code> ┊ • <b>AGI:</b> <code>{hunter.agi}</code>\n"
            f"• <b>VIT:</b> <code>{hunter.vit}</code> ┊ • <b>INT:</b> <code>{hunter.int_stat}</code> ┊ • <b>PER:</b> <code>{hunter.per}</code>\n\n"
            f"💪 <b>Combat Power:</b> <code>{hunter.power:,}</code>\n"
            "</blockquote>\n\n"
            "<i>Tap an attribute below to invest points:</i>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
        )
        await query.message.reply_text(text, reply_markup=_stats_keyboard(hunter), parse_mode=enums.ParseMode.HTML)
        return

    if data == "quest_menu":
        await query.answer()
        caption = build_quest_caption(hunter)
        photo_buf = await asyncio.to_thread(render_quest_image, hunter)
        await query.message.reply_photo(photo=photo_buf, caption=caption, reply_markup=_quest_keyboard(hunter), parse_mode=enums.ParseMode.HTML)
        return

    if data == "quest_noop":
        await query.answer("Daily quests reset at 00:00 UTC.", show_alert=False)
