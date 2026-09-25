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
from pyrogram import Client, enums
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
    CallbackQuery,
)

from channel_db import ChannelDB
from config import RARITY_EMOJI, EQUIPPABLE_TYPES
from game.formatting import format_inventory, format_not_registered, _hp_bar
from game.rich_text import escape_html
from game.items import apply_consumable
from game.captions import build_inventory_caption, build_shop_caption
from game.inventory_image import render_inventory_image
from game.shop_image import render_shop_image
from game.shop import get_shop_items_by_type, get_shop_item, create_item_from_shop
from models import Inventory, Item

logger = logging.getLogger(__name__)

# Per-user purchase lock: serializes gold check → deduct → save across await points.
# ponytail: handler-level, NOT ChannelDB._get_lock — that lock is non-reentrant and
# add_item/save_hunter acquire it internally (wrapping would deadlock).
_buy_locks: dict[int, asyncio.Lock] = {}


def _get_buy_lock(user_id: int) -> asyncio.Lock:
    if user_id not in _buy_locks:
        _buy_locks[user_id] = asyncio.Lock()
    return _buy_locks[user_id]


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
            rows.append([InlineKeyboardButton(label, callback_data=f"equip_{item.id}_{active_cat}", style=enums.ButtonStyle.PRIMARY)])

        if len(unequipped_items) > 4:
            rows.append([
                InlineKeyboardButton(f"⚡ All Equippable Gear ({len(unequipped_items)} items)", callback_data="inv_to_equip", style=enums.ButtonStyle.PRIMARY)
            ])
    elif inventory and active_cat == "consumable":
        # Group consumables by name for sleek 1-tap usage
        consumable_items = inventory.get_by_type("consumable")
        grouped: dict[str, list[Item]] = {}
        for item in consumable_items:
            grouped.setdefault(item.name, []).append(item)

        for name, items in list(grouped.items())[:6]:
            first_item = items[0]
            rarity_icon = RARITY_EMOJI.get(first_item.rarity, "")
            stats = first_item.stat_summary()
            count = len(items)
            count_str = f" x{count}" if count > 1 else ""
            label = f"🧪 Use: {rarity_icon} {first_item.name}{count_str} ({stats})"
            rows.append([InlineKeyboardButton(label, callback_data=f"use_{first_item.id}", style=enums.ButtonStyle.SUCCESS)])
    elif inventory:
        unequipped_total = sum(
            1 for item in inventory.items
            if item.type in EQUIPPABLE_TYPES and not item.is_equipped
        )
        if unequipped_total > 0:
            rows.append([
                InlineKeyboardButton(f"⚡ Equip Gear ({unequipped_total} available)", callback_data="inv_to_equip", style=enums.ButtonStyle.PRIMARY)
            ])

    # Bottom Actions: Shop & Refresh
    rows.append([
        InlineKeyboardButton("🛒 Hunter Shop", callback_data="shop_menu", style=enums.ButtonStyle.PRIMARY),
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
            [InlineKeyboardButton(label, callback_data=f"buy_{entry['key']}", style=enums.ButtonStyle.PRIMARY)]
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
        f"<b>[ EXCHANGE DEPOT // {label} ]</b>",
        "",
        f"💰 <b>Available Treasury:</b> <code>{gold:,} G</code>",
        "",
        "<blockquote expandable>",
        "<b>Catalog Inventory:</b>",
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
        i_name = escape_html(entry["name"])
        r_name = escape_html(entry["rarity"])
        lines.append(f"• {rarity_icon} <b>{i_name}</b> [<b>{r_name}</b>]")
        lines.append(f"  └ <code>{escape_html(stats)}</code> ┊ 💰 <code>{entry['price']:,} G</code> {can_afford}")

    lines.extend([
        "</blockquote>",
        "",
        "<i>Tap an item button below to complete purchase:</i>",
    ])
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
            u_name = escape_html(user.first_name)
            gc_text = (
                "<b>[ SYSTEM AWAKENING REQUIRED // 각성 필요 ]</b>\n\n"
                f"👤 <b>Citizen:</b> <b>{u_name}</b>\n\n"
                "<blockquote>"
                "• You have not awakened as an active Hunter yet.\n"
                "• Tap below to awaken in private chat and claim your starter inventory."
                "</blockquote>"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ Awaken in Bot PM", url=pm_url)]
            ])
            await message.reply_text(gc_text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)
            return

        inventory = await db.get_inventory(user.id)
        h_name = escape_html(hunter.hunter_name)

        # Attempt direct transmission to PM if the user has messaged the bot before
        direct_sent = False
        try:
            photo_buf = await asyncio.to_thread(render_inventory_image, hunter, inventory, "weapon")
            caption = build_inventory_caption(hunter, inventory, "weapon")
            await client.send_photo(
                chat_id=user.id,
                photo=photo_buf,
                caption=caption,
                reply_markup=_inventory_keyboard(inventory, "weapon"),
                parse_mode=enums.ParseMode.HTML,
                show_caption_above_media=True,
            )
            direct_sent = True
        except Exception:
            direct_sent = False

        status_notice = (
            "✨ <i>Dimensional Storage was also dispatched directly to your PM!</i>"
            if direct_sent
            else "🔒 <i>Open private chat with the System to view and manage your items.</i>"
        )

        gc_text = (
            "<b>[ SHADOW STORAGE // 그림자 보관함 ]</b>\n\n"
            f"👤 <b>Hunter:</b> <b>{h_name}</b> [Rank <b>{hunter.rank}</b>]\n"
            f"📦 <b>Vault:</b> <code>{len(inventory.items)} items</code> ┊ 💰 <b>Gold:</b> <code>{hunter.gold:,} G</code>\n\n"
            "<blockquote expandable>"
            "<b>Notice: Group Chat Privacy Protocol</b>\n"
            "• Dimensional inventory operations are restricted to private chat.\n"
            f"• {status_notice}\n"
            "</blockquote>\n\n"
            "<i>Tap below to open your dimensional vault:</i>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎒 Open Inventory in Bot PM", url=pm_url, style=enums.ButtonStyle.PRIMARY)]
        ])
        await message.reply_text(gc_text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)
        return

    # 2. Private Chat (PM) — render dimensional inventory image card
    if not hunter:
        await message.reply_text(format_not_registered(), parse_mode=enums.ParseMode.HTML)
        return

    inventory = await db.get_inventory(user.id)
    caption = build_inventory_caption(hunter, inventory, "weapon")

    try:
        photo_buf = await asyncio.to_thread(render_inventory_image, hunter, inventory, "weapon")
        await message.reply_photo(
            photo=photo_buf,
            caption=caption,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=_inventory_keyboard(inventory, "weapon"),
            show_caption_above_media=True,
        )
    except Exception as exc:
        logger.error("Failed to render inventory image, falling back to text: %s", exc, exc_info=True)
        text = format_inventory(inventory, hunter, "weapon")
        await message.reply_text(
            text,
            reply_markup=_inventory_keyboard(inventory, "weapon"),
            parse_mode=enums.ParseMode.HTML,
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
                [InlineKeyboardButton(label, callback_data=f"equip_{item.id}_{item.type}", style=enums.ButtonStyle.PRIMARY)]
            )
        buttons.append(
            [InlineKeyboardButton("⬅️ Back to Inventory", callback_data="inv_weapon")]
        )
        equip_caption = (
            "<b>[ EQUIPMENT BINDING // 장비 장착 ]</b>\n\n"
            f"👤 <b>Hunter:</b> {escape_html(hunter.hunter_name)} ┊ 💪 <b>Power:</b> <code>{hunter.power:,}</code>\n\n"
            "<blockquote>"
            "Select an equipment piece below to bind it to your Hunter's soul resonance:"
            "</blockquote>"
        )
        if query.message and query.message.photo:
            await query.edit_message_caption(caption=equip_caption, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        else:
            await query.edit_message_text(equip_caption, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        return

    # ── Inventory tabs ────────────────────────────────────
    if data.startswith("inv_"):
        category = data.replace("inv_", "")
        inventory = await db.get_inventory(user.id)
        caption = build_inventory_caption(hunter, inventory, category)

        try:
            photo_buf = await asyncio.to_thread(render_inventory_image, hunter, inventory, category)
            if query.message and query.message.photo:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                    reply_markup=_inventory_keyboard(inventory, category),
                )
            else:
                await query.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=_inventory_keyboard(inventory, category),
                )
        except MessageNotModified:
            return  # double-tapped an already-open tab — no-op, not an error
        except Exception as e:
            logger.error("Failed to render inventory image on tab switch: %s", e, exc_info=True)
            text = format_inventory(inventory, hunter, category)
            if query.message and query.message.photo:
                await query.edit_message_caption(caption=caption, reply_markup=_inventory_keyboard(inventory, category), parse_mode=enums.ParseMode.HTML)
            else:
                await query.edit_message_text(text, reply_markup=_inventory_keyboard(inventory, category), parse_mode=enums.ParseMode.HTML)

    # ── Shop menu ─────────────────────────────────────────
    elif data == "shop_menu":
        caption = build_shop_caption(hunter, "menu")
        try:
            photo_buf = await asyncio.to_thread(render_shop_image, hunter, "menu")
            if query.message and query.message.photo:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                    reply_markup=_shop_category_keyboard(),
                )
            else:
                await query.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=_shop_category_keyboard(),
                )
        except MessageNotModified:
            return  # double-tapped the already-open shop menu
        except Exception as e:
            logger.error("Failed to render shop menu image: %s", e, exc_info=True)
            if query.message and query.message.photo:
                await query.edit_message_caption(caption=caption, reply_markup=_shop_category_keyboard(), parse_mode=enums.ParseMode.HTML)
            else:
                await query.edit_message_text(caption, reply_markup=_shop_category_keyboard(), parse_mode=enums.ParseMode.HTML)

    # ── Shop category view ────────────────────────────────
    elif data.startswith("shop_"):
        category = data.replace("shop_", "")
        caption = build_shop_caption(hunter, category)
        try:
            photo_buf = await asyncio.to_thread(render_shop_image, hunter, category)
            if query.message and query.message.photo:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                    reply_markup=_shop_items_keyboard(category),
                )
            else:
                await query.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=_shop_items_keyboard(category),
                )
        except MessageNotModified:
            return  # double-tapped an already-open shop category
        except Exception as e:
            logger.error("Failed to render shop category image: %s", e, exc_info=True)
            text = _format_shop_category(category, hunter.gold)
            if query.message and query.message.photo:
                await query.edit_message_caption(
                    caption=text, reply_markup=_shop_items_keyboard(category), parse_mode=enums.ParseMode.HTML
                )
            else:
                await query.edit_message_text(
                    text, reply_markup=_shop_items_keyboard(category), parse_mode=enums.ParseMode.HTML
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

    caption = build_inventory_caption(hunter, inventory, return_cat, notice=notice)

    try:
        photo_buf = await asyncio.to_thread(render_inventory_image, hunter, inventory, return_cat, notice)
        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_inventory_keyboard(inventory, return_cat),
            )
        else:
            await query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_inventory_keyboard(inventory, return_cat),
            )
    except Exception as e:
        logger.error("Failed to render inventory image on equip: %s", e, exc_info=True)
        text = format_inventory(inventory, hunter, return_cat, notice=notice)
        if query.message and query.message.photo:
            await query.edit_message_caption(caption=caption, reply_markup=_inventory_keyboard(inventory, return_cat), parse_mode=enums.ParseMode.HTML)
        else:
            await query.edit_message_text(text, reply_markup=_inventory_keyboard(inventory, return_cat), parse_mode=enums.ParseMode.HTML)


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

    # Check gold + purchase atomically per user
    price = shop_entry["price"]
    async with _get_buy_lock(user.id):
        if hunter.gold < price:
            await query.answer(
                f"❌ Not enough gold! Need {price:,}💰, you have {hunter.gold:,}💰",
                show_alert=True,
            )
            return

        hunter.gold -= price
        new_item = create_item_from_shop(shop_entry)
        await db.add_item(user.id, new_item)
        await db.save_hunter(user.id)

    notice = f"Acquired {new_item.name}! (-{price:,} G)"
    await query.answer(f"✅ Purchased {new_item.name}!", show_alert=True)

    # Refresh the shop view with updated image and notice
    cat = shop_entry["type"]
    caption = build_shop_caption(hunter, cat, notice=notice)
    try:
        photo_buf = await asyncio.to_thread(render_shop_image, hunter, cat, notice)
        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_shop_items_keyboard(cat),
            )
        else:
            await query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_shop_items_keyboard(cat),
            )
    except Exception as e:
        logger.error("Failed to render shop purchase image: %s", e, exc_info=True)
        text = _format_shop_category(cat, hunter.gold)
        if query.message and query.message.photo:
            await query.edit_message_caption(
                caption=text, reply_markup=_shop_items_keyboard(cat), parse_mode=enums.ParseMode.HTML
            )
        else:
            await query.edit_message_text(
                text, reply_markup=_shop_items_keyboard(cat), parse_mode=enums.ParseMode.HTML
            )


