"""Progression rebalance tests — script-style asserts (no pytest).

Approach A: XP_EXPONENT 1.75, DAILY_DUEL_XP_LIMIT 10, GUILD_XP_BONUS 0.05,
flat duel-loser XP 10, capped daily duel XP, hunt loss consolation // 10,
dead tower consolation removed, no add_xp(bonus=...).
"""
import inspect
import sys
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from models import Hunter

passed = 0

def check(name, cond):
    global passed
    assert cond, f"FAIL: {name}"
    passed += 1
    print(f"ok: {name}")

# ── Task 1: config knobs + curve ─────────────────────────
check("XP_EXPONENT == 1.75", config.XP_EXPONENT == 1.75)
check("DAILY_DUEL_XP_LIMIT == 10", config.DAILY_DUEL_XP_LIMIT == 10)
check("GUILD_XP_BONUS == 0.05", config.GUILD_XP_BONUS == 0.05)
check("xp_for_level(1) == 100", config.xp_for_level(1) == 100)
check("xp_for_level(10) == 5623", config.xp_for_level(10) == 5623)
check("xp_for_level(20) == 18914", config.xp_for_level(20) == 18914)
check("xp_for_level(50) == 94015", config.xp_for_level(50) == 94015)
check("xp_for_level(100) == 316227", config.xp_for_level(100) == 316227)

print(f"\n{passed} passed")
