"""
game/formatting.py — Rich Telegram message formatting.

Uses plain text with Unicode symbols (not MarkdownV2) to avoid
escaping headaches. Telegram supports Unicode box-drawing, bars, and emoji natively.
"""

from __future__ import annotations

from config import RARITY_EMOJI, RANK_EMOJI
from models import Hunter, Item, HuntResult, Inventory


def _stat_bar(value: int, max_val: int = 50) -> str:
    """Create a visual stat bar using block characters."""
    filled = min(10, max(0, int((value / max_val) * 10)))
    empty = 10 - filled
    return "▰" * filled + "▱" * empty


def _progress_bar(current: int, maximum: int, length: int = 16) -> str:
    """Create a smooth progress bar with percentage."""
    ratio = min(1.0, current / maximum) if maximum > 0 else 0
    filled = int(ratio * length)
    empty = length - filled
    bar = "█" * filled + "░" * empty
    pct = int(ratio * 100)
    return f"{bar} {pct}%"


def _hp_bar(current: int, maximum: int) -> str:
    """HP bar with color-coded emoji based on health percentage."""
    ratio = current / maximum if maximum > 0 else 0
    if ratio > 0.6:
        icon = "💚"
    elif ratio > 0.3:
        icon = "💛"
    else:
        icon = "❤️"
    return f"{icon} {current}/{maximum}  {_progress_bar(current, maximum, 12)}"


def _rank_badge(rank: str) -> str:
    """Create a decorative rank badge."""
    rank_icon = RANK_EMOJI.get(rank, "❓")
    badges = {
        "E":              f"┃  {rank_icon} 「 E-Rank Hunter 」",
        "D":              f"┃  {rank_icon} 「 D-Rank Hunter 」",
        "C":              f"┃  {rank_icon} 「 C-Rank Hunter 」",
        "B":              f"┃  {rank_icon} 「 B-Rank Hunter 」",
        "A":              f"┃  {rank_icon} 「 A-Rank Hunter 」",
        "S":              f"┃  {rank_icon} 「 S-Rank Hunter 」",
        "SS":             f"┃  {rank_icon} 「 SS-Rank Hunter 」",
        "SSS":            f"┃  {rank_icon} 「 SSS-Rank Hunter 」",
        "National Level": f"┃  {rank_icon} 「 National Level Hunter 」",
        "Monarch":        f"┃  {rank_icon} 「 Monarch 」",
    }
    return badges.get(rank, f"┃  {rank_icon} 「 {rank}-Rank 」")


def _format_equip_line(label: str, icon: str, item) -> str:
    """Format a single equipment slot line."""
    if item:
        rarity_icon = RARITY_EMOJI.get(item.rarity, "")
        stats = item.stat_summary()
        return f"┃  {icon} {item.name} {rarity_icon}\n┃     └ {stats}"
    return f"┃  {icon} — empty —"


