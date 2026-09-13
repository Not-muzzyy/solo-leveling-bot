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
/equip
   ↓
Become Stronger
   ↓
/hunt again
```

---

## Future Expansion

Once the MVP works, expand the system with:

### Combat

- `/battle`
- `/boss`
- `/arena`
- `/duel`

### Dungeons

- `/gate`
- `/dungeon`
- `/raid`
- `/party`

### Multiplayer

- Party-based dungeon runs
- Cooperative bosses
- Player vs Player combat
- Player killing
- Looting defeated Hunters
- Bounties
- Revenge system

### Social

- `/leaderboard`
- `/inspect @user`
- `/guild`
- `/guildwar`
- `/wanted`

### Endgame

- Shadow system
- Hunter awakening
- Monarch progression
- World bosses
- Legendary quests
- Seasonal rankings

---

## Design Goal

The bot should not feel like a collection of commands.

It should feel like a **living Hunter System inside Telegram**, where players can:

**Progress → Flex → Compete → Cooperate → Betray → Dominate**