# CLAUDE.md — Project Context for AI Agents

## Project Overview

**Solo Leveling Hunter RPG Bot** — A Telegram group-based RPG bot inspired by Solo Leveling's Hunter System. Players become Hunters, fight monsters, collect gear, level up, and compete.

- **Language**: Python 3.11+
- **Framework**: `python-telegram-bot` v22.8 (fully async, `ApplicationBuilder` pattern)
- **Database**: **Telegram Channel** — a private channel stores all game data as JSON messages (no SQLite/Postgres)
- **Config**: `python-dotenv` loading `.env` (contains `BOT_TOKEN` and `DATA_CHANNEL_ID`)

## Project Structure

```
solo-leveling-bot/
├── .env                     # BOT_TOKEN + DATA_CHANNEL_ID (secrets, gitignored)
├── .gitignore
├── requirements.txt         # python-telegram-bot==22.8, python-dotenv, Pillow>=10.0.0
├── idea.md                  # Original game design document
├── main.py                  # Entry point — registers handlers, initializes DB, runs polling
├── config.py                # All game constants: ranks, rarities, XP curve, cooldowns, item/monster name parts
├── models.py                # Dataclasses: Hunter, Item, Inventory, Monster, HuntResult (all have to_json/from_json)
├── channel_db.py            # ChannelDB class — Telegram channel as persistent storage with in-memory cache
├── game/
│   ├── __init__.py
│   ├── hunter.py            # create_new_hunter(), add_xp(), check_rank_up()
│   ├── combat.py            # generate_monster(), simulate_hunt() → HuntResult
│   ├── items.py             # generate_loot(), create_starter_weapon(), rarity rolls
│   ├── shop.py              # 21 purchasable items across 5 categories, get_shop_item(), create_item_from_shop()
│   ├── profile_image.py     # Pillow renderer — Solo Leveling themed System Status Window image
│   └── formatting.py        # All Telegram message formatting (hunt results, inventory, equip, fallback profile, etc.)
└── handlers/
    ├── __init__.py
    ├── start.py             # /start — create new hunter + starter weapon
    ├── profile.py           # /profile — image-based status card via reply_photo (with text fallback)
    ├── hunt.py              # /hunt — fight monster, 15min cooldown, XP/gold/loot
    ├── inventory.py         # /inventory — browse items by category tabs + 🛒 Shop (buy with gold)
    ├── equip.py             # /equip — equip gear via inline buttons, shows stat diff
    ├── claim.py             # /claim — daily reward (24h cooldown), level-scaled XP+Gold
    └── help.py              # /help — command list + how to play guide
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

### Handler Pattern

All handlers follow this pattern (python-telegram-bot v22.x):
```python
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: ChannelDB = context.bot_data["db"]   # Access DB from bot_data
    hunter = await db.get_hunter(user.id)     # Read from cache
    # ... game logic ...
    await db.save_all(user.id)                # Flush to channel
    await update.message.reply_text(result)   # Send response
```

### Inline Keyboards & Callbacks

- Inventory tabs: `CallbackQueryHandler` with pattern `^inv_` for category switching
- Shop navigation: `CallbackQueryHandler` with pattern `^shop_` for shop categories
- Buy items: `CallbackQueryHandler` with pattern `^buy_` for purchases
- Equip items: `CallbackQueryHandler` with pattern `^equip_` for equipment changes

Callbacks are registered in `main.py` and routed to handler functions.

### Cooldown System

- `/hunt`: 15-minute cooldown — tracked in-memory via `dict[user_id, float]` in `handlers/hunt.py`
- `/claim`: 24-hour cooldown — tracked in-memory via `dict[user_id, float]` in `handlers/claim.py`
- Cooldowns reset on bot restart (in-memory only, not persisted)

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
21 items in `game/shop.py` — weapons, armor, accessories, consumables, materials.
Prices range from 15💰 (iron ore) to 5000💰 (Dragon's Fang). Accessible via 🛒 tab in `/inventory`.

## Key Technical Notes

- **All handlers are async** — `python-telegram-bot` v22.x requires `async def` handlers
- **Message formatting uses plain Unicode** — NOT MarkdownV2. This avoids escaping issues with special characters
- **ChannelDB.initialize()** runs in `post_init` callback of `ApplicationBuilder` — loads all data before bot starts polling
- **The `Inventory` class** manages item IDs internally via `_next_id` counter
- **Hunter stats** use `str_stat` and `int_stat` to avoid shadowing Python builtins `str` and `int`
- **`/profile` renders an image** — `game/profile_image.py` renders an 860x1180 PNG Status Window using Pillow (including user's Telegram PFP avatar with rank-colored ring and First+Last name), executed via `asyncio.to_thread()`, sent via `reply_photo` with text fallback
- **`.env` contains real credentials** — never commit, always gitignored

## Known Issues / TODOs

- Cooldowns are in-memory only — they reset when the bot restarts
- No error handling for Telegram API rate limits during heavy concurrent usage
- The startup loading uses `forward_message` to read channel messages (creates temp copies then deletes them) — could be optimized
- No `/leaderboard`, `/battle`, `/duel`, `/guild` yet — see `idea.md` "Future Expansion" section
- Consumables can be bought in the shop but there's no `/use` command to consume them yet
- No item selling/discard mechanism
