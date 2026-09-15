"""
handlers/inventory.py — /inventory command handler.

Displays the hunter's inventory as a stylized, high-resolution image card
showcasing active equipment (weapon, armor, accessory) with glowing vector equipment graphics,
integrated 1-tap gear equipping directly inside inventory,
and a Hunter Shop for purchasing items with gold.
Directs users to open their inventory in private chat (PM) when invoked from a group chat.
"""

from __future__ import annotations

import asyncio
import logging
from pyrogram import Client
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
    CallbackQuery,
)

from channel_db import ChannelDB
from config import RARITY_EMOJI, EQUIPPABLE_TYPES
from game.formatting import format_inventory, format_not_registered
from game.inventory_image import render_inventory_image
from game.shop_image import render_shop_image
from game.shop import get_shop_items_by_type, get_shop_item, create_item_from_shop
from models import Inventory, Item

logger = logging.getLogger(__name__)


# ── Keyboard layouts ──────────────────────────────────────

def _inventory_keyboard(
    inventory: Inventory | None = None,
    active_cat: str = "weapon"
) -> InlineKeyboardMarkup:
    """Dynamic inventory category tabs with item counts + 1-tap quick equip buttons."""
    if inventory:
        w_count = len(inventory.get_by_type("weapon"))
        a_count = len(inventory.get_by_type("armor"))
        acc_count = len(inventory.get_by_type("accessory"))
        c_count = len(inventory.get_by_type("consumable"))
        m_count = len(inventory.get_by_type("material"))
    else:
        w_count = a_count = acc_count = c_count = m_count = 0

    def tab_btn(cat: str, icon: str, label: str, count: int) -> InlineKeyboardButton:
        is_active = (cat == active_cat)
        text = f"• {icon} {label} ({count}) •" if is_active else f"{icon} {label} ({count})"
        return InlineKeyboardButton(text, callback_data=f"inv_{cat}")

    rows: list[list[InlineKeyboardButton]] = [
        [
            tab_btn("weapon", "⚔️", "Weapons", w_count),
            tab_btn("armor", "🛡️", "Armor", a_count),
            tab_btn("accessory", "💍", "Acc", acc_count),
        ],
        [
            tab_btn("consumable", "🧪", "Consumables", c_count),
            tab_btn("material", "📦", "Materials", m_count),
        ],
    ]

    # Quick 1-tap Equip Buttons for unequipped gear in the active category
    if inventory and active_cat in EQUIPPABLE_TYPES:
        unequipped_items = [
            item for item in inventory.get_by_type(active_cat)
            if not item.is_equipped
        ]
        # Show 1-tap equip button for each unequipped item in this category (up to 4)
        for item in unequipped_items[:4]:
            rarity_icon = RARITY_EMOJI.get(item.rarity, "")
            stats = item.stat_summary()
            label = f"⚡ Equip: {rarity_icon} {item.name} ({stats})"
            rows.append([InlineKeyboardButton(label, callback_data=f"equip_{item.id}_{active_cat}")])

        if len(unequipped_items) > 4:
            rows.append([
                InlineKeyboardButton(f"⚡ All Equippable Gear ({len(unequipped_items)} items)", callback_data="inv_to_equip")
            ])
    elif inventory:
        unequipped_total = sum(
            1 for item in inventory.items
            if item.type in EQUIPPABLE_TYPES and not item.is_equipped
        )
        if unequipped_total > 0:
            rows.append([
                InlineKeyboardButton(f"⚡ Equip Gear ({unequipped_total} available)", callback_data="inv_to_equip")
            ])

    # Bottom Actions: Shop & Refresh
    rows.append([
        InlineKeyboardButton("🛒 Hunter Shop", callback_data="shop_menu"),
        InlineKeyboardButton("🔄 Refresh", callback_data=f"inv_{active_cat}"),
    ])

    return InlineKeyboardMarkup(rows)


