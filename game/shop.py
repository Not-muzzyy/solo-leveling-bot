"""
game/shop.py — Shop system with purchasable items.
"""

from __future__ import annotations

from models import Item


# ── Shop Inventory ────────────────────────────────────────
# Each entry: (key, name, type, rarity, atk, def, hp, spd, price)
# key is used for callback_data

SHOP_ITEMS: list[dict] = [
    # ── Weapons ───────────────────────────────────────────
    {
        "key": "iron_sword",
        "name": "Iron Longsword",
        "type": "weapon",
        "rarity": "Common",
        "atk": 5, "def": 0, "hp": 0, "spd": 1,
        "price": 50,
    },
    {
        "key": "steel_axe",
        "name": "Steel Battle Axe",
        "type": "weapon",
        "rarity": "Uncommon",
        "atk": 10, "def": 0, "hp": 0, "spd": 0,
        "price": 150,
    },
    {
        "key": "mithril_katana",
        "name": "Mithril Katana",
        "type": "weapon",
        "rarity": "Rare",
        "atk": 20, "def": 0, "hp": 0, "spd": 5,
        "price": 500,
    },
    {
        "key": "shadow_blade",
        "name": "Shadow Blade",
        "type": "weapon",
        "rarity": "Epic",
        "atk": 35, "def": 0, "hp": 0, "spd": 8,
        "price": 1500,
    },
    {
        "key": "dragons_fang",
        "name": "Dragon's Fang",
        "type": "weapon",
        "rarity": "Legendary",
        "atk": 60, "def": 5, "hp": 0, "spd": 10,
        "price": 5000,
    },

    # ── Armor ─────────────────────────────────────────────
    {
        "key": "leather_vest",
        "name": "Leather Vest",
        "type": "armor",
        "rarity": "Common",
        "atk": 0, "def": 4, "hp": 10, "spd": 0,
        "price": 40,
    },
    {
        "key": "chainmail",
        "name": "Steel Chainmail",
        "type": "armor",
        "rarity": "Uncommon",
        "atk": 0, "def": 8, "hp": 20, "spd": 0,
        "price": 120,
    },
    {
        "key": "plate_armor",
        "name": "Knight's Plate Armor",
        "type": "armor",
        "rarity": "Rare",
        "atk": 0, "def": 18, "hp": 40, "spd": 0,
        "price": 450,
    },
    {
        "key": "shadow_robe",
        "name": "Shadow Silk Robe",
        "type": "armor",
        "rarity": "Epic",
        "atk": 5, "def": 25, "hp": 60, "spd": 5,
        "price": 1200,
    },
    {
        "key": "monarch_armor",
        "name": "Monarch's Aegis",
        "type": "armor",
        "rarity": "Legendary",
        "atk": 10, "def": 50, "hp": 100, "spd": 8,
        "price": 4500,
    },

    # ── Accessories ───────────────────────────────────────
    {
        "key": "copper_ring",
        "name": "Copper Ring",
        "type": "accessory",
        "rarity": "Common",
        "atk": 2, "def": 1, "hp": 5, "spd": 1,
        "price": 30,
    },
    {
        "key": "silver_amulet",
        "name": "Silver Amulet",
        "type": "accessory",
        "rarity": "Uncommon",
        "atk": 4, "def": 3, "hp": 10, "spd": 2,
        "price": 100,
    },
    {
        "key": "mana_pendant",
        "name": "Mana Crystal Pendant",
        "type": "accessory",
        "rarity": "Rare",
        "atk": 8, "def": 6, "hp": 20, "spd": 5,
        "price": 400,
    },
    {
        "key": "shadow_earring",
        "name": "Shadow Monarch's Earring",
        "type": "accessory",
        "rarity": "Epic",
        "atk": 15, "def": 10, "hp": 35, "spd": 8,
        "price": 1000,
    },

    # ── Consumables ───────────────────────────────────────
    {
        "key": "hp_potion",
        "name": "Health Potion",
        "type": "consumable",
        "rarity": "Common",
        "atk": 0, "def": 0, "hp": 50, "spd": 0,
        "price": 20,
    },
    {
        "key": "str_elixir",
        "name": "Elixir of Strength",
        "type": "consumable",
        "rarity": "Uncommon",
        "atk": 5, "def": 0, "hp": 0, "spd": 0,
        "price": 80,
    },
    {
        "key": "shield_scroll",
        "name": "Scroll of Protection",
        "type": "consumable",
        "rarity": "Uncommon",
        "atk": 0, "def": 5, "hp": 20, "spd": 0,
        "price": 80,
    },
    {
        "key": "speed_potion",
        "name": "Swift Potion",
        "type": "consumable",
        "rarity": "Rare",
        "atk": 0, "def": 0, "hp": 0, "spd": 10,
        "price": 200,
    },

    # ── Materials ─────────────────────────────────────────
    {
        "key": "iron_ore",
        "name": "Refined Iron Ore",
        "type": "material",
        "rarity": "Common",
        "atk": 0, "def": 0, "hp": 0, "spd": 0,
        "price": 15,
    },
    {
        "key": "magic_crystal",
        "name": "Magic Crystal",
        "type": "material",
        "rarity": "Uncommon",
        "atk": 0, "def": 0, "hp": 0, "spd": 0,
        "price": 60,
    },
    {
        "key": "shadow_essence",
        "name": "Shadow Essence",
        "type": "material",
        "rarity": "Rare",
        "atk": 0, "def": 0, "hp": 0, "spd": 0,
        "price": 250,
    },
    {
        "key": "dragon_scale",
        "name": "Dragon Scale",
        "type": "material",
        "rarity": "Epic",
        "atk": 0, "def": 0, "hp": 0, "spd": 0,
        "price": 800,
    },
]

# Build lookup dict
_SHOP_BY_KEY: dict[str, dict] = {item["key"]: item for item in SHOP_ITEMS}


def get_shop_item(key: str) -> dict | None:
    """Look up a shop item by its key."""
    return _SHOP_BY_KEY.get(key)


def get_shop_items_by_type(item_type: str) -> list[dict]:
    """Get all shop items of a given type."""
    return [i for i in SHOP_ITEMS if i["type"] == item_type]


def create_item_from_shop(shop_entry: dict) -> Item:
    """Create an Item instance from a shop entry."""
    return Item(
        id=0,  # assigned by Inventory.add_item()
        name=shop_entry["name"],
        type=shop_entry["type"],
        rarity=shop_entry["rarity"],
        atk_bonus=shop_entry["atk"],
        def_bonus=shop_entry["def"],
        hp_bonus=shop_entry["hp"],
        spd_bonus=shop_entry["spd"],
    )
