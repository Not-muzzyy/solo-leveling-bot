"""
game/tower.py — Demon Castle 100-Floor Spire Simulation & Reward Logic.

Provides:
- 100-floor scaling monster guardian generation
- Milestone boss definitions (Cerberus, Vulcan, Metus, Baran)
- Turn-based ascension duel calculation
- Reward distribution (Gold, XP, Titles, Milestone Artifacts)
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional, Tuple

from config import RARITY_STAT_MULTIPLIER
from game.items import generate_weapon, generate_armor, generate_accessory
from models import Hunter, Item

MILESTONE_BOSSES = {
    10: {
        "name": "Cerberus, Gatekeeper of the Underworld",
        "hp_mult": 1.5,
        "atk_mult": 1.3,
        "gold": 1500,
        "xp": 350,
        "title": "Hell Gatekeeper Vanquisher",
        "drop_rarity": "Uncommon",
    },
    25: {
        "name": "Demon Knight Commander",
        "hp_mult": 1.8,
        "atk_mult": 1.4,
        "gold": 4000,
        "xp": 800,
        "title": "Demon Vanguard Slayer",
        "drop_rarity": "Rare",
    },
    50: {
        "name": "Flame Monarch Vulcan",
        "hp_mult": 2.2,
        "atk_mult": 1.6,
        "gold": 12000,
        "xp": 2000,
        "title": "Flame Conqueror",
        "drop_rarity": "Epic",
    },
    75: {
        "name": "Arch-Lich Metus",
        "hp_mult": 2.6,
        "atk_mult": 1.8,
        "gold": 30000,
        "xp": 5000,
        "title": "Soul Reaper",
        "drop_rarity": "Legendary",
    },
    100: {
        "name": "Demon King Baran",
        "hp_mult": 3.2,
        "atk_mult": 2.2,
        "gold": 100000,
        "xp": 15000,
        "title": "Demon King Conqueror",
        "drop_rarity": "Mythic",
    },
}

NORMAL_GUARDIANS = [
    "Lesser Demon Grunt",
    "Hellhound Stalker",
    "Sulfur Imp Warlock",
    "Ironfang Demon Hound",
    "Flame Orc Berserker",
    "Obsidian Gargoyle",
    "Infernal Bloodhound",
    "Abyssal Demon Warrior",
    "Torment Fiend",
    "Hellfire Elemental",
]


@dataclass
class TowerGuardian:
    floor: int
    name: str
    hp: int
    atk: int
    defense: int
    is_boss: bool = False
    reward_gold: int = 0
    reward_xp: int = 0

    @property
    def power(self) -> int:
        return self.atk * 2 + self.defense + (self.hp // 5)

    @property
    def is_milestone(self) -> bool:
        return self.is_boss

    @property
    def gold_reward(self) -> int:
        return self.reward_gold

    @property
    def xp_reward(self) -> int:
        return self.reward_xp


@dataclass
class TowerBattleResult:
    victory: bool
    floor: int
    guardian: TowerGuardian
    damage_dealt: int
    damage_taken: int
    gold_gained: int = 0
    xp_gained: int = 0
    item_drop: Optional[Item] = None
    title_unlocked: Optional[str] = None
    leveled_up: bool = False
    new_rank: Optional[str] = None


def generate_guardian(floor: int) -> TowerGuardian:
    """Generate the Demon Castle guardian for a specific floor (1..100)."""
    if floor in MILESTONE_BOSSES:
        info = MILESTONE_BOSSES[floor]
        base_hp = int((100 + floor * 30) * info["hp_mult"])
        base_atk = int((10 + floor * 3.5) * info["atk_mult"])
        base_def = int((5 + floor * 2.2) * 1.3)
        return TowerGuardian(
            floor=floor,
            name=info["name"],
            hp=base_hp,
            atk=base_atk,
            defense=base_def,
            is_boss=True,
            reward_gold=info["gold"],
            reward_xp=info["xp"],
        )
    else:
        name_prefix = NORMAL_GUARDIANS[(floor - 1) % len(NORMAL_GUARDIANS)]
        full_name = f"{name_prefix} (Floor {floor})"
        base_hp = 70 + (floor * 22) + random.randint(-5, 10)
        base_atk = 7 + int(floor * 2.8) + random.randint(-1, 3)
        base_def = 3 + int(floor * 1.8)
        gold = 25 + (floor * 12) + random.randint(0, 10)
        xp = 40 + (floor * 18) + random.randint(0, 15)
        return TowerGuardian(
            floor=floor,
            name=full_name,
            hp=base_hp,
            atk=base_atk,
            defense=base_def,
            is_boss=False,
            reward_gold=gold,
            reward_xp=xp,
        )


def simulate_tower_climb(hunter: Hunter, floor: int) -> TowerBattleResult:
    """Simulate a battle on the given Demon Castle floor."""
    guardian = generate_guardian(floor)

    hunter_atk = hunter.str_stat + (hunter.per * 0.4)
    hunter_def = hunter.vit + (hunter.agi * 0.3)

    # Damage calculation
    raw_h_dmg = hunter_atk * random.uniform(0.9, 1.25)
    dmg_to_guardian = max(1, int(raw_h_dmg - guardian.defense * 0.35))

    # Critical hit chance
    if random.random() < 0.20:
        dmg_to_guardian = int(dmg_to_guardian * 1.5)

    raw_g_dmg = guardian.atk * random.uniform(0.8, 1.15)
    dmg_to_hunter = max(0, int(raw_g_dmg - hunter_def * 0.35))

    # Outcome evaluation
    hunter_score = dmg_to_guardian * 1.2 + hunter.power + random.randint(0, 10)
    guardian_score = guardian.hp * 0.3 + guardian.atk * 2.5 + random.randint(0, 10)

    victory = hunter_score >= guardian_score

    gold_gained = 0
    xp_gained = 0
    item_drop: Optional[Item] = None
    title_unlocked: Optional[str] = None

    if victory:
        gold_gained = guardian.reward_gold
        xp_gained = guardian.reward_xp

        # Milestone boss rewards
        if floor in MILESTONE_BOSSES:
            info = MILESTONE_BOSSES[floor]
            title_unlocked = info.get("title")
            drop_rarity = info.get("drop_rarity", "Rare")
            item_drop = generate_weapon(hunter.level, rarity=drop_rarity)
        elif random.random() < 0.25:
            # Random loot chance on regular floors
            item_drop = generate_accessory(hunter.level)
    else:
        # Consolation XP on defeat
        xp_gained = max(5, guardian.reward_xp // 6)

    return TowerBattleResult(
        victory=victory,
        floor=floor,
        guardian=guardian,
        damage_dealt=dmg_to_guardian,
        damage_taken=dmg_to_hunter,
        gold_gained=gold_gained,
        xp_gained=xp_gained,
        item_drop=item_drop,
        title_unlocked=title_unlocked,
    )
