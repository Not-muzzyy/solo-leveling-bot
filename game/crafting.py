"""
game/crafting.py — Solo Leveling Blacksmith Forge & Equipment Synthesis Engine.

Manages:
1. Equipment Enhancement (+1 to +10) with level-scaled success rates and stat amplification.
2. Rarity Fusion: Combining 3 duplicate rarity items + 1 catalyst material to synthesize higher-tier gear.
3. Material identification and crafting cost calculation.
"""

from __future__ import annotations

import random
from typing import Optional, Tuple

from config import EQUIPPABLE_TYPES, RARITIES
from game.items import generate_weapon, generate_armor, generate_accessory
from models import Hunter, Inventory, Item

# Enhancement success rates by target level (+1 to +10)
UPGRADE_SUCCESS_RATES = {
    1: 1.00,   # 100%
    2: 0.95,   # 95%
    3: 0.85,   # 85%
    4: 0.75,   # 75%
    5: 0.65,   # 65%
    6: 0.50,   # 50%
    7: 0.40,   # 40%
    8: 0.30,   # 30%
    9: 0.25,   # 25%
    10: 0.15,  # 15%
}

# Next rarity progression tier
NEXT_RARITY = {
    "Common": "Uncommon",
    "Uncommon": "Rare",
    "Rare": "Epic",
    "Epic": "Legendary",
    "Legendary": "Mythic",
}

FUSION_GOLD_COST = {
    "Common": 100,
    "Uncommon": 250,
    "Rare": 600,
    "Epic": 1500,
    "Legendary": 4000,
}


def get_upgrade_cost(item: Item) -> Tuple[int, str]:
    """Calculate gold and catalyst material cost for the next upgrade level."""
    target_lvl = item.upgrade_level + 1
    gold_cost = target_lvl * 75
    return gold_cost, "Refined Iron Ore (or 1 Material)"


def find_catalyst_material(inventory: Inventory) -> Optional[Item]:
    """Find a material item in inventory to serve as forge catalyst."""
    materials = inventory.get_by_type("material")
    if not materials:
        return None
    # Prefer Refined Iron Ore, else first available material
    for mat in materials:
        if "Iron" in mat.name or "Ore" in mat.name:
            return mat
    return materials[0]


def upgrade_equipment(item: Item, hunter: Hunter, inventory: Inventory) -> Tuple[bool, str]:
    """
    Attempt to upgrade an equippable item by 1 level (up to +10).
    Returns (success: bool, status_message: str).
    """
    if item.type not in EQUIPPABLE_TYPES:
        return False, "Only weapons, armor, and accessories can be forged at the anvil."

    if item.upgrade_level >= 10:
        return False, f"Maximum transcendence reached! {item.display_name} is already +10."

    target_lvl = item.upgrade_level + 1
    gold_cost, _ = get_upgrade_cost(item)

    if hunter.gold < gold_cost:
        return False, f"Insufficient Gold! Need {gold_cost:,} G (You have {hunter.gold:,} G)."

    catalyst = find_catalyst_material(inventory)
    if not catalyst:
        return False, "No crafting materials found! Slay monsters via /hunt or explore to collect Ore & Crystals."

    # Deduct resources
    hunter.gold -= gold_cost
    inventory.remove_item(catalyst.id)

    # Roll success
    success_rate = UPGRADE_SUCCESS_RATES.get(target_lvl, 0.20)
    roll = random.random()

    if roll <= success_rate:
        # Success!
        item.upgrade_level = target_lvl
        # Stat amplification: +15% per upgrade level
        if item.atk_bonus > 0:
            item.atk_bonus += max(1, int(item.atk_bonus * 0.15))
        if item.def_bonus > 0:
            item.def_bonus += max(1, int(item.def_bonus * 0.15))
        if item.hp_bonus > 0:
            item.hp_bonus += max(3, int(item.hp_bonus * 0.15))
        if item.spd_bonus > 0:
            item.spd_bonus += max(1, int(item.spd_bonus * 0.10))

        # Recalculate power if currently equipped
        if item.is_equipped:
            hunter.recalculate_power()

        return True, f"✨ FORGE SUCCESS: {item.display_name} enhanced to +{item.upgrade_level}! (-{gold_cost} G, consumed {catalyst.name})"
    else:
        # Failure
        downgraded = False
        if target_lvl >= 7 and random.random() < 0.40:
            item.upgrade_level = max(0, item.upgrade_level - 1)
            downgraded = True

        msg = (
            f"💥 FORGE FAILED: The enhancement shattered! {item.name} degraded to +{item.upgrade_level}."
            if downgraded
            else f"❌ FORGE FAILED: Anvil shockwave absorbed the catalyst. {item.display_name} remained unchanged."
        )
        return False, f"{msg} (-{gold_cost} G, consumed {catalyst.name})"


def fuse_items(hunter: Hunter, inventory: Inventory, rarity: str) -> Tuple[bool, str, Optional[Item]]:
    """
    Fuse 3 unequipped items of the specified rarity into 1 item of the next rarity tier.
    Returns (success: bool, message: str, new_item: Optional[Item]).
    """
    if rarity not in NEXT_RARITY:
        return False, f"Items of rarity [{rarity}] cannot be fused further.", None

    next_rarity = NEXT_RARITY[rarity]
    gold_cost = FUSION_GOLD_COST.get(rarity, 200)

    if hunter.gold < gold_cost:
        return False, f"Insufficient Gold! Fusion requires {gold_cost:,} G.", None

    # Collect 3 unequipped gear items of this rarity
    candidates = [
        i for i in inventory.items
        if i.type in EQUIPPABLE_TYPES and i.rarity == rarity and not i.is_equipped
    ]

    if len(candidates) < 3:
        return False, f"Need at least 3 unequipped [{rarity}] gear pieces to fuse! (You have {len(candidates)}).", None

    catalyst = find_catalyst_material(inventory)
    if not catalyst:
        return False, "Fusion requires 1 catalyst material (Magic Crystal, Ore, etc.) from storage!", None

    # Consume 3 items & 1 catalyst
    to_consume = candidates[:3]
    for c in to_consume:
        inventory.remove_item(c.id)
    inventory.remove_item(catalyst.id)
    hunter.gold -= gold_cost

    # Synthesize new item of next rarity scaled to hunter's level
    gear_types = ["weapon", "armor", "accessory"]
    chosen_type = random.choice(gear_types)

    if chosen_type == "weapon":
        new_item = generate_weapon(hunter.level, rarity=next_rarity)
    elif chosen_type == "armor":
        new_item = generate_armor(hunter.level, rarity=next_rarity)
    else:
        new_item = generate_accessory(hunter.level, rarity=next_rarity)

    inventory.add_item(new_item)

    return (
        True,
        f"🔮 TRANSMUTATION COMPLETE: Synthesized [{next_rarity}] {new_item.name} ({new_item.stat_summary()})! (-{gold_cost} G)",
        new_item,
    )
