"""
game/hunter.py — Hunter creation, leveling, and rank-up logic.
"""

from __future__ import annotations

import random
from typing import Optional

from config import (
    STAT_MIN,
    STAT_MAX,
    BASE_HP,
    BASE_GOLD,
    RANKS,
    RANK_LEVEL_THRESHOLDS,
    xp_for_level,
)
from models import Hunter


def create_new_hunter(
    user_id: int,
    username: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> Hunter:
    """Create a fresh Hunter with randomized starting stats."""
    str_stat = random.randint(STAT_MIN, STAT_MAX)
    agi = random.randint(STAT_MIN, STAT_MAX)
    vit = random.randint(STAT_MIN, STAT_MAX)
    int_stat = random.randint(STAT_MIN, STAT_MAX)
    per = random.randint(STAT_MIN, STAT_MAX)
    power = str_stat + agi + vit + int_stat + per

    # HP scales with vitality
    max_hp = BASE_HP + (vit * 5)

    fn = (first_name or "").strip()
    ln = (last_name or "").strip()
    if fn and ln:
        hunter_name = f"{fn} {ln}"
    elif fn:
        hunter_name = fn
    elif username:
        hunter_name = username
    else:
        hunter_name = f"Hunter_{user_id}"

    return Hunter(
        user_id=user_id,
        username=username,
        hunter_name=hunter_name,
        level=1,
        rank="E",
        xp=0,
        xp_needed=xp_for_level(1),
        gold=BASE_GOLD,
        hp=max_hp,
        max_hp=max_hp,
        str_stat=str_stat,
        agi=agi,
        vit=vit,
        int_stat=int_stat,
        per=per,
        power=power,
        title="Novice Hunter",
        first_name=first_name,
        last_name=last_name,
    )


def add_xp(hunter: Hunter, amount: int) -> tuple[bool, Optional[str]]:
    """
    Add XP to a hunter. Returns (leveled_up, new_rank_or_None).
    Handles multiple level-ups in one call.
    """
    hunter.xp += amount
    leveled_up = False
    new_rank = None

    while hunter.xp >= hunter.xp_needed:
        hunter.xp -= hunter.xp_needed
        hunter.level += 1
        hunter.xp_needed = xp_for_level(hunter.level)
        leveled_up = True

        # Stat gains on level up
        hunter.str_stat += random.randint(1, 3)
        hunter.agi += random.randint(1, 3)
        hunter.vit += random.randint(1, 3)
        hunter.int_stat += random.randint(1, 3)
        hunter.per += random.randint(1, 3)

        # Recalculate derived stats
        hunter.max_hp = BASE_HP + (hunter.vit * 5)
        hunter.hp = hunter.max_hp  # Full heal on level up
        hunter.recalculate_power()

        # Check rank up
        rank_result = check_rank_up(hunter)
        if rank_result:
            new_rank = rank_result

    return leveled_up, new_rank


def check_rank_up(hunter: Hunter) -> Optional[str]:
    """
    Check if hunter qualifies for a rank promotion.
    Returns new rank name if promoted, None otherwise.
    """
    current_rank_idx = RANKS.index(hunter.rank) if hunter.rank in RANKS else 0

    for rank in reversed(RANKS):
        threshold = RANK_LEVEL_THRESHOLDS.get(rank, 999)
        if hunter.level >= threshold:
            rank_idx = RANKS.index(rank)
            if rank_idx > current_rank_idx:
                hunter.rank = rank
                return rank
            break

    return None


def calculate_effective_power(hunter: Hunter, equipped_items: list) -> int:
    """Calculate total power including equipment bonuses."""
    base_power = hunter.str_stat + hunter.agi + hunter.vit + hunter.int_stat + hunter.per
    equip_bonus = sum(
        item.atk_bonus + item.def_bonus + item.hp_bonus + item.spd_bonus
        for item in equipped_items
    )
    return base_power + equip_bonus
