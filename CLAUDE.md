# CLAUDE.md — Project Context for AI Agents

## Project Overview

**Solo Leveling Hunter RPG Bot** — A Telegram group-based RPG bot inspired by Solo Leveling's Hunter System. Players become Hunters, fight monsters, collect gear, level up, and compete. A companion Telegram Mini App handles daily claims, shop purchases, and read-only guild browsing.

- **Languages**: Python 3.11+ for the bot/API; TypeScript for the Mini App frontend.
- **Frameworks**: `kurigram` v2.2.25+ for the bot, FastAPI for the Mini App API, React + Vite for the frontend.
- **Database**: **Telegram Channel** — private channels store all game data as JSON messages (no SQLite/Postgres). The Mini App API shares the bot's initialized `ChannelDB` in the same process.
- **Config**: `python-dotenv` loading `.env` (bot secrets, channel IDs, and optional `MINIAPP_*` API settings)

## Project Structure

```
solo-leveling-bot/
├── .env                     # BOT_TOKEN + API_ID + API_HASH + DATA_CHANNEL_ID (secrets, gitignored)
├── .gitignore
├── requirements.txt         # kurigram, python-dotenv, Pillow, FastAPI, Uvicorn
├── idea.md                  # Original game design document
├── main.py                  # Entry point — registers handlers, initializes DB, runs polling
├── miniapp_api.py           # Authenticated API served inside the bot process
├── config.py                # All game constants: ranks, rarities, XP curve, cooldowns, item/monster name parts
├── models.py                # Dataclasses: Hunter, Item, Inventory, Monster, HuntResult, Guild, ShadowCharacter, UserShadow
├── channel_db.py            # Primary ChannelDB class — Telegram channel as persistent storage with in-memory cache
├── shadows_db.py            # Dedicated ShadowsDB class — Telegram channel storage for shadow characters, spawns, user armies
├── game/
│   ├── __init__.py
│   ├── hunter.py            # create_new_hunter(), add_xp(), check_rank_up()
│   ├── combat.py            # generate_monster(), simulate_hunt() → HuntResult
│   ├── items.py             # generate_loot(), create_starter_weapon(), rarity rolls
│   ├── shop.py              # Shop catalogue, get_shop_item(), create_item_from_shop()
│   ├── economy.py           # Shared locked claim and shop purchase operations
│   ├── miniapp.py           # Mini App launch links used by bot commands
│   ├── font_manager.py      # Universal Unicode Font Cascade & Normalizer (Fraktur, Hangul, CJK, Emoji, zero tofu)
│   ├── design_tokens.py     # Hallmark design system tokens, atmospheric canvas, and vector shapes
│   ├── hunt_image.py        # Pillow renderer — 16:9 Combat Cards (Victory & Defeat) for /hunt
│   ├── hunt_gif.py          # Backward compatibility shim for hunt_image
│   ├── inventory_image.py   # Pillow renderer — High-res Dimensional Inventory image with equipment visuals
│   ├── shop_image.py        # Pillow renderer — High-res Hunter Shop image with vector catalogue & treasury
│   ├── shadows_image.py     # Pillow renderer — Clean Hallmark Shadow Army collection card with 3-stat bar
│   ├── leaderboard_image.py # Pillow renderer — High-res System Hall of Fame with real names & podium
│   ├── duel.py              # Pure combat simulation engine for PvP arena duels
│   ├── duel_image.py        # Pillow renderer — 920x580 High-def Duel Card with VS clash, WON/LOST banners
│   ├── formatting.py        # All Telegram message formatting (hunt results, inventory, equip, fallback profile, etc.)
├── handlers/
    ├── __init__.py
    ├── start.py             # /start — create new hunter + starter weapon (deep-links: inventory, shop, help)
    ├── profile.py           # /profile — image-based status card via reply_photo (with text fallback)
    ├── hunt.py              # /hunt — visual combat card (Victory/Defeat) via reply_photo (60s cooldown, 20/day cap)
    ├── inventory.py         # /inventory — browse items in PM, dynamic tabs, 1-tap gear equip, shop
    ├── shop.py              # /shop — visual Hunter Shop cards, 5 departments, in-place purchases
    ├── leaderboard.py       # /leaderboard — visual System Hall of Fame with interactive category tabs
    ├── duel.py              # /duel — group reply PvP duel challenge, accept/decline buttons, image resolution
    ├── arise.py             # /arise & /shadows — automated 250-msg spawns, name guessing, army browser, superadmin suite
    ├── guild.py             # /guild — create, join, leave, info, top, war, kick, disband, edit
    ├── guild_war.py         # /guild war — guild-vs-guild war system with visual cards
    ├── claim.py             # /claim — daily reward (24h cooldown), level-scaled XP+Gold
    └── help.py              # /help — command list + how to play guide
└── miniapp/                 # TypeScript + React + Vite static Telegram Mini App
    ├── src/App.tsx          # Claim, shop, and read-only guild directory
    ├── src/api/client.ts    # API client sending Telegram initData
    └── README.md            # Local run and deployment instructions
```

## Architecture

### Database: Telegram Channel as Storage

Instead of a traditional database, all data lives in a **private Telegram channel** as JSON messages:

- **Message #1** (pinned): INDEX — maps `user_id → {hunter_msg_id, inv_msg_id}`
- **Message #N**: Hunter JSON or Inventory JSON (one message per hunter, one per inventory)
- **Reads**: On startup, forward all messages to read text → populate in-memory cache
- **Writes**: `bot.edit_message_text()` to update existing messages
- **In-memory cache**: `ChannelDB._cache` dict holds all hunter/inventory data for instant reads
- **Per-user locks**: `asyncio.Lock` per user_id prevents race conditions
- **4096 char limit**: Hunter and inventory stored as separate messages to stay within Telegram's limit

### Telegram Mini App

- `miniapp/` is a TypeScript, React, and Vite frontend. Deploy this static directory to Vercel or GitHub Pages; keep the API with the bot.
- `miniapp_api.py` starts an opt-in FastAPI server from `main.py` after channel databases initialize. It shares the bot client and `ChannelDB` cache.
- The frontend sends `Telegram.WebApp.initData`. Validate its HMAC on the server with `BOT_TOKEN`; never trust `initDataUnsafe` for identity or expose the bot token in `VITE_*` variables.
- Claim and shop calls use `game/economy.py`, shared with bot handlers. Guild listing and detail are read-only; guild mutations stay in bot commands.
- With the API and `MINIAPP_BOT_USERNAME` configured, `/claim`, `/shop`, and `/guild info` open the corresponding Mini App section (named guilds open their detail record).
- Hunter and inventory records are separate Telegram messages, so a purchase cannot be fully transactional across both. Shared locks and compensating writes reduce failures but cannot cover a process interruption between messages.
- Local instructions are in `miniapp/README.md`. Authenticated Telegram use needs an HTTPS frontend URL and a reachable API origin allowed by `MINIAPP_ALLOWED_ORIGINS`.

### Handler Pattern

All handlers follow this pattern (kurigram / Pyrogram fork):
```python
async def handle(client: Client, message: Message) -> None:
    db: ChannelDB = client.db            # Access DB from client attribute
    hunter = await db.get_hunter(user.id) # Read from cache
    # ... game logic ...
    await db.save_all(user.id)            # Flush to channel
    await message.reply_text(result)      # Send response
```

### Inline Keyboards & Callbacks

- Inventory tabs: `on_callback_query` with `filters.regex(r"^inv_")` for category switching
- Shop navigation: `on_callback_query` with `filters.regex(r"^shop_")` for shop categories
- Buy items: `on_callback_query` with `filters.regex(r"^buy_")` for purchases
- Equip items: `on_callback_query` with `filters.regex(r"^equip_")` handled in `handlers/inventory.py` (1-tap gear binding with live stat diffs without leaving inventory)

Callbacks are registered in `main.py` and routed to handler functions.

### Cooldown System

- `/hunt`: 60-second cooldown + 20 hunts/day — persisted on Hunter (`last_hunt_time`, `daily_hunts`) with an in-memory fallback cache in `handlers/hunt.py`
- `/claim`: 24-hour cooldown — persisted on Hunter (`last_claim_time`) and applied through the shared economy service
- Cooldowns persist on the Hunter (`last_hunt_time`, `last_claim_time`) and survive restart
- Guild index may be sharded across `IndexPart` messages when pinned text exceeds 3900 chars (`INDEX_SOFT_LIMIT` in `channel_db.py`)

## Game Systems

### Ranks (ascending)
`E → D → C → B → A → S → SS → SSS → National Level → Monarch`
Rank thresholds defined in `config.RANK_LEVEL_THRESHOLDS`.

### Item Rarities (ascending)
`Common → Uncommon → Rare → Epic → Legendary → Mythic`
Drop weights: 50% / 25% / 15% / 7% / 2.5% / 0.5% — defined in `config.RARITY_WEIGHTS`.

### Stats
5 base stats: STR, AGI, VIT, INT, PER — start at 5–10, gain 1–3 per level-up.
Power = sum of all stats. Equipment adds bonus ATK/DEF/HP/SPD.

### Combat Formula
`damage = attacker_str * random(0.8, 1.2) - defender_def * 0.4`
10% crit chance (2x damage), 30% loot drop chance, 5% special event chance.

### Shop
The catalogue in `game/shop.py` covers weapons, armor, accessories, consumables, and materials.
Prices range from 15💰 (iron ore) to 5000💰 (Dragon's Fang). Accessible via 🛒 tab in `/inventory`.

## Key Technical Notes

- **All handlers are async** — kurigram requires `async def` handlers
- **Message formatting uses plain Unicode** — NOT MarkdownV2. This avoids escaping issues with special characters
- **ChannelDB.initialize()** runs in `on_start()` lifecycle hook — loads all data before bot starts polling
- **The `Inventory` class** manages item IDs internally via `_next_id` counter
- **Hunter stats** use `str_stat` and `int_stat` to avoid shadowing Python builtins `str` and `int`
- **`/profile` renders an image** — `game/profile_image.py` renders an 860x1180 PNG Status Window using Pillow (including user's Telegram PFP avatar with rank-colored ring and First+Last name), executed via `asyncio.to_thread()`, sent via `reply_photo` with text fallback
- **`/hunt` renders a visual Combat Card** — `game/hunt_image.py` renders a high-definition 16:9 banner Combat Card (800x450 px) using Pillow (two-column layout: monster target card left with HP bar, hunter status; outcome banner right showing Victory or Defeat, damage dealt/taken, EXP bounty, gold reward, loot drop, level/rank ups, or defeat tactical briefing). Rendered as pristine 24-bit PNG with zero compression blur or animation latency. Executed via `asyncio.to_thread()`, sent via `reply_photo` with text fallback.
- **`/inventory` renders a dynamic image card** — `game/inventory_image.py` renders an 860x1060 PNG Dimensional Storage Window showcasing active equipment loadout (weapon, armor, accessory) with glowing vector artwork, rarity auras, stat badges, and storage matrix items; tab switching and 1-tap equipping dynamically update the image in-place via `edit_message_media`! When invoked in a group or supergroup, sends a notification card with an `[🎒 Open Inventory in Bot PM]` deep-link button (`t.me/<bot>?start=inventory`).
- **`/shop` opens the Mini App when its API and bot username are configured**; otherwise, the existing `game/shop_image.py` visual shop card and group-to-PM flow remain available.
- **`/leaderboard` renders an interactive visual Hall of Fame card** — `game/leaderboard_image.py` renders an 860x1140 PNG System Leaderboard HUD card featuring podium highlights (#1 Gold Crown, #2 Silver, #3 Bronze), #4-#10 elite rankings, and a personal rank standing footer card. Strictly displays players' real First Name and Last Name (never @username). Inline keyboard tabs (`lb_power`, `lb_level`, `lb_wealth`, `lb_victories`) dynamically re-sort hunters and update the card in-place via `edit_message_media`.
- **`/duel` renders a high-definition PvP Arena card** — `game/duel_image.py` renders a 920x580 PNG Combat Resolution Card showing Challenger vs Opponent side-by-side with avatars, illuminated rank rings, combat breakdown, central glowing "VS" clash emblem, and prominent "VICTORY • WON" (emerald/gold) and "DEFEATED • LOST" (crimson) banners. Executed in group chats strictly by replying to another hunter's message.
- **Universal Font Cascade & Normalizer** — `game/font_manager.py` cleans fancy font generator Unicode (Fraktur, Script, Small Caps, Circled) and dynamically cascades glyphs across Windows global fonts (Korean Malgun Gothic / Batang, Japanese Meiryo / Yu Gothic, Chinese YaHei, Arial / Segoe UI, Segoe UI Symbol) to prevent missing glyph "tofu" boxes (`□`).
- **`.env` contains real credentials** — never commit, always gitignored

## Known Issues / TODOs

- No error handling for Telegram API rate limits during heavy concurrent usage
- The startup loading uses `forward_message` to read channel messages (creates temp copies then deletes them) — could be optimized
- Consumables can be bought in the shop but there's no `/use` command to consume them yet
- Telegram channel messages do not provide an atomic transaction across hunter and inventory records
- No item selling/discard mechanism
