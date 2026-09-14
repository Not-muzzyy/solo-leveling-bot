"""
game/duel.py — PvP Hunter Duel combat engine.

Simulates turn-based arena combat between two registered hunters factoring in:
- Hunter core attributes (STR, AGI, VIT, INT, PER)
- Equipped weapons, armor, accessories
- Initiative (Speed), Critical strikes, Damage mitigation
- Level-up, Rank-up, XP/Gold spoils, and Duel win/loss records.
"""

from __future__ import annotations

import random
from typing import Optional, Tuple

from config import (
    CRITICAL_HIT_CHANCE,
    CRITICAL_HIT_MULTIPLIER,
)
from models import Hunter, Inventory, Item, DuelResult
from game.hunter import add_xp


def _get_equipment_bonuses(inv: Optional[Inventory]) -> Tuple[int, int, int, int, Optional[Item], Optional[Item]]:
    """
    Extract ATK, DEF, HP, SPD bonuses from currently equipped gear,
    along with equipped weapon and armor items for display.
    """
    if not inv:
        return 0, 0, 0, 0, None, None

    atk_bonus = 0
    def_bonus = 0
    hp_bonus = 0
    spd_bonus = 0

    weapon = inv.get_equipped("weapon")
    armor = inv.get_equipped("armor")
    accessory = inv.get_equipped("accessory")

    for item in (weapon, armor, accessory):
        if item:
            atk_bonus += item.atk_bonus
            def_bonus += item.def_bonus
            hp_bonus += item.hp_bonus
            spd_bonus += item.spd_bonus

    return atk_bonus, def_bonus, hp_bonus, spd_bonus, weapon, armor


