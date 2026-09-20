# AGENTS.md — Context & Instructions for AI Agents

## Project Overview

**Solo Leveling Hunter RPG Bot** — A high-performance, atmospheric Telegram group RPG bot inspired by the **Solo Leveling** Hunter System. Players awaken as Hunters, battle dimensional gate monsters, gear up with glowing equipment, join guilds, challenge rivals in PvP arena duels, and command a growing **Shadow Monarch Army** (`/arise` & `/shadows`).

- **Language**: Python 3.11+
- **Framework**: `kurigram` v2.2.25+ (Pyrogram fork, MTProto API, fully asynchronous, decorator pattern)
- **Database**: **Telegram Channel Databases** (`channel_db.py` & `shadows_db.py`) — private Telegram channels store all game records and shadow entities as JSON messages (no external SQLite/Postgres server required).
- **Design System**: Hallmark-compliant anti-slop visual renderer using Pillow with universal font cascading (0 tofu blocks for any Unicode/Fraktur/CJK/Emoji characters).

---

## Project Structure

```
solo-leveling-bot/
├── .env                     # Secrets: BOT_TOKEN, API_ID, API_HASH, DATA_CHANNEL_ID, SHADOWS_CHANNEL_ID, SUPERADMIN_IDS (gitignored)
├── .env.example             # Configuration template
├── .gitignore               # Secrets, session databases, scratch files ignored
├── requirements.txt         # kurigram>=2.2.25, python-dotenv, Pillow>=10.0.0
├── main.py                  # Entry point — registers handlers, initializes DBs, runs polling
├── config.py                # Game balances: ranks, rarities, XP curves, shop items, guild settings
├── models.py                # Dataclasses: Hunter, Item, Inventory, Monster, HuntResult, Guild, ShadowCharacter, UserShadow
├── channel_db.py            # Primary ChannelDB class — Telegram channel storage for hunters & guilds
├── shadows_db.py            # Dedicated ShadowsDB class — Telegram channel storage for shadow character catalog & user armies
├── game/
│   ├── hunter.py            # Hunter creation, XP gain, level/rank up calculations
│   ├── combat.py            # Monster generation, combat damage formula, hunt simulation
│   ├── items.py             # Procedural loot generation & rarity weight tables
│   ├── shop.py              # 21 purchasable items across 5 categories, purchasing logic
│   ├── font_manager.py      # Universal Unicode Font Cascade & Normalizer (Fraktur, Hangul, CJK, Emoji, zero tofu)
│   ├── design_tokens.py     # Hallmark design system tokens, atmospheric canvas, and vector shapes
│   ├── profile_image.py     # Pillow renderer — High-res System Status Window with avatar neon ring
│   ├── hunt_image.py        # Pillow renderer — 16:9 Combat Cards (Victory & Defeat) for /hunt
│   ├── hunt_gif.py          # Backward compatibility shim for hunt_image
│   ├── inventory_image.py   # Pillow renderer — High-res Dimensional Inventory image with equipment visuals
│   ├── shop_image.py        # Pillow renderer — High-res Hunter Shop image with vector catalogue & treasury
│   ├── shadows_image.py     # Pillow renderer — Clean Hallmark Shadow Army collection card with 3-stat bar
│   ├── guild_image.py       # Pillow renderer — Guild Card with owner, top 5, and member roster
│   ├── guild_leaderboard_image.py # Pillow renderer — Guild Leaderboard HUD card
│   ├── guild_war_image.py   # Pillow renderer — War challenge, status, and result cards
│   ├── leaderboard_image.py # Pillow renderer — High-res System Hall of Fame with real names & podium
│   ├── duel.py              # Pure combat simulation engine for PvP arena duels
│   ├── duel_image.py        # Pillow renderer — 920x580 High-def Duel Card with VS clash, WON/LOST banners
│   └── formatting.py        # Plain-text formatting with Unicode box-drawing
└── handlers/
    ├── start.py             # /start & deep-link router (inventory, shop, help)
    ├── profile.py           # /profile — photo status card
    ├── hunt.py              # /hunt — visual combat resolution card (15m cooldown)
    ├── inventory.py         # /inventory — image storage, 1-tap equip & shop (PM protection)
    ├── shop.py              # /shop — visual exchange depot image cards (PM protection)
    ├── leaderboard.py       # /leaderboard — visual Hall of Fame with interactive category tabs
    ├── duel.py              # /duel — PvP arena with visual resolution card
    ├── arise.py             # /arise & /shadows — automated 250-msg spawns, name guessing, army browser, superadmin suite
    ├── guild.py             # /guild — create, join, leave, info, top, war, kick, disband, edit
    ├── guild_war.py         # /guild war — guild-vs-guild war system with visual cards
    ├── claim.py             # /claim — daily reward (24h cooldown)
    └── help.py              # /help — operational manual
```

