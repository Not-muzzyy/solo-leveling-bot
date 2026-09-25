# Rich Messages Migration — Design Spec

**Date:** 2026-09-26
**Status:** Approved design (chat review), awaiting spec review
**Stack:** Python 3.14 / kurigram 2.2.26 (pyrogram Layer 229) / telegram-text 0.2.0
**Precedent:** telegram-text adoption (plan: `docs/superpowers/plans/2026-09-25-telegram-text-adoption.md`) — the proof-of-work patterns (SDD ledger, byte-evidence, task-done gates) are reused.

## 1. Goal

Migrate **all 330 bot send/edit sites** from classic `parse_mode=HTML` messages to Telegram **Rich Messages** (`sendRichMessage`, Bot API 10.1–10.3), gaining: real headings, tables, dividers, structured lists, footers, expandable/collapse blocks, in-document TOC links, in-body buttons, embedded card photos, and the 32,768-char "Show more" length.

User decisions (binding):

- **"Up and down" = all four features:** `<details>`/`<blockquote expandable>` collapse blocks, in-document anchor TOC links, Prev/Next pagination buttons (existing inline keyboards), long-message Show-more folding.
- **No feature flag.** Rich everywhere. Runtime `try/except → classic fallback` on every rich send/edit is *not* a flag; it is a correctness net against server-side rejection (oversized/bad HTML) and remains.
- **Scope: all 330 sites**, executed in phases.
- Known risks accepted: Telegram Web shows an "unsupported message" card for rich messages (mobile/desktop render fine); rich text is harder to copy.

## 2. Current State (measured)

| Metric | Count |
|---|--:|
| Total send/edit sites (handlers/ + main.py) | 330 |
| photo+caption | 68 |
| plain text | 262 |
| in-place edits | 52 (`edit_message_media` 22, `edit_message_caption` 7, `edit_message_text` 20, misc 3) |
| sites with inline keyboards | 107 |
| already rich (help.py proof) | 2 |

Two reference sites prove the API end-to-end in this codebase: `handlers/help.py:406` (`send_rich_message`) and `handlers/help.py:475` (`edit_message_text(rich_message=...)`), both with exception fallback to classic HTML.

Non-UI sends excluded: 3 channel-DB writes (`guild_war.py:99,107`, `arise.py:634`). Callback toasts (`query.answer`) are not messages and stay untouched.

## 3. Architecture

### 3.1 New module: `game/rich_message.py`

A composition layer producing `InputRichMessage` — the rich counterpart of `game/rich_text.py` (classic HTML) with the same job split: **escaping at the leaves, structure at the builders, one conversion point.**

```
RichDoc(*blocks)            # ordered block list, .to_html() -> str, .validate() -> limits
heading(level, text)         # <h1>..<h6>
paragraph(content)           # <p>   (or implicit: bare inline runs wrap in <p>)
divider()                    # <hr/>
footer(text)                 # <footer>
bullet_list(items) / number_list(items) / checkbox_list(pairs)
table(rows, header=True, caption=None, aligns=None)   # max 20 cols
quote(text, expandable=True, cite=None)               # <blockquote [expandable]>
details(summary, body, open=False)                    # <details><summary>
photo_block(media_id, caption=None)                   # <figure><img src="tg://photo?id=..."/>
link(text, url) / anchor(name) / toc_link(text, name) # <a href="#name"> + <a name=...>
button_row(buttons, align=None)                       # in-body <tg-button-row>
bold/italic/code/strike/spoiler/mark/sub/sup          # inline (reuse telegram-text where possible)
```

- **Golden rule (inherited):** every dynamic value passes `escape_html()` **before** being wrapped in a builder; static literal block HTML is exempt. Rich HTML allows only a fixed named-entity set (`&lt; &gt; &amp; &quot; &apos; &nbsp; &hellip; &mdash; &ndash; &lsquo; &rsquo; &ldquo; &rdquo;`) plus all numeric entities — `game.rich_text.escape_html` (via `html.escape(quote=True)`) already emits only compliant entities.
- `RichDoc.to_html()` returns the HTML string; callers pass it to `InputRichMessage(html=..., skip_entity_detection=True)`. `skip_entity_detection=True` preserves classic behavior where we control links explicitly (auto-detection would turn `t.me` mentions in plain text into links where classic HTML did not).
- `RichDoc.validate()` enforces: ≤32,768 chars (text incl. alt text), ≤500 blocks (rows/items count), ≤16 nesting, ≤50 media, ≤20 table columns. Failure raises `RichValidationError`; callers treat it like any other send failure (fallback path).

