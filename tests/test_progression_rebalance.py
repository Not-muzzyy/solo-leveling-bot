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

# ── Task 3: duel XP formulas + daily cap + grant_xp ──────
import random as _random
from game.hunter import add_xp
from game.duel import simulate_duel

def _mk(level, uid, name, duel_xp=0):
    h = Hunter(user_id=uid, username="u", hunter_name=name, level=level, xp=0,
               xp_needed=config.xp_for_level(level), duel_xp_today=duel_xp)
    return h

# 1+2. Formula band + flat loser XP (raise limit so raw formulas are observable)
import game.duel as _duel_mod
config.DAILY_DUEL_XP_LIMIT = 100000
_duel_mod.DAILY_DUEL_XP_LIMIT = 100000
try:
    for i in range(50):
        w = _mk(20, 200 + i, "W")
        o = _mk(30, 300 + i, "O")
        r = simulate_duel(w, None, o, None)
        lo = r.loser
        base = 25 + lo.level * 6
        check(f"winner XP in band [{base}..{base+10}] (loser L{lo.level})",
              base <= r.winner_xp_gained <= base + 10)
        check(f"loser XP flat 10 (loser L{lo.level})", r.loser_xp_gained == 10)
finally:
    config.DAILY_DUEL_XP_LIMIT = 10
    _duel_mod.DAILY_DUEL_XP_LIMIT = 10

# 3. Full cap: counter 0 → awarded 10, counter 10
w = _mk(20, 401, "W")
o = _mk(30, 402, "O")
r = simulate_duel(w, None, o, None)
check("full cap: awarded winner XP == 10", r.winner_xp_gained == 10)
check("full cap: awarded loser XP == 10", r.loser_xp_gained == 10)
check("full cap: winner counter == 10", r.winner.duel_xp_today == 10)
check("full cap: loser counter == 10", r.loser.duel_xp_today == 10)

# 4. Partial cap: counter 8 → awarded 2, counter 10
w = _mk(20, 403, "W", duel_xp=8)
o = _mk(30, 404, "O")
r = simulate_duel(w, None, o, None)
check("partial cap: awarded winner XP == 2", r.winner_xp_gained == 2)
check("partial cap: winner counter == 10", r.winner.duel_xp_today == 10)

# 5. grant_xp=False: 0 XP, counters untouched, gold identical to grant path (same seed)
w1 = _mk(20, 405, "A"); o1 = _mk(30, 406, "B")
w2 = _mk(20, 405, "A"); o2 = _mk(30, 406, "B")
_random.seed(42)
r1 = simulate_duel(w1, None, o1, None)
_random.seed(42)
r2 = simulate_duel(w2, None, o2, None, grant_xp=False)
check("grant_xp=False: winner XP == 0", r2.winner_xp_gained == 0)
check("grant_xp=False: loser XP == 0", r2.loser_xp_gained == 0)
check("grant_xp=False: winner counter untouched", r2.winner.duel_xp_today == 0)
check("grant_xp=False: loser counter untouched", r2.loser.duel_xp_today == 0)
check("grant_xp=False: gold matches grant path",
      r2.winner_gold_gained == r1.winner_gold_gained
      and r2.winner.gold == r1.winner.gold
      and r2.loser.gold == r1.loser.gold)

# 6. add_xp: no bonus param; old xp_needed mid-bar hunter still levels up
check("add_xp has no bonus parameter", "bonus" not in inspect.signature(add_xp).parameters)
h_mid = _mk(1, 407, "Mid")
h_mid.xp = 90
h_mid.xp_needed = 100  # old-curve mid-bar value
_lvl, _ = add_xp(h_mid, 20)
check("mid-bar hunter levels up", _lvl and h_mid.level == 2)
check("mid-bar XP remainder == 10", h_mid.xp == 10)

print(f"\n{passed} passed")
