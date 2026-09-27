# Progression Rebalance — "Make Leveling Hard" Design

**Status:** Approved approach (A: HARD), awaiting spec review
**Date:** 2026-09-28
**Scope:** XP economy, duel/war rewards, level curve, loss-consolation tuning
**Decision makers:** Bot owner (selected: both-hard, flat loser token, daily duel cap, keep existing levels)

---

## 1. Problem Statement

Leveling up is too fast and trivially exploitable. Three root causes were found in the
full XP audit (13 `add_xp` call sites):

1. **The duel farm (critical).** Duels have **no cooldown and no daily cap**. The loser
   still receives `15 + 2 × winner.level` XP. Two players tapping `/duel` against each
   other in a loop earn unlimited XP — loser included. Two colluding players can double
   a normal account's daily income and reach S-rank in ~35 days instead of ~76.
2. **Guild war stacks on top.** War matches run the same duel simulator, so every war
   fighter earns **full duel winner XP *plus* the +150 war bonus** — and wars have no
   cooldown either (only a global one-war-at-a-time lock).
3. **The curve lets grinders run away.** `xp_needed = 100 × level^1.5` is polynomial.
   Research (gamedev.stackexchange, gamedesign.gg) shows sub-exponential curves let a
   player who grinds twice as hard pull ever-further ahead; the *time per level* barely
   grows (`level^0.5`), so late-game status ranks (S, SS, Monarch) are reachable by
   anyone with a spreadsheet and a dueling partner.

Secondary findings: hunt defeat pays ~20% of monster XP (a losing player levels up by
losing), a guild +10% hunt bonus is the only multiplier in the game, tower's loss
consolation is dead code (computed, never granted), and `add_xp(bonus=)` is a dead
parameter.

## 2. Design Principles (from research)

- **Author the curve in hours, not XP** — pacing tables argue better than formulas.
  (gamedesign.gg: *"Argue about the hours… only then multiply by measured XP-per-hour."*)
- **Cap or diminish the dominant path, don't hard-nerf it** — a hard nerf punishes the
  players who found the activity. → daily duel XP cap instead of deleting duel XP.
- **No activity should yield >~50% more XP/hour than its peers** — otherwise it becomes
  the only content anyone plays. After this design all daily totals sit in the same band.
- **Loss must never be a strategy** — consolation XP stays (learning reward) but drops
  to a token that cannot outpace winning.
- **One knob per system** — curve exponent, duel cap, guild bonus are independent config
  values so future tuning needs no code restructuring.

## 3. Goals / Non-Goals

**Goals**
- Leveling becomes genuinely hard: A-rank ≈ 4 months, S-rank ≈ 7–8 months, Monarch ≈ 2
  years of active daily play (approach A).
- Eliminate the unbounded duel/war XP faucet.
- Loss gives a token, never a farming strategy.
- Guild bonus trimmed from +10% → +5% (present, not dominant).
- Existing 13 hunters keep their levels; the new curve slows only future progress.

**Non-Goals (explicitly unchanged)**
- Gold economy (duel gold remains uncapped — separate concern, noted as follow-up).
- Explore / claim / quest / tower / shadow amounts — all already capped or traffic-bound.
- Stat rewards per level (+1..3 × 5 stats), rank thresholds, full-heal on level-up.
- Shop (grants no XP), redeem codes, admin `/addxp` (superadmin tools).

## 4. Approach Selection

| | C: nerf sources only | **A: curve 1.75 + nerfs (CHOSEN)** | B: curve 2.0 + nerfs |
|---|---|---|---|
| Curve exponent | 1.5 (unchanged) | **1.75** | 2.0 |
| Reach D (L10) | 2.5 d | **3.9 d** | 6.1 d |
| Reach C (L20) | 9.9 d | **18.8 d** | 35 d |
| Reach B (L35) | 28 d | **60 d** | 128 d |
| Reach A (L50) | 52 d | **123 d** | 283 d |
| Reach S (L70) | 91 d | **235 d** | 589 d |
| Monarch (L120) | 220 d | **646 d** | 1,846 d |

