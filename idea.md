# Telegram Hunter RPG — MVP Idea

## Concept

A Telegram group-based RPG inspired by the **Hunter System** concept from Solo Leveling.

Players become Hunters, level up, collect gear, fight monsters, enter dungeons, compete with other Hunters, and eventually form parties and guilds.

The game should feel like a **system existing inside the Telegram group**, with public actions that other players can see and react to.

---

## MVP — First 5 Commands

### `/start`

Create a new Hunter.

- Generate Hunter profile
- Assign starting Rank
- Give starting stats
- Give a basic weapon
- Give starting Gold
- Set Level 1

✅ **Implemented**

---

### `/profile`

Display the player's Hunter profile.

Show:

- Hunter name
- Level
- Rank
- Power
- XP
- Gold
- Basic stats
- Equipped weapon
- Titles

The profile should be visually impressive and suitable for showing off in groups.

✅ **Implemented** — High-resolution 860×1180 visual Status Card with PFP avatar, rank ring, stat bars, and equipment loadout.

---

### `/hunt`

Main progression command.

The player fights a randomly generated monster.

Possible results:

- Victory
- Defeat
- XP gained
- Gold gained
- Item drop
- Rare drop chance
- Critical attack
- Special event

Hunts should become progressively harder as the player levels up.

✅ **Implemented** — 16:9 Combat Banner (800×450 px) with Victory/Defeat layouts, monster card, damage stats, loot drops, and 60-second cooldown (20 hunts/day cap).

---

### `/inventory`

Display everything the Hunter owns.

Categories:

- Weapons
- Armor
- Accessories
- Consumables
- Materials
- Rare items

Items should have different rarities.

Example:

`Common → Uncommon → Rare → Epic → Legendary → Mythic`

✅ **Implemented** — 860×1060 visual Dimensional Storage Card with category tabs, 1-tap equip buttons, and shop deep-link. Group chats get PM redirect for security.

---

### `/equip`

Allow the Hunter to equip an item from their inventory.

Equipping gear should affect:

- Attack
- Defense
- HP
- Speed
- Overall Power

The command should immediately show the player's updated stats.

✅ **Implemented** — Integrated into `/inventory` via 1-tap inline equip buttons. No separate command needed.

---

## Core Gameplay Loop

```text
/start
   ↓
Create Hunter
   ↓
/hunt
   ↓
Gain XP + Gold + Loot
   ↓
/inventory
   ↓
/equip (via inventory buttons)
   ↓
Become Stronger
   ↓
/hunt again
```

✅ **Fully implemented**

---

## Future Expansion

Once the MVP works, expand the system with:

### Combat

- `/battle`
- `/boss`
- `/arena`
- `/duel`

✅ `/duel` **Implemented** — Group-exclusive PvP with visual 920×580 resolution card, accept/decline buttons, and HP bars.

### Dungeons

- `/gate`
- `/dungeon`
- `/raid`
- `/party`

❌ Not yet implemented

### Multiplayer

- Party-based dungeon runs
- Cooperative bosses
- Player vs Player combat
- Player killing
- Looting defeated Hunters
- Bounties
- Revenge system

❌ Not yet implemented

### Social

- `/leaderboard`
- `/inspect @user`
- `/guild`
- `/guildwar`
- `/wanted`

✅ `/leaderboard` **Implemented** — 860×1140 visual Hall of Fame with podium, category tabs (Power/Level/Wealth/Victories), and personal rank tracker.

✅ `/guild` **Implemented** — Full guild system: create, join, leave, info, members, kick, disband, edit. 860×720 visual guild card. +10% XP bonus for members. Max 15 members per guild.

### Endgame

- Shadow system
- Hunter awakening
- Monarch progression
- World bosses
- Legendary quests
- Seasonal rankings

❌ Not yet implemented

---

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: `kurigram` v2.2.25+ (Pyrogram fork, MTProto API, fully async, decorator pattern)
- **Database**: Telegram Channel (private channel stores all game data as JSON messages)
- **Graphics**: Pillow (high-res visual cards for all major commands)
- **Config**: `python-dotenv` loading `.env` (contains `BOT_TOKEN`, `API_ID`, `API_HASH`, and `DATA_CHANNEL_ID`)

---

## Design Goal

The bot should not feel like a collection of commands.

It should feel like a **living Hunter System inside Telegram**, where players can:

**Progress → Flex → Compete → Cooperate → Betray → Dominate**
