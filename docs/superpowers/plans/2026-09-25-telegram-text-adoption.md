# telegram-text Adoption — Shared Builders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt `telegram-text` element composition in the two shared message modules (`game/captions.py`, `game/formatting.py`) with byte-identical rendered output.

**Architecture:** Output stays HTML (`parse_mode=HTML` is wired bot-wide) — elements render via `.to_html()` and are interpolated into the existing f-string/line scaffolds. `escape_html()` remains the escaping boundary because **telegram-text's `to_html()` does NOT escape** (verified from source: `PlainText` only overrides `to_markdown`). Handlers are untouched.

**Tech Stack:** `telegram-text>=0.2.0` (MIT, zero deps), existing `game/rich_text.py`, kurigram.

**Spec:** Brainstorming outcome — scope = "Shared builders only": convert `captions.py` (18 builders, 52 escape sites) + `formatting.py` (13 functions, 23 sites). Handlers (139 sites) explicitly out of scope.

## Global Constraints
- Output: HTML strings wrapped in `safe_caption()` / `safe_message()` — unchanged
- Golden rule: **every dynamic value passes `escape_html()` before entering an element**
- f-string interpolation of elements **must use explicit `.to_html()`** — `{Bold(x)}` calls `__str__` → MarkdownV2 → wrong format
- `Quote()` replaces only non-expandable `<blockquote>`; `<blockquote expandable>` stays literal
- Never touch `handlers/*.py`, `channel_db.py`, or anything under live data
- No new abstractions beyond the one documented re-export surface
- Acceptance: post-change render == pre-change render, **byte-identical**, all outputs pass `validate_telegram_html()`

## Review Focus
1. **Missed `escape_html()` at a converted site** → adversarial baseline (names/notices/items containing `<b>&"`) caught by byte-diff + validator — Task 2 creates it, Task 6 runs it
2. **`{Element}` in f-string renders MarkdownV2** → conversion rules state `.to_html()` explicitly; validator fails on stray `*`/`_` output — Task 6
3. **`Chain` sep inserts stray spaces** → only `Chain` used inside `Quote(Chain(..., sep=" "))` where current strings already have that space; byte-diff catches any drift — Tasks 4-5
4. **Deleting a helper with a hidden caller** → re-run exact `rg` before delete + import smoke + bot boot — Task 3
5. **`Quote` used on an expandable blockquote** → byte-diff (output would lose `expandable`) — Tasks 4-5

---

### Task 1: Install telegram-text + contract probe

**Files:**
- Modify: `requirements.txt`
- Create (temp, not committed): `C:\Users\saman\AppData\Local\Temp\opencode\probe_telegram_text.py`

- [ ] **Step 1:** `pip install telegram-text` → expect `Successfully installed telegram-text-0.2.0`
- [ ] **Step 2:** Add to `requirements.txt`: `telegram-text>=0.2.0`
- [ ] **Step 3:** Write probe pinning the behaviors conversion relies on:

```python
import sys; sys.path.insert(0, r"W:\solo-leveling-bot")
from telegram_text import Bold, Italic, InlineCode, Chain, Quote, PlainText

# 1. to_html does NOT escape (golden rule justification)
assert Bold("a<b>&c").to_html() == "<b>a<b>&c</b>"
# 2. tags match our current literals exactly
assert Bold("X").to_html() == "<b>X</b>"
assert Italic("X").to_html() == "<i>X</i>"
assert InlineCode("X").to_html() == "<code>X</code>"
# 3. Quote == non-expandable blockquote
assert Quote(Chain(Bold("H:"), Italic("n"), sep=" ")).to_html() == \
    "<blockquote><b>H:</b> <i>n</i></blockquote>"
# 4. Chain constructor does NOT wrap raw str (crash footgun) -> PlainText required
try:
    Chain("raw", sep="").to_html(); raise SystemExit("Chain wraps str now - revisit rules")
except AttributeError:
    pass
assert Chain(PlainText("a"), Bold("b"), sep="").to_html() == "a<b>b</b>"
print("PROBE OK")
```

- [ ] **Step 4:** Run: `python C:\Users\saman\AppData\Local\Temp\opencode\probe_telegram_text.py` → `PROBE OK` (if step 4 assertion fails "Chain wraps str now", revisit Chain rules before Task 4)
- [ ] **Step 5:** Commit `requirements.txt` → `chore: add telegram-text dependency`

### Task 2: Golden baseline capture (before any code edits)

**Files:**
- Create (temp, not committed): `C:\Users\saman\AppData\Local\Temp\opencode\render_baseline.py`

