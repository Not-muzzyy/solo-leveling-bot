# Callback In-Place Refresh Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every inline-keyboard view-refresh callback must edit the existing message in place (`edit_rich`) instead of sending a new message or doing nothing — for rich-origin cards as well as classic photo cards.

**Architecture:** One shared root cause: `if query.message.photo:` was used as the "may I edit in place?" discriminator. Classic cards were always real photos so the edit branch always ran; rich cards (`InputRichMessage`) have `.photo == None` and fall into a reply-new or no-op path. Fix = make `edit_rich(...)` the unconditional primary path; `.photo` survives only to select the classic fallback lambda (the proven `help.py:617-637` pattern).

**Tech Stack:** Python 3.11, kurigram (pyrogram fork), Pillow renderers, `game/rich_send.py` transport.

**Spec:** Root-cause analysis done in-session (systematic-debugging); site audit verified against source at `handlers/{leaderboard,guild,inventory,forge,tower,quest,guild_war}.py`.

## Global Constraints

- Fallback lambda bodies are MOVED VERBATIM from the existing photo/else branches — never retype caption/classic text (escaping golden rules: dynamic values stay `escape_html`d as-is; no `&` changes).
- `photo_media("<id>", photo_buf)` first arg must equal the media id already used at that site.
- Keep every existing `query.answer(...)` call and toast exactly where it is.
- Keep existing `except MessageNotModified` / `except BadRequest "not modified"` wrappers unchanged.
- New one-line guard `if not query.message: return` (after any existing `query.answer()` in that scope) at the top of each touched callback function — protects render-fail paths that dereference `query.message.chat.id`.
- Raw `\n` in block literals; do not nest `details` in `<li>`; `photo_first` values unchanged.
- PowerShell 5.1: no `&&`; run commands separately.

## Review Focus

1. Rich-origin card tapped → must take `edit_rich` primary path (grep audit: no `reply_rich(query.message` left in touched callbacks).
2. Classic/degraded photo card tapped → `query.edit_message_media(...)` fallback still runs byte-verbatim (lambdas moved, not rewritten).
3. Same-tab re-tap → `Message is not modified` must not traceback beyond existing catches (inventory/leaderboard/guild-glb already catch; others log-only, pre-existing class).
4. Deleted card (`query.message is None`) → guard returns cleanly, no AttributeError in render-fail paths.
5. Static HTML/escaping untouched → only control flow moves; captions pass through unchanged.

---

### Task 1: leaderboard.py — reported bug

**Files:** Modify `handlers/leaderboard.py:202-225` (inside `callback`, try block at :193).

**Interfaces:** Consumes `edit_rich/reply_rich/photo_media` (already imported), `build_leaderboard_rich`, `_leaderboard_keyboard`, `build_leaderboard_caption`.

- [ ] **Step 1:** Add guard at top of `callback` (after `if not query:` / `query.answer()` block at :168-175 area): `if not query.message: return`
- [ ] **Step 2:** Replace lines 202-225 with:

```python
        if query.message.photo:
            fallback = lambda: query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_leaderboard_keyboard(category),
            )
        else:
            fallback = lambda: query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=_leaderboard_keyboard(category),
                parse_mode=enums.ParseMode.HTML,
                show_caption_above_media=True,
            )
        await edit_rich(
            client, query.message.chat.id, query.message.id,
            build_leaderboard_rich(category, photo_first=False),
            reply_markup=_leaderboard_keyboard(category),
            media=[photo_media("leaderboard", photo_buf)],
            fallback=fallback,
        )
```

(`except BadRequest "Message is not modified"` at :226 unchanged.)
- [ ] **Step 3:** `python -m py_compile handlers\leaderboard.py` → OK
- [ ] **Step 4:** Commit `fix(leaderboard): edit in place on category tab switch`

### Task 2: guild.py — glb sorts + gview/gjoin/gleave

**Files:** Modify `handlers/guild.py:1309-1333`, `:1416-1426`, `:1479-1489`, `:1534-1544`; guard in `guild_leaderboard_callback` (:1261) and `guild_interaction_callback`.

- [ ] **Step 1:** Guards: `if not query.message: return` after `await query.answer()` in `guild_leaderboard_callback` (:1266) and at top of `guild_interaction_callback` after its `query.answer()`/user check.
- [ ] **Step 2:** `guild_leaderboard_callback` :1309-1333 (inside try) →