Days = cumulative days of a grinder hitting **every daily cap, every day**. Casual play
takes roughly 2–3× longer. C fails the "hard" requirement (source nerfs alone move the
needle only ~20%); B is near-unreachable (5 years to Monarch). **A chosen.**

## 5. The XP Economy — Diagram

### 5.1 Before (current)

```
                        XP SOURCES (all feed add_xp)
  ┌──────────────── CAPPED ────────────────┐  ┌──────── UNCAPPED (exploit) ────────┐
  │ hunt      20/day   win: 8L+25 ×1.10    │  │ duel     NONE                      │
  │                     loss: ≈20% monster │  │   win : 8L+45        per duel      │
  │ explore    3/day   28L+357             │  │   loss: 15+2L   ← pays to lose!    │
  │ claim      1/day   8L+35               │  │ guild war: full duel XP            │
  │ quest      1/day   250 flat            │  │          + 150 win  − 30 loss      │
  │ tower      3 keys  18f+47              │  │   (war runs the duel simulator →   │
  │ shadows    traffic avg 411/claim       │  │    every match pays TWICE)         │
  └───────────────────┬────────────────────┘  └──────────────┬────────────────────┘
                      │                                      │
                      └───────────────┬──────────────────────┘
                                      ▼
                             add_xp(hunter, n)
                                      ▼
                  ┌────────── level-up loop (while) ──────────┐
                  │  xp_needed = 100 × level ^ 1.5   ← too soft │
                  │  +1..3 to each of 5 stats, full heal       │
                  │  check_rank_up()                           │
                  └────────────────────────────────────────────┘
```

### 5.2 After (this design)

```
                        XP SOURCES (all feed add_xp)
  ┌──────────────── CAPPED ────────────────┐  ┌────────── CAPPED (new) ───────────┐
  │ hunt      20/day   win: 8L+25 ×1.05    │  │ duel   XP for first 10 /day only  │
  │                     loss: ≈10% monster │  │   win : 6L+30   (was 8L+45)       │
  │ explore    3/day   28L+357  (unchanged)│  │   loss: 10 flat  (was 15+2L)      │
  │ claim      1/day   8L+35    (unchanged)│  │ guild war: 0 duel XP in matches   │
  │ quest      1/day   250 flat (unchanged)│  │          + 150 win  − 30 loss     │
  │ tower      3 keys  18f+47   (unchanged)│  │          (war XP only — no stack) │
  │ shadows    traffic avg 411  (unchanged)│  └──────────────┬────────────────────┘
  └───────────────────┬────────────────────┘                 │
                      │                    ┌─────────────────┘
                      │                    ▼
                      │        hunter.duel_xp_today counter
                      │        (reset in daily UTC reset)
                      └──────────────┬───────┘
                                     ▼
                            add_xp(hunter, n)
                                     ▼
                  ┌────────── level-up loop (while) ───────────┐
                  │  xp_needed = 100 × level ^ 1.75  ← HARD    │
                  │  +1..3 to each of 5 stats, full heal       │
                  │  check_rank_up()                           │
                  └────────────────────────────────────────────┘
```

### 5.3 Duel daily-cap flow (new mechanic)

```
  player taps /duel ──► fight simulated ──► result card sent (always)
                                   │
                     ┌─────────────▼──────────────┐
                     │ hunter.duel_xp_today >= 10? │
                     └──┬─────────────────────┬───┘
                       YES                    NO
                        │                      │
              award 0 XP (gold still      duel_xp_today += 1
              given, quest counter        award win/loss XP
              still counts)               (winner 6L+30, loser 10)
                        │                      │
                        └──────────┬───────────┘
                                   ▼
                     daily reset (UTC midnight, same hook
                     as hunt/explore/tower counters)
                     resets duel_xp_today = 0
```

## 6. Change List (exact, per file)

