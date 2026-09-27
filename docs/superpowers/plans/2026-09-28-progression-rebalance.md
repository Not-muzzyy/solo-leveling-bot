# Plan: Progression Rebalance (Approach A)

**Spec (authority):** `docs/superpowers/specs/2026-09-28-progression-rebalance-design.md` (commit `22d02e8`)
**Execution:** native (executing-plans + TDD), one commit per task, unpushed until user approves.

## Goal

Make leveling hard: steeper XP curve (`XP_EXPONENT = 1.75`, was hard-coded 1.5), cap daily duel XP farming (`DAILY_DUEL_XP_LIMIT = 10`), halve loss consolation, halve guild XP bonus. Gold formulas unchanged. No migration — existing 13 hunters keep levels; the curve only slows future progress.

Pacing target (grinder, daily caps): D≈4d, C≈19d, B≈60d, A≈123d, S≈235d, SS≈339d, Monarch≈646d.

## Exact formulas & values

- `xp_for_level(level) = int(100 * level ** XP_EXPONENT)` with `XP_EXPONENT = 1.75`
  - L1=100, L10=5623, L20=18914, L50=94015, L100=316227
- Duel winner XP: `int(25 + loser.level * 6 + random.randint(0, 10))` (was `35 + 8L + randint(5, 15)`)
- Duel loser XP: flat `10` (was `max(5, 15 + winner.level * 2)`)
- Hunt loss consolation: `max(1, monster.xp_reward // 10)` (was `// 5`)
- `GUILD_XP_BONUS = 0.05` (was 0.10)
- Daily duel XP limit: `10` per hunter per calendar day

## Global Constraints

- PowerShell 5.1: no bare `&&`; `$env:PYTHONIOENCODING='utf-8'` before python tests; the Grep tool ignores `path` — use `bash` + `rg` for repo-scoped counts.
- Script-style tests, NO pytest (not in requirements). Test file: `tests/test_progression_rebalance.py`, run: `python tests\test_progression_rebalance.py`.
- No new dependencies. Gold formulas unchanged. No data migration.
- One commit per task; commits stay local until user approves push.
- Bot kill: `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py*' -and $_.Name -like 'python*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }`
- Bot start: `Start-Process python -ArgumentList main.py -WorkingDirectory W:\solo-leveling-bot -RedirectStandardError bot_err.log -RedirectStandardOutput bot_out.log` → expect `Session started`, 0 Tracebacks → kill again.
- TDD Iron Law: failing test first, watch it fail for the right reason, then minimal code.

## Review Focus (final whole-branch review)

1. Cap arithmetic: partial award `remaining` never negative, never exceeds limit; counter only increments when XP is actually granted.
2. `grant_xp=False` path: gold and `DuelResult` still correct; XP fields = 0.
3. Handler ordering: `check_and_reset_daily()` for both hunters AFTER the missing-hunter guard and BEFORE `simulate_duel(`; saves persist the counter.
4. No gold / tower-XP / quest-counter behavior changed beyond spec.
5. Curve values exact; no stray `** 1.5`, `bonus`, `// 5` consolation, or `0.10` guild bonus anywhere.

---

## Task 1: Config knobs + test suite skeleton

**Files:** `config.py`, `tests/test_progression_rebalance.py` (new)

**Edits:**
1. `config.py` — `xp_for_level` (:110-112): replace `100 * level ** 1.5` with `100 * level ** XP_EXPONENT`; add module constant `XP_EXPONENT = 1.75` directly above.
2. `config.py` — add `DAILY_DUEL_XP_LIMIT = 10` right after `DAILY_EXPLORE_LIMIT` (:125).
3. `config.py` — `GUILD_XP_BONUS` (:189): `0.10` → `0.05`.
4. `config.py` — fix wrong comment at :194 (war/quest comment mismatching the code beneath it — correct it to describe what the constant actually feeds).

**TDD steps:**
- RED: create `tests/test_progression_rebalance.py` (script-style asserts) asserting:
  - `xp_for_level` values: L1=100, L10=5623, L20=18914, L50=94015, L100=316227
  - `config.XP_EXPONENT == 1.75`, `config.DAILY_DUEL_XP_LIMIT == 10`, `config.GUILD_XP_BONUS == 0.05`
  - Run → must FAIL (XP_EXPONENT missing / values from 1.5 curve).
- GREEN: apply the 4 config edits → run → PASS.
- Commit: `feat(config): steeper XP curve (1.75), daily duel XP limit, halved guild XP bonus`

**Expected:** curve test fails first because `XP_EXPONENT` doesn't exist; passes after edits.

## Task 2: Hunter duel-XP daily counter

**Files:** `models.py`

**Edits:**
1. `Hunter` dataclass (:46-68): add `duel_xp_today: int = 0` and `last_duel_date: str = ""` (keep them next to the other daily/limit fields).
2. `check_and_reset_daily()` (:70-89): add reset block — when `last_duel_date != today`, set `last_duel_date = today` and `duel_xp_today = 0`. (Same pattern as the existing daily resets.)

**TDD steps:**
- RED: append tests to `tests/test_progression_rebalance.py`:
  - Hunter with stale `last_duel_date` (yesterday) and `duel_xp_today = 7` → after `check_and_reset_daily()`, `duel_xp_today == 0` and `last_duel_date == today`.
  - Hunter with today's date and `duel_xp_today = 7` → unchanged.
  - Run → FAIL (field missing / no reset).
- GREEN: apply model edits → PASS.
- Commit: `feat(models): per-hunter daily duel XP counter with date rollover reset`

## Task 3: Duel XP formulas + grant_xp gate

**Files:** `game/hunter.py`, `game/duel.py`

