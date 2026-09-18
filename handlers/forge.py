"""
handlers/forge.py — Blacksmith Forge & Equipment Synthesis Handler.

Provides:
- Interactive Hallmark visual Forge card
- 1-tap equipment enhancement (+1 to +10)
- 1-tap rarity transmutation & gear fusion
- PM enforcement for group chat calls
"""

from __future__ import annotations

import asyncio
import logging
from pyrogram import Client, enums
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from channel_db import ChannelDB
from config import EQUIPPABLE_TYPES, RARITY_EMOJI
from game.captions import build_forge_caption
from game.crafting import upgrade_equipment, fuse_items, get_upgrade_cost
from game.formatting import format_not_registered
from game.rich_text import escape_html
from game.forge_image import render_forge_image
from models import Hunter, Inventory, Item

logger = logging.getLogger(__name__)


def _forge_keyboard(inventory: Inventory, selected_item: Item | None = None) -> InlineKeyboardMarkup:
    """Build interactive forge buttons for upgrading gear and fusion."""
    buttons = []

    # If an item is selected, prioritize its upgrade button at top
    if selected_item and selected_item.upgrade_level < 10:
        cost, _ = get_upgrade_cost(selected_item)
        buttons.append([
            InlineKeyboardButton(
                f"🔨 Upgrade to +{selected_item.upgrade_level + 1} ({cost:,} G)",
                callback_data=f"forge_up_{selected_item.id}",
            )
        ])

    # Show up to 4 equippable items to upgrade
    equippable = [i for i in inventory.items if i.type in EQUIPPABLE_TYPES]
    gear_buttons = []
    for itm in equippable[:4]:
        if selected_item and itm.id == selected_item.id:
            continue
        r_icon = RARITY_EMOJI.get(itm.rarity, "")
        gear_buttons.append([
            InlineKeyboardButton(
                f"⚡ {r_icon} {itm.display_name} (+{itm.upgrade_level})",
                callback_data=f"forge_sel_{itm.id}",
            )
        ])
    buttons.extend(gear_buttons)

    # Rarity Fusion row
    fuse_row = []
    for r in ["Common", "Uncommon", "Rare"]:
        count = sum(1 for i in inventory.items if i.type in EQUIPPABLE_TYPES and i.rarity == r and not i.is_equipped)
        if count >= 3:
            fuse_row.append(InlineKeyboardButton(f"🔮 Fuse {r} (3/{count})", callback_data=f"forge_fuse_{r}"))

    if fuse_row:
        buttons.append(fuse_row)

    # Navigation row
    buttons.append([
        InlineKeyboardButton("🎒 Dimensional Inventory", callback_data="inv_weapon"),
        InlineKeyboardButton("🛒 Hunter Shop", callback_data="shop_menu"),
    ])

    return InlineKeyboardMarkup(buttons)


