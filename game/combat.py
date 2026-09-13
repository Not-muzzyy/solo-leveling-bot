"""
game/combat.py — Monster generation and hunt simulation.
"""

from __future__ import annotations

import random
from typing import Optional

from config import (
    RANKS,
    RANK_LEVEL_THRESHOLDS,
    MONSTER_PREFIXES,
    MONSTER_NAMES,
    CRITICAL_HIT_CHANCE,
    CRITICAL_HIT_MULTIPLIER,
    LOOT_DROP_CHANCE,
    SPECIAL_EVENT_CHANCE,
    GOLD_LOSS_ON_DEFEAT_PERCENT,
)
from models import Hunter, Monster, HuntResult, Item
from game.items import generate_loot


# ── Special Events ────────────────────────────────────────

SPECIAL_EVENTS = [
    "⚡ A Shadow Extraction was attempted... but failed.",
    "🌀 A Gate has been detected nearby. Something powerful lurks within...",
    "👁️ You feel an overwhelming presence watching you. The System trembles.",
    "💀 A whisper echoes: \"You are not yet worthy, Hunter.\"",
    "🔮 A mysterious rune appears on your hand and fades away...",
    "⚔️ Your weapon glows with a faint dark aura for a moment.",
    "🌑 For a split second, your shadow moves on its own...",
    "📜 A quest scroll materializes... then crumbles to dust.",
    "🗝️ You found a fragment of an unknown key.",
    "💎 A rare magic crystal embedded in the monster caught your eye.",
]


def _rank_for_level(level: int) -> str:
    """Determine rank based on level."""
    result = "E"
    for rank in RANKS:
        threshold = RANK_LEVEL_THRESHOLDS.get(rank, 999)
        if level >= threshold:
            result = rank
        else:
            break
    return result


def generate_monster(hunter_level: int) -> Monster:
    """Generate a random monster scaled to the hunter's level (±2 levels)."""
    monster_level = max(1, hunter_level + random.randint(-2, 2))
    rank = _rank_for_level(monster_level)

    prefix = random.choice(MONSTER_PREFIXES)
    name = random.choice(MONSTER_NAMES)
    full_name = f"{prefix} {name}"

    # Scale monster stats to level
    base_hp = 50 + (monster_level * 15) + random.randint(-10, 10)
    base_atk = 5 + (monster_level * 3) + random.randint(-2, 3)
    base_def = 2 + (monster_level * 2) + random.randint(-2, 2)

    # Rewards scale with level
    xp_reward = int(20 + (monster_level * 8) + random.randint(-5, 10))
    gold_reward = int(10 + (monster_level * 5) + random.randint(-3, 8))

    return Monster(
        name=full_name,
        level=monster_level,
        rank=rank,
        hp=max(30, base_hp),
        attack=max(3, base_atk),
        defense=max(1, base_def),
        xp_reward=max(10, xp_reward),
        gold_reward=max(5, gold_reward),
    )


def simulate_hunt(hunter: Hunter, monster: Monster) -> HuntResult:
    """
    Simulate a hunt encounter between a hunter and a monster.
    Uses a simplified turn-based system resolved in one calculation.
    """
    # ── Calculate hunter effective stats ──
    hunter_atk = hunter.str_stat + (hunter.per * 0.3)
    hunter_def = hunter.vit + (hunter.agi * 0.2)

    # ── Calculate damage ──
    # Hunter → Monster
    raw_damage = hunter_atk * random.uniform(0.8, 1.2)
    damage_to_monster = max(1, int(raw_damage - monster.defense * 0.4))

    # Check critical hit
    critical_hit = random.random() < CRITICAL_HIT_CHANCE
    if critical_hit:
        damage_to_monster = int(damage_to_monster * CRITICAL_HIT_MULTIPLIER)

    # Monster → Hunter
    raw_monster_damage = monster.attack * random.uniform(0.7, 1.1)
    damage_to_hunter = max(0, int(raw_monster_damage - hunter_def * 0.3))

    # ── Determine outcome ──
    # Compare effective combat scores
    hunter_score = damage_to_monster + (hunter.agi * 0.5) + random.randint(0, 5)
    monster_score = damage_to_monster * 0.3 + (monster.hp * 0.1) + random.randint(0, 3)

    # Higher level monsters are harder but not impossible
    level_diff = monster.level - hunter.level
    if level_diff > 0:
        monster_score += level_diff * 3

    victory = hunter_score > monster_score

    # ── Calculate rewards ──
    xp_gained = 0
    gold_gained = 0
    gold_lost = 0
    item_drop: Optional[Item] = None
    special_event: Optional[str] = None

    if victory:
        xp_gained = monster.xp_reward + random.randint(0, 5)
        gold_gained = monster.gold_reward + random.randint(0, 3)

        # Loot drop chance
        if random.random() < LOOT_DROP_CHANCE:
            item_drop = generate_loot(monster.level)

        # Special event chance
        if random.random() < SPECIAL_EVENT_CHANCE:
            special_event = random.choice(SPECIAL_EVENTS)
    else:
        # Defeat penalty: lose some gold
        gold_lost = max(1, int(hunter.gold * GOLD_LOSS_ON_DEFEAT_PERCENT))
        # Still get a small amount of XP for trying
        xp_gained = max(1, monster.xp_reward // 5)

    return HuntResult(
        victory=victory,
        monster=monster,
        damage_dealt=damage_to_monster,
        damage_taken=damage_to_hunter,
        xp_gained=xp_gained,
        gold_gained=gold_gained,
        critical_hit=critical_hit,
        item_drop=item_drop,
        special_event=special_event,
        gold_lost=gold_lost,
    )