def _shop_category_keyboard() -> InlineKeyboardMarkup:
    """Shop category selection keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚔️ Weapons", callback_data="shop_weapon"),
            InlineKeyboardButton("🛡️ Armor", callback_data="shop_armor"),
            InlineKeyboardButton("💍 Accessories", callback_data="shop_accessory"),
        ],
        [
            InlineKeyboardButton("🧪 Consumables", callback_data="shop_consumable"),
            InlineKeyboardButton("📦 Materials", callback_data="shop_material"),
        ],
        [
            InlineKeyboardButton("⬅️ Back to Inventory", callback_data="inv_weapon"),
        ],
    ])


def _shop_items_keyboard(item_type: str) -> InlineKeyboardMarkup:
    """Build buy buttons for a shop category."""
    items = get_shop_items_by_type(item_type)
    buttons = []
    for entry in items:
        rarity_icon = RARITY_EMOJI.get(entry["rarity"], "")
        label = f"{rarity_icon} {entry['name']} — {entry['price']}💰"
        buttons.append(
            [InlineKeyboardButton(label, callback_data=f"buy_{entry['key']}")]
        )
    buttons.append(
        [InlineKeyboardButton("⬅️ Shop Menu", callback_data="shop_menu")]
    )
    return InlineKeyboardMarkup(buttons)


def _format_shop_category(item_type: str, gold: int) -> str:
    """Format shop listing for a category with rich RPG styling."""
    TYPE_LABELS = {
        "weapon": "⚔️ WEAPONS",
        "armor": "🛡️ ARMOR",
        "accessory": "💍 ACCESSORIES",
        "consumable": "🧪 CONSUMABLES",
        "material": "📦 MATERIALS",
    }
    label = TYPE_LABELS.get(item_type, item_type.upper())
    items = get_shop_items_by_type(item_type)

    lines = [
        "╔══════════════════════════════╗",
        f"║   🛒 SHOP — {label:<17}║",
        "║     System Exchange Depot    ║",
        "╚══════════════════════════════╝",
        "",
        f"💰 Available Gold: {gold:,} G",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for entry in items:
        rarity_icon = RARITY_EMOJI.get(entry["rarity"], "⚪")
        stats_parts = []
        if entry["atk"]:
            stats_parts.append(f"+{entry['atk']} ATK")
        if entry["def"]:
            stats_parts.append(f"+{entry['def']} DEF")
        if entry["hp"]:
            stats_parts.append(f"+{entry['hp']} HP")
        if entry["spd"]:
            stats_parts.append(f"+{entry['spd']} SPD")
        stats = ", ".join(stats_parts) if stats_parts else "Crafting Material"

        can_afford = "✅" if gold >= entry["price"] else "❌"
        lines.append(f"{rarity_icon} {entry['name']} [{entry['rarity']}]")
        lines.append(f"  ├ Stats: {stats}")
        lines.append(f"  └ Price: 💰 {entry['price']:,} G  {can_afford}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("Tap an item below to purchase.")
    return "\n".join(lines)


# ── Handlers ──────────────────────────────────────────────

async def handle(client: Client, message: Message) -> None:
    """Handle the /inventory command. Directs to PM if called in a group chat."""
    user = message.from_user
    chat = message.chat
    if not user or not chat:
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)

    # 1. Group / Supergroup chat detection
    is_group = chat.type in ["group", "supergroup"]

    if is_group:
        me = await client.get_me()
        bot_user = me.username or "solo_leveling_hunter_bot"
        pm_url = f"https://t.me/{bot_user}?start=inventory"

        if not hunter:
            gc_text = (
                "╔══════════════════════════════╗\n"
                "║   ⚡ SYSTEM NOTIFICATION ⚡   ║\n"
                "╚══════════════════════════════╝\n\n"
                f"👤 {user.first_name}, you are not an awakened Hunter yet!\n\n"
                "Tap below to awaken in private chat and claim your starter inventory."
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ Awaken in Bot PM", url=pm_url)]
            ])
            await message.reply_text(gc_text, reply_markup=keyboard)
            return

        inventory = await db.get_inventory(user.id)

        # Attempt direct transmission to PM if the user has messaged the bot before
        direct_sent = False
        try:
            photo_buf = await asyncio.to_thread(render_inventory_image, hunter, inventory, "weapon")
            caption = f"🎒 Dimensional Inventory — ⚔️ Weapons\n👤 Hunter: {hunter.hunter_name} [Rank {hunter.rank}] ┊ 💰 Gold: {hunter.gold:,} G"
            await client.send_photo(
                chat_id=user.id,
                photo=photo_buf,
                caption=caption,
                reply_markup=_inventory_keyboard(inventory, "weapon"),
            )
            direct_sent = True
        except Exception:
            direct_sent = False

        status_notice = (
            "✨ Dimensional Storage was also dispatched directly to your PM!"
            if direct_sent
            else "🔒 Open private chat with the System to view and manage your items."
        )

        gc_text = (
            "╔══════════════════════════════╗\n"
            "║   ⚡ SYSTEM NOTIFICATION ⚡   ║\n"
            "║     DIMENSIONAL STORAGE      ║\n"
            "╚══════════════════════════════╝\n\n"
            f"👤 Hunter: {hunter.hunter_name} ┊ 🏅 Rank {hunter.rank}\n"
            f"📦 Stored: {len(inventory.items)} items ┊ 💰 Gold: {hunter.gold:,} G\n\n"
            "⚠️ To keep the group chat clean and protect your gear details,\n"
            "your Dimensional Inventory must be opened in Private Chat (PM).\n\n"
            f"{status_notice}"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎒 Open Inventory in Bot PM", url=pm_url)]
        ])
        await message.reply_text(gc_text, reply_markup=keyboard)
        return

    # 2. Private Chat (PM) — render dimensional inventory image card
    if not hunter:
        await message.reply_text(format_not_registered())
        return

    inventory = await db.get_inventory(user.id)
    caption = f"🎒 Dimensional Inventory — ⚔️ Weapons\n👤 Hunter: {hunter.hunter_name} [Rank {hunter.rank}] ┊ 💰 Gold: {hunter.gold:,} G"

    try:
        photo_buf = await asyncio.to_thread(render_inventory_image, hunter, inventory, "weapon")
        await message.reply_photo(
            photo=photo_buf,
            caption=caption,
            reply_markup=_inventory_keyboard(inventory, "weapon"),
        )
    except Exception as exc:
        logger.error("Failed to render inventory image, falling back to text: %s", exc, exc_info=True)
        text = format_inventory(inventory, hunter, "weapon")
        await message.reply_text(
            text, reply_markup=_inventory_keyboard(inventory, "weapon")
        )


async def tab_callback(client: Client, query: CallbackQuery) -> None:
    """Handle inventory tab button presses, equip shortcut, and shop navigation."""
    await query.answer()

    user = query.from_user
    chat = query.message.chat if query.message else None
    if not user:
        return

    # If triggered in a group chat, warn user to manage inventory in PM
    if chat and chat.type in ["group", "supergroup"]:
        await query.answer("⚠️ Please manage your inventory in Bot PM!", show_alert=True)
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await query.answer("You are not a registered Hunter!", show_alert=True)
        return

    data = query.data

    # ── Quick Equip Shortcut from Inventory ────────────────
    if data == "inv_to_equip":
        inventory = await db.get_inventory(user.id)
        equippable = [
            item for item in inventory.items
            if item.type in EQUIPPABLE_TYPES and not item.is_equipped
        ]
        if not equippable:
            await query.answer("You have no unequipped gear to change!", show_alert=True)
            return

        buttons = []
        for item in equippable:
            rarity_icon = RARITY_EMOJI.get(item.rarity, "")
            type_icon = "⚔️" if item.type == "weapon" else ("🛡️" if item.type == "armor" else "💍")
            label = f"⚡ {type_icon} {rarity_icon} {item.name} ({item.stat_summary()})"
            buttons.append(
                [InlineKeyboardButton(label, callback_data=f"equip_{item.id}_{item.type}")]
            )
        buttons.append(
            [InlineKeyboardButton("⬅️ Back to Inventory", callback_data="inv_weapon")]
        )
        equip_caption = (
            "⚡ SELECT GEAR TO EQUIP\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Hunter: {hunter.hunter_name} ┊ 💪 Power: {hunter.power}\n\n"
            "Tap any item below to bind it to your Hunter:"
        )
        if query.message and query.message.photo:
            await query.edit_message_caption(caption=equip_caption, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.edit_message_text(equip_caption, reply_markup=InlineKeyboardMarkup(buttons))
        return

    # ── Inventory tabs ────────────────────────────────────
    if data.startswith("inv_"):
        category = data.replace("inv_", "")
        inventory = await db.get_inventory(user.id)
        cat_title = category.title()
        caption = f"🎒 Dimensional Inventory — {cat_title}\n👤 Hunter: {hunter.hunter_name} [Rank {hunter.rank}] ┊ 💰 Gold: {hunter.gold:,} G"

        try:
            photo_buf = await asyncio.to_thread(render_inventory_image, hunter, inventory, category)
            if query.message and query.message.photo:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=photo_buf, caption=caption),
                    reply_markup=_inventory_keyboard(inventory, category),
                )
            else:
                await query.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    reply_markup=_inventory_keyboard(inventory, category),
                )
        except Exception as e:
            logger.error("Failed to render inventory image on tab switch: %s", e, exc_info=True)
            text = format_inventory(inventory, hunter, category)
            if query.message and query.message.photo:
                await query.edit_message_caption(caption=caption, reply_markup=_inventory_keyboard(inventory, category))
            else:
                await query.edit_message_text(text, reply_markup=_inventory_keyboard(inventory, category))

    # ── Shop menu ─────────────────────────────────────────
    elif data == "shop_menu":
        caption = (
            f"🛒 Hunter Shop — System Exchange Depot\n"
            f"👤 Hunter: {hunter.hunter_name} [Rank {hunter.rank}] ┊ 💰 Available Treasury: {hunter.gold:,} G\n\n"
            "Select a department below to browse items:"
        )
        try:
            photo_buf = await asyncio.to_thread(render_shop_image, hunter, "menu")
            if query.message and query.message.photo:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=photo_buf, caption=caption),
                    reply_markup=_shop_category_keyboard(),
                )
            else:
                await query.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    reply_markup=_shop_category_keyboard(),
                )
        except Exception as e:
            logger.error("Failed to render shop menu image: %s", e, exc_info=True)
            text = (
                "🛒 HUNTER SHOP — SYSTEM EXCHANGE DEPOT\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Hunter: {hunter.hunter_name} ┊ 🏅 Rank {hunter.rank}\n"
                f"💰 Available Gold: {hunter.gold:,} G\n\n"
                "Select a category below to browse items:"
            )
            if query.message and query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=_shop_category_keyboard())
            else:
                await query.edit_message_text(text, reply_markup=_shop_category_keyboard())

    # ── Shop category view ────────────────────────────────
    elif data.startswith("shop_"):
        category = data.replace("shop_", "")
        caption = (
            f"🛒 Hunter Shop — {category.title()}\n"
            f"👤 Hunter: {hunter.hunter_name} [Rank {hunter.rank}] ┊ 💰 Available Treasury: {hunter.gold:,} G\n\n"
            "Tap an item below to purchase:"
        )
        try:
            photo_buf = await asyncio.to_thread(render_shop_image, hunter, category)
            if query.message and query.message.photo:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=photo_buf, caption=caption),
                    reply_markup=_shop_items_keyboard(category),
                )
            else:
                await query.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    reply_markup=_shop_items_keyboard(category),
                )
        except Exception as e:
            logger.error("Failed to render shop category image: %s", e, exc_info=True)
            text = _format_shop_category(category, hunter.gold)
            if query.message and query.message.photo:
                await query.edit_message_caption(
                    caption=text, reply_markup=_shop_items_keyboard(category)
                )
            else:
                await query.edit_message_text(
                    text, reply_markup=_shop_items_keyboard(category)
                )


async def equip_callback(client: Client, query: CallbackQuery) -> None:
    """Handle 1-tap equipment changes directly inside the inventory."""
    user = query.from_user
    chat = query.message.chat if query.message else None
    if not user:
        await query.answer()
        return

    if chat and chat.type in ["group", "supergroup"]:
        await query.answer("⚠️ Please manage your equipment in Bot PM!", show_alert=True)
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await query.answer("You are not a registered Hunter!", show_alert=True)
        return

    # Extract item ID & optional return category: "equip_3_weapon" or "equip_3"
    raw_data = query.data.replace("equip_", "")
    parts = raw_data.split("_")
    try:
        item_id = int(parts[0])
    except ValueError:
        await query.answer("❌ Invalid item selection.", show_alert=True)
        return

    inventory = await db.get_inventory(user.id)
    new_item = inventory.get_item(item_id)
    if not new_item:
        await query.answer("❌ Item not found in your inventory.", show_alert=True)
        return

    return_cat = parts[1] if len(parts) > 1 else new_item.type
    old_item = inventory.get_equipped(new_item.type)

    # Equip the item in DB
    equipped = await db.equip_item(user.id, item_id)
    if not equipped:
        await query.answer("❌ Failed to equip item.", show_alert=True)
        return

    # Refresh hunter & inventory after equip
    hunter = await db.get_hunter(user.id)
    inventory = await db.get_inventory(user.id)

    # Build stat change notice
    stat_diffs = []
    if old_item:
        for stat_name, new_val, old_val in [
            ("ATK", equipped.atk_bonus, old_item.atk_bonus),
            ("DEF", equipped.def_bonus, old_item.def_bonus),
            ("HP", equipped.hp_bonus, old_item.hp_bonus),
            ("SPD", equipped.spd_bonus, old_item.spd_bonus),
        ]:
            diff = new_val - old_val
            if diff != 0:
                sign = "+" if diff > 0 else ""
                stat_diffs.append(f"{stat_name} {old_val}→{new_val} ({sign}{diff})")
    else:
        if equipped.atk_bonus:
            stat_diffs.append(f"ATK +{equipped.atk_bonus}")
        if equipped.def_bonus:
            stat_diffs.append(f"DEF +{equipped.def_bonus}")
        if equipped.hp_bonus:
            stat_diffs.append(f"HP +{equipped.hp_bonus}")
        if equipped.spd_bonus:
            stat_diffs.append(f"SPD +{equipped.spd_bonus}")

    diff_str = ", ".join(stat_diffs) if stat_diffs else "Stats updated"
    notice = f"GEAR EQUIPPED: {equipped.name} [{diff_str}] | Power: {hunter.power}"
    await query.answer(f"✅ Equipped {equipped.name}!", show_alert=False)

    caption = (
        f"🎒 Dimensional Inventory — {return_cat.title()}\n"
        f"✨ Equipped: {equipped.name} ({diff_str})"
    )

    try:
        photo_buf = await asyncio.to_thread(render_inventory_image, hunter, inventory, return_cat, notice)
        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption),
                reply_markup=_inventory_keyboard(inventory, return_cat),
            )
        else:
            await query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=_inventory_keyboard(inventory, return_cat),
            )
    except Exception as e:
        logger.error("Failed to render inventory image on equip: %s", e, exc_info=True)
        text = format_inventory(inventory, hunter, return_cat, notice=notice)
        if query.message and query.message.photo:
            await query.edit_message_caption(caption=caption, reply_markup=_inventory_keyboard(inventory, return_cat))
        else:
            await query.edit_message_text(text, reply_markup=_inventory_keyboard(inventory, return_cat))


async def buy_callback(client: Client, query: CallbackQuery) -> None:
    """Handle buy button presses from the shop."""
    user = query.from_user
    chat = query.message.chat if query.message else None
    if not user:
        await query.answer()
        return

    if chat and chat.type in ["group", "supergroup"]:
        await query.answer("⚠️ Please use the Hunter Shop in Bot PM!", show_alert=True)
        return

    db: ChannelDB = client.db

    hunter = await db.get_hunter(user.id)
    if not hunter:
        await query.answer("You are not a registered Hunter!", show_alert=True)
        return

    # Extract item key: "buy_iron_sword" → "iron_sword"
    item_key = query.data.replace("buy_", "")
    shop_entry = get_shop_item(item_key)

    if not shop_entry:
        await query.answer("❌ Item not found!", show_alert=True)
        return

    # Check gold
    price = shop_entry["price"]
    if hunter.gold < price:
        await query.answer(
            f"❌ Not enough gold! Need {price:,}💰, you have {hunter.gold:,}💰",
            show_alert=True,
        )
        return

    # Purchase: deduct gold, create item, add to inventory
    hunter.gold -= price
    new_item = create_item_from_shop(shop_entry)
    await db.add_item(user.id, new_item)
    await db.save_hunter(user.id)

    notice = f"Acquired {new_item.name}! (-{price:,} G)"
    await query.answer(f"✅ Purchased {new_item.name}!", show_alert=True)

    # Refresh the shop view with updated image and notice
    cat = shop_entry["type"]
    caption = (
        f"🛒 Hunter Shop — {cat.title()}\n"
        f"✨ Acquired {new_item.name}! ┊ 💰 Remaining: {hunter.gold:,} G"
    )
    try:
        photo_buf = await asyncio.to_thread(render_shop_image, hunter, cat, notice)
        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption),
                reply_markup=_shop_items_keyboard(cat),
            )
        else:
            await query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=_shop_items_keyboard(cat),
            )
    except Exception as e:
        logger.error("Failed to render shop purchase image: %s", e, exc_info=True)
        text = _format_shop_category(cat, hunter.gold)
        if query.message and query.message.photo:
            await query.edit_message_caption(
                caption=text, reply_markup=_shop_items_keyboard(cat)
            )
        else:
            await query.edit_message_text(
                text, reply_markup=_shop_items_keyboard(cat)
            )