async def handle(client: Client, message: Message) -> None:
    """Handle /forge, /craft, /upgrade command."""
    user = message.from_user
    chat = message.chat
    if not user or not chat:
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)

    # Group chat redirection
    if chat.type in ["group", "supergroup"]:
        me = await client.get_me()
        bot_user = me.username or "solo_leveling_hunter_bot"
        pm_url = f"https://t.me/{bot_user}?start=forge"
        gc_text = (
            "<b>╭━━━「 ⚒️ DIMENSIONAL FORGE 」━━━╮</b>\n\n"
            "<blockquote>"
            "The Blacksmith's Anvil contains searing heat &amp; delicate runes.\n"
            "To keep public chat clean, manage equipment forging in Private Chat."
            "</blockquote>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
        )
        await message.reply_text(
            gc_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚒️ Open Forge in Bot PM", url=pm_url)]
            ]),
            parse_mode=enums.ParseMode.HTML,
        )
        return

    if not hunter:
        await message.reply_text(format_not_registered(), parse_mode=enums.ParseMode.HTML)
        return

    inventory = await db.get_inventory(user.id)
    if not inventory:
        await message.reply_text("❌ Could not load dimensional inventory.", parse_mode=enums.ParseMode.HTML)
        return

    # Check if user specified an item ID e.g. /forge 4 or /upgrade 4
    args = (message.text or "").split()
    selected_item = None
    if len(args) > 1 and args[1].isdigit():
        selected_item = inventory.get_item(int(args[1]))

    # Default to equipped weapon if none specified
    if not selected_item:
        selected_item = inventory.get_equipped("weapon")

    caption = build_forge_caption(hunter, inventory, selected_item)

    try:
        photo_buf = await asyncio.to_thread(render_forge_image, hunter, inventory, selected_item)
        await message.reply_photo(
            photo=photo_buf,
            caption=caption,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=_forge_keyboard(inventory, selected_item),
        )
    except Exception as e:
        logger.error("Failed to render forge image: %s", e, exc_info=True)
        await message.reply_text(caption, reply_markup=_forge_keyboard(inventory, selected_item), parse_mode=enums.ParseMode.HTML)


async def callback(client: Client, query: CallbackQuery) -> None:
    """Handle forge inline button callbacks."""
    user = query.from_user
    if not user:
        await query.answer()
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await query.answer("You are not a registered Hunter!", show_alert=True)
        return

    inventory = await db.get_inventory(user.id)
    if not inventory:
        await query.answer("Could not load inventory!", show_alert=True)
        return

    data = query.data

    if data in ["forge_menu", "forge_refresh"]:
        await query.answer("Opening Dimensional Forge...")
        caption = build_forge_caption(hunter, inventory, None)
        photo_buf = await asyncio.to_thread(render_forge_image, hunter, inventory, None)
        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_forge_keyboard(inventory, None),
            )
        elif query.message:
            await query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_forge_keyboard(inventory, None),
            )
        return

    # 1. Select equipment piece for anvil preview: "forge_sel_12"
    if data.startswith("forge_sel_"):
        item_id = int(data.replace("forge_sel_", ""))
        item = inventory.get_item(item_id)
        if not item:
            await query.answer("Item not found!", show_alert=True)
            return

        await query.answer(f"Selected {item.display_name} for the anvil!")
        caption = build_forge_caption(hunter, inventory, item)
        photo_buf = await asyncio.to_thread(render_forge_image, hunter, inventory, item)
        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_forge_keyboard(inventory, item),
            )
        return

    # 2. Upgrade action: "forge_up_12"
    if data.startswith("forge_up_"):
        item_id = int(data.replace("forge_up_", ""))
        item = inventory.get_item(item_id)
        if not item:
            await query.answer("Item not found!", show_alert=True)
            return

        success, notice = upgrade_equipment(item, hunter, inventory)
        await db.save_all(user.id)

        toast = f"✅ Enhanced to +{item.upgrade_level}!" if success else "❌ Enhancement failed!"
        await query.answer(toast, show_alert=True)

        caption = build_forge_caption(hunter, inventory, item, notice=notice)
        photo_buf = await asyncio.to_thread(render_forge_image, hunter, inventory, item, notice)
        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_forge_keyboard(inventory, item),
            )
        return

    # 3. Fuse action: "forge_fuse_Common"
    if data.startswith("forge_fuse_"):
        rarity = data.replace("forge_fuse_", "")
        success, notice, new_item = fuse_items(hunter, inventory, rarity)
        if success:
            await db.save_all(user.id)
            await query.answer(f"🎉 Transmuted {new_item.name}!", show_alert=True)
        else:
            await query.answer(notice, show_alert=True)
            return

        caption = build_forge_caption(hunter, inventory, new_item, notice=notice)
        photo_buf = await asyncio.to_thread(render_forge_image, hunter, inventory, new_item, notice)
        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_forge_keyboard(inventory, new_item),
            )
        return