def format_profile(hunter: Hunter, inventory: Inventory) -> str:
    """Format a hunter's profile card for display."""

    # Get equipped items
    weapon = inventory.get_equipped("weapon")
    armor = inventory.get_equipped("armor")
    accessory = inventory.get_equipped("accessory")

    # Calculate equipment power bonus
    equip_atk = sum(i.atk_bonus for i in [weapon, armor, accessory] if i)
    equip_def = sum(i.def_bonus for i in [weapon, armor, accessory] if i)
    equip_hp = sum(i.hp_bonus for i in [weapon, armor, accessory] if i)
    equip_spd = sum(i.spd_bonus for i in [weapon, armor, accessory] if i)
    total_equip = equip_atk + equip_def + equip_hp + equip_spd

    # Win rate
    win_rate = "—"
    if hunter.total_hunts > 0:
        wr = (hunter.victories / hunter.total_hunts) * 100
        win_rate = f"{wr:.0f}%"

    # Total items count
    total_items = len(inventory.items)

    lines = [
        "╔══════════════════════════╗",
        "║    ⚔️  H U N T E R  ⚔️    ║",
        "║      S Y S T E M        ║",
        "╚══════════════════════════╝",
        "",
        f"┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓",
        f"┃  👤 {hunter.hunter_name}",
        f"┃  🏅 {hunter.title}",
        _rank_badge(hunter.rank),
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛",
        "",
        f"  📊 Level {hunter.level}   ┊   💪 Power {hunter.power} (+{total_equip})",
        "",
        f"  ✨ XP   {_progress_bar(hunter.xp, hunter.xp_needed)}",
        f"          {hunter.xp} / {hunter.xp_needed}",
        "",
        f"  {_hp_bar(hunter.hp, hunter.max_hp)}",
        "",
        "┌─── 📈 STATS ─────────────────┐",
        f"│ STR  {hunter.str_stat:>3}  {_stat_bar(hunter.str_stat)}  │",
        f"│ AGI  {hunter.agi:>3}  {_stat_bar(hunter.agi)}  │",
        f"│ VIT  {hunter.vit:>3}  {_stat_bar(hunter.vit)}  │",
        f"│ INT  {hunter.int_stat:>3}  {_stat_bar(hunter.int_stat)}  │",
        f"│ PER  {hunter.per:>3}  {_stat_bar(hunter.per)}  │",
        "└──────────────────────────────┘",
        "",
        "┌─── ⚔️ EQUIPMENT ────────────┐",
        _format_equip_line("Weapon", "🗡️", weapon),
        _format_equip_line("Armor", "🛡️", armor),
        _format_equip_line("Accessory", "💍", accessory),
        "└──────────────────────────────┘",
        "",
        "┌─── 📋 SUMMARY ──────────────┐",
        f"│ 💰 Gold: {hunter.gold:>10}          │",
        f"│ 🎒 Items: {total_items:>9}          │",
        f"│ 🗡️ Hunts: {hunter.total_hunts:>9}          │",
        f"│ 📈 Win Rate: {win_rate:>7}          │",
        f"│ ✅ Wins: {hunter.victories:>4}  💀 Losses: {hunter.defeats:>4} │",
        "└──────────────────────────────┘",
        "",
        "「 The System sees all, Hunter. 」",
    ]

    return "\n".join(lines)


def format_welcome(hunter: Hunter) -> str:
    """Format the dramatic welcome message for a new hunter."""
    return (
        f"⚡ SYSTEM NOTIFICATION ⚡\n"
        f"\n"
        f"A new Hunter has been detected.\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 Hunter: {hunter.hunter_name}\n"
        f"⭐ Rank: {hunter.rank}\n"
        f"💪 Power: {hunter.power}\n"
        f"\n"
        f"📈 Starting Stats:\n"
        f"├ STR: {hunter.str_stat}\n"
        f"├ AGI: {hunter.agi}\n"
        f"├ VIT: {hunter.vit}\n"
        f"├ INT: {hunter.int_stat}\n"
        f"└ PER: {hunter.per}\n"
        f"\n"
        f"⚔️ Weapon: Rusty Short Sword ⚪\n"
        f"💰 Gold: {hunter.gold}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"「 The System has acknowledged you. 」\n"
        f"\n"
        f"Your journey begins now, Hunter.\n"
        f"Use /hunt to slay your first monster."
    )


