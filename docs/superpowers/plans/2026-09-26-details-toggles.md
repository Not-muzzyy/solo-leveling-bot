# Details Toggles — Apply `<details>` Everywhere Needed

**Date:** 2026-09-26
**Status:** approved (plan mode review)
**Predecessor:** 2026-09-26-rich-messages-migration.md (fully landed, pushed at bb85429)

## Goal

Replace multi-section `<blockquote expandable>` / flat sectioned content with native
collapsible `<details><summary>` toggles (`RichBlockDetails`, Bot API 10.1+) across the
bot's rich messages, and fix the `/help` routing so the details-based manual actually
reaches users.

User-approved example shape: collapsed-by-default toggles with `<summary>` section
labels, sections separated by `<hr>`, single-topic lore quotes kept as quotes.

## Conversion rule

- Multi-section content (>=2 bold subsection headers, each with its own items) ->
  one collapsed `details(label, body)` per section.
- Single-topic blocks (tips, lore quotes, dossiers, toasts, one-off notices) stay
  `quote`/`paragraph`.
- Classic strings stay byte-identical: `TOPIC_TEXTS`, `HELP_CAPTION`,
  `HELP_FALLBACK_TEXT`, every `fallback=` (verbatim rule from migration).
- Never nest `details` inside `<li>` or `<blockquote>` (tdesktop #30906 bubble bug);
  `details` is always a top-level block in `RichDoc`.
- `details()` passes `body` RAW (`game/rich_message.py:114`, only `summary` gets
  `_nl()`), so bodies must be pre-rendered HTML (`bullet_list(...)` or explicit
  `<br>`), never raw `\n`.
- Callers escape dynamic values (`escape_html`) before feeding builders; static bare
  `&` already written as `&amp;` in these sites.

## Site inventory

### Toggle candidates (convert)

| Site | Current | Sections after |
|---|---|---|
| `handlers/help.py:244` `_sec()` | `heading(2)+bullet_list` | 1 change converts combat x4, forge x3, guild x3, shadows x3, admin x3, quests x2 |
| `handlers/help.py:328-336` quests first block | manual heading+paragraphs+number_list | 1 toggle |
| `handlers/help.py:250-280` tiers | raw `h2+table` x2 | 2 toggles (tables inside details) |
| `handlers/admin.py:245-277` /admin guide | 5 quotes | 5 details + bullet_list bodies |
| `handlers/guild.py:284-303` /guild help | 2 quotes | 2 details |
| `handlers/guild_war.py:293-304` /guild war help | 1 quote, 4 headers | 4 details |
| `handlers/redeem.py:125-133` /redeem help | 1 quote, 2 headers | intro paragraph + 2 details |
| `handlers/arise.py:706-715` /addshadow help | 1 quote, 3 headers | intro paragraph + 3 details |

### Not candidates (leave as-is)

- `game/captions.py` all single-topic builders; `build_help_rich` already uses details.
- `HELP_CAPTION` / `HELP_FALLBACK_TEXT` / `TOPIC_TEXTS` — classic fallback surfaces.
- `/update` telemetry (`admin.py:1403`) — admin-only readout, wants visible.
- 86 toasts, profile/inventory stat dossiers, single-topic quotes everywhere.
- Topic-photo classic `reply_text(TOPIC_TEXTS)` branch (`help.py:635-638`) — keeps the
  card intact, classic-on-classic consistency.

### Root cause being fixed

- First send: `reply_rich(build_help_rich(), ..., fallback=reply_photo(HELP_CAPTION))`
  — rejection reason unknown (logs deleted during cleanup); measured in Task 1.
- `help_main` callback (`help.py:608-613`): if `query.message.photo` truthy -> ALWAYS
  classic `edit_message_media(HELP_CAPTION)`; converted to `edit_rich` with verbatim
  classic fallback.

## Tasks

### Task 1 — Diagnose /help classic path
1. Start bot: `Start-Process python -ArgumentList main.py -WorkingDirectory
   W:\solo-leveling-bot -RedirectStandardError bot_err.log -RedirectStandardOutput
   bot_out.log`.
2. PM `/help`; read `bot_err.log` for `reply_rich failed` / traceback.
3. Tap "Back to manual" (`help_main`); note rich vs classic result.
4. Record verdict in `.superpowers/sdd/details-toggles/progress.md`.
5. Branch: first-send rejected -> identify failing block in `build_help_rich()` and
   fix in this task; clean log -> classic came from `help_main` photo branch
   (expected), proceed to Task 2.

### Task 2 — Fix help_main routing
1. `handlers/help.py:608-613`: replace classic branch with
   `edit_rich(build_help_rich(), media=photo_media("help", photo_buf),
   reply_markup=_help_pm_keyboard(), fallback=<current classic edit_message_media
   lambda, verbatim>)`.
2. Check: exactly one `edit_message_media` remains in help.py (inside fallback).

### Task 3 — TOPIC_RICH -> toggles
1. `_sec()` (`help.py:244-246`) -> `[details(title, bullet_list(list(items)))]`.
2. quests first block (`:328-336`) -> wrap in
   `details("🏋️ Daily Physical Conditioning (<code>/daily</code>)",
   paragraph(...) + paragraph(...) + number_list([...]))`.
3. tiers (`:250-280`) -> wrap each `h2+table` in
   `<details><summary>...</summary><table>...</table></details>`.
4. Probe: validate all 7 `TOPIC_RICH` values via `RichDoc(...).validate()`.
5. `help.py:30` `details` import now used (was dead).

### Task 4 — Inline guides -> toggles
1. `admin.py:245-277`: 5 quotes -> 5 `details(label, bullet_list(items))`
   (strip `• ` prefixes into list items; keep `&amp;`/`<code>` markup);
   tip quote `:278` stays.
2. `guild.py:284-303`: 2 quotes -> 2 details.
3. `guild_war.py:293-304`: split into 4 details
   (Declaration Directive / Combat Structure / 🎁 Spoils / 💀 Defeat),
   f-string interpolation preserved.
4. `redeem.py:125-133`: intro -> top-level `paragraph`, Command Syntax and
   Examples -> 2 details (`<br>` bodies fine); lore quote `:134` stays.
5. `arise.py:706-715`: intro -> `paragraph`, Syntax / Example / Valid Rarities
   -> 3 details (no raw `\n` in bodies).
6. Fallbacks at every site untouched.

### Task 5 — Verification
1. Self-check probes: `RICH SELF-CHECK`, `RICH SEND SELF-CHECK`,
   `FULL IMPORT SMOKE` (re-create inline via python -c / temp scripts; originals
   deleted with .superpowers cleanup).
2. `rg "quote\("` audit over handlers + captions: each remaining hit classified
   single-topic into ledger.
3. `git diff` — fallback strings byte-identical (no changes under
   `fallback=`/TOPIC_TEXTS/HELP_CAPTION/HELP_FALLBACK_TEXT).
4. Live pass (bot restarted): `/help` first send rich; Back-to-manual rich;
   all 7 topic tabs show toggles and collapse/expand; `/guild`, `/admin`,
   `/guild war` help, `/redeem`, `/addshadow` without photo show toggles.
5. User acceptance ping.

### Task 6 — Closeout
1. Ledger: tasks done, verdicts, exclusions.
2. Conventional commit(s): `feat(rich): ...`; push only on user OK.

## Non-goals

/update telemetry, toasts, single-topic quotes, all classic fallbacks, feature flags.

## Risks

- Inline `<code>` inside `<summary>` unproven -> live-verified in Task 5;
  fallback covers rejects.
- First-send rejection (size/tags) -> Task 1 branch handles.
- `RichDoc.validate()` requires balanced body HTML -> builders emit balanced only.

## Tooling (PowerShell 5.1)

- No `&&`, no interior double quotes in `cmd /c "..."`, emoji via files not -c.
- grep tool `path` param ignored -> use `read` or `cmd /c "rg ..."`.
- Bot start/kill commands as in AGENTS.md session history; `TgCrypto` warning
  harmless.
