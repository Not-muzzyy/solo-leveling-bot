"""
config.py — Game constants and environment configuration.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
API_ID: int = int(os.getenv("API_ID", "0"))
API_HASH: str = os.getenv("API_HASH", "")
DATA_CHANNEL_ID: int = int(os.getenv("DATA_CHANNEL_ID", "0"))

# ── Superadmin / Bot Owner ─────────────────────────────────
OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))
SUPERADMIN_IDS: list[int] = [
    int(x.strip())
    for x in os.getenv("SUPERADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]
if OWNER_ID and OWNER_ID not in SUPERADMIN_IDS:
    SUPERADMIN_IDS.append(OWNER_ID)

# ── Ranks (ordered) ──────────────────────────────────────
RANKS = ["E", "D", "C", "B", "A", "S", "SS", "SSS", "National Level", "Monarch"]

RANK_LEVEL_THRESHOLDS: dict[str, int] = {
    "E": 1,
    "D": 10,
    "C": 20,
    "B": 35,
    "A": 50,
    "S": 70,
    "SS": 85,
    "SSS": 95,
    "National Level": 100,
    "Monarch": 120,
}

RANK_EMOJI: dict[str, str] = {
    "E": "🅴",
    "D": "🅳",
    "C": "🅲",
    "B": "🅱️",
    "A": "🅰️",
    "S": "⭐",
    "SS": "🌟",
    "SSS": "💫",
    "National Level": "🔱",
    "Monarch": "👑",
}

# ── Rarities ─────────────────────────────────────────────
RARITIES = ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythic"]

RARITY_WEIGHTS: list[float] = [50.0, 25.0, 15.0, 7.0, 2.5, 0.5]

RARITY_EMOJI: dict[str, str] = {
    "Common": "⚪",
    "Uncommon": "🟢",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟡",
    "Mythic": "🔴",
}

RARITY_STAT_MULTIPLIER: dict[str, float] = {
    "Common": 1.0,
    "Uncommon": 1.5,
    "Rare": 2.5,
    "Epic": 4.0,
    "Legendary": 7.0,
    "Mythic": 10.0,
}

# ── Stats ────────────────────────────────────────────────
STAT_MIN = 5
STAT_MAX = 10

BASE_HP = 100
BASE_GOLD = 100

# ── Leveling ─────────────────────────────────────────────
def xp_for_level(level: int) -> int:
    """XP required to reach the next level."""
    return int(100 * (level ** 1.5))

# ── Combat ───────────────────────────────────────────────
CRITICAL_HIT_CHANCE = 0.10         # 10%
CRITICAL_HIT_MULTIPLIER = 2.0
LOOT_DROP_CHANCE = 0.30            # 30% base
SPECIAL_EVENT_CHANCE = 0.05        # 5%
GOLD_LOSS_ON_DEFEAT_PERCENT = 0.10 # Lose 10% gold on defeat

# ── Hunt Cooldown ────────────────────────────────────────
HUNT_COOLDOWN_SECONDS = 900  # 15 minutes

# ── Item Types ───────────────────────────────────────────
ITEM_TYPES = ["weapon", "armor", "accessory", "consumable", "material"]
EQUIPPABLE_TYPES = ["weapon", "armor", "accessory"]

# ── Monster Names ────────────────────────────────────────
MONSTER_PREFIXES = [
    "Steel-Fanged", "Iron-Scaled", "Shadow", "Crimson", "Frost",
    "Venom", "Stone", "Dark", "Blood", "Thunder", "Cursed",
    "Bone", "Flame", "Wind", "Ice", "Void", "Ancient",
]

MONSTER_NAMES = [
    "Lycan", "Cerberus", "Goblin", "Orc", "Elf Scout",
    "Ant Soldier", "Spider", "Golem", "Wraith", "Serpent",
    "Dire Wolf", "Troll", "Wyvern", "Skeleton Knight", "Mage",
    "Berserker", "Archer", "Necromancer", "Drake", "Demon",
    "Naga", "Minotaur", "Chimera", "Gargoyle", "Lich",
]

# ── Item Name Parts ──────────────────────────────────────
WEAPON_PREFIXES = [
    "Blazing", "Frozen", "Shadow", "Holy", "Cursed", "Ancient",
    "Storm", "Crimson", "Void", "Rusty", "Iron", "Steel",
    "Obsidian", "Crystal", "Demonic", "Silver", "Golden",
]

WEAPON_MATERIALS = [
    "Iron", "Steel", "Mithril", "Adamantite", "Orichalcum",
    "Bone", "Obsidian", "Crystal", "Shadow", "Dragon",
]

WEAPON_TYPES = [
    "Short Sword", "Longsword", "Dagger", "Axe", "Spear",
    "Mace", "Bow", "Staff", "Katana", "Greatsword",
    "Scimitar", "Halberd", "Warhammer", "Rapier", "Crossbow",
]

ARMOR_TYPES = [
    "Leather Vest", "Chainmail", "Plate Armor", "Robe",
    "Cloak", "Brigandine", "Scale Armor", "Shield",
    "Gauntlets", "Helm", "Boots", "Greaves",
]

ACCESSORY_TYPES = [
    "Ring", "Amulet", "Earring", "Bracelet", "Belt",
    "Pendant", "Charm", "Talisman", "Crown", "Cape",
]

# ── Titles ───────────────────────────────────────────────
TITLES: dict[str, str] = {
    "first_hunt": "Monster Slayer",
    "level_10": "Proven Hunter",
    "level_25": "Veteran Hunter",
    "level_50": "Elite Hunter",
    "first_legendary": "Fortune's Chosen",
    "first_mythic": "Myth Breaker",
    "100_hunts": "Relentless",
    "defeat_streak_5": "Unyielding",
}

# ── Guilds ──────────────────────────────────────────────
GUILD_MAX_MEMBERS = 15
GUILD_XP_BONUS = 0.10  # +10% XP for guild members while hunting

# ── Guild War Constants ──────────────────────────────────
GUILD_WAR_GOLD_REWARD = 200     # gold per member for winner
GUILD_WAR_BASE_XP = 100         # XP for all fighters
GUILD_WAR_WIN_BONUS_XP = 50     # extra XP per individual duel win
GUILD_WAR_WIN_SCORE = 50        # war_score gained by winner guild
GUILD_WAR_LOSS_SCORE = 30       # war_score lost by loser guild
GUILD_WAR_XP_PENALTY = 30       # XP lost by loser guild members