def format_hunt_victory(result: HuntResult) -> str:
    """Format a victorious hunt result."""
    monster = result.monster
    rank_icon = RANK_EMOJI.get(monster.rank, "")

    crit_text = " 💥 CRITICAL!" if result.critical_hit else ""

    lines = [
        f"🗡️ HUNT INITIATED",
        f"",
        f"You encountered a「{monster.name}」(Lv.{monster.level}) {rank_icon}",
        f"",
        f"⚔️ Battle Result: ✅ VICTORY",
        f"",
        f"💥 Damage dealt: {result.damage_dealt}{crit_text}",
        f"💔 Damage taken: {result.damage_taken}",
        f"",
        f"━━━ REWARDS ━━━",
        f"✨ XP: +{result.xp_gained}",
        f"💰 Gold: +{result.gold_gained}",
    ]

    if result.item_drop:
        rarity_icon = RARITY_EMOJI.get(result.item_drop.rarity, "")
        stats = result.item_drop.stat_summary()
        lines.append(f"🎁 DROP: {result.item_drop.name} {rarity_icon} ({stats})")

    if result.leveled_up:
        lines.append(f"")
        lines.append(f"⚡ LEVEL UP! → Level {result.new_level}")

    if result.ranked_up:
        new_rank_icon = RANK_EMOJI.get(result.new_rank, "")
        lines.append(f"🔥 RANK UP! → {result.new_rank} {new_rank_icon}")

    if result.special_event:
        lines.append(f"")
        lines.append(result.special_event)

    return "\n".join(lines)


def format_hunt_defeat(result: HuntResult) -> str:
    """Format a hunt defeat result."""
    monster = result.monster
    rank_icon = RANK_EMOJI.get(monster.rank, "")

    lines = [
        f"🗡️ HUNT INITIATED",
        f"",
        f"You encountered a「{monster.name}」(Lv.{monster.level}) {rank_icon}",
        f"",
        f"⚔️ Battle Result: ☠️ DEFEAT",
        f"",
        f"💥 Damage dealt: {result.damage_dealt}",
        f"💔 Damage taken: {result.damage_taken}",
        f"",
        f"━━━ PENALTIES ━━━",
        f"💸 Gold lost: -{result.gold_lost}",
        f"✨ XP gained: +{result.xp_gained} (consolation)",
        f"",
        f"Recover and try again, Hunter.",
    ]

    if result.special_event:
        lines.append(f"")
        lines.append(result.special_event)

    return "\n".join(lines)


def format_hunt_result(result: HuntResult) -> str:
    """Format a hunt result (routes to victory or defeat)."""
    if result.victory:
        return format_hunt_victory(result)
    return format_hunt_defeat(result)


def format_inventory(
    inventory: Inventory,
    hunter_or_cat: Hunter | str | None = None,
    category: str = "weapon",
    notice: str | None = None,
) -> str:
    """Format a polished, Solo Leveling themed Dimensional Inventory window."""
    if isinstance(hunter_or_cat, str):
        cat = hunter_or_cat
        hunter = None
    else:
        hunter = hunter_or_cat
        cat = category

    TYPE_LABELS = {
        "weapon": ("⚔️", "Weapons"),
        "armor": ("🛡️", "Armor"),
        "accessory": ("💍", "Accessories"),
        "consumable": ("🧪", "Consumables"),
        "material": ("📦", "Materials"),
    }

    icon, name = TYPE_LABELS.get(cat, ("🎒", cat.title()))
    items = inventory.get_by_type(cat)
    total_items = len(inventory.items)

    lines = [
        "╔══════════════════════════════╗",
        "║   🎒 DIMENSIONAL INVENTORY   ║",
        "║     System Storage Matrix    ║",
        "╚══════════════════════════════╝",
    ]

    if hunter:
        lines.extend([
            f"👤 Hunter: {hunter.hunter_name} ┊ 🏅 Rank {hunter.rank}",
            f"💰 Gold: {hunter.gold:,} G ┊ 📦 Capacity: {total_items} items",
            "",
        ])
    else:
        lines.extend([
            f"📦 Stored Items: {total_items}",
            "",
        ])

    if notice:
        lines.extend([
            notice,
            "",
        ])

    lines.extend([
        f"┏━━ {icon} CATEGORY: {name.upper()} ({len(items)}) ━━┓",
        "",
    ])

    if not items:
        lines.extend([
            "  「 Dimensional pocket empty. 」",
            "  Defeat monsters via /hunt or browse",
            "  the 🛒 Shop to collect gear & items!",
            "",
        ])
    else:
        for i, item in enumerate(items, 1):
            rarity_icon = RARITY_EMOJI.get(item.rarity, "⚪")
            status_tag = "⚡ [EQUIPPED]" if item.is_equipped else "📦 [IN STORAGE]"
            stats = item.stat_summary()

            lines.append(f" {i}. {rarity_icon} {item.name} [{item.rarity}]")
            lines.append(f"    ├ Status: {status_tag}")
            lines.append(f"    └ Stats:  {stats}")
            lines.append("")

    lines.extend([
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛",
        "💡 Quick Actions:",
        "• Tap tabs to switch categories",
        "• Tap ⚡ Equip buttons below to bind gear",
        "• Tap 🛒 Hunter Shop to buy new items",
    ])

    return "\n".join(lines)