### 3.2 Send/edit helpers: `game/rich_send.py`

Thin async wrappers — the single choke point for transport, matching the existing reference pattern:

```python
async def send_rich(client, chat_id, doc: RichDoc, reply_markup=None,
                    media: list[InputRichMessageMedia] | None = None,
                    fallback: Callable[[], Awaitable[Message]]) -> Message
async def edit_rich(client, chat_id_or_msg, doc, reply_markup=None,
                    media=None, fallback=...) -> Message
```

- Builds `InputRichMessage(html=doc.to_html(), media=media, skip_entity_detection=True)`.
- **`try/except Exception → await fallback()`** with a `logger.warning`. The fallback is always the *existing* classic call (unchanged behavior), so a rich-path regression degrades one message, never breaks a command.
- No environment flag, no global switch.
- `media`: Pillow `BytesIO` card images uploaded via `InputRichMessageMedia(id="card", media=InputMediaPhoto(bytesio))`, referenced in HTML as `<img src="tg://photo?id=card"/>`. `file_id` reuse across messages is a later optimization (not in v1 — `InputMediaPhoto` with bytes re-uploads; measured acceptable at our volume, revisit if slow).

### 3.3 Handler integration contract

Each send/edit site converts from:

```python
await message.reply_text(TEXT, reply_markup=kb, parse_mode=HTML)
```

to:

```python
await send_rich(client, chat.id, doc, reply_markup=kb,
                fallback=lambda: message.reply_text(TEXT, reply_markup=kb, parse_mode=HTML))
```

- The classic text stays as the fallback argument → zero behavior change when rich fails; the classic string also serves as the content-equivalence reference for review.
- In-place edits: `edit_rich` mirrors today's branch structure. Handlers that branch on `query.message.photo` gain a `query.message.rich_message` branch (received `Message.rich_message` field exists in kurigram).
- `inventory.py`'s repeated triple-branch (photo path → `edit_message_media` / caption path → `edit_message_caption` / text path → `edit_message_text`) collapses to: **photo message** → unchanged classic media edit; **rich message** → `edit_rich`; **text message** → `edit_rich` (rich replaces both text branches' content rendering).
- Group-guard notices, cooldown/not-registered errors, and admin console messages convert too (scope = all 330), except the 3 non-UI channel writes and 86 `query.answer` toasts.

### 3.4 Feature mapping (the four "up and down" requirements)

| Requirement | Mechanism |
|---|---|
| Expandable / collapse | `<details><summary>` (sections of help/admin/war) and `<blockquote expandable>` (notices, lore — already proven in tiers proof) |
| TOC links | At top of long messages: `<a href="#sec-id">` list + `<a name="sec-id"/>` markers; "⬆️ Top" link at bottom |
| Pagination buttons | Existing 107 inline keyboards unchanged, attached via `reply_markup` (supported by `send_rich_message`); Prev/Next/Tab callbacks keep their handler code |
| Show-more | Client-side folding of long rich messages up to 32,768 chars; `safe_caption`'s 1024 clamp is replaced by `RichDoc.validate()`'s 32,768 check for rich paths (classic fallback keeps `safe_caption`) |

In-body `<tg-button-row>` is used only where a button belongs inside the text flow (e.g., help deep links). Navigation buttons stay on `reply_markup` so callback routing is untouched.

### 3.5 Content builders (`game/captions.py`, `game/formatting.py`)

- New `build_*_rich()` counterparts are added **per converted surface only** (lazy, not a big-bang rewrite): each returns a `RichDoc`. The classic `build_*_caption()` remains, serving as fallback and content reference.
- Content parity rule: same information as the classic version (same numbers, names, lines) — layout may use headings/tables/dividers instead of emoji-led line soup. Two exceptions where content legitimately changes: (a) the 1024-caption clamp no longer truncates; (b) tables replace pre-formatted line lists where the data is tabular (rank thresholds, drop rates, war scores, leaderboard).
- `game/formatting.py`'s plain-HTML fallbacks (`format_not_registered`, `format_cooldown`, …) get one `RichDoc` variant each; they are small static-ish strings and convert mechanically.

