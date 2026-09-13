"""
handlers/equip.py — /equip command handler.

Allows hunters to equip items from inventory via inline keyboard buttons.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from channel_db import ChannelDB
from config import RARITY_EMOJI, EQUIPPABLE_TYPES
from game.formatting import format_equip_result, format_not_registered


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /equip command. Shows equippable items as buttons."""
    user = update.effective_user
    if not user:
        return

    db: ChannelDB = context.bot_data["db"]

    hunter = await db.get_hunter(user.id)
    if not hunter:
        await update.message.reply_text(format_not_registered())
        return

    inventory = await db.get_inventory(user.id)

    # Get all equippable items (not currently equipped)
    equippable = [
        item for item in inventory.items
        if item.type in EQUIPPABLE_TYPES and not item.is_equipped
    ]

    if not equippable:
        await update.message.reply_text(
            "⚔️ EQUIPMENT\n\n"
            "You have no unequipped gear to change.\n"
            "Hunt more monsters to find better loot!"
        )
        return

    # Build inline keyboard with item buttons
    buttons = []
    for item in equippable:
        rarity_icon = RARITY_EMOJI.get(item.rarity, "")
        label = f"{rarity_icon} {item.name} ({item.stat_summary()})"
        buttons.append(
            [InlineKeyboardButton(label, callback_data=f"equip_{item.id}")]
        )

    # Add cancel button
    buttons.append(
        [InlineKeyboardButton("❌ Cancel", callback_data="equip_cancel")]
    )

    keyboard = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(
        "⚔️ EQUIPMENT\n\n"
        "Select an item to equip:",
        reply_markup=keyboard,
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle equip button presses."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if not user:
        return

    # Handle cancel
    if query.data == "equip_cancel":
        await query.edit_message_text("⚔️ Equipment change cancelled.")
        return

    db: ChannelDB = context.bot_data["db"]

    hunter = await db.get_hunter(user.id)
    if not hunter:
        await query.edit_message_text(format_not_registered())
        return

    # Extract item ID from callback: "equip_3" → 3
    try:
        item_id = int(query.data.replace("equip_", ""))
    except ValueError:
        await query.edit_message_text("❌ Invalid item selection.")
        return

    inventory = await db.get_inventory(user.id)

    # Get the old equipped item of the same type (for stat diff)
    new_item = inventory.get_item(item_id)
    if not new_item:
        await query.edit_message_text("❌ Item not found in your inventory.")
        return

    old_item = inventory.get_equipped(new_item.type)

    # Equip the item via DB (handles unequip + save)
    equipped = await db.equip_item(user.id, item_id)

    if not equipped:
        await query.edit_message_text("❌ Failed to equip item.")
        return

    # Format the result with stat diff
    result_text = format_equip_result(equipped, old_item, hunter)
    await query.edit_message_text(result_text)
