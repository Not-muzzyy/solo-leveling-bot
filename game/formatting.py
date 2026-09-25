"""
game/formatting.py — Rich Telegram message formatting.

Uses clean HTML with authentic Solo Leveling anime "System" (시스템) headers,
expandable blockquotes, and zero ASCII box-drawing fences.
"""

from __future__ import annotations

from config import RARITY_EMOJI, RANK_EMOJI
from models import Hunter, Item, HuntResult, Inventory
from game.rich_text import escape_html, safe_message, Bold, Italic, InlineCode, Chain, Quote, PlainText


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
        "E":              f"⚔️ [ E-Rank Hunter ]",
        "D":              f"⚔️ [ D-Rank Hunter ]",
        "C":              f"⚔️ [ C-Rank Hunter ]",
        "B":              f"⚔️ [ B-Rank Hunter ]",
        "A":              f"⚔️ [ A-Rank Hunter ]",
        "S":              f"⚔️ [ S-Rank Hunter ]",
        "SS":             f"⚔️ [ SS-Rank Hunter ]",
        "SSS":            f"⚔️ [ SSS-Rank Hunter ]",
        "National Level": f"👑 [ National Level Hunter ]",
        "Monarch":        f"👑 [ Shadow Monarch ]",
    }
    return badges.get(rank, f"{rank_icon} [ {rank}-Rank ]")


def _format_equip_line(label: str, icon: str, item: Item | None) -> str:
    """Format a single equipment slot line."""
    if item:
        rarity_icon = RARITY_EMOJI.get(item.rarity, "")
        stats = item.stat_summary()
        return f"• {icon} <b>{item.name}</b> {rarity_icon} (<i>{stats}</i>)"
    return f"• {icon} <i>— empty —</i>"


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
            return f"• {icon} {Bold(escape_html(item.name)).to_html()} {r_icon} ({InlineCode(escape_html(item.stat_summary())).to_html()})"
        return f"• {icon} <i>— empty —</i>"

    lines = [
        "<b>[ STATUS WINDOW // 상태창 ]</b>",
        "",
        f"👤 <b>Hunter:</b> {h_name} [Rank {Bold(escape_html(hunter.rank)).to_html()} {rank_icon}]",
        f"🏅 <b>Title:</b> {Italic(title_esc).to_html()}",
        f"📊 <b>Level:</b> {InlineCode(escape_html(str(hunter.level))).to_html()} ┊ 💪 <b>Power:</b> {InlineCode(escape_html(f'{hunter.power:,}')).to_html()} ({InlineCode(escape_html(f'+{total_equip}')).to_html()})",
        f"✨ <b>XP:</b> {InlineCode(escape_html(f'{hunter.xp}/{hunter.xp_needed}')).to_html()}  {_progress_bar(hunter.xp, hunter.xp_needed)}",
        f"❤️ <b>Vitality:</b> {_hp_bar(hunter.hp, hunter.max_hp)}",
        "",
        "<blockquote expandable>",
        "<b>📈 Core Attributes:</b>",
        f"• STR: {InlineCode(escape_html(f'{hunter.str_stat:>3}')).to_html()}  {_stat_bar(hunter.str_stat)}",
        f"• AGI: {InlineCode(escape_html(f'{hunter.agi:>3}')).to_html()}  {_stat_bar(hunter.agi)}",
        f"• VIT: {InlineCode(escape_html(f'{hunter.vit:>3}')).to_html()}  {_stat_bar(hunter.vit)}",
        f"• INT: {InlineCode(escape_html(f'{hunter.int_stat:>3}')).to_html()}  {_stat_bar(hunter.int_stat)}",
        f"• PER: {InlineCode(escape_html(f'{hunter.per:>3}')).to_html()}  {_stat_bar(hunter.per)}",
        "",
        "<b>⚔️ Equipped Loadout:</b>",
        _equip_html("🗡️", weapon),
        _equip_html("🛡️", armor),
        _equip_html("💍", accessory),
        "</blockquote>",
        "",
        "<blockquote expandable>",
        "<b>📋 Association Records:</b>",
        f"• 💰 Gold: {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()}",
        f"• 🎒 Stored Items: {InlineCode(escape_html(str(total_items))).to_html()}",
        f"• 🗡️ Hunts: {InlineCode(escape_html(str(hunter.total_hunts))).to_html()} (Win Rate: {InlineCode(escape_html(win_rate)).to_html()})",
        f"• ⚔️ Duels: {InlineCode(escape_html(f'{hunter.duel_wins}W - {hunter.duel_losses}L')).to_html()}",
        "</blockquote>",
        "",
        Quote(Italic("「 The System sees all, Hunter. 」")).to_html(),
    ]

    return safe_message("\n".join(lines))


