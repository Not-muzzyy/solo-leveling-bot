# ⚔️ Solo Leveling Hunter RPG Bot

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![kurigram](https://img.shields.io/badge/kurigram-v2.2.25+-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://github.com/Mayuri-Chan/kurigram)
[![Pillow](https://img.shields.io/badge/Pillow-Graphics-FF6F00?style=for-the-badge)](https://python-pillow.org)
[![License](https://img.shields.io/badge/License-MIT-green.style=for-the-badge)](LICENSE)

An immersive, high-performance Telegram RPG bot inspired by the **Solo Leveling** Hunter System. Awaken as a Hunter, challenge menacing Gate dungeons, collect rare weapons, gear up with glowing dimensional equipment, and climb from E-Rank to the legendary rank of **Shadow Monarch**.

---

## ✨ Features

### 👤 System Status Window (`/profile`)
- **High-Resolution Visual Status Card (`860 × 1180` px)** rendered dynamically via Pillow.
- Displays the player's **real Telegram avatar (PFP)** encased in an illuminated rank-colored neon ring.
- First and last name branding, hunter title, and current level.
- Live progress bars for **HP** and **EXP**, detailed 5-stat ability matrix (STR, AGI, VIT, INT, PER), equipped gear summaries, and win-rate statistics.

### 🗡️ Visual Combat Resolution (`/hunt`)
- **High-Definition 16:9 Combat Banner (`800 × 450` px)** engineered specifically for mobile Telegram screens.
- **Dynamic Victory & Defeat Layouts**:
  - **Left Side**: Gate monster target card with HP bar, rank badge, level, and engaged Hunter combat stats.
  - **Right Side**: Comprehensive combat resolution displaying damage dealt, critical hits, damage taken, experience bounty, gold reward, rare loot drops, level-ups, or tactical system briefings upon defeat.
- **Pristine PNG Rendering**: Instant delivery with zero compression blur, rich 24-bit color fidelity, and razor-sharp typography.

### 🎒 Image-Based Dimensional Storage (`/inventory`)
- **High-Resolution Visual Inventory Card (`860 × 1060` px)**:
  - **Custom Vector Equipment Artwork**: Luminous swords, assassin daggers, reinforced heater shields, gem rings, alchemy flasks, and mana crystals.
  - **Active Loadout Showcase**: Real-time display of equipped Weapon, Armor, and Accessory with rarity borders.
  - **Category Storage Matrix**: Displays items in the active category with stat badges, rarity tiers, and glowing status tags (`• EQUIPPED •` / `IN STORAGE`).
- **1-Tap Inline Equipping**: Unequipped items have dedicated equip buttons in the keyboard. Tapping an item immediately mounts it into your loadout with live in-place image updates via `edit_message_media`!
- **Group Chat Protection**: Invoking `/inventory` in any group chat automatically provides an instant deep-link button (`[🎒 Open Inventory in Bot PM]`) to protect private gear details and prevent chat clutter.

### 🛒 Visual System Exchange Depot (`/shop`)
- **High-Resolution Visual Shop Card (`860 × 1060` px)** rendered dynamically with custom vector art.
- **5 Full Exchange Departments**: Weapons, Armor, Accessories, Consumables, and Materials.
- **Dynamic Real-Time Affordability**: Displays your Hunter Treasury vault, item stats, prices, and live affordability badges (`READY TO PURCHASE` vs. `NEED X G MORE`).
- **Live In-Place Purchases**: Tapping buy instantly executes transactions, deposits gear, and updates the image card in-place with real-time acquisition notices!
- **Group Chat Protection**: Deep-links to Bot PM (`t.me/<bot>?start=shop`) when invoked in groups to ensure secure transactions.

### 🏰 Hunter Guild System (`/guild`)
- **Create & Manage Guilds**: Establish your own Hunter Guild for a 500💰 investment.
- **Guild XP Bonus**: All guild members receive **+10% XP** on every hunt.
- **Visual Guild Card (`860 × 720` px)**: High-resolution guild roster with owner card, top 5 hunters, and remaining members.
- **Guild Leaderboard (`/guild top`)**: Top 10 guilds ranked by Total Power, Average Level, Total Gold, or Member Count — with interactive category tabs.
- **Guild Wars (`/guild war`)**: Challenge another guild to a 1v1 bracket war. Winner gets gold, XP, and war_score. Loser loses XP and war_score. Visual challenge, status, and result cards.
- **Full Guild Management**:
  - `/guild create <name>` — Create a guild (1 per user, max 15 members)
  - `/guild join <name>` — Join an existing guild
  - `/guild leave` — Leave your current guild
  - `/guild info` — View guild card with owner, top 5, and member roster
  - `/guild members` — List all guild members with stats
  - `/guild top` — Top 10 guilds leaderboard with category tabs
  - `/guild war <name>` — Challenge another guild to war (owner only)
  - `/guild kick` — Kick a member (owner only, reply to their message)
  - `/guild disband` — Delete your guild (owner only)
  - `/guild edit <desc>` — Edit guild description (owner only)

### 🏆 Visual System Leaderboard (`/leaderboard`)
- **High-Resolution Hall of Fame Card (`860 × 1140` px)** rendered dynamically via Pillow with Solo Leveling HUD aesthetics.
- **Strict Real-Name Privacy**: Displays players strictly using their **First Name and Last Name** (never exposing usernames or `@handles`).
- **Podium Styling & Elite Hierarchy**:
  - **#1 Champion**: Royal Gold Crown, glowing gold border, and gold score highlights.
  - **#2 Silver & #3 Bronze Medals**: Distinct metallic vector badges and stat cards.
  - **#4 to #10 Elite Hierarchy**: Sleek zebra-striped rows with rank badges and right-aligned metrics.
- **Personal Standing Tracker**: A dedicated cyan-bordered footer card displays the viewing hunter's real-time global rank, stats, and score.
- **Dynamic Category Tabs**: Switch instantly between **⚡ Combat Power**, **🏆 Hunter Level**, **💰 Treasury Wealth**, and **⚔️ Gate Victories** with live image updates in-place.

### ⚔️ Visual PvP Arena Duels (`/duel`)
- **Group-Exclusive Reply Challenges**: Issue an arena duel challenge by simply **replying** to any Hunter's message in a group with `/duel`.
- **Opponent Security Verification**: Generates an invitation card with interactive inline buttons: `[ ⚔️ Accept Duel ]` and `[ ❌ Decline ]`. Only the challenged hunter can accept or decline (unauthorized clicks trigger an instant alert).
- **High-Definition Combat Resolution Card (`920 × 580` px)**:
  - **Dual Fighter Panels**: Challenger (left) vs Opponent (right), each displaying circular player avatars (PFP) with illuminated rank rings, real First & Last names, Rank badges, Level, Combat Power, equipped gear, and live remaining HP bars.
  - **Central Clashing "VS" Emblem**: Glowing cyan energy beam with round counter.
  - **Prominent Outcome Banners**:
    - **👑 VICTORY • WON**: Glowing emerald/gold banner with spoils (+XP, +Gold, level-up celebration).
    - **💀 DEFEATED • LOST**: Glowing crimson banner with consolation combat training XP.
  - **Multi-Font Fallback & Native Vectors**: Universal font cascade ensures 0 tofu boxes (`□`) for any fancy Unicode characters, CJK scripts, or emojis.

### 💰 Daily Hunter Allowance (`/claim`)
- Claim daily rewards once every 24 hours.
- Rewards dynamically scale with the Hunter's level to accelerate progression.

### 🎁 Guild Gift System (`/gift`)
- **Gift Items**: Transfer any unequipped inventory item to a guildmate with `/gift item <id>` (reply to their message).
- **Gift Gold**: Send gold directly to a guildmate with `/gift gold <amount>` (reply to their message).
- **Guild-Only**: Both sender and receiver must be in the same guild.
- **No Limits**: Gift as many items and as much gold as you want — trust your guild!

### 🗄️ Serverless Telegram Channel Database (`ChannelDB`)
- No external SQLite, PostgreSQL, or MongoDB server required.
- All player data, inventories, and guilds persist safely in a **private Telegram channel** as JSON message payloads.
- High-speed in-memory caching with per-user asynchronous locks prevents race conditions while maintaining sub-millisecond read times.

---

## 🎮 Command Reference

| Command | Scope | Description |
| :--- | :---: | :--- |
| `/start` | PM & Groups | Awaken as a new Hunter & claim starter weapon |
| `/profile` | PM & Groups | View your high-resolution visual RPG Status Window |
| `/hunt` | PM & Groups | Slay gate monsters & earn loot via visual Combat Cards (15m cooldown) |
| `/inventory` | PM & Groups | Open visual Dimensional Storage with 1-tap equip & shop (redirects to PM in groups) |
| `/shop` | PM & Groups | Open visual Hunter Shop & Exchange Depot (redirects to PM in groups) |
| `/leaderboard` | PM & Groups | View visual System Hall of Fame with interactive category tabs |
| `/duel` | Groups (Reply) | Challenge another Hunter to a PvP Arena duel with visual resolution |
| `/claim` | PM & Groups | Claim daily Hunter allowance (scaled XP + Gold, 24h cooldown) |
| `/guild` | PM & Groups | Manage your Hunter Guild (create, join, top, info, etc.) |
| `/gift` | PM & Groups | Gift items or gold to guildmates (reply to their message) |
| `/help` | PM & Groups | Display the Hunter operational guide |

---

## 📈 Game Progression

### ⭐ Hunter Ranks (Ascending)
```
🅴 E-Rank ➜ 🅳 D-Rank ➜ 🅲 C-Rank ➜ 🅱️ B-Rank ➜ 🅰️ A-Rank
➜ ⭐ S-Rank ➜ 🌟 SS-Rank ➜ 💫 SSS-Rank ➜ 🔱 National Level ➜ 👑 Monarch
```

### 💎 Item Rarities & Drop Rates
```
⚪ Common (50%) ➜ 🟢 Uncommon (25%) ➜ 🔵 Rare (15%)
➜ 🟣 Epic (7%) ➜ 🟡 Legendary (2.5%) ➜ 🔴 Mythic (0.5%)
```

### 📊 Hunter Attributes
- **STR (Strength)**: Increases physical attack damage dealt during hunts.
- **AGI (Agility)**: Improves hit accuracy, dodge rate, and combat speed.
- **VIT (Vitality)**: Increases maximum health pool (HP) and physical defense.
- **INT (Intelligence)**: Boosts magical defense and special event outcomes.
- **PER (Perception)**: Enhances critical strike chance and loot discovery rates.

### 🏰 Guild Benefits
- **+10% XP Bonus**: All guild members receive a flat 10% XP boost on every hunt.
- **Max Members**: 15 hunters per guild.
- **Unique Names**: Each guild must have a unique name.

---

## 🚀 Installation & Setup

### 1. Prerequisites
- **Python 3.11+** installed on your system.
- A **Telegram Bot Token** from [@BotFather](https://t.me/BotFather).
- A **Telegram API ID & Hash** from [my.telegram.org](https://my.telegram.org) (required for kurigram userbot+bot mode).
- A **Private Telegram Channel** to serve as your database.

### 2. Clone Repository
```powershell
git clone https://github.com/your-username/solo-leveling-bot.git
cd solo-leveling-bot
```

### 3. Create Virtual Environment
```powershell
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```

Open `.env` and fill in your values:
```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
API_ID=12345678
API_HASH=your_api_hash_here
DATA_CHANNEL_ID=-1001234567890
```

> **How to get your credentials:**
> 1. **BOT_TOKEN**: Talk to [@BotFather](https://t.me/BotFather) on Telegram, create a bot with `/newbot`, and copy the token.
> 2. **API_ID & API_HASH**: Go to [my.telegram.org](https://my.telegram.org), create an application, and copy the API_ID and API_HASH.
> 3. **DATA_CHANNEL_ID**: Create a private Telegram channel, add your bot as an **Administrator** with permission to *Post Messages* and *Edit Messages*, then forward any message from the channel to [@userinfobot](https://t.me/userinfobot) to get the ID (must start with `-100`).

### 6. Run the Bot
```powershell
python main.py
```

---

## 📂 Project Architecture

```
solo-leveling-bot/
├── .env.example             # Configuration template
├── .gitignore               # Ignored files (secrets, cache, venvs)
├── requirements.txt         # Dependencies (kurigram, Pillow, python-dotenv)
├── main.py                  # Entry point — registers handlers, initializes DB
├── config.py                # Game balances: ranks, rarities, XP curves, shop items, guild settings
├── models.py                # Dataclasses: Hunter, Item, Inventory, Monster, HuntResult, Guild
├── channel_db.py            # Telegram channel database with in-memory caching
├── game/
│   ├── hunter.py            # Hunter creation, XP gain, level/rank up calculations
│   ├── combat.py            # Monster generation, combat damage formula, hunt simulation
│   ├── items.py             # Procedural loot generation & rarity weight tables
│   ├── shop.py              # Hunter shop items and purchasing logic
│   ├── profile_image.py     # Pillow renderer: High-res System Status Window
│   ├── hunt_image.py        # Pillow renderer: 16:9 Combat Cards (Victory & Defeat)
│   ├── hunt_gif.py          # Backward compatibility shim for hunt_image
│   ├── inventory_image.py   # Pillow renderer: Dimensional Storage image with equipment artwork
│   ├── shop_image.py        # Pillow renderer: High-res Hunter Shop image with vector catalogue
│   ├── guild_image.py       # Pillow renderer: Guild Card with owner, top 5, and roster
│   ├── guild_leaderboard_image.py # Pillow renderer: Guild Leaderboard HUD card
│   ├── guild_war_image.py   # Pillow renderer: War challenge, status, and result cards
│   ├── font_manager.py      # Universal Unicode font cascade for zero-tofu rendering
│   └── formatting.py        # Plain-text formatting with Unicode box-drawing
└── handlers/
    ├── start.py             # /start & deep-link router (inventory, shop, help)
    ├── profile.py           # /profile — photo status card
    ├── hunt.py              # /hunt — visual combat resolution card
    ├── inventory.py         # /inventory — image storage, 1-tap equip & shop
    ├── shop.py              # /shop — visual exchange depot image cards
    ├── leaderboard.py       # /leaderboard — visual Hall of Fame with category tabs
    ├── duel.py              # /duel — PvP arena with visual resolution card
    ├── guild.py             # /guild — create, join, leave, info, top, war, kick, disband, edit
    ├── guild_war.py         # /guild war — guild-vs-guild war system with visual cards
    ├── claim.py             # /claim — daily reward (24h cooldown)
    └── help.py              # /help — operational manual
```

---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE).