## 4. Error Handling

1. **Send/edit failure** (server rejects, validation fails, unexpected exception) → `logger.warning` + run the classic fallback callable. Never a user-visible error caused by the rich path.
2. **Validation failure** (`RichValidationError`) raised before send → same fallback.
3. **Photo-upload failure** → same fallback (classic photo+caption path).
4. **Callback edit failures** → existing `query.answer()` still fires first (unchanged), fallback sends a fresh classic reply if edit fails.
5. All conversions keep the current `parse_mode=HTML` classic call text intact as the fallback body — no path becomes worse than today.

## 5. Verification Strategy

Byte-parity is **not** applicable (structure intentionally changes). Instead:

1. **Builder self-checks:** `python -m game.rich_message` assert-based demo (tag output, escaping, each block type, limit errors) — the ponytail-required runnable check.
2. **HTML smoke:** every `RichDoc.to_html()` passes a well-formedness check (balanced tags via `html.parser` subclass) in the same self-check.
3. **Import smoke:** all handlers import cleanly after each phase.
4. **Content equivalence:** per converted surface, reviewer (user) diff-checks classic vs rich rendering of the same command — done live in Telegram after each phase, since rendering is client-side.
5. **Probe (Phase 0):** one live message proving: embedded Pillow photo renders, `reply_markup` buttons work on rich messages, `edit_message_text(rich_message=...)` swaps content/media in place on a rich message, `<details>`/anchors/expandable render. Probe result decides Phase 3's edit strategy (§6). **The probe is a hard gate: Phase 1 starts only after it passes.**
6. **Final sweep:** `rg` inventory re-run — every site either calls `send_rich`/`edit_rich` or is on the documented exclusion list (non-UI/toasts); bot restart with clean log; live pass over key commands (`/help`, `/profile`, `/hunt`, `/shop`, `/inventory`, `/leaderboard`, `/guild`, `/tower`, `/duel`).

## 6. Phasing

Each phase = one commit group, gate = phases' verification items, ledger-tracked like the telegram-text adoption.

| Phase | Content | Sites | Gate |
|---|---|---|--:|
| 0 | `game/rich_message.py`, `game/rich_send.py`, self-check, **media-edit probe** | new | probe passes; `python -m game.rich_message` green |
| 1 | `help.py` complete: TOC, details, all 13 sites | 13 | import smoke + user visual check of `/help` |
| 2 | Text-first: profile, claim, shop, start, hunt, duel, explore, redeem | ~55 | import smoke + user visual spot-checks |
| 3 | Edit-heavy photo: inventory, tower, forge, quest, leaderboard | ~85 | per-surface tab/pagination click-through by user |
| 4 | guild, guild_war, arise, admin, main | ~175 | same |
| 5 | Final sweep (§5.6), restart, closeout | — | all gates green |

**Phase 3 contingency:** if the probe shows rich in-place edits cannot swap embedded media, the 22 `edit_message_media` sites adopt send-new/delete-old (reply + delete original) instead of `edit_rich`; recorded as a plan amendment before Phase 3 starts.

## 7. Explicit Non-Goals (v1)

- No `sendRichMessageDraft` streaming, no math blocks (`<tg-math>`), no maps/collages/slideshows — none of our content needs them.
- No removal of classic path (fallback always retained).
- No changes to command logic, cooldowns, DB, keyboards' callback data, or the 15 Pillow image renderers.
- No auto-detection of user clients; no per-chat routing (user chose "rich everywhere").
- No `file_id` caching across sends (optimization, revisit on evidence).
- Markdown mode unused — HTML only (we already own an HTML escaping layer).

## 8. Risks & Accepted Trade-offs

| Risk | Mitigation / status |
|---|---|
| Telegram Web shows "unsupported message" card | **Accepted by user** (no flag). Fallback exists only on send failure, not per-client. |
| Rich text hard to copy | Accepted. |
| 22 photo-swap edits depend on probe | Phase 0 gate + Phase 3 contingency (§6). |
| Server-side limits (32,768 / 500 / 20 cols) | `RichDoc.validate()` pre-send + fallback net. |
| Silent content truncation on huge formatted runs (~5,849 runs) | Unlikely at our message sizes; final visual sweep covers converted surfaces. |
| Behavior drift in 290 `parse_mode` sites | Classic call kept verbatim as fallback; per-phase user visual checks. |
