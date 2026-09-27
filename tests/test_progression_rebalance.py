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

# ── Task 2: duel XP daily counter reset ──────────────────
_today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
_yesterday = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

h_stale = Hunter(user_id=1, username="u", hunter_name="Stale")
h_stale.duel_xp_today = 7
h_stale.last_duel_date = _yesterday
h_stale.check_and_reset_daily()
check("stale date resets duel_xp_today to 0", h_stale.duel_xp_today == 0)
check("stale date updates last_duel_date to today", h_stale.last_duel_date == _today)

h_fresh = Hunter(user_id=2, username="u", hunter_name="Fresh")
h_fresh.duel_xp_today = 7
h_fresh.last_duel_date = _today
h_fresh.check_and_reset_daily()
check("fresh date keeps duel_xp_today", h_fresh.duel_xp_today == 7)

print(f"\n{passed} passed")