**Edits:**
1. `game/hunter.py` — `add_xp` (:73-107): delete the dead `bonus` parameter (no caller passes it; bonus never added to the award).
2. `game/duel.py` — `simulate_duel` signature (:51): add `grant_xp: bool = True`.
3. `game/duel.py` — rewards block (:174-186):
   - Winner XP: `int(25 + loser.level * 6 + random.randint(0, 10))`.
   - Loser XP: flat `10`.
   - When `grant_xp` is False: both awarded XP = 0, counters untouched.
   - When True: `remaining = max(0, config.DAILY_DUEL_XP_LIMIT - hunter.duel_xp_today)`; awarded = `min(needed, remaining)` (can be 0); if awarded > 0: `hunter.duel_xp_today += awarded`.
   - `DuelResult.winner_xp_gained` / `loser_xp_gained` = actually-awarded values (card honestly shows +0 when capped).
   - Gold formulas untouched (compute gold regardless of the cap).
4. No changes to `handlers/duel.py` quest counters here (Task 4 covers reset; quest counters stay as-is).

**TDD steps (6 tests):**
- RED: append tests:
  1. Formula band: level-20 winner vs level-30 loser → `25 + 180 + [0..10]` = 205–215 XP (assert range).
  2. Loser XP flat = 10 regardless of levels.
  3. Full cap: hunter with `duel_xp_today = 0`, limit 10 → awarded 10, counter becomes 10.
  4. Partial cap: `duel_xp_today = 8` → awarded 2, counter 10.
  5. `grant_xp=False` → awarded 0 for both, counter unchanged, gold unchanged vs `True` path (same seed).
  6. `add_xp` signature has no `bonus` (inspect) AND a hunter with old `xp_needed` mid-bar still levels up correctly.
  - Run → FAIL.
- GREEN: implement → PASS.
- Commit: `feat(duel): rebalanced duel XP (flat 10 loser, scaled winner) + daily cap gate`

## Task 4: Daily reset call in duel handler

**Files:** `handlers/duel.py`

**Edits:**
1. After the `if not challenger or not opponent` guard (:268-277), BEFORE `simulate_duel(`:
   ```python
   challenger.check_and_reset_daily()
   opponent.check_and_reset_daily()
   ```
   (This handler never resets today → without this the counter never rolls over.)

**TDD steps:**
- RED: static test — read `handlers/duel.py` source; assert `check_and_reset_daily()` appears twice for the two hunters and both occurrences sit after the missing-hunter guard and before the `simulate_duel(` call line.
- GREEN: add the two calls → PASS.
- Commit: `fix(duel): reset daily counters in duel handler before simulation`

## Task 5: Wars stop granting duel XP

**Files:** `handlers/guild_war.py`

**Edits:**
1. War `simulate_duel(...)` call (:644): add `grant_xp=False`. War's own XP award (:706) unchanged.

**TDD steps:**
- RED: static test — the `simulate_duel(` call inside `handlers/guild_war.py` contains `grant_xp=False`.
- GREEN: add the kwarg → PASS.
- Commit: `fix(guild_war): exclude war duels from daily duel XP cap`

## Task 6: Hunt loss consolation halved

**Files:** `game/combat.py`

**Edits:**
1. :140 — loss consolation `monster.xp_reward // 5` → `monster.xp_reward // 10` (keep `max(1, ...)`).

**TDD steps:**
- RED: test — defeat grants `max(1, xp_reward // 10)` and is strictly ≤ half of the old `// 5` award for a sample monster with even `xp_reward`.
- GREEN: edit → PASS.
- Commit: `balance(hunt): halve loss consolation XP`

## Task 7: Delete dead tower consolation branch

**Files:** `game/tower.py`

**Edits:**
1. Delete the dead `else` clause (:205-207) that assigns consolation XP (never granted — `xp_gained` already initialized to `0` at :188). (Comment at `config.py:194` was already fixed in Task 1.)

**TDD steps:**
- RED: static test — `game/tower.py` source contains no `else` branch assigning consolation XP (assert the specific dead-code pattern is absent).
- GREEN: delete the branch → PASS.
- Commit: `chore(tower): remove unreachable loss consolation branch`

## Task 8: Full verification battery

1. `py_compile` all touched files: `config.py`, `models.py`, `game/hunter.py`, `game/duel.py`, `handlers/duel.py`, `handlers/guild_war.py`, `game/combat.py`, `game/tower.py`.
2. Full suite: `python tests\test_progression_rebalance.py` → all asserts green.
3. Grep audits (rg, repo-wide): `bonus` in `game/` (callers of add_xp must not pass bonus) → 0; `** 1.5` → 0; `// 5` consolation in combat.py → 0; `GUILD_XP_BONUS.*0\.10` → 0.
4. Import smoke: `python -c "import main"`-equivalent module import of touched handlers (no side effects beyond init) → no exceptions.
5. Boot smoke: kill bot → start → `Session started` + 0 Tracebacks → kill.
6. `git status` → clean (all committed); report commits; **await push approval**.

**Expected:** every check green; otherwise systematic-debugging, no symptom patches.

**Commit:** `test(progression): verification battery for rebalance`

---

## Interfaces (pre-flight)

- Task 1 produces config knobs (`XP_EXPONENT`, `DAILY_DUEL_XP_LIMIT`, `GUILD_XP_BONUS`) consumed by Task 3 (`simulate_duel` cap) — plan self-consistent.
- Task 2 produces `Hunter.duel_xp_today` / `last_duel_date` consumed by Task 3 (increment) and Task 4 (reset) — names consistent.
- Task 3 produces `grant_xp` param consumed by Task 5 — signature consistent.
- Task 4's static test consumes the guard/`simulate_duel` ordering in `handlers/duel.py` — unchanged by other tasks.
