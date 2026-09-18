"""
game/formatting.py — Rich Telegram message formatting.

Uses plain text with Unicode symbols (not MarkdownV2) to avoid
escaping headaches. Telegram supports Unicode box-drawing, bars, and emoji natively.
"""

from __future__ import annotations

from config import RARITY_EMOJI, RANK_EMOJI
from models import Hunter, Item, HuntResult, Inventory
from game.rich_text import escape_html, bold, italic, code, blockquote, system_lore, pre


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
    """Format a hunter's profile card for display with rich HTML."""

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
    h_name = escape_html(hunter.hunter_name)
    title_esc = escape_html(hunter.title)
    rank_icon = RANK_EMOJI.get(hunter.rank, "❓")

    def _equip_html(icon: str, item: Item | None) -> str:
        if item:
            r_icon = RARITY_EMOJI.get(item.rarity, "")
            return f"• {icon} <b>{escape_html(item.name)}</b> {r_icon} (<code>{escape_html(item.stat_summary())}</code>)"
        return f"• {icon} <i>— empty —</i>"

    lines = [
        "<b>╭━━━「 ⚔️ HUNTER STATUS MATRIX 」━━━╮</b>",
        "",
        f"👤 <b>Hunter:</b> {h_name} [Rank <b>{hunter.rank}</b> {rank_icon}]",
        f"🏅 <b>Title:</b> <i>{title_esc}</i>",
        f"📊 <b>Level:</b> <code>{hunter.level}</code> ┊ 💪 <b>Power:</b> <code>{hunter.power:,}</code> (<code>+{total_equip}</code>)",
        f"✨ <b>XP:</b> <code>{hunter.xp}/{hunter.xp_needed}</code>  {_progress_bar(hunter.xp, hunter.xp_needed)}",
        f"❤️ <b>Vitality:</b> {_hp_bar(hunter.hp, hunter.max_hp)}",
        "",
        "<blockquote>",
        "📈 <b>Core Attributes:</b>",
        f"• STR: <code>{hunter.str_stat:>3}</code>  {_stat_bar(hunter.str_stat)}",
        f"• AGI: <code>{hunter.agi:>3}</code>  {_stat_bar(hunter.agi)}",
        f"• VIT: <code>{hunter.vit:>3}</code>  {_stat_bar(hunter.vit)}",
        f"• INT: <code>{hunter.int_stat:>3}</code>  {_stat_bar(hunter.int_stat)}",
        f"• PER: <code>{hunter.per:>3}</code>  {_stat_bar(hunter.per)}",
        "",
        "⚔️ <b>Equipped Loadout:</b>",
        _equip_html("🗡️", weapon),
        _equip_html("🛡️", armor),
        _equip_html("💍", accessory),
        "</blockquote>",
        "",
        "<blockquote>",
        "📋 <b>Association Records:</b>",
        f"• 💰 Gold: <code>{hunter.gold:,} G</code>",
        f"• 🎒 Stored Items: <code>{total_items}</code>",
        f"• 🗡️ Hunts: <code>{hunter.total_hunts}</code> (Win Rate: <code>{win_rate}</code>)",
        f"• ⚔️ Duels: <code>{hunter.duel_wins}W - {hunter.duel_losses}L</code>",
        "</blockquote>",
        "",
        "<blockquote><i>「 The System sees all, Hunter. 」</i></blockquote>",
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
    ]

    return "\n".join(lines)