async def use_callback(client: Client, query: CallbackQuery) -> None:
    """Handle 1-tap consumable item usage directly inside the inventory."""
    user = query.from_user
    chat = query.message.chat if query.message else None
    if not user:
        await query.answer()
        return

    if chat and chat.type in ["group", "supergroup"]:
        await query.answer("⚠️ Please manage your inventory in Bot PM!", show_alert=True)
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await query.answer("You are not a registered Hunter!", show_alert=True)
        return

    # Extract item ID: "use_12" -> 12
    raw_id = query.data.replace("use_", "")
    try:
        item_id = int(raw_id)
    except ValueError:
        await query.answer("❌ Invalid item selection.", show_alert=True)
        return

    inventory = await db.get_inventory(user.id)
    item = inventory.get_item(item_id) if inventory else None
    if not item:
        await query.answer("❌ Item no longer in your inventory.", show_alert=True)
        return

    # Apply consumable effect
    success, result_msg = apply_consumable(hunter, item)
    if not success:
        await query.answer(f"⚠️ {result_msg}", show_alert=True)
        return

    # Remove item from inventory
    inventory.remove_item(item.id)
    hunter.check_and_reset_daily()
    hunter.daily_quest_use += 1

    # Persist hunter & inventory changes to channel DB
    await db.save_all(user.id)

    notice = f"CONSUMED: {item.name} [{result_msg}]"
    await query.answer(f"✅ Used {item.name}! ({result_msg})", show_alert=False)

    caption = build_inventory_caption(hunter, inventory, "consumable", notice=notice)

    try:
        photo_buf = await asyncio.to_thread(render_inventory_image, hunter, inventory, "consumable", notice)
        if query.message and query.message.photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_inventory_keyboard(inventory, "consumable"),
            )
        else:
            await query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_inventory_keyboard(inventory, "consumable"),
            )
    except Exception as e:
        logger.error("Failed to render inventory image on potion use: %s", e, exc_info=True)
        text = format_inventory(inventory, hunter, "consumable", notice=notice)
        if query.message and query.message.photo:
            await query.edit_message_caption(caption=caption, reply_markup=_inventory_keyboard(inventory, "consumable"), parse_mode=enums.ParseMode.HTML)
        else:
            await query.edit_message_text(text, reply_markup=_inventory_keyboard(inventory, "consumable"), parse_mode=enums.ParseMode.HTML)