def format_welcome(hunter: Hunter) -> str:
    """Format the dramatic welcome message for a new hunter."""
    h_name = escape_html(hunter.hunter_name)
    r_name = escape_html(hunter.rank)
    return safe_message(
        "<b>[ SYSTEM AWAKENING NOTICE // 각성 확인 ]</b>\n\n"
        "<i>A new Hunter has been detected and registered by the System.</i>\n\n"
        f"👤 <b>Hunter:</b> {h_name}\n"
        f"⭐ <b>Rank:</b> {InlineCode(f'{r_name}-Rank').to_html()}\n"
        f"💪 <b>Combat Power:</b> {InlineCode(escape_html(f'{hunter.power:,}')).to_html()}\n\n"
        "<blockquote expandable>\n"
        "<b>📈 Awakened Core Attributes:</b>\n"
        f"• STR: {InlineCode(escape_html(str(hunter.str_stat))).to_html()} ┊ AGI: {InlineCode(escape_html(str(hunter.agi))).to_html()}\n"
        f"• VIT: {InlineCode(escape_html(str(hunter.vit))).to_html()} ┊ INT: {InlineCode(escape_html(str(hunter.int_stat))).to_html()} ┊ PER: {InlineCode(escape_html(str(hunter.per))).to_html()}\n"
        "• Starter Weapon: 🗡️ <b>Rusty Short Sword</b> ⚪\n"
        f"• Initial Treasury: 💰 {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()}\n"
        "</blockquote>\n\n"
        + Quote(Chain(
            PlainText("\n"),
            Italic("「 The System has acknowledged your awakening. 」"),
            PlainText("\n\nYour journey begins now, Hunter.\nUse <code>/hunt</code> to exterminate your first dungeon beast.\n"),
            sep="",
        )).to_html()
    )


def format_hunt_victory(result: HuntResult) -> str:
    """Format a victorious hunt result."""
    monster = result.monster
    rank_icon = RANK_EMOJI.get(monster.rank, "")
    m_name = escape_html(monster.name)

    crit_text = " 💥 <b>CRITICAL!</b>" if result.critical_hit else ""

    lines = [
        "<b>[ GATE RAID // 던전 클리어 ]</b>",
        "",
        f"🎯 <b>Target:</b> {Bold(m_name).to_html()} (Lv.{monster.level}) {rank_icon}",
        f"⚔️ <b>Battle Outcome:</b> ✅ <b>VICTORY</b>",
        "",
        "<blockquote expandable>",
        f"💥 <b>Damage Dealt:</b> {InlineCode(escape_html(f'{result.damage_dealt:,}')).to_html()}{crit_text}",
        f"💔 <b>Damage Taken:</b> {InlineCode(escape_html(f'{result.damage_taken:,}')).to_html()}",
        "",
        "<b>✨ EXPEDITION REWARDS:</b>",
        f"• EXP Gained: ✨ {InlineCode(escape_html(f'+{result.xp_gained:,} XP')).to_html()}",
        f"• Gold Acquired: 💰 {InlineCode(escape_html(f'+{result.gold_gained:,} G')).to_html()}",
    ]

    if result.item_drop:
        rarity_icon = RARITY_EMOJI.get(result.item_drop.rarity, "")
        stats = escape_html(result.item_drop.stat_summary())
        drop_name = escape_html(result.item_drop.name)
        drop_rarity = escape_html(result.item_drop.rarity)
        lines.append(f"• 🎁 <b>Loot Drop:</b> [{drop_rarity}] {Bold(drop_name).to_html()} {rarity_icon} ({Italic(stats).to_html()})")

    if result.leveled_up:
        lines.append(f"• ⚡ <b>LEVEL UP!</b> → {Bold(escape_html(f'Level {result.new_level}')).to_html()}")

    if result.ranked_up:
        new_rank_icon = RANK_EMOJI.get(result.new_rank, "")
        lines.append(f"• 🔥 <b>RANK ADVANCEMENT!</b> → {Bold(escape_html(result.new_rank)).to_html()} {new_rank_icon}")

    lines.append("</blockquote>")

    if result.special_event:
        lines.append("")
        lines.append(Quote(PlainText(escape_html(result.special_event))).to_html())

    return safe_message("\n".join(lines))


