"""
game/items.py — Item generation and rarity system.
"""

from __future__ import annotations

import random

from config import (
    RARITIES,
    RARITY_WEIGHTS,
    RARITY_STAT_MULTIPLIER,
    WEAPON_PREFIXES,
    WEAPON_MATERIALS,
    WEAPON_TYPES,
    ARMOR_TYPES,
    ACCESSORY_TYPES,
)
from models import Hunter, Item


def roll_rarity() -> str:
    """Roll a random rarity based on weighted probabilities."""
    return random.choices(RARITIES, weights=RARITY_WEIGHTS, k=1)[0]


def generate_weapon(level: int, rarity: str | None = None) -> Item:
    """Generate a random weapon scaled to the given level."""
    if rarity is None:
        rarity = roll_rarity()

    multiplier = RARITY_STAT_MULTIPLIER[rarity]
    base_atk = max(1, int((level * 2 + random.randint(1, 5)) * multiplier))

    prefix = random.choice(WEAPON_PREFIXES)
    material = random.choice(WEAPON_MATERIALS)
    weapon_type = random.choice(WEAPON_TYPES)
    name = f"{prefix} {material} {weapon_type}"

    return Item(
        id=0,  # Assigned by Inventory.add_item()
        name=name,
        type="weapon",
        rarity=rarity,
        atk_bonus=base_atk,
        def_bonus=0,
        hp_bonus=0,
        spd_bonus=random.randint(0, max(1, int(level * 0.5 * multiplier))),
    )


def generate_armor(level: int, rarity: str | None = None) -> Item:
    """Generate a random armor piece scaled to the given level."""
    if rarity is None:
        rarity = roll_rarity()

    multiplier = RARITY_STAT_MULTIPLIER[rarity]
    base_def = max(1, int((level * 1.5 + random.randint(1, 4)) * multiplier))
    base_hp = max(0, int((level * 2 + random.randint(0, 5)) * multiplier))

    prefix = random.choice(WEAPON_PREFIXES)  # Reuse prefixes
    armor_type = random.choice(ARMOR_TYPES)
    name = f"{prefix} {armor_type}"

    return Item(
        id=0,
        name=name,
        type="armor",
        rarity=rarity,
        atk_bonus=0,
        def_bonus=base_def,
        hp_bonus=base_hp,
        spd_bonus=0,
    )


def generate_accessory(level: int, rarity: str | None = None) -> Item:
    """Generate a random accessory scaled to the given level."""
    if rarity is None:
        rarity = roll_rarity()

    multiplier = RARITY_STAT_MULTIPLIER[rarity]

    acc_type = random.choice(ACCESSORY_TYPES)
    prefix = random.choice(WEAPON_PREFIXES)
    name = f"{prefix} {acc_type}"

    # Accessories give mixed small bonuses
    return Item(
        id=0,
        name=name,
        type="accessory",
        rarity=rarity,
        atk_bonus=random.randint(0, max(1, int(level * 0.8 * multiplier))),
        def_bonus=random.randint(0, max(1, int(level * 0.5 * multiplier))),
        hp_bonus=random.randint(0, max(1, int(level * 1.0 * multiplier))),
        spd_bonus=random.randint(0, max(1, int(level * 0.5 * multiplier))),
    )


def generate_material(level: int) -> Item:
    """Generate a crafting material (no stats, for future use)."""
    materials = [
        "Monster Fang", "Beast Hide", "Magic Crystal", "Dark Essence",
        "Shadow Fragment", "Mana Stone", "Dragon Scale", "Spirit Core",
        "Iron Ore", "Mystic Herb", "Venom Sac", "Bone Shard",
    ]
    rarity = roll_rarity()
    name = f"{rarity} {random.choice(materials)}"

    return Item(
        id=0,
        name=name,
        type="material",
        rarity=rarity,
    )


def generate_loot(monster_level: int) -> Item:
    """Generate a random loot drop from a monster kill."""
    # Weighted type selection: weapons and armor more common
    item_type = random.choices(
        ["weapon", "armor", "accessory", "material"],
        weights=[35, 30, 15, 20],
        k=1,
    )[0]

    if item_type == "weapon":
        return generate_weapon(monster_level)
    elif item_type == "armor":
        return generate_armor(monster_level)
    elif item_type == "accessory":
        return generate_accessory(monster_level)
    else:
        return generate_material(monster_level)


def create_starter_weapon() -> Item:
    """Create the starter weapon every new hunter receives."""
    return Item(
        id=0,
        name="Rusty Short Sword",
        type="weapon",
        rarity="Common",
        atk_bonus=3,
        def_bonus=0,
        hp_bonus=0,
        spd_bonus=0,
    )


def apply_consumable(hunter: Hunter, item: Item) -> tuple[bool, str]:
    """
    Apply consumable potion, elixir, or scroll effect to a Hunter.
    Returns (success: bool, description: str).
    If a pure healing potion is used while hunter is at full health, returns (False, reason).
    """
    if item.type != "consumable":
        return False, "This item is not a consumable."

    is_pure_hp = (item.hp_bonus > 0 and item.atk_bonus == 0 and item.def_bonus == 0 and item.spd_bonus == 0)

    # Prevent wasting pure health potions when already full
    if is_pure_hp and hunter.hp >= hunter.max_hp:
        return False, f"Vitality already at maximum ({hunter.hp}/{hunter.max_hp} HP)!"

    effects: list[str] = []

    # Stat boosts
    if item.atk_bonus > 0:
        hunter.str_stat += item.atk_bonus
        effects.append(f"+{item.atk_bonus} STR")

    if item.def_bonus > 0:
        hunter.vit += item.def_bonus
        effects.append(f"+{item.def_bonus} VIT")

    if item.spd_bonus > 0:
        hunter.agi += item.spd_bonus
        effects.append(f"+{item.spd_bonus} AGI")

    # Pure healing vs hybrid max HP bonus
    if is_pure_hp:
        healed = min(item.hp_bonus, hunter.max_hp - hunter.hp)
        hunter.hp += healed
        effects.append(f"+{healed} HP ({hunter.hp}/{hunter.max_hp})")
    elif item.hp_bonus > 0:
        hunter.max_hp += item.hp_bonus
        hunter.hp = min(hunter.max_hp, hunter.hp + item.hp_bonus)
        effects.append(f"+{item.hp_bonus} Max HP")

    hunter.recalculate_power()
    effects.append(f"Power: {hunter.power}")

    return True, ", ".join(effects)

