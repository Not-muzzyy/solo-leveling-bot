# Design Spec — Mini App "System Window" UI

**Date**: 2026-09-28 · **Status**: approved in-session (user: "ok good" → approach A; all scope questions answered)

## Goal

Full visual redesign of the Telegram Mini App into a Solo-Leveling "System" HUD — pixel-consistent with the bot's Pillow card language — plus a new Profile status screen as the default home. Pure CSS motion, zero new frontend dependencies, minimal approved backend additions.

## Decisions (locked with user)

| Question | Decision |
|---|---|
| Screen scope | Redesign all 3 existing screens + new Profile home screen |
| Visual direction | Deep SL-System HUD, match bot cards (holistic holographic blue panels, HUD brackets, mono headers) |
| Motion | Polished CSS-only, no libraries, `prefers-reduced-motion` guard |
| Approach | **A** — structural split into `screens/` + `components/` |
| Profile data | Extend existing `/me` with attribute fields (6 keys) + fix stale guild XP bonus display |
| Non-goals | No new endpoints, no router/UI-kit deps, no bot-side link changes, no inventory/leaderboard/shadow screens |

## 1. HUD Design System

Keep `tokens.css` byte-match palette with `game/design_tokens.py`; add an HUD layer.

**Token changes**
- Add: `--glow-sm`, `--glow-md` (layered cyan box-shadows); rank/rarity accents byte-matched to bot `RANK_COLORS`/`RARITY_COLORS`: `--color-gold-bright #fbbf24` (rank S / Legendary), `--color-amber #f59e0b` (SS), `--color-rose #f43f5e` (A), `--color-monarch #c084fc`, `--color-pink #ec4899` (National Level), `--color-silver #e2e8f0`, `--color-bronze #d97706` (leaderboard tier medals). Currency gold stays `#facc15` (bot `INK_GOLD`).
- Documented deviation: keep `--color-ink-muted: #64748b` (bot uses `#475569`, which fails contrast for web text on `#070b18`).

**New CSS primitives** (styles.css, one class each)
- `.hud-frame` — corner brackets via pseudo-elements (SL window corner marks) + scanline class.
- `.sys-header` — `TITLE // 한국어` mono header, cyan title + muted suffix, matching bot card headers (`STATUS WINDOW // 상태창`, `GUILD REGISTRY // 길드 정보`, `EXCHANGE DEPOT // 헌터협회 상점`).
- `.scanlines` — `repeating-linear-gradient` overlay, `opacity ≈ .05`, `pointer-events: none`.
- `.status-grid` — bot-faithful stat rows: sky mono label, muted full name, white mono value, full-width segmented **cyan gauge** (profile_image.py `_draw_stat_row` anatomy — not anime-fan green brackets).
- `.xp-bar` — track + fill + one-shot shimmer keyframe.
- `.sys-btn` — bordered glow button (primary / ghost / disabled).
- `.sys-notice` — centered notification box replacing bare `.notice`; auto-dismiss.

## 2. File Structure

```
miniapp/src/
├── App.tsx            (~160 lines: shell, state, data load, section routing)
├── tokens.css         (existing + HUD layer)
├── styles.css         (reorganized by section + new primitives)
├── screens/           Profile.tsx · Claim.tsx · Shop.tsx · Guilds.tsx
├── components/        TopBar.tsx · BottomNav.tsx · SystemPanel.tsx ·
│                      SystemNotice.tsx · StatePanels.tsx
├── api/client.ts      unchanged
├── lib/telegram.ts    default section → 'profile'; accept 'profile' param
└── types.ts           Section + 'profile'; HunterSummary + 6 fields
```

Navigation: BottomNav `◈ STATUS` (home, default) · `CLAIM` · `SHOP` · `GUILDS`. Deep-link default `claim → profile`; existing `claim|shop|guilds|guild_<id>` links keep working. Bot-side `game/miniapp.py` unchanged.

## 3. Screens

- **Profile (new, default)** — SL Status window: `[ STATUS // name ]`; rank badge + level + title; XP bar `xp/xp_needed` with shimmer + mono numbers; attribute grid `[ STR 32 ] [ AGI 18 ] [ VIT ] [ INT ] [ PER ]` green brackets + POWER row; claim countdown chip; gold + `inventory_count` + guild chip (navigates to Guilds detail).
- **Claim** — `[ DAILY RATION ]`; gold amount + XP estimate; mono countdown ticker; `SYS:CLAIM` button; success → `.sys-notice` pop-in (`+GOLD +XP`, level-up / rank-up variants) + hunter refresh; cooldown → disabled button + remaining time.
- **Shop** — `[ SYSTEM SHOP ]`; category chips; item cards with rarity left-edge glow + `ATK +12` mono stat rows + price; `SYS:BUY`; insufficient gold → inline reason; header shows gold + `inventory_count`.
- **Guilds** — `[ GUILD DIRECTORY ]`; sort chips (power/level/gold/members); HUD rows with tier medals; detail window: stat grid including `XP BONUS +5%` (config-derived) + member roster; honors `guild_<id>` deep link (App-level selected-guild state preserved).
- **Shared chrome**: TopBar merges old topbar + hunter-strip (name, `[Lv.X | Rank]` chip, gold, cooldown dot); SystemPanel wraps every screen for a consistent frame; StatePanels keep loading / error / no-hunter / telegram-required states.

## 4. Backend Touches (approved, minimal)

1. `miniapp_api.py:_hunter_summary` + `types.ts HunterSummary`: add `str_stat, agi, vit, int_stat, per, title` (same endpoint, no new routes).
2. `miniapp_api.py:130`: hard-coded `xp_bonus_percent: 10` → `int(config.GUILD_XP_BONUS * 100)` (stale since progression rebalance set 5).

## 5. Motion (CSS-only, all behind `@media (prefers-reduced-motion: reduce)`)

- Section change: panel fade + slide-up 160ms (keyed by section).
- XP bar: width transition 600ms + one-shot shimmer sweep.
- Claim success / level-up: notice pop-in + border glow pulse.
- Buttons/nav: press scale `.97` + glow intensify; countdown `:` blink.

## 6. Verification

1. `npm run build` (`tsc -b && vite build`) clean.
2. `python -m py_compile miniapp_api.py`; `tests/verify_progression_battery.sh` still green (no regression).
3. Screenshots: `npx playwright` with mocked `window.Telegram.WebApp.initData` + route-intercepted `/api/v1/*` covering all 4 screens + notice; fallback — user smoke-tests in Telegram.
4. Bot boot smoke: starts clean, Mini App API serves `/api/health`.

## Commits (in order; push only on user OK)

1. backend fields + stale-bonus fix
2. tokens + primitives
3. component/screen split (behavior-neutral)
4. screen designs + motion
5. polish from smoke (if any)