def format_hunt_defeat(result: HuntResult) -> str:
    """Format a hunt defeat result."""
    monster = result.monster
    rank_icon = RANK_EMOJI.get(monster.rank, "")
    m_name = escape_html(monster.name)

    lines = [
        "<b>[ GATE CASUALTY // 공략 실패 ]</b>",
        "",
        f"🎯 <b>Target:</b> {Bold(m_name).to_html()} (Lv.{monster.level}) {rank_icon}",
        f"⚔️ <b>Battle Outcome:</b> ☠️ <b>DEFEAT</b>",
        "",
        "<blockquote expandable>",
        f"💥 <b>Damage Dealt:</b> {InlineCode(escape_html(f'{result.damage_dealt:,}')).to_html()}",
        f"💔 <b>Damage Taken:</b> {InlineCode(escape_html(f'{result.damage_taken:,}')).to_html()}",
        "",
        "<b>💸 PENALTIES:</b>",
        f"• Gold Lost: {InlineCode(escape_html(f'-{result.gold_lost:,} G')).to_html()}",
        f"• Consolation EXP: {InlineCode(escape_html(f'+{result.xp_gained:,} XP')).to_html()}",
        "</blockquote>",
        "",
        Quote(Italic("Recover your vitality with <code>/use</code> or <code>/heal</code> and try again, Hunter.")).to_html(),
    ]

    if result.special_event:
        lines.insert(-1, Quote(PlainText(escape_html(result.special_event))).to_html())

    return safe_message("\n".join(lines))


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
        f"{Bold(f'[ SHADOW STORAGE // {name.upper()} ]').to_html()}",
        "",
    ]

    if hunter:
        lines.extend([
            f"👤 <b>Hunter:</b> {escape_html(hunter.hunter_name)} ┊ 🏅 Rank {Bold(escape_html(hunter.rank)).to_html()}",
            f"💰 <b>Gold:</b> {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()} ┊ 📦 <b>Capacity:</b> {InlineCode(escape_html(f'{total_items} items')).to_html()}",
            "",
        ])
    else:
        lines.extend([
            f"📦 <b>Stored Items:</b> {InlineCode(escape_html(str(total_items))).to_html()}",
            "",
        ])

    if notice:
        lines.extend([
            Quote(Chain(Bold("⚡ System Notice:"), Italic(escape_html(notice)), sep=" ")).to_html(),
            "",
        ])

    lines.extend([
        "<blockquote expandable>",
        f"{Bold(escape_html(f'{icon} CATEGORY: {name.upper()} ({len(items)})')).to_html()}",
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
            it_rarity = escape_html(item.rarity)

            lines.append(f"{i}. {rarity_icon} {Bold(it_name).to_html()} [{Bold(it_rarity).to_html()}]")
            lines.append(f"   ├ Status: {InlineCode(escape_html(status_tag)).to_html()}")
            lines.append(f"   └ Stats:  {InlineCode(stats).to_html()}")

        lines.extend([
            "</blockquote>",
            "",
        ])

    lines.extend([
        "💡 <b>Directives:</b>",
        "• Tap tabs to switch categories",
        "• Tap ⚡ Equip buttons below to bind gear",
        "• Tap 🛒 Hunter Shop to buy new items",
    ])

    return safe_message("\n".join(lines))


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
                stat_diffs.append(f"• {Bold(escape_html(f'{stat_name}:')).to_html()} {old_val} → {new_val} ({InlineCode(escape_html(f'{sign}{diff}')).to_html()}) {arrow}")

        if not stat_diffs:
            stat_diffs.append("• <i>No stat alterations.</i>")
    else:
        if item.atk_bonus:
            stat_diffs.append(f"• <b>ATK:</b> 0 → {item.atk_bonus} ({InlineCode(escape_html(f'+{item.atk_bonus}')).to_html()}) ⬆️")
        if item.def_bonus:
            stat_diffs.append(f"• <b>DEF:</b> 0 → {item.def_bonus} ({InlineCode(escape_html(f'+{item.def_bonus}')).to_html()}) ⬆️")
        if item.hp_bonus:
            stat_diffs.append(f"• <b>HP:</b> 0 → {item.hp_bonus} ({InlineCode(escape_html(f'+{item.hp_bonus}')).to_html()}) ⬆️")
        if item.spd_bonus:
            stat_diffs.append(f"• <b>SPD:</b> 0 → {item.spd_bonus} ({InlineCode(escape_html(f'+{item.spd_bonus}')).to_html()}) ⬆️")
        if not stat_diffs:
            stat_diffs.append("• <i>Standard piece with no bonus attributes.</i>")

    diff_body = "\n".join(stat_diffs)

    return safe_message(
        "<b>[ EQUIPMENT BINDING // 장비 장착 ]</b>\n\n"
        f"⚡ <b>Equipped:</b> {InlineCode(f'[{escape_html(item.rarity)}]').to_html()} {Bold(i_name).to_html()} {rarity_icon}\n"
        f"💪 <b>Combat Power:</b> {InlineCode(escape_html(f'{hunter.power:,}')).to_html()}\n\n"
        "<blockquote expandable>"
        "<b>Attribute Alterations:</b>\n"
        f"{diff_body}\n"
        "</blockquote>\n\n"
        "<i>Gear soulbound to hunter status matrix.</i>"
    )


def format_cooldown(remaining_seconds: int) -> str:
    """Format cooldown remaining message."""
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60
    return safe_message(
        "<b>[ RECOVERY IN PROGRESS // 피로도 회복 중 ]</b>\n\n"
        "<i>You are still catching your breath from your previous hunt.</i>\n\n"
        "<blockquote expandable>"
        f"⏱️ <b>Ready In:</b> {InlineCode(escape_html(f'{minutes}m {seconds:02d}s')).to_html()}\n"
        "• Mana fatigue is dissipating. Please stand by before entering another gate.\n"
        "</blockquote>"
    )


def format_already_registered(hunter: Hunter) -> str:
    """Message when a user tries to /start again."""
    h_name = escape_html(hunter.hunter_name)
    r_name = escape_html(hunter.rank)
    return safe_message(
        "<b>[ HUNTER RE-AUTHENTICATION // 헌터 인증 ]</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name}\n"
        f"⭐ <b>Rank:</b> {Bold(f'{r_name}-Rank').to_html()} ┊ 📊 <b>Level:</b> {InlineCode(escape_html(str(hunter.level))).to_html()}\n"
        f"⚡ <b>Power:</b> {InlineCode(escape_html(f'{hunter.power:,}')).to_html()} ┊ 💰 <b>Gold:</b> {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()}\n\n"
        "<blockquote expandable>"
        "<b>Available Directives:</b>\n"
        "• <code>/profile</code> — Status matrix & attributes\n"
        "• <code>/hunt</code> — Enter dungeon gates\n"
        "• <code>/inventory</code> — Manage equipped artifacts\n"
        "• <code>/help</code> — Operational manual\n"
        "</blockquote>"
    )


def format_not_registered() -> str:
    """Message when unregistered user tries a command."""
    return safe_message(
        "<b>[ SYSTEM AWAKENING REQUIRED // 각성 필요 ]</b>\n\n"
        "<i>The System detects no awakened mana signature for your identity.</i>\n\n"
        "<blockquote>"
        "<b>Status:</b> ❌ <b>Unawakened Citizen</b>\n"
        "• To awaken as a Hunter and receive your starter gear, tap or type:\n"
        "👉 <code>/start</code>\n"
        "</blockquote>"
    )


# ── Rich Message twins (Bot API 10.1+). Classic versions above stay untouched
# and are the verbatim fallback at every send site. ──────────────────────────


def format_not_registered_rich() -> "RichDoc":
    """Rich twin of format_not_registered (same copy, block structure)."""
    from game.rich_message import RichDoc, heading, paragraph, quote
    return RichDoc(
        heading(1, "[ SYSTEM AWAKENING REQUIRED // 각성 필요 ]"),
        paragraph("<i>The System detects no awakened mana signature for your identity.</i>"),
        quote(
            "<b>Status:</b> ❌ <b>Unawakened Citizen</b><br>"
            "• To awaken as a Hunter and receive your starter gear, tap or type:<br>"
            "👉 <code>/start</code>",
            expandable=False,
        ),
    )


def format_cooldown_rich(remaining_seconds: int) -> "RichDoc":
    """Rich twin of format_cooldown (hunt recovery, fixed interface for Tasks 6-9)."""
    from game.rich_message import RichDoc, code, heading, paragraph, quote
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60
    return RichDoc(
        heading(1, "[ RECOVERY IN PROGRESS // 피로도 회복 중 ]"),
        paragraph("<i>You are still catching your breath from your previous hunt.</i>"),
        quote(
            f"⏱️ <b>Ready In:</b> {code(escape_html(f'{minutes}m {seconds:02d}s'))}<br>"
            "• Mana fatigue is dissipating. Please stand by before entering another gate.",
            expandable=True,
        ),
    )


def format_profile_rich(hunter: Hunter, inventory: Inventory) -> "RichDoc":
    """Rich twin of format_profile (text fallback of /profile photo)."""
    from game.rich_message import RichDoc, heading, paragraph, quote

    weapon = inventory.get_equipped("weapon")
    armor = inventory.get_equipped("armor")
    accessory = inventory.get_equipped("accessory")

    equip_atk = sum(i.atk_bonus for i in [weapon, armor, accessory] if i)
    equip_def = sum(i.def_bonus for i in [weapon, armor, accessory] if i)
    equip_hp = sum(i.hp_bonus for i in [weapon, armor, accessory] if i)
    equip_spd = sum(i.spd_bonus for i in [weapon, armor, accessory] if i)
    total_equip = equip_atk + equip_def + equip_hp + equip_spd

    win_rate = "—"
    if hunter.total_hunts > 0:
        wr = (hunter.victories / hunter.total_hunts) * 100
        win_rate = f"{wr:.0f}%"

    total_items = len(inventory.items)
    h_name = escape_html(hunter.hunter_name)
    title_esc = escape_html(hunter.title)
    rank_icon = RANK_EMOJI.get(hunter.rank, "❓")

    def _equip_html(icon: str, item: Item | None) -> str:
        if item:
            r_icon = RARITY_EMOJI.get(item.rarity, "")
            return f"• {icon} {Bold(escape_html(item.name)).to_html()} {r_icon} ({InlineCode(escape_html(item.stat_summary())).to_html()})"
        return f"• {icon} <i>— empty —</i>"

    return RichDoc(
        heading(1, "[ STATUS WINDOW // 상태창 ]"),
        paragraph(
            f"👤 <b>Hunter:</b> {h_name} [Rank {Bold(escape_html(hunter.rank)).to_html()} {rank_icon}]<br>"
            f"🏅 <b>Title:</b> {Italic(title_esc).to_html()}<br>"
            f"📊 <b>Level:</b> {InlineCode(escape_html(str(hunter.level))).to_html()} ┊ 💪 <b>Power:</b> {InlineCode(escape_html(f'{hunter.power:,}')).to_html()} ({InlineCode(escape_html(f'+{total_equip}')).to_html()})<br>"
            f"✨ <b>XP:</b> {InlineCode(escape_html(f'{hunter.xp}/{hunter.xp_needed}')).to_html()}  {_progress_bar(hunter.xp, hunter.xp_needed)}<br>"
            f"❤️ <b>Vitality:</b> {_hp_bar(hunter.hp, hunter.max_hp)}"
        ),
        quote(
            "<b>📈 Core Attributes:</b><br>"
            f"• STR: {InlineCode(escape_html(f'{hunter.str_stat:>3}')).to_html()}  {_stat_bar(hunter.str_stat)}<br>"
            f"• AGI: {InlineCode(escape_html(f'{hunter.agi:>3}')).to_html()}  {_stat_bar(hunter.agi)}<br>"
            f"• VIT: {InlineCode(escape_html(f'{hunter.vit:>3}')).to_html()}  {_stat_bar(hunter.vit)}<br>"
            f"• INT: {InlineCode(escape_html(f'{hunter.int_stat:>3}')).to_html()}  {_stat_bar(hunter.int_stat)}<br>"
            f"• PER: {InlineCode(escape_html(f'{hunter.per:>3}')).to_html()}  {_stat_bar(hunter.per)}<br><br>"
            "<b>⚔️ Equipped Loadout:</b><br>"
            f"{_equip_html('🗡️', weapon)}<br>{_equip_html('🛡️', armor)}<br>{_equip_html('💍', accessory)}",
            expandable=True,
        ),
        quote(
            "<b>📋 Association Records:</b><br>"
            f"• 💰 Gold: {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()}<br>"
            f"• 🎒 Stored Items: {InlineCode(escape_html(str(total_items))).to_html()}<br>"
            f"• 🗡️ Hunts: {InlineCode(escape_html(str(hunter.total_hunts))).to_html()} (Win Rate: {InlineCode(escape_html(win_rate)).to_html()})<br>"
            f"• ⚔️ Duels: {InlineCode(escape_html(f'{hunter.duel_wins}W - {hunter.duel_losses}L')).to_html()}",
            expandable=True,
        ),
        quote("<i>「 The System sees all, Hunter. 」</i>", expandable=False),
    )


def format_welcome_rich(hunter: Hunter) -> "RichDoc":
    """Rich twin of format_welcome (new hunter awakening message)."""
    from game.rich_message import RichDoc, heading, paragraph, quote
    h_name = escape_html(hunter.hunter_name)
    r_name = escape_html(hunter.rank)
    return RichDoc(
        heading(1, "[ SYSTEM AWAKENING NOTICE // 각성 확인 ]"),
        paragraph("<i>A new Hunter has been detected and registered by the System.</i>"),
        paragraph(
            f"👤 <b>Hunter:</b> {h_name}<br>"
            f"⭐ <b>Rank:</b> {InlineCode(f'{r_name}-Rank').to_html()}<br>"
            f"💪 <b>Combat Power:</b> {InlineCode(escape_html(f'{hunter.power:,}')).to_html()}"
        ),
        quote(
            "<b>📈 Awakened Core Attributes:</b><br>"
            f"• STR: {InlineCode(escape_html(str(hunter.str_stat))).to_html()} ┊ AGI: {InlineCode(escape_html(str(hunter.agi))).to_html()}<br>"
            f"• VIT: {InlineCode(escape_html(str(hunter.vit))).to_html()} ┊ INT: {InlineCode(escape_html(str(hunter.int_stat))).to_html()} ┊ PER: {InlineCode(escape_html(str(hunter.per))).to_html()}<br>"
            "• Starter Weapon: 🗡️ <b>Rusty Short Sword</b> ⚪<br>"
            f"• Initial Treasury: 💰 {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()}",
            expandable=True,
        ),
        quote(
            "<i>「 The System has acknowledged your awakening. 」</i><br><br>"
            "Your journey begins now, Hunter.<br>"
            "Use <code>/hunt</code> to exterminate your first dungeon beast.",
            expandable=False,
        ),
    )


def format_already_registered_rich(hunter: Hunter) -> "RichDoc":
    """Rich twin of format_already_registered (/start for returning hunter)."""
    from game.rich_message import RichDoc, heading, paragraph, quote
    h_name = escape_html(hunter.hunter_name)
    r_name = escape_html(hunter.rank)
    return RichDoc(
        heading(1, "[ HUNTER RE-AUTHENTICATION // 헌터 인증 ]"),
        paragraph(
            f"👤 <b>Hunter:</b> {h_name}<br>"
            f"⭐ <b>Rank:</b> {Bold(f'{r_name}-Rank').to_html()} ┊ 📊 <b>Level:</b> {InlineCode(escape_html(str(hunter.level))).to_html()}<br>"
            f"⚡ <b>Power:</b> {InlineCode(escape_html(f'{hunter.power:,}')).to_html()} ┊ 💰 <b>Gold:</b> {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()}"
        ),
        quote(
            "<b>Available Directives:</b><br>"
            "• <code>/profile</code> — Status matrix &amp; attributes<br>"
            "• <code>/hunt</code> — Enter dungeon gates<br>"
            "• <code>/inventory</code> — Manage equipped artifacts<br>"
            "• <code>/help</code> — Operational manual",
            expandable=True,
        ),
    )