---

## Key Subsystems

### 1. Dual Channel Database Architecture
- **Primary Database (`ChannelDB`)**: Operates on `DATA_CHANNEL_ID`. Stores hunter profiles, equipment, and guilds.
- **Shadows Database (`ShadowsDB`)**: Operates on `SHADOWS_CHANNEL_ID` (falls back to `DATA_CHANNEL_ID` if unset). Stores the character catalog, spawn history, and user shadow armies.
- **In-Memory Caching & Concurrency**: Startup loads indexes into memory for instant synchronous reads. Writes flush asynchronously. Per-entity `asyncio.Lock` protects concurrent operations against race conditions.

### 2. Dimensional Rift & Shadow Spawning (`handlers/arise.py`)
- **Group Message Tracking**: In-memory message counter across group chats triggers an automated spawn every 250 messages (`SHADOW_SPAWN_MESSAGE_THRESHOLD = 250`).
- **Entity Spawning**: Selects a character via weighted random rarity roll, dispatches the anime image to the group with clean Telegram HTML captions.
- **Race-Condition Locked Claiming**: `_get_chat_lock(chat_id)` ensures atomic resolution when multiple hunters race with `/arise <name>`.
- **Fuzzy & Korean Alias Matching**: `match_character_name` matches case-insensitively, handles token subsets, and resolves aliases defined in the character catalog.

### 3. Streamlined Shadow Army UI (`/shadows`)
- **Atmospheric Visual Card (`game/shadows_image.py`)**: 920 × 640 px card on a dark velvet purple ground with 3 crystal-clear stats (`TOTAL SOLDIERS`, `UNIQUE FORMS`, `PAGE`), high-contrast soldier cards (`×3`), and zero military jargon clutter.
- **Instant Telegram HTML Caption**: Current page shadows are directly listed in text with rarity emojis and counts.
- **Single-Row Inline Navigation**: `[ ◀ Prev ] [ Page X/Y ] [ Next ▶ ]` (omitted when collection fits on 1 page).

### 4. Hallmark Anti-Slop Visual Standards
- Universal font cascade in `game/font_manager.py` resolves Windows, Linux, and macOS fonts with safe glyph fallbacks (Fraktur, Hangul, CJK, Emoji).
- Pure high-contrast typography tokens from `game/design_tokens.py`.
- Native geometric vector icons (Diamond, Crown, Skull, Lightning, Coin, Shield) prevent tofu boxes (`□`).

---

## Superadmin Directives
Bot superadmins (configured in `SUPERADMIN_IDS`) have access to management commands:
- `/addshadow <rarity> <name> [| aliases]` — Register a new character (attach photo or reply to image).
- `/delshadow <id>` — Delete a character from the catalog.
- `/listshadows [page]` — View all registered shadow characters.
- `/spawnshadow [character_id]` — Instantly force-spawn a shadow entity in the current chat.
- `/shadowstats` — View global catalog counts, spawns, and extraction statistics.