def simulate_duel(
    challenger: Hunter,
    challenger_inv: Optional[Inventory],
    opponent: Hunter,
    opponent_inv: Optional[Inventory],
) -> DuelResult:
    """
    Simulate a full arena duel between challenger and opponent.
    Updates duel_wins, duel_losses, XP, Gold, and levels.
    Returns DuelResult with full battle metrics.
    """
    # 1. Calculate Challenger Effective Combat Stats
    c_atk_b, c_def_b, c_hp_b, c_spd_b, _, _ = _get_equipment_bonuses(challenger_inv)
    c_atk = challenger.str_stat * 1.5 + challenger.agi * 0.4 + c_atk_b
    c_def = challenger.vit * 1.2 + c_def_b
    c_spd = challenger.agi * 1.3 + c_spd_b
    c_max_hp = max(60, challenger.max_hp + c_hp_b)
    c_crit_rate = min(0.45, max(0.10, CRITICAL_HIT_CHANCE + (challenger.per / 250.0)))
    c_crit_mult = CRITICAL_HIT_MULTIPLIER + (challenger.int_stat / 250.0)

    # 2. Calculate Opponent Effective Combat Stats
    o_atk_b, o_def_b, o_hp_b, o_spd_b, _, _ = _get_equipment_bonuses(opponent_inv)
    o_atk = opponent.str_stat * 1.5 + opponent.agi * 0.4 + o_atk_b
    o_def = opponent.vit * 1.2 + o_def_b
    o_spd = opponent.agi * 1.3 + o_spd_b
    o_max_hp = max(60, opponent.max_hp + o_hp_b)
    o_crit_rate = min(0.45, max(0.10, CRITICAL_HIT_CHANCE + (opponent.per / 250.0)))
    o_crit_mult = CRITICAL_HIT_MULTIPLIER + (opponent.int_stat / 250.0)

    # 3. Simulate Combat Rounds
    c_cur_hp = c_max_hp
    o_cur_hp = o_max_hp
    c_total_damage = 0
    o_total_damage = 0
    c_crits = 0
    o_crits = 0

    max_rounds = 8
    actual_rounds = 0

    for round_num in range(1, max_rounds + 1):
        actual_rounds = round_num

        # Determine initiative for this turn
        c_initiative = c_spd + random.uniform(-5, 5)
        o_initiative = o_spd + random.uniform(-5, 5)

        if c_initiative >= o_initiative:
            first_actor = "c"
        else:
            first_actor = "o"

        # Turn 1 Action
        if first_actor == "c":
            # Challenger strikes Opponent
            is_crit = random.random() < c_crit_rate
            dmg = max(8, int(c_atk * random.uniform(0.85, 1.15) - o_def * 0.45))
            if is_crit:
                dmg = int(dmg * c_crit_mult)
                c_crits += 1
            o_cur_hp = max(0, o_cur_hp - dmg)
            c_total_damage += dmg

            if o_cur_hp <= 0:
                break

            # Opponent retaliates
            is_crit = random.random() < o_crit_rate
            dmg = max(8, int(o_atk * random.uniform(0.85, 1.15) - c_def * 0.45))
            if is_crit:
                dmg = int(dmg * o_crit_mult)
                o_crits += 1
            c_cur_hp = max(0, c_cur_hp - dmg)
            o_total_damage += dmg

            if c_cur_hp <= 0:
                break
        else:
            # Opponent strikes Challenger
            is_crit = random.random() < o_crit_rate
            dmg = max(8, int(o_atk * random.uniform(0.85, 1.15) - c_def * 0.45))
            if is_crit:
                dmg = int(dmg * o_crit_mult)
                o_crits += 1
            c_cur_hp = max(0, c_cur_hp - dmg)
            o_total_damage += dmg

            if c_cur_hp <= 0:
                break

            # Challenger retaliates
            is_crit = random.random() < c_crit_rate
            dmg = max(8, int(c_atk * random.uniform(0.85, 1.15) - o_def * 0.45))
            if is_crit:
                dmg = int(dmg * c_crit_mult)
                c_crits += 1
            o_cur_hp = max(0, o_cur_hp - dmg)
            c_total_damage += dmg

            if o_cur_hp <= 0:
                break

    # 4. Determine Winner & Loser
    if c_cur_hp > 0 and o_cur_hp <= 0:
        winner_is_challenger = True
    elif o_cur_hp > 0 and c_cur_hp <= 0:
        winner_is_challenger = False
    else:
        # Both standing: compare remaining HP percentage
        c_pct = c_cur_hp / c_max_hp
        o_pct = o_cur_hp / o_max_hp
        if c_pct >= o_pct:
            winner_is_challenger = True
        else:
            winner_is_challenger = False

    winner = challenger if winner_is_challenger else opponent
    loser = opponent if winner_is_challenger else challenger

    # 5. Update Hunter Records
    winner.duel_wins += 1
    loser.duel_losses += 1

    # 6. Rewards
    # Scaling rewards based on opponent level
    base_winner_xp = int(35 + (loser.level * 8) + random.randint(5, 15))
    base_winner_gold = int(25 + (loser.level * 6) + random.randint(5, 15))
    base_loser_xp = max(5, int(15 + (winner.level * 2)))

    winner.gold += base_winner_gold

    # Winner XP & Level progression
    w_leveled_up, w_new_rank = add_xp(winner, base_winner_xp)

    # Loser consolation XP
    add_xp(loser, base_loser_xp)

    return DuelResult(
        challenger=challenger,
        opponent=opponent,
        winner=winner,
        loser=loser,
        winner_is_challenger=winner_is_challenger,
        challenger_damage_dealt=c_total_damage,
        opponent_damage_dealt=o_total_damage,
        challenger_hp_left=c_cur_hp,
        opponent_hp_left=o_cur_hp,
        challenger_max_hp=c_max_hp,
        opponent_max_hp=o_max_hp,
        challenger_crits=c_crits,
        opponent_crits=o_crits,
        total_rounds=actual_rounds,
        winner_xp_gained=base_winner_xp,
        winner_gold_gained=base_winner_gold,
        loser_xp_gained=base_loser_xp,
        winner_leveled_up=w_leveled_up,
        winner_new_level=winner.level if w_leveled_up else None,
        winner_ranked_up=w_new_rank is not None,
        winner_new_rank=w_new_rank,
    )