def format_welcome(hunter: Hunter) -> str:
    """Format the dramatic welcome message for a new hunter."""
    h_name = escape_html(hunter.hunter_name)
    r_name = escape_html(hunter.rank)
    return (
        "<b>╭━━━「 ⚡ SYSTEM AWAKENING NOTICE 」━━━╮</b>\n\n"
        "<i>A new Hunter has been detected and registered by the System.</i>\n\n"
        f"👤 <b>Hunter:</b> {h_name}\n"
        f"⭐ <b>Rank:</b> <code>{r_name}-Rank</code>\n"
        f"💪 <b>Combat Power:</b> <code>{hunter.power:,}</code>\n\n"
        "<blockquote>\n"
        "<b>📈 Awakened Core Attributes:</b>\n"
        f"• STR: <code>{hunter.str_stat}</code> ┊ AGI: <code>{hunter.agi}</code>\n"
        f"• VIT: <code>{hunter.vit}</code> ┊ INT: <code>{hunter.int_stat}</code> ┊ PER: <code>{hunter.per}</code>\n"
        "• Starter Weapon: 🗡️ <b>Rusty Short Sword</b> ⚪\n"
        f"• Initial Treasury: 💰 <code>{hunter.gold:,} G</code>\n"
        "</blockquote>\n\n"
        "<blockquote>\n"
        "<i>「 The System has acknowledged your awakening. 」</i>\n\n"
        "Your journey begins now, Hunter.\n"
        "Use <code>/hunt</code> to exterminate your first dungeon beast.\n"
        "</blockquote>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )


def format_hunt_victory(result: HuntResult) -> str:
    """Format a victorious hunt result."""
    monster = result.monster
    rank_icon = RANK_EMOJI.get(monster.rank, "")
    m_name = escape_html(monster.name)

    crit_text = " 💥 <b>CRITICAL!</b>" if result.critical_hit else ""

    lines = [
        "<b>╭━━━「 ⚔️ GATE HUNT // VICTORY 」━━━╮</b>",
        "",
        f"🎯 <b>Target:</b> <b>{m_name}</b> (Lv.{monster.level}) {rank_icon}",
        f"⚔️ <b>Battle Outcome:</b> ✅ <b>VICTORY</b>",
        "",
        "<blockquote>",
        f"💥 <b>Damage Dealt:</b> <code>{result.damage_dealt}</code>{crit_text}",
        f"💔 <b>Damage Taken:</b> <code>{result.damage_taken}</code>",
        "",
        "<b>✨ EXPEDITION REWARDS:</b>",
        f"• EXP Gained: ✨ <code>+{result.xp_gained:,} XP</code>",
        f"• Gold Acquired: 💰 <code>+{result.gold_gained:,} G</code>",
    ]

    if result.item_drop:
        rarity_icon = RARITY_EMOJI.get(result.item_drop.rarity, "")
        stats = escape_html(result.item_drop.stat_summary())
        drop_name = escape_html(result.item_drop.name)
        lines.append(f"• 🎁 <b>Loot Drop:</b> [{result.item_drop.rarity}] <b>{drop_name}</b> {rarity_icon} (<i>{stats}</i>)")

    if result.leveled_up:
        lines.append(f"• ⚡ <b>LEVEL UP!</b> → <b>Level {result.new_level}</b>")

    if result.ranked_up:
        new_rank_icon = RANK_EMOJI.get(result.new_rank, "")
        lines.append(f"• 🔥 <b>RANK ADVANCEMENT!</b> → <b>{result.new_rank}</b> {new_rank_icon}")

    lines.append("</blockquote>")

    if result.special_event:
        lines.append("")
        lines.append(f"<blockquote>{escape_html(result.special_event)}</blockquote>")

    lines.append("<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>")
    return "\n".join(lines)


def format_hunt_defeat(result: HuntResult) -> str:
    """Format a hunt defeat result."""
    monster = result.monster
    rank_icon = RANK_EMOJI.get(monster.rank, "")
    m_name = escape_html(monster.name)

    lines = [
        "<b>╭━━━「 ☠️ GATE HUNT // CASUALTY 」━━━╮</b>",
        "",
        f"🎯 <b>Target:</b> <b>{m_name}</b> (Lv.{monster.level}) {rank_icon}",
        f"⚔️ <b>Battle Outcome:</b> ☠️ <b>DEFEAT</b>",
        "",
        "<blockquote>",
        f"💥 <b>Damage Dealt:</b> <code>{result.damage_dealt}</code>",
        f"💔 <b>Damage Taken:</b> <code>{result.damage_taken}</code>",
        "",
        "<b>💸 PENALTIES:</b>",
        f"• Gold Lost: <code>-{result.gold_lost:,} G</code>",
        f"• Consolation EXP: <code>+{result.xp_gained:,} XP</code>",
        "</blockquote>",
        "",
        "<blockquote><i>Recover your vitality with <code>/use</code> or <code>/heal</code> and try again, Hunter.</i></blockquote>",
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
    ]

    if result.special_event:
        lines.insert(-1, f"<blockquote>{escape_html(result.special_event)}</blockquote>")

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
        f"<b>╭━━━「 🎒 DIMENSIONAL INVENTORY // {name.upper()} 」━━━╮</b>",
        "",
    ]

    if hunter:
        lines.extend([
            f"👤 <b>Hunter:</b> {escape_html(hunter.hunter_name)} ┊ 🏅 Rank <b>{hunter.rank}</b>",
            f"💰 <b>Gold:</b> <code>{hunter.gold:,} G</code> ┊ 📦 <b>Capacity:</b> <code>{total_items} items</code>",
            "",
        ])
    else:
        lines.extend([
            f"📦 <b>Stored Items:</b> <code>{total_items}</code>",
            "",
        ])

    if notice:
        lines.extend([
            f"<blockquote><b>⚡ System Notice:</b> <i>{escape_html(notice)}</i></blockquote>",
            "",
        ])

    lines.extend([
        "<blockquote>",
        f"<b>{icon} CATEGORY: {name.upper()} ({len(items)})</b>",
        "",
    ])

    if not items:
        lines.extend([
            "<i>「 Dimensional pocket empty. 」</i>\n"
            "• Defeat monsters via <code>/hunt</code> or browse\n"
            "  the 🛒 Shop to collect gear &amp; items!",
            "</blockquote>",
            "",
        ])
    else:
        for i, item in enumerate(items, 1):
            rarity_icon = RARITY_EMOJI.get(item.rarity, "⚪")
            status_tag = "⚡ [EQUIPPED]" if item.is_equipped else "📦 [IN STORAGE]"
            stats = escape_html(item.stat_summary())
            it_name = escape_html(item.name)

            lines.append(f"{i}. {rarity_icon} <b>{it_name}</b> [<b>{item.rarity}</b>]")
            lines.append(f"   ├ Status: <code>{status_tag}</code>")
            lines.append(f"   └ Stats:  <code>{stats}</code>")

        lines.extend([
            "</blockquote>",
            "",
        ])

    lines.extend([
        "💡 <b>Directives:</b>",
        "• Tap tabs to switch categories",
        "• Tap ⚡ Equip buttons below to bind gear",
        "• Tap 🛒 Hunter Shop to buy new items",
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>",
    ])

    return "\n".join(lines)