```python
        if query.message.photo:
            fallback = lambda: query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=ParseMode.HTML),
                reply_markup=_glb_keyboard(category),
            )
        else:
            fallback = lambda: query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=_glb_keyboard(category),
                parse_mode=ParseMode.HTML,
                show_caption_above_media=True,
            )
        await edit_rich(
            client, query.message.chat.id, query.message.id,
            build_guild_leaderboard_rich(cat_name, photo_first=False),
            reply_markup=_glb_keyboard(category),
            media=[photo_media("guild", photo_buf)],
            fallback=fallback,
        )
```

(`except BadRequest` at :1334 unchanged.)
- [ ] **Step 3:** `gview_` :1416-1426 →

```python
            if query.message.photo:
                fallback = lambda: query.edit_message_media(
                    media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=keyboard,
                )
            else:
                fallback = lambda: query.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                    show_caption_above_media=True,
                )
            await edit_rich(
                client, query.message.chat.id, query.message.id,
                build_guild_rich(target_guild, len(member_hunters), total_power, GUILD_MAX_MEMBERS, photo_first=False),
                reply_markup=keyboard,
                media=[photo_media("guild", photo_buf)],
                fallback=fallback,
            )
```

(existing `except BadRequest` unchanged; the trailing `return` at :1430 stays.)
- [ ] **Step 4:** `gjoin_` :1479-1489 → same shape, identifiers: `build_guild_rich(target_guild, len(member_hunters), total_power, GUILD_MAX_MEMBERS, photo_first=False)`, `keyboard`, `photo_media("guild", photo_buf)`, `caption`; keep `except Exception as e: logger.warning(f"In-place media edit error after join: {e}")`.
- [ ] **Step 5:** `gleave_` :1534-1544 → same shape (identifiers identical to gjoin block as written there); keep its `except Exception` warning.
- [ ] **Step 6:** `python -m py_compile handlers\guild.py` → OK; commit `fix(guild): in-place refresh for leaderboard tabs and guild view/join/leave`

### Task 3: inventory.py — 6 sites + guards

**Files:** Modify `handlers/inventory.py` branches in `tab_callback` (:478, :521, :564), `equip_callback` (:689), `buy_callback` (:774), `use_callback` (:868).

- [ ] **Step 1:** Guards: `if not query.message: return` after the chat-type check in `tab_callback`, and after the chat check in `equip_callback` (:617), `buy_callback` (:736), `use_callback` (:825-ish).
- [ ] **Step 2:** `inv_` :478-500 →

```python
            if query.message.photo:
                fallback = lambda: query.edit_message_media(
                    media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                    reply_markup=_inventory_keyboard(inventory, category),
                )
            else:
                fallback = lambda: query.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=_inventory_keyboard(inventory, category),
                )
            await edit_rich(
                client, query.message.chat.id, query.message.id,
                build_inventory_rich(hunter, inventory, category, photo_first=True),
                reply_markup=_inventory_keyboard(inventory, category),
                media=[photo_media("inventory", photo_buf)],
                fallback=fallback,
            )
```

(keep `except MessageNotModified:` and render-fail `except Exception` blocks unchanged)
- [ ] **Step 3:** `shop_menu` :521-543 → same shape; identifiers: `build_shop_rich(hunter, "menu", photo_first=True)`, `_shop_category_keyboard()`, `photo_media("shop", photo_buf)`, `caption`. Keep excepts.
- [ ] **Step 4:** `shop_<cat>` :564-586 → same shape; identifiers: `build_shop_rich(hunter, category, photo_first=True)`, `_shop_items_keyboard(category)`, `photo_media("shop", photo_buf)`, `caption`. Keep excepts.
- [ ] **Step 5:** `equip_` :689-711 → same shape; identifiers: `build_inventory_rich(hunter, inventory, return_cat, notice=notice, photo_first=True)`, `_inventory_keyboard(inventory, return_cat)`, `photo_media("inventory", photo_buf)`, `caption`. Keep `except Exception` render-fail.
- [ ] **Step 6:** `buy_` :774-796 → same shape; identifiers: `build_shop_rich(hunter, cat, notice=notice, photo_first=True)`, `_shop_items_keyboard(cat)`, `photo_media("shop", photo_buf)`, `caption`.
- [ ] **Step 7:** `use_` :868-890 → same shape; identifiers: `build_inventory_rich(hunter, inventory, "consumable", notice=notice, photo_first=True)`, `_inventory_keyboard(inventory, "consumable")`, `photo_media("inventory", photo_buf)`, `caption`.
- [ ] **Step 8:** `python -m py_compile handlers\inventory.py` → OK; commit `fix(inventory): in-place refresh for tabs, equip, buy, and use`

### Task 4: forge.py — menu refresh + 3 no-op sites

**Files:** Modify `handlers/forge.py` in `callback`: `:205-228`, `:242-252`, `:271-281`, `:297-307`; guard after inventory check (:197).