async def handle_use(client: Client, message: Message) -> None:
    """Handle /use, /potion, and /heal commands."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await message.reply_text(format_not_registered(), parse_mode=enums.ParseMode.HTML)
        return

    inventory = await db.get_inventory(user.id)
    if not inventory:
        await message.reply_text("❌ Your inventory could not be loaded.", parse_mode=enums.ParseMode.HTML)
        return

    command_text = message.text or ""
    parts = command_text.strip().split(maxsplit=1)
    cmd = parts[0].lower().lstrip("/")
    arg = parts[1].strip() if len(parts) > 1 else ""

    consumables = inventory.get_by_type("consumable")

    # If /heal shortcut:
    if cmd == "heal":
        healing_item = next(
            (i for i in consumables if i.hp_bonus > 0 and i.atk_bonus == 0 and i.def_bonus == 0 and i.spd_bonus == 0),
            None
        )
        if not healing_item:
            healing_item = next((i for i in consumables if i.hp_bonus > 0), None)

        h_name = escape_html(hunter.hunter_name)
        if not healing_item:
            await message.reply_text(
                "<b>[ SYSTEM ALERT // 회복 포션 부재 ]</b>\n\n"
                f"👤 <b>Hunter:</b> {h_name}\n"
                f"❤️ <b>Current HP:</b> <code>{hunter.hp}/{hunter.max_hp}</code>\n\n"
                "<blockquote>"
                "You do not possess any Health Potions in storage.\n"
                "Visit <code>/shop</code> to purchase recovery elixirs!"
                "</blockquote>",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        success, result_msg = apply_consumable(hunter, healing_item)
        if not success:
            await message.reply_text(
                "<b>[ SYSTEM NOTICE // 체력 회복 불필요 ]</b>\n\n"
                f"👤 <b>Hunter:</b> {h_name}\n"
                f"❤️ <b>Current HP:</b> <code>{hunter.hp}/{hunter.max_hp}</code>  {_hp_bar(hunter.hp, hunter.max_hp)}\n\n"
                f"<blockquote>{escape_html(result_msg)}</blockquote>",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        inventory.remove_item(healing_item.id)
        hunter.check_and_reset_daily()
        hunter.daily_quest_use += 1
        await db.save_all(user.id)

        await message.reply_text(
            "<b>[ SYSTEM RESTORATION // 활력 회복 ]</b>\n\n"
            f"👤 <b>Hunter:</b> {h_name} [Rank <b>{hunter.rank}</b>]\n"
            f"✨ <b>Item Used:</b> {escape_html(healing_item.name)}\n"
            f"📊 <b>Recovery:</b> {escape_html(result_msg)}\n"
            f"❤️ <b>Vitality:</b> <code>{hunter.hp} / {hunter.max_hp}</code>\n"
            f"  {_hp_bar(hunter.hp, hunter.max_hp)}\n\n"
            "<blockquote><i>「 Your wounds knit together as mana circulates through your core. 」</i></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # If /use or /potion with no argument
    h_name = escape_html(hunter.hunter_name)
    if not arg:
        if not consumables:
            await message.reply_text(
                "<b>[ SHADOW STORAGE // 소비 아이템 ]</b>\n\n"
                f"👤 <b>Hunter:</b> {h_name}\n\n"
                "<blockquote>"
                "You do not have any potions, elixirs, or scrolls in storage.\n"
                "Visit <code>/shop</code> to browse available consumable items!"
                "</blockquote>",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        grouped: dict[str, list[Item]] = {}
        for itm in consumables:
            grouped.setdefault(itm.name, []).append(itm)

        buttons = []
        for name, items in list(grouped.items())[:6]:
            first = items[0]
            r_icon = RARITY_EMOJI.get(first.rarity, "")
            cnt = len(items)
            cnt_str = f" x{cnt}" if cnt > 1 else ""
            stats = first.stat_summary()
            buttons.append([
                InlineKeyboardButton(f"🧪 Use: {r_icon} {first.name}{cnt_str} ({stats})", callback_data=f"use_{first.id}", style=enums.ButtonStyle.SUCCESS)
            ])
        buttons.append([
            InlineKeyboardButton("🎒 Open Full Inventory", callback_data="inv_consumable"),
            InlineKeyboardButton("🛒 Hunter Shop", callback_data="shop_consumable", style=enums.ButtonStyle.PRIMARY)
        ])

        await message.reply_text(
            "<b>[ AVAILABLE CONSUMABLES // 사용 가능 아이템 ]</b>\n\n"
            f"👤 <b>Hunter:</b> {h_name} ┊ ❤️ <b>HP:</b> <code>{hunter.hp}/{hunter.max_hp}</code>\n\n"
            "<blockquote>"
            "Select an item below to consume immediately, or type <code>/use &lt;item name&gt;</code>:"
            "</blockquote>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # If /use <arg>
    target_item: Optional[Item] = None
    if arg.isdigit():
        target_id = int(arg)
        target_item = inventory.get_item(target_id)
        if target_item and target_item.type != "consumable":
            await message.reply_text(
                f"❌ Item #<code>{target_id}</code> ({escape_html(target_item.name)}) is a {escape_html(target_item.type)}, not a consumable!",
                parse_mode=enums.ParseMode.HTML,
            )
            return
    else:
        arg_lower = arg.lower()
        for itm in consumables:
            if itm.name.lower() == arg_lower:
                target_item = itm
                break
        if not target_item:
            for itm in consumables:
                if arg_lower in itm.name.lower():
                    target_item = itm
                    break

    if not target_item:
        await message.reply_text(
            f"❌ Consumable matching '<code>{escape_html(arg)}</code>' not found in your inventory.\n"
            "Check <code>/inventory</code> (Consumables tab) to see what items you carry.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    success, result_msg = apply_consumable(hunter, target_item)
    if not success:
        await message.reply_text(
            "<b>[ ACTION CANCELLED // 사용 취소 ]</b>\n\n"
            f"<blockquote>{escape_html(result_msg)}</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    inventory.remove_item(target_item.id)
    hunter.check_and_reset_daily()
    hunter.daily_quest_use += 1
    await db.save_all(user.id)

    await message.reply_text(
        "<b>[ ITEM CONSUMED // 아이템 사용 완료 ]</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} [Rank <b>{hunter.rank}</b>]\n"
        f"✨ <b>Used:</b> {escape_html(target_item.name)} [<code>{target_item.rarity}</code>]\n"
        f"📊 <b>Effect:</b> {escape_html(result_msg)}\n"
        f"❤️ <b>Vitality:</b> <code>{hunter.hp} / {hunter.max_hp}</code>\n"
        f"  {_hp_bar(hunter.hp, hunter.max_hp)}\n"
        f"💪 <b>Total Power:</b> <code>{hunter.power:,}</code>\n\n"
        "<blockquote><i>「 The System records your enhanced status. 」</i></blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )

