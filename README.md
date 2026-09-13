# ⚔️ Solo Leveling Hunter RPG Bot

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![python-telegram-bot](https://img.shields.io/badge/PTB-v22.8-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://python-telegram-bot.org)
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

### 🗡️ Snappy Combat Animation (`/hunt`)
- **Compact 16:9 Banner Combat GIF (`640 × 360` px)** engineered specifically for mobile Telegram screens.
- **Two-Column Solo Leveling HUD**:
  - **Left Side**: Gate monster status card with animated HP bar, level, and Hunter combat power.
  - **Right Side**: Multi-stage combat sequence: Red Gate warning ➜ energy charge ➜ high-voltage laser slash ➜ critical impact burst ➜ victory/defeat rewards freeze.
- **Zero-Dither Adaptive Quantization**: Crisp, blur-free vector rendering at ~77 KB for instant mobile playback.

### 🎒 Image-Based Dimensional Storage (`/inventory`)
- **High-Resolution Visual Inventory Card (`860 × 1060` px)**:
  - **Custom Vector Equipment Artwork**: Luminous swords, assassin daggers, reinforced heater shields, gem rings, alchemy flasks, and mana crystals.
  - **Active Loadout Showcase**: Real-time display of equipped Weapon, Armor, and Accessory with rarity borders.
  - **Category Storage Matrix**: Displays items in the active category with stat badges, rarity tiers, and glowing status tags (`• EQUIPPED •` / `IN STORAGE`).
- **1-Tap Inline Equipping**: Unequipped items have dedicated equip buttons in the keyboard. Tapping an item immediately mounts it into your loadout with live in-place image updates via `edit_message_media`!
- **Group Chat Protection**: Invoking `/inventory` in any group chat automatically provides an instant deep-link button (`[🎒 Open Inventory in Bot PM]`) to protect private gear details and prevent chat clutter.

### 💰 Daily Hunter Allowance (`/claim`)
- Claim daily rewards once every 24 hours.
- Rewards dynamically scale with the Hunter's level to accelerate progression.

### 🗄️ Serverless Telegram Channel Database (`ChannelDB`)
- No external SQLite, PostgreSQL, or MongoDB server required.
- All player data and inventories persist safely in a **private Telegram channel** as JSON message payloads.
- High-speed in-memory caching with per-user asynchronous locks prevents race conditions while maintaining sub-millisecond read times.

---

## 🎮 Command Reference

| Command | Scope | Description |
| :--- | :---: | :--- |
| `/start` | PM & Groups | Awaken as a new Hunter & claim starter weapon |
| `/profile` | PM & Groups | View your high-resolution visual RPG Status Window |
| `/hunt` | PM & Groups | Slay gate monsters via animated GIF (15m cooldown) |
| `/inventory` | PM & Groups | Open visual Dimensional Storage with 1-tap equip & shop (redirects to PM in groups) |
| `/claim` | PM & Groups | Claim daily Hunter allowance (scaled XP + Gold, 24h cooldown) |
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

---

## 🚀 Installation & Setup

### 1. Prerequisites
- **Python 3.11+** installed on your system.
- A **Telegram Bot Token** from [@BotFather](https://t.me/BotFather).
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
DATA_CHANNEL_ID=-1001234567890
```

> **How to get your `DATA_CHANNEL_ID`:**
> 1. Create a private Telegram channel (e.g., `Hunter Database`).
> 2. Add your bot into the channel as an **Administrator** with permission to *Post Messages* and *Edit Messages*.
> 3. Forward any message from the channel to [@userinfobot](https://t.me/userinfobot) to get the ID (must start with `-100`).

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
├── requirements.txt         # Dependencies (python-telegram-bot, Pillow, python-dotenv)
├── main.py                  # Entry point — registers handlers, initializes DB
├── config.py                # Game balances: ranks, rarities, XP curves, shop items
├── models.py                # Dataclasses: Hunter, Item, Inventory, Monster, HuntResult
├── channel_db.py            # Telegram channel database with in-memory caching
├── game/
│   ├── hunter.py            # Hunter creation, XP gain, level/rank up calculations
│   ├── combat.py            # Monster generation, combat damage formula, hunt simulation
│   ├── items.py             # Procedural loot generation & rarity weight tables
│   ├── shop.py              # Hunter shop items and purchasing logic
│   ├── profile_image.py     # Pillow renderer: High-res System Status Window
│   ├── hunt_gif.py          # Pillow renderer: 16:9 Banner Combat GIF sequence
│   ├── inventory_image.py   # Pillow renderer: Dimensional Storage image with equipment artwork
│   └── formatting.py        # Plain-text formatting with Unicode box-drawing
└── handlers/
    ├── start.py             # /start & /start inventory deep-link router
    ├── profile.py           # /profile — photo status card
    ├── hunt.py              # /hunt — animated combat GIF
    ├── inventory.py         # /inventory — image storage, 1-tap equip & shop
    ├── equip.py             # Backward-compatible redirect to inventory
    ├── claim.py             # /claim — daily reward (24h cooldown)
    └── help.py              # /help — operational manual
```

---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE).