def format_equip_result(item: Item, old_item: Item | None, hunter: Hunter) -> str:
    """Format equipment change result with stat diff."""
    rarity_icon = RARITY_EMOJI.get(item.rarity, "")

    lines = [
        f"⚔️ EQUIPMENT CHANGED",
        f"",
        f"Equipped: {item.name} {rarity_icon}",
        f"",
        f"📊 Stat Changes:",
    ]

    if old_item:
        atk_diff = item.atk_bonus - old_item.atk_bonus
        def_diff = item.def_bonus - old_item.def_bonus
        hp_diff = item.hp_bonus - old_item.hp_bonus
        spd_diff = item.spd_bonus - old_item.spd_bonus

        for stat_name, diff, old_val, new_val in [
            ("ATK", atk_diff, old_item.atk_bonus, item.atk_bonus),
            ("DEF", def_diff, old_item.def_bonus, item.def_bonus),
            ("HP", hp_diff, old_item.hp_bonus, item.hp_bonus),
            ("SPD", spd_diff, old_item.spd_bonus, item.spd_bonus),
        ]:
            if diff != 0:
                arrow = "⬆️" if diff > 0 else "⬇️"
                sign = "+" if diff > 0 else ""
                lines.append(f"  {stat_name}: {old_val} → {new_val} ({sign}{diff}) {arrow}")

        if all(d == 0 for d in [atk_diff, def_diff, hp_diff, spd_diff]):
            lines.append("  No stat changes.")
    else:
        lines.append(f"  ATK: 0 → {item.atk_bonus} (+{item.atk_bonus}) ⬆️" if item.atk_bonus else "")
        lines.append(f"  DEF: 0 → {item.def_bonus} (+{item.def_bonus}) ⬆️" if item.def_bonus else "")
        lines.append(f"  HP: 0 → {item.hp_bonus} (+{item.hp_bonus}) ⬆️" if item.hp_bonus else "")
        lines.append(f"  SPD: 0 → {item.spd_bonus} (+{item.spd_bonus}) ⬆️" if item.spd_bonus else "")

    # Filter empty lines from conditional appends
    lines = [l for l in lines if l is not None and l != ""]

    lines.append(f"")
    lines.append(f"💪 Power: {hunter.power}")

    return "\n".join(lines)


def format_cooldown(remaining_seconds: int) -> str:
    """Format cooldown remaining message."""
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60
    return (
        f"⏳ You are still recovering from your last hunt.\n"
        f"\n"
        f"⏱️ Ready in: {minutes}m {seconds:02d}s"
    )


def format_already_registered(hunter: Hunter) -> str:
    """Message when a user tries to /start again."""
    return (
        f"⚠️ You are already a registered Hunter!\n"
        f"\n"
        f"👤 {hunter.hunter_name} — Rank {hunter.rank}, Level {hunter.level}\n"
        f"\n"
        f"Use /profile to view your stats.\n"
        f"Use /hunt to slay monsters."
    )


def format_not_registered() -> str:
    """Message when unregistered user tries a command."""
    return (
        f"❌ You are not a registered Hunter yet.\n"
        f"\n"
        f"Use /start to awaken as a Hunter!"
    )