def format_equip_result(item: Item, old_item: Item | None, hunter: Hunter) -> str:
    """Format equipment change result with stat diff."""
    rarity_icon = RARITY_EMOJI.get(item.rarity, "")
    i_name = escape_html(item.name)

    stat_diffs = []
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
                stat_diffs.append(f"• <b>{stat_name}:</b> {old_val} → {new_val} (<code>{sign}{diff}</code>) {arrow}")

        if not stat_diffs:
            stat_diffs.append("• <i>No stat alterations.</i>")
    else:
        if item.atk_bonus:
            stat_diffs.append(f"• <b>ATK:</b> 0 → {item.atk_bonus} (<code>+{item.atk_bonus}</code>) ⬆️")
        if item.def_bonus:
            stat_diffs.append(f"• <b>DEF:</b> 0 → {item.def_bonus} (<code>+{item.def_bonus}</code>) ⬆️")
        if item.hp_bonus:
            stat_diffs.append(f"• <b>HP:</b> 0 → {item.hp_bonus} (<code>+{item.hp_bonus}</code>) ⬆️")
        if item.spd_bonus:
            stat_diffs.append(f"• <b>SPD:</b> 0 → {item.spd_bonus} (<code>+{item.spd_bonus}</code>) ⬆️")
        if not stat_diffs:
            stat_diffs.append("• <i>Standard piece with no bonus attributes.</i>")

    diff_body = "\n".join(stat_diffs)

    return (
        "<b>╭━━━「 ⚔️ EQUIPMENT BINDING COMPLETE 」━━━╮</b>\n\n"
        f"⚡ <b>Equipped:</b> <code>[{escape_html(item.rarity)}]</code> <b>{i_name}</b> {rarity_icon}\n"
        f"💪 <b>Combat Power:</b> <code>{hunter.power:,}</code>\n\n"
        "<blockquote>"
        "<b>Attribute Alterations:</b>\n"
        f"{diff_body}\n"
        "</blockquote>\n\n"
        "<i>Gear soulbound to hunter status matrix.</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )


def format_cooldown(remaining_seconds: int) -> str:
    """Format cooldown remaining message."""
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60
    return (
        "<b>╭━━━「 ⏳ RECOVERY IN PROGRESS 」━━━╮</b>\n\n"
        "<i>You are still catching your breath from your previous hunt.</i>\n\n"
        "<blockquote>"
        f"⏱️ <b>Ready In:</b> <code>{minutes}m {seconds:02d}s</code>\n"
        "• Mana fatigue is dissipating. Please stand by before entering another gate.\n"
        "</blockquote>\n\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )


def format_already_registered(hunter: Hunter) -> str:
    """Message when a user tries to /start again."""
    h_name = escape_html(hunter.hunter_name)
    return (
        "<b>╭━━━「 ⚡ HUNTER SYSTEM CONNECTED 」━━━╮</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name}\n"
        f"⭐ <b>Rank:</b> <b>{hunter.rank}-Rank</b> ┊ 📊 <b>Level:</b> <code>{hunter.level}</code>\n"
        f"⚡ <b>Power:</b> <code>{hunter.power:,}</code> ┊ 💰 <b>Gold:</b> <code>{hunter.gold:,} G</code>\n\n"
        "<blockquote>"
        "<b>Available Directives:</b>\n"
        "• <code>/profile</code> — Status matrix & attributes\n"
        "• <code>/hunt</code> — Enter dungeon gates\n"
        "• <code>/inventory</code> — Manage equipped artifacts\n"
        "• <code>/help</code> — Operational manual\n"
        "</blockquote>\n\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )


def format_not_registered() -> str:
    """Message when unregistered user tries a command."""
    return (
        "<b>╭━━━「 ⚠️ SYSTEM AWAKENING REQUIRED 」━━━╮</b>\n\n"
        "<i>The System detects no awakened mana signature for your identity.</i>\n\n"
        "<blockquote>"
        "<b>Status:</b> ❌ <b>Unawakened Citizen</b>\n"
        "• To awaken as a Hunter and receive your starter gear, tap or type:\n"
        "👉 <code>/start</code>\n"
        "</blockquote>\n\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )

