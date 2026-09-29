# Mini App "System Window" UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign all Mini App screens into a Solo-Leveling System HUD, add a Profile status screen as default home, minimal backend field additions.

**Architecture:** Approach A — split `App.tsx` (486 lines) into `screens/` + `components/`; App keeps all state and data loading, screens are presentational. HUD layer (tokens + CSS primitives) styles everything; motion is pure CSS behind a `prefers-reduced-motion` guard. Backend adds 6 fields to the existing `/me` serializer and fixes one stale constant.

**Tech Stack:** React 19 + TypeScript 5.8 + Vite 6, plain CSS (zero new deps), FastAPI backend (`miniapp_api.py`).

**Spec:** `docs/superpowers/specs/2026-09-28-miniapp-system-ui-design.md`

> **Implementation status (2026-09-30):** Mini App Tasks 1–6 are present in repository history. Bot Premium emoji Task 7 is implemented in the local working tree. Task 8 verification remains pending; unchecked verification steps below have not been confirmed.

## Global Constraints

- Zero new frontend dependencies (React + react-dom only — package.json must not gain deps).
- Palette stays byte-consistent with `game/design_tokens.py` except documented deviations: `ink-muted #64748b` kept for contrast; Legendary `#fbbf24`, Rank A `#f43f5e`, Monarch `#c084fc` aligned to bot.
- All animations behind `@media (prefers-reduced-motion: reduce)` disabling them.
- Deep links: `claim|shop|guilds|guild_<id>` must keep working; default section becomes `profile`.
- No new Mini App API endpoints or bot-side link changes (`game/miniapp.py` stays unchanged). The separately approved bot Premium emoji work updates bot message presentation.
- Bot custom emoji come only from the semantic allowlist in `game/premium_emoji.py`, retain Unicode fallbacks, and never enter Telegram channel JSON or the browser Mini App.
- Continue using `telegram-text` through `game/rich_text.py`; escape dynamic HTML and use `.to_html()` when rendering its elements.
- Build must stay green: `npm run build` (= `tsc -b && vite build`).

## Review Focus

1. **Cold deep-link `startapp=claim` after default flips to profile** — existing links must still open Claim: covered by Task 3 step (telegram.ts accepts all five params; verify via unit-less manual check in `initialSection` logic + build).
2. **`/me` response shape drift** — frontend must not crash if optional new fields are absent (old backend): Profile reads `str_stat` etc. with `?? 7` fallbacks? No — API ships together; instead verify py_compile + boot smoke, and frontend `types.ts` marks them required (same deploy unit).
3. **Claim cooldown state** — countdown must tick and disable button (existing logic lifted, not rewritten): Task 5 keeps `claimDaily()`/`claimRemaining` logic byte-identical from App.tsx:126-143.
4. **Guild sort re-fetch + selected-guild refresh race** — existing `cancelled` guard (App.tsx:113-119) must survive the split: Task 3 lifts `loadSystem`/effects verbatim.
5. **Notice auto-dismiss vs rapid actions** — claim then shop click must not double-dismiss or leak timers: SystemNotice owns one timer, clears on unmount (Task 4).

---

### Task 1: Backend fields + stale bonus fix

**Files:**
- Modify: `miniapp_api.py:84-96` (`_hunter_summary`), `miniapp_api.py:130` (`xp_bonus_percent`)
- Modify: `miniapp_api.py` imports (add `GUILD_XP_BONUS` from config — check existing config import line first)

**Interfaces:**
- Produces: `_hunter_summary()` returns dict with 6 new keys: `str_stat: int, agi: int, vit: int, int_stat: int, per: int, title: string` (consumed by Task 3 `types.ts`).

**Steps:**
- [ ] Add 6 keys to `_hunter_summary` dict (values from `hunter.str_stat`, `hunter.agi`, `hunter.vit`, `hunter.int_stat`, `hunter.per`, `hunter.title`).
- [ ] Replace `"xp_bonus_percent": 10,` with `"xp_bonus_percent": int(GUILD_XP_BONUS * 100),` (import `GUILD_XP_BONUS` from config alongside existing config imports).
- [ ] Verify: `python -m py_compile miniapp_api.py` → exit 0.
- [ ] Verify: `rg 'xp_bonus_percent' miniapp_api.py` → shows `int(GUILD_XP_BONUS * 100)`.
- [ ] Commit: `fix(miniapp): expose hunter attributes in /me + config-driven guild xp bonus`

### Task 2: HUD tokens + CSS primitives

**Files:**
- Modify: `miniapp/src/tokens.css`
- Modify: `miniapp/src/styles.css`

**Interfaces:**
- Produces CSS classes consumed by Tasks 3-6: `.hud-frame`, `.sys-header`, `.scanlines`, `.status-grid`, `.xp-bar`, `.sys-btn`, `.sys-notice`; tokens `--color-stat-green`, `--glow-sm`, `--glow-md`.

**Steps:**
- [ ] tokens.css: add
  ```css
  --color-stat-green: #4ade80;
  --glow-sm: 0 0 8px rgba(0, 210, 255, 0.25);
  --glow-md: 0 0 18px rgba(0, 210, 255, 0.35), 0 0 40px rgba(0, 210, 255, 0.12);
  ```
  Align: `--color-rarity-legendary: #fbbf24`, `--color-rank-a: #f43f5e`, `--color-monarch: #c084fc` (only if those exact token names exist — match current names, adjust value only).
- [ ] styles.css: append a `/* ── HUD SYSTEM ── */` section with the 7 primitives:
  - `.hud-frame` — `position: relative; border: 1px solid rgba(0,210,255,.22)` + `::before/::after` corner-bracket gradient trick (two pseudo-elements, 14px arms, `--glow-sm`).
  - `.sys-header` — flex row, `font-family: var(--font-mono)`, uppercase, letter-spacing `.14em`, cyan `[ ` bracket spans, 1px divider line via `::after`.
  - `.scanlines` — `::after` overlay, `repeating-linear-gradient(0deg, transparent 0 3px, rgba(0,0,0,.18) 3px 4px)`, `opacity:.05; pointer-events:none`.
  - `.status-grid` — grid rows `auto`, each `.stat-row` flex space-between with `.stat-value` `color: var(--color-stat-green); font-family: var(--font-mono)`.
  - `.xp-bar` — track `rgba(0,210,255,.10)`, fill `linear-gradient(90deg, #0891b2, #00d2ff)` with `transition: width .6s ease`, `.xp-shimmer` keyframe sweep.
  - `.sys-btn` — bordered glow primary/ghost variants, `:active { transform: scale(.97) }`, `[disabled]` dimmed.
  - `.sys-notice` — centered fixed box, `--glow-md` border pulse, pop-in keyframe `notice-pop 180ms`.
- [ ] Motion keyframes at end of styles.css + `@media (prefers-reduced-motion: reduce)` block setting `animation: none !important; transition: none !important` on `.panel-enter, .xp-fill, .sys-notice, .sys-btn, .nav-item`.
- [ ] Verify: `npm run build` → passes.
- [ ] Commit: `feat(miniapp): HUD token layer + System window CSS primitives`

### Task 3: Structural split (behavior-neutral) + types + deep links

**Files:**
- Create: `miniapp/src/components/TopBar.tsx`, `BottomNav.tsx`, `SystemPanel.tsx`, `SystemNotice.tsx`, `StatePanels.tsx`
- Create: `miniapp/src/screens/Profile.tsx`, `Claim.tsx`, `Shop.tsx`, `Guilds.tsx`
- Modify: `miniapp/src/App.tsx` (gut → shell), `miniapp/src/types.ts`, `miniapp/src/lib/telegram.ts`
- Move unchanged logic: helpers `number/countdown/errorMessage/getRequestId` → keep in App.tsx and pass as needed, or export from a tiny `src/lib/format.ts` (prefer `format.ts` — Claim/Shop/Guilds all need `number`).

**Interfaces:**
- Consumes: Task 1 fields, Task 2 classes.
- Produces (all tasks 4-6 build on these):
  ```ts
  // App state owner; screens get props only
  TopBar({ me: MeResponse | null; loading: boolean; onRefresh: () => void })
  BottomNav({ section: Section; onChange: (s: Section) => void })
  SystemPanel({ title: string; suffix?: string; children: ReactNode })
  SystemNotice({ message: string; tone?: 'ok' | 'error'; onClear: () => void })
  StatePanels({ loading: boolean; error: string; hasMe: boolean; onRetry: () => void })
  ProfileScreen({ me: MeResponse; claimRemaining: number; onOpenGuild: () => void })
  ClaimScreen({ level: number; remaining: number; busy: boolean; onClaim: () => void })
  ShopScreen({ items: ShopItem[]; category: ShopCategory; gold: number; busyItem: string | null;
               inventoryCount: number; onCategory: (c: ShopCategory) => void; onBuy: (i: ShopItem) => void })
  GuildsScreen({ guilds: GuildSummary[]; currentGuild: GuildSummary | null;
                 selectedGuild: GuildSummary | null; sort: GuildSort; onSort: (s: GuildSort) => void;
                 onSelect: (g: GuildSummary) => void })
  ```
- `types.ts`: `Section = 'profile' | 'claim' | 'shop' | 'guilds'`; `HunterSummary` + `str_stat: number; agi: number; vit: number; int_stat: number; per: number; title: string`.
- `telegram.ts`: default branch `'claim'` → `'profile'`; accept `param === 'profile'`.

**Steps:**
- [ ] Create `src/lib/format.ts` with `number`, `countdown`, `errorMessage`, `getRequestId` moved verbatim from App.tsx:37-55.
- [ ] Update `types.ts` (Section + 6 HunterSummary fields).
- [ ] Update `telegram.ts:33-38`: add `'profile'` to accepted params, default `'profile'`.
- [ ] Create `SystemPanel` (wraps children in `.hud-frame` + `.sys-header` with `[ title ]` + optional suffix), `TopBar` (merged topbar + hunter-strip from App.tsx:192-217, adds cooldown dot), `BottomNav` (4 buttons incl. `◈ Status`), `SystemNotice` (own `setTimeout(2500)` → `onClear`, cleanup on unmount), `StatePanels` (lift App.tsx:230-248 verbatim, restyled with `.state-panel` kept).
- [ ] Create 4 screens by lifting panels **verbatim first** (Claim from App.tsx:300-337, Shop 339-402, Guilds 404-486) wrapped in `SystemPanel`; `Profile.tsx` starts as minimal status stub (rank/level/XP/gold rows — restyled in Task 4).
- [ ] Rewrite `App.tsx` as shell: keep state, `loadSystem`, effects, `claimDaily`, `buy`, `openGuild`, `changeSection` **unchanged**; render TopBar → section-heading (profile copy added to `sectionCopy`) → StatePanels | screen → BottomNav; `SystemNotice` rendered when `notice` set (replaces bare `.notice` div).
- [ ] Add `sectionCopy.profile = { eyebrow: 'Hunter record', title: 'Status Window', detail: 'Your current standing in the System.' }`.
- [ ] Verify: `npm run build` → clean; grep old component names gone from App.tsx.
- [ ] Commit: `refactor(miniapp): split App into screens + HUD components`

### Task 4: Profile status screen (real design) + SystemNotice wiring

**Files:**
- Modify: `miniapp/src/screens/Profile.tsx`
- Modify: `miniapp/src/styles.css` (`.status-*` screen styles)
- Modify: `miniapp/src/App.tsx` (only if notice wiring needs tone)

**Steps:**
- [ ] Build ProfileScreen inside `SystemPanel title="STATUS" suffix={hunter.display_name}`:
  - Rank seal (big letter) + `LV. {level}` + `title` line + rank chip.
  - `.xp-bar` with inline `width: min(100%, xp/xp_needed*100%)`, mono `xp / xp_needed` numbers.
  - `.status-grid`: 5 rows `STR/AGI/VIT/INT/PER` → `str_stat/agi/vit/int_stat/per` green brackets + `POWER` row (`me.hunter.power`).
  - Claim chip: `countdown(claimRemaining)` or `READY`, clickable → `onOpenGuild`? No — claim chip links to Claim section: App passes `onOpenClaim`. Add prop `onOpenClaim: () => void` (extend interface above) — profile quick-actions: `CLAIM` (→claim section) and guild chip (→guilds section, only if `me.guild`).
  - Stats strip: `◈ gold`, `◇ {inventory_count} items`, guild name.
- [ ] Wire `SystemNotice` in App (message + tone from claim/buy results; errors tone `'error'`).
- [ ] Verify: `npm run build`.
- [ ] Commit: `feat(miniapp): Profile status window with attribute grid`

### Task 5: Claim + Shop redesign

**Files:**
- Modify: `miniapp/src/screens/Claim.tsx`, `miniapp/src/screens/Shop.tsx`
- Modify: `miniapp/src/styles.css`