- [ ] **Step 1:** Script imports every builder from `game.captions` (all 18) and `game.formatting` (`format_profile, format_welcome, format_hunt_victory, format_hunt_defeat, format_inventory, format_equip_result, format_cooldown, format_already_registered, format_not_registered`), renders each with **two datasets**:
  - normal: fabricated `Hunter`/`Inventory`/`Item`/`HuntResult` (dataclasses from `models.py`)
  - adversarial: `hunter_name='<b>&"q"', title='A<B> & C', notice="x <i>y & 'z", story='<script>&</script>', item.name='Sharp <Sword> "of" & Glory'`
- [ ] **Step 2:** Script asserts on every output: `validate_telegram_html(out) is True`, `len(out) <= 4096` (captions: `<= 1024`), then writes `baseline.json` (key → html string) to the temp dir
- [ ] **Step 3:** Run with `workdir=W:\solo-leveling-bot`, `PYTHONIOENCODING=utf-8` → `baseline.json` created, zero assertion failures

### Task 3: `game/rich_text.py` integration + dead-helper removal

**Files:**
- Modify: `game/rich_text.py`

- [ ] **Step 1:** Re-verify zero callers before deleting:

```
rg "\b(escape_markdown_v2|bold|italic|underline|strike|spoiler|code|pre|link|mention|user_link|blockquote|expandable_blockquote|custom_emoji|system_lore|system_header)\(" -g "*.py" .
```
Expected: only hits inside `game/rich_text.py` itself. Any hit elsewhere → stop, keep that helper.

- [ ] **Step 2:** Delete from `rich_text.py`: `escape_markdown_v2`, `_MD_V2_SPECIAL`, `bold, italic, underline, strike, spoiler, code, pre, link, mention, user_link, blockquote, expandable_blockquote, custom_emoji, system_lore, system_header`. Keep: `escape_html, safe_caption, safe_message, validate_telegram_html, TelegramHTMLValidator, ALLOWED_TELEGRAM_TAGS, inline_button, callback_button, copy_button, url_button, inline_keyboard, build_keyboard_grid`.
- [ ] **Step 3:** Add import + re-export near top:

```python
from telegram_text import Bold, Italic, InlineCode, Chain, Quote, PlainText
```

- [ ] **Step 4:** Rewrite module docstring to document the integration:

```python
"""
game/rich_text.py — Telegram Rich Text Formatting Helper (HTML Mode).

telegram-text integration: Bold / Italic / InlineCode / Chain / Quote / PlainText
are re-exported for composing messages. Render with .to_html() — NEVER rely on
str(element) or f-string interpolation without .to_html() (that yields MarkdownV2).

GOLDEN RULE: telegram-text does NOT HTML-escape. Every dynamic/user-controlled
value must pass escape_html() BEFORE being wrapped in an element:
    Bold(escape_html(hunter.hunter_name)).to_html()

Also provides: safe_caption / safe_message (length-safe truncation that closes
open tags) and validate_telegram_html (strict Telegram tag validator).
"""
```

- [ ] **Step 5:** Import smoke: `python -c "from game.rich_text import escape_html, safe_caption, safe_message, validate_telegram_html, Bold, Quote, Chain"` → no error
- [ ] **Step 6:** Re-run baseline script → output byte-identical to `baseline.json` (deleting dead code must not change rendering)
- [ ] **Step 7:** Commit → `refactor: back rich_text with telegram-text, drop unused html helpers`

### Task 4: Convert `game/captions.py` (18 builders)

**Files:**
- Modify: `game/captions.py`

**Conversion rules (apply exactly):**
1. Any f-expression inside `<b>…</b>` / `<i>…</i>` / `<code>…</code>` → element: `{Bold(esc).to_html()}` / `{Italic(esc).to_html()}` / `{InlineCode(esc).to_html()}` — `esc` = existing escaped var or `escape_html(...)` for str; ints get `escape_html(str(x))` per golden rule (no-op on bytes)
2. Static labels/tags (`<b>Hunter:</b>`, `<code>/hunt</code>` literals) stay literal — converting them is churn, not adoption
3. Non-expandable `<blockquote>…</blockquote>` notice/lore fragments → `Quote(Chain(...)).to_html()`; `<blockquote expandable>` stays literal (`# ponytail: telegram-text Quote has no expandable variant`)
4. Conditional fragment variables (`loot_line`, `shadow_prompt`, `notice_block`, `ascend_block`, …) keep their structure — apply rules 1-3 inside them
5. Fallback for multi-part dynamic fragments where spacing already exists between styled runs: `Chain(a, b, sep=" ")` (matches the literal space in current strings)

**Worked example — `build_profile_caption` (rule application shown):**