| # | File | Change |
|---|---|---|
| 1 | `config.py:110-112` | `xp_for_level`: hard-coded `1.5` → `XP_EXPONENT = 1.75` config constant |
| 2 | `config.py:189` | `GUILD_XP_BONUS = 0.10` → `0.05` |
| 3 | `config.py:194` | Fix wrong comment (war bonus is flat per fighter, not per duel win) |
| 4 | `config.py` | New: `DAILY_DUEL_XP_LIMIT = 10` |
| 5 | `models.py` | `Hunter` field `duel_xp_today: int = 0`; reset in daily reset block (same place as hunt/explore counters, `models.py:80-89`) |
| 6 | `game/duel.py:176` | Winner: `int(35 + loser.level*8 + randint(5,15))` → `int(25 + loser.level*6 + randint(0,10))` |
| 7 | `game/duel.py:178` | Loser: `max(5, 15 + winner.level*2)` → `10` flat |
| 8 | `game/duel.py` | `simulate_duel(..., grant_xp: bool = True)` — new param; both `add_xp` calls gated on it |
| 9 | `handlers/duel.py` | Award XP only while `hunter.duel_xp_today < DAILY_DUEL_XP_LIMIT`; increment counter when awarded; quest duel counter unchanged |
| 10 | `handlers/guild_war.py:644` | War matches call `simulate_duel(..., grant_xp=False)` — war fighters earn only ±war XP |
| 11 | `game/combat.py:140` | Hunt loss: `max(1, monster.xp_reward // 5)` → `max(1, monster.xp_reward // 10)` |
| 12 | `game/hunter.py:73` | Delete dead `bonus` parameter from `add_xp` (no caller passes it) |
| 13 | `game/tower.py:207` | Delete dead loss-consolation computation (never granted — `handlers/tower.py` only awards on victory) |

**Existing players:** no migration. Stored `xp_needed` stays valid; the new exponent
takes effect at each hunter's *next* level-up (`add_xp` recomputes `xp_needed` from
`xp_for_level(level)`). Levels and ranks are never reduced.

## 7. Pacing Model (approach A)

Income model after nerfs (grinder hitting every cap, guild member, equal-level opponents):

```
daily_XP(L) ≈ hunt 168L+525  +  explore 84L+1072  +  claim 8L+35
            + quest 250      +  tower   54L+142    +  duel(10) 30L+200
            ≈ 344L + 2,224          (shadow extraction extra, traffic-bound)

level time(L) = 100 × L^1.75  /  (344L + 2,224)  days
```

| Milestone | Level | Cumulative days (grinder) | Casual (×2–3) |
|---|---|---|---|
| D rank | 10 | ~4 d | ~1–2 wk |
| C rank | 20 | ~19 d | ~1–1.5 mo |
| B rank | 35 | ~60 d | ~2–3 mo |
| A rank | 50 | ~123 d | ~4–6 mo |
| S rank | 70 | ~235 d | ~8–12 mo |
| SS rank | 85 | ~339 d | ~1–1.5 yr |
| Monarch | 120 | ~646 d | ~2–3 yr |

S-rank becomes a genuine status symbol; Monarch stays legendary (theme-accurate for
*Shadow Monarch*). Tuning later = edit three config numbers (`XP_EXPONENT`,
`DAILY_DUEL_XP_LIMIT`, `GUILD_XP_BONUS`), no code restructuring.

## 8. Verification Plan

- **Unit-style checks** (script style consistent with `tests/`):
  - `xp_for_level` monotonic and matches table values at L=1, 10, 50, 100 (new exponent).
  - duel: winner/loser XP formulas at L=10/50/100 fall inside expected bands.
  - daily cap: 11th duel of the day grants 0 XP; counter resets with daily reset.
  - `grant_xp=False` path: war simulation produces no `add_xp` calls.
  - hunt loss ≈ half of previous consolation.
- **Static:** `python -m py_compile` on touched files; grep confirms no remaining
  `xp_reward // 5`, no `bonus=` caller, no dead tower consolation.
- **Live smoke:** bot boots clean (no traceback), one duel + one hunt exercised if
  test group available.

## 9. Follow-ups (out of scope, recorded)

- Duel **gold** has no cap either (winner `25+6L+15`) — same farm shape as XP. Consider
  mirroring the daily cap on gold later.
- `hunt` loss already costs 10% gold + HP — kept as-is.
- Shadow extraction (avg 411/claim) is traffic-bound; if group volume ever makes it a
  dominant source, apply its own daily cap then.