- [ ] **Step 1:** Guard: `if not query.message: return` after `await query.answer("Could not load inventory!", ...)`/return block.
- [ ] **Step 2:** `forge_menu/forge_refresh` :205-228 →

```python
        if query.message.photo:
            fallback = lambda: query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_forge_keyboard(inventory, None),
            )
        else:
            fallback = lambda: query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_forge_keyboard(inventory, None),
                show_caption_above_media=True,
            )
        await edit_rich(
            client, query.message.chat.id, query.message.id,
            build_forge_rich(hunter, inventory, None, photo_first=False),
            reply_markup=_forge_keyboard(inventory, None),
            media=[photo_media("forge", photo_buf)],
            fallback=fallback,
        )
        return
```

- [ ] **Step 3:** `forge_sel_` :242-252 →

```python
        if query.message.photo:
            fallback = lambda: query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_forge_keyboard(inventory, item),
            )
        else:
            fallback = lambda: query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_forge_keyboard(inventory, item),
                show_caption_above_media=True,
            )
        await edit_rich(
            client, query.message.chat.id, query.message.id,
            build_forge_rich(hunter, inventory, item, photo_first=False),
            reply_markup=_forge_keyboard(inventory, item),
            media=[photo_media("forge", photo_buf)],
            fallback=fallback,
        )
        return
```

- [ ] **Step 4:** `forge_up_` :271-281 → same shape as Step 3 but `build_forge_rich(hunter, inventory, item, notice=notice, photo_first=False)` as doc.
- [ ] **Step 5:** `forge_fuse_` :297-307 → same shape as Step 3 with `item` → `new_item` everywhere and doc `build_forge_rich(hunter, inventory, new_item, notice=notice, photo_first=False)`.
- [ ] **Step 6:** `python -m py_compile handlers\forge.py` → OK; commit `fix(forge): in-place refresh for menu, select, upgrade, fuse`

### Task 5: tower.py — _execute_climb + tower_menu

**Files:** Modify `handlers/tower.py`: `_execute_climb` :222-251, `callback` :306-333; guards.

- [ ] **Step 1:** In `_execute_climb`, replace branches :222-251 with:

```python
        if isinstance(target, CallbackQuery):
            await target.answer("Ascension battle concluded!", show_alert=False)
            if not target.message:
                return
            if target.message.photo:
                fallback = lambda: target.edit_message_media(
                    media=InputMediaPhoto(
                        media=photo_buf,
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                    ),
                    reply_markup=_tower_keyboard(hunter),
                )
            else:
                fallback = lambda: target.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=_tower_keyboard(hunter),
                    show_caption_above_media=True,
                )
            await edit_rich(
                client, target.message.chat.id, target.message.id,
                build_tower_rich(hunter, next_guardian, result, notice, photo_first=False),
                reply_markup=_tower_keyboard(hunter),
                media=[photo_media("tower", photo_buf)],
                fallback=fallback,
            )
        else:
```

(the `else:` keeps the existing Message-target `reply_rich(target, ...)` block :252-264 verbatim; render-fail path :265-283 unchanged — both arms already edit/reply correctly)
- [ ] **Step 2:** In `callback`, add guard `if not query.message: return` after hunter check (:297); replace :306-333 with the same shape as Task 1 Step 2, identifiers: doc `build_tower_rich(hunter, guardian, photo_first=False)`, kb `_tower_keyboard(hunter)`, media `photo_media("tower", photo_buf)`, caption `caption`, answer already at :302.
- [ ] **Step 3:** `python -m py_compile handlers\tower.py` → OK; commit `fix(tower): in-place refresh for climb result and spire menu`

### Task 6: quest.py — claim no-op + stats/menu refresh

**Files:** Modify `handlers/quest.py`: guard in `callback`; `:380-391`, `:416-460`, `:464-484`, `:486-496`.

- [ ] **Step 1:** Guard `if not query.message: return` after hunter check in `callback`.
- [ ] **Step 2:** `quest_claim` :380-391 →

```python
        if query.message.photo:
            fallback = lambda: query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                reply_markup=_quest_keyboard(hunter),
            )
        else:
            fallback = lambda: query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=_quest_keyboard(hunter),
                parse_mode=enums.ParseMode.HTML,
                show_caption_above_media=True,
            )
        await edit_rich(
            client, query.message.chat.id, query.message.id, claim_doc,
            reply_markup=_quest_keyboard(hunter),
            media=[photo_media("quest", photo_buf)],
            fallback=fallback,
        )
        return
```

- [ ] **Step 3:** `stats_add_` :416-460 → collapse both arms:

```python
        if query.message.photo:
            fallback = lambda: query.message.reply_text(
                "<b>[ STAT ALLOCATION // 능력치 배분 ]</b>\n\n"
                ...entire existing :421-435 classic text verbatim...,
                reply_markup=_stats_keyboard(hunter),
                parse_mode=enums.ParseMode.HTML,
            )
        else:
            fallback = lambda: query.edit_message_text(
                "<b>[ STAT ALLOCATION // 능력치 배분 ]</b>\n\n"
                ...entire existing :444-458 classic text verbatim...,
                reply_markup=_stats_keyboard(hunter),
                parse_mode=enums.ParseMode.HTML,
            )
        await edit_rich(
            client, query.message.chat.id, query.message.id,
            _stats_menu_rich(hunter, "alloc"),
            reply_markup=_stats_keyboard(hunter),
            fallback=fallback,
        )
        return
```

- [ ] **Step 4:** `stats_menu` :464-484 →

```python
        await query.answer()
        if not query.message:
            return
        await edit_rich(
            client, query.message.chat.id, query.message.id,
            _stats_menu_rich(hunter, "compact"),
            reply_markup=_stats_keyboard(hunter),
            fallback=lambda: query.message.reply_text(
                ...entire existing :470-481 classic text verbatim...,
                reply_markup=_stats_keyboard(hunter),
                parse_mode=enums.ParseMode.HTML,
            ),
        )
        return
```

- [ ] **Step 5:** `quest_menu` :486-496 → Task 6 Step 2 shape with doc `build_quest_rich(hunter, photo_first=False)`, kb `_quest_keyboard(hunter)`, media `photo_media("quest", photo_buf)`, caption `caption` (classic fallback `reply_photo(...)` lambda body from :494 as the else arm).
- [ ] **Step 6:** `python -m py_compile handlers\quest.py` → OK; commit `fix(quest): in-place refresh for claim, stats, and menu callbacks`

### Task 7: guild_war.py — war accept status card

**Files:** Modify `handlers/guild_war.py` in `war_callback`: guard; `:561-584`.

- [ ] **Step 1:** Guard `if not query.message: return` right after the first `await query.answer()` in `war_callback` (~:470).
- [ ] **Step 2:** :561-584 (inside try) →

```python
        if query.message.photo:
            fallback = lambda: query.edit_message_media(
                media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=ParseMode.HTML),
                reply_markup=None,
            )
        else:
            fallback = lambda: query.message.reply_photo(
                photo=photo_buf,
                caption=caption,
                reply_markup=None,
                parse_mode=ParseMode.HTML,
                show_caption_above_media=True,
            )
        await edit_rich(
            client, query.message.chat.id, query.message.id,
            build_war_status_rich(
                war['challenger_guild_name'], war['defender_guild_name'],
                0, 0, 0, len(active_war["matchups"]),
                photo_first=False,
            ),
            media=[photo_media("war", photo_buf)],
            fallback=fallback,
        )
```

(existing `except Exception` render-fail edit_rich at :585 unchanged)
- [ ] **Step 3:** `python -m py_compile handlers\guild_war.py` → OK; commit `fix(guild-war): in-place war status card on accept`

### Task 8: Full verification battery

**Files:** none modified.

- [ ] **Step 1:** `python -m py_compile handlers\leaderboard.py handlers\guild.py handlers\inventory.py handlers\forge.py handlers\tower.py handlers\quest.py handlers\guild_war.py` → OK
- [ ] **Step 2:** `python game\rich_message.py` → `RICH SELF-CHECK OK`; `python game\rich_send.py` → `RICH SEND SELF-CHECK OK`
- [ ] **Step 3:** Import smoke: `python -c "import handlers.leaderboard, handlers.guild, handlers.inventory, handlers.forge, handlers.tower, handlers.quest, handlers.guild_war; print('IMPORT SMOKE OK')"` → OK
- [ ] **Step 4:** Grep audit: `rg -n "reply_rich\(query|reply_rich\(\s*$" handlers\` — every remaining hit must be in command handlers or the 3 deferred classic-parity sites (`quest:464` gone after Task 6; allowed remain: duel/`explore` message replies etc.). Then `rg -n "query.message.photo|target.message.photo" handlers\` — every hit must be a fallback-selection line, an unchanged render-fail caption line, or deferred `help.py:618/:646`. Review each line manually.
- [ ] **Step 5:** Start bot (`Start-Process python -ArgumentList main.py -WorkingDirectory W:\solo-leveling-bot -RedirectStandardError bot_err.log -RedirectStandardOutput bot_out.log`), wait 8s, assert `Session started` in `bot_out.log` and 0 `Traceback` in `bot_err.log`.
- [ ] **Step 6:** Report diff summary; await user's live click test + push approval.