```python
# BEFORE
f"🎖️ <b>Title:</b> <i>{title_str}</i>\n"
f"⚡ <b>Power:</b> <code>{hunter.power:,}</code> ┊ 💰 <b>Gold:</b> <code>{hunter.gold:,} G</code>\n\n"
# AFTER
f"🎖️ <b>Title:</b> {Italic(title_str).to_html()}\n"
f"⚡ <b>Power:</b> {InlineCode(escape_html(f'{hunter.power:,}'))} ┊ 💰 <b>Gold:</b> {InlineCode(escape_html(f'{hunter.gold:,} G'))}\n\n"

# BEFORE (notice_block pattern, also in inventory/shop/forge)
notice_block = f"<blockquote><b>⚡ System Notice:</b> <i>{escape_html(notice)}</i></blockquote>\n\n"
# AFTER
notice_block = Quote(Chain(Bold("⚡ System Notice:"), Italic(escape_html(notice)), sep=" ")).to_html() + "\n\n"
```

- [ ] **Step 1:** Convert batch A: `build_profile_caption`, `build_hunt_caption`, `build_explore_caption` (rules 1-5; `quota_str` = `InlineCode(...)` per rule 1)
- [ ] **Step 2:** Run baseline script → all batch-A entries byte-identical, validator green → stop and fix any diff before continuing
- [ ] **Step 3:** Convert batch B: `build_inventory_caption`, `build_shop_caption`, `build_tower_caption`, `build_quest_caption`, `build_forge_caption` → baseline check (byte-identical + green)
- [ ] **Step 4:** Convert batch C: `build_help_caption`, `build_claim_caption`, `build_start_welcome_caption`, `build_start_existing_caption`, `build_duel_challenge_caption`, `build_duel_result_caption`, `build_leaderboard_caption`, `build_guild_caption`, `build_war_challenge_caption`, `build_war_status_caption` → baseline check
- [ ] **Step 5:** Update import line: `from game.rich_text import escape_html, safe_caption, Bold, Italic, InlineCode, Quote, Chain` (only names actually used)
- [ ] **Step 6:** Commit → `refactor: compose captions with telegram-text elements`

### Task 5: Convert `game/formatting.py` (13 functions)

**Files:**
- Modify: `game/formatting.py`

Same rules 1-5. Line-list functions (`format_profile`, `format_hunt_victory/defeat`, `format_inventory`) keep `lines = [...]` structure — elements interpolate per rule 1 inside each line; join + `safe_message(...)` unchanged. `_stat_bar/_progress_bar/_hp_bar/_rank_badge` untouched (pure text).

- [ ] **Step 1:** Convert: `format_profile`, `format_welcome`, `format_hunt_victory`, `format_hunt_defeat` → baseline check
- [ ] **Step 2:** Convert: `format_inventory`, `format_equip_result`, `format_cooldown`, `format_already_registered`, `format_not_registered` → baseline check
- [ ] **Step 3:** Update import: `from game.rich_text import escape_html, safe_message, Bold, Italic, InlineCode, Quote, Chain` (only used names)
- [ ] **Step 4:** Commit → `refactor: compose formatting builders with telegram-text elements`

### Task 6: Full verification

- [ ] **Step 1:** Re-run baseline script → `after.json`; diff against `baseline.json` → **must be 100% identical** (any diff: investigate, justify, or fix)
- [ ] **Step 2:** `rg -n "<blockquote expandable>" game/captions.py game/formatting.py` → still present (rule 3 respected); `rg -n "escape_html\(" game/captions.py game/formatting.py` → no dynamic value lost its escape
- [ ] **Step 3:** Syntax/import smoke: `python -c "import game.captions, game.formatting, handlers.inventory, handlers.start"` → no error
- [ ] **Step 4:** Commit any stragglers → `test: verify telegram-text conversion parity` (message-only if no diff files)

### Task 7: Restart live bot

- [ ] **Step 1:** Find running `main.py` process(es) and `Stop-Process -Id <pid> -Force`
- [ ] **Step 2:** Restart background: `Start-Process -FilePath python -ArgumentList "main.py" -WorkingDirectory "W:\solo-leveling-bot" -RedirectStandardError "W:\solo-leveling-bot\bot_err.log" -RedirectStandardOutput "W:\solo-leveling-bot\bot_out.log"`
- [ ] **Step 3:** Wait ~10s, read `bot_err.log` tail → expect `ChannelDB initialized...` + `Bot initialized and ready!`, zero `Traceback`

### Task 8: Final commit & summary

- [ ] `git status` / `git diff --stat` → only intended files (`requirements.txt`, `game/rich_text.py`, `game/captions.py`, `game/formatting.py`); commit leftovers if any

**Skipped (add when needed):** handler migration (139 sites — migrate opportunistically), MarkdownV2 output (parse_mode is HTML bot-wide), auto-escaping wrapper (lib offers no hook; convention + baseline covers it), `OrderedList`/`Link` re-exports (no current use).