**Steps:**
- [ ] Claim: restructure to `.sys-claim` — `[ DAILY RATION ]` header via SystemPanel; reward cells keep estimates; button becomes `.sys-btn` (`SYS:CLAIM` label; disabled shows `Next ration in …`); ready state glows (`--glow-sm`).
- [ ] Shop: `.sys-shop` — category chips get `.sys-chip` active glow; item cards keep rarity class, add left-edge glow: `.item-card { border-left: 2px solid var(--color-rarity-X) }` per rarity + `box-shadow: -4px 0 12px -6px currentColor`; stat rows mono; buy button `.sys-btn`; insufficient state shows inline `Need {price}G · have {gold}G`.
- [ ] Keep all handler props/logic unchanged (Task 3 lift).
- [ ] Verify: `npm run build`.
- [ ] Commit: `feat(miniapp): System-styled Claim + rarity-glow Shop`

### Task 6: Guilds redesign + motion polish

**Files:**
- Modify: `miniapp/src/screens/Guilds.tsx`, `miniapp/src/styles.css`
- Verify against: `xp_bonus_percent` now 5 (Task 1) — display `+{guild.xp_bonus_percent}% HUNT XP`.

**Steps:**
- [ ] Guilds: rows get `.hud-frame`-lite (top/bottom hairlines), tier medals (place `01` → gold/silver/bronze color by index), detail becomes SystemPanel `[ GUILD RECORD // #id ]`; metrics grid uses `.status-grid` styling; bonus line reads config-correct value.
- [ ] Add `.panel-enter` animation: apply `key={section}` on the screen wrapper div in App so section switches replay `panel-enter 160ms` fade+slide-up.
- [ ] XP bar shimmer: add `.xp-shimmer` sweep on Profile (one-shot via `animation-iteration-count: 1`).
- [ ] Verify reduced-motion block from Task 2 covers every new animation class (grep `animation:` in styles.css, cross-check list).
- [ ] Verify: `npm run build`.
- [ ] Commit: `feat(miniapp): guild directory HUD styling + section motion`

### Task 7: Bot-wide Premium custom emoji — implemented locally

**Files:**
- Modify: `game/premium_emoji.py` (single immutable semantic registry of real custom emoji IDs plus Unicode fallback text)
- Modify: `game/rich_text.py` (registry re-exports, safe rendering, and allowlisted inline button icon helper)
- Modify: `game/captions.py`, `game/formatting.py`, and user-facing bot handlers to use semantic section tokens

**Coverage:** start/profile, hunt/explore, claim/shop/inventory/equipment/forge, guild/guild war, duel, quest/redeem/tower, shadows/leaderboard/help, and admin output.

**Status:** Message bodies across the covered feature paths use registry entries. The inline button icon helper is available in `game/rich_text.py`.

**Constraints:**
- Only use verified registry entries; unknown semantic keys or IDs fail closed. Never invent IDs or accept a caller-supplied ID.
- Keep each custom emoji's Unicode fallback in message markup. Use button icons only through the helper that validates IDs against the same allowlist.
- The bot owner has Telegram Premium, enabling the bot to send custom emoji in private, group, and supergroup chats.
- Rich markup is presentation only: never persist it in channel JSON or render Telegram `tg-emoji` markup in the web Mini App.

**Verification:** pending under Task 8. Inspect representative message output for every section, confirm fallback text remains present, and smoke-check custom emoji rendering in private and group chats. Check button icons where supported by the installed Kurigram version.

### Task 8: Full verification

**Steps:**
- [ ] `npm run build` → clean (tsc + vite).
- [ ] `python -m py_compile miniapp_api.py` → 0.
- [ ] `python -m py_compile config.py models.py channel_db.py shadows_db.py main.py` → 0 (no accidental damage).
- [ ] Run `tests/verify_progression_battery.sh` → PASS (regression guard from prior work).
- [ ] Visual check: `npx --yes playwright` + local `vite dev` with mocked initData/API (best effort — webapp-testing skill); fallback: document manual Telegram smoke for user.
- [ ] Bot emoji check: representative messages render custom emoji in Telegram; Unicode fallback remains valid; no raw custom emoji IDs appear outside `game/premium_emoji.py` or its helper integration.
- [ ] `git status` + `git diff --stat` review; fix any stragglers.
- [ ] Report results; commits already staged per-task; **push only on user OK**.
