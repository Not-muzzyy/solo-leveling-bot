"""
handlers/inventory.py — /inventory command handler.

Displays the hunter's inventory with inline keyboard tabs for categories,
plus a Shop tab for purchasing items with gold.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from channel_db import ChannelDB
from config import RARITY_EMOJI
from game.formatting import format_inventory, format_not_registered
from game.shop import get_shop_items_by_type, get_shop_item, create_item_from_shop


# ── Keyboard layouts ──────────────────────────────────────

def _inventory_keyboard() -> InlineKeyboardMarkup:
    """Inventory tabs + shop button."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚔️ Weapons", callback_data="inv_weapon"),
            InlineKeyboardButton("🛡️ Armor", callback_data="inv_armor"),
            InlineKeyboardButton("💍 Acc", callback_data="inv_accessory"),
        ],
        [
            InlineKeyboardButton("🧪 Cons", callback_data="inv_consumable"),
            InlineKeyboardButton("📦 Mats", callback_data="inv_material"),
        ],
        [
            InlineKeyboardButton("🛒 SHOP", callback_data="shop_menu"),
        ],
    ])


def _shop_category_keyboard() -> InlineKeyboardMarkup:
    """Shop category selection."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚔️ Weapons", callback_data="shop_weapon"),
            InlineKeyboardButton("🛡️ Armor", callback_data="shop_armor"),
            InlineKeyboardButton("💍 Acc", callback_data="shop_accessory"),
        ],
        [
            InlineKeyboardButton("🧪 Cons", callback_data="shop_consumable"),
            InlineKeyboardButton("📦 Mats", callback_data="shop_material"),
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
    """Format shop listing for a category."""
    TYPE_LABELS = {
        "weapon": "⚔️ Weapons",
        "armor": "🛡️ Armor",
        "accessory": "💍 Accessories",
        "consumable": "🧪 Consumables",
        "material": "📦 Materials",
    }
    label = TYPE_LABELS.get(item_type, item_type.title())
    items = get_shop_items_by_type(item_type)

    lines = [
        f"🛒 SHOP — {label}",
        f"💰 Your Gold: {gold}",
        f"",
    ]

    for entry in items:
        rarity_icon = RARITY_EMOJI.get(entry["rarity"], "")
        stats_parts = []
        if entry["atk"]:
            stats_parts.append(f"+{entry['atk']} ATK")
        if entry["def"]:
            stats_parts.append(f"+{entry['def']} DEF")
        if entry["hp"]:
            stats_parts.append(f"+{entry['hp']} HP")
        if entry["spd"]:
            stats_parts.append(f"+{entry['spd']} SPD")
        stats = ", ".join(stats_parts) if stats_parts else "Material"

        lines.append(f"{rarity_icon} {entry['name']}")
        lines.append(f"   {stats} — 💰 {entry['price']}")
        lines.append("")

    lines.append("Tap an item below to purchase.")
    return "\n".join(lines)


# ── Handlers ──────────────────────────────────────────────

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /inventory command. Shows weapons by default."""
    user = update.effective_user
    if not user:
        return

    db: ChannelDB = context.bot_data["db"]

    hunter = await db.get_hunter(user.id)
    if not hunter:
        await update.message.reply_text(format_not_registered())
        return

    inventory = await db.get_inventory(user.id)
    text = format_inventory(inventory, "weapon")

    await update.message.reply_text(text, reply_markup=_inventory_keyboard())


async def tab_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inventory tab button presses + shop navigation."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if not user:
        return

    db: ChannelDB = context.bot_data["db"]

    hunter = await db.get_hunter(user.id)
    if not hunter:
        await query.edit_message_text(format_not_registered())
        return

    data = query.data

    # ── Inventory tabs ────────────────────────────────────
    if data.startswith("inv_"):
        category = data.replace("inv_", "")
        inventory = await db.get_inventory(user.id)
        text = format_inventory(inventory, category)
        await query.edit_message_text(text, reply_markup=_inventory_keyboard())

    # ── Shop menu ─────────────────────────────────────────
    elif data == "shop_menu":
        text = (
            "🛒 HUNTER SHOP\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"💰 Your Gold: {hunter.gold}\n"
            f"\n"
            f"Select a category to browse items.\n"
            f"Spend gold earned from hunts to\n"
            f"gear up and grow stronger!"
        )
        await query.edit_message_text(text, reply_markup=_shop_category_keyboard())

    # ── Shop category view ────────────────────────────────
    elif data.startswith("shop_"):
        category = data.replace("shop_", "")
        text = _format_shop_category(category, hunter.gold)
        await query.edit_message_text(
            text, reply_markup=_shop_items_keyboard(category)
        )


async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle buy button presses from the shop."""
    query = update.callback_query
    user = query.from_user
    if not user:
        await query.answer()
        return

    db: ChannelDB = context.bot_data["db"]

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
            f"❌ Not enough gold! Need {price}💰, you have {hunter.gold}💰",
            show_alert=True,
        )
        return

    # Purchase: deduct gold, create item, add to inventory
    hunter.gold -= price
    new_item = create_item_from_shop(shop_entry)
    await db.add_item(user.id, new_item)
    await db.save_hunter(user.id)

    rarity_icon = RARITY_EMOJI.get(new_item.rarity, "")
    await query.answer(f"✅ Purchased {new_item.name}!", show_alert=True)

    # Refresh the shop view for that category
    text = _format_shop_category(shop_entry["type"], hunter.gold)
    await query.edit_message_text(
        text, reply_markup=_shop_items_keyboard(shop_entry["type"])
    )
