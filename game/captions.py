"""
game/captions.py — Reusable Telegram Rich Text Caption Templates (HTML Mode).

Implements aesthetic, authentic Solo Leveling anime "System" (시스템) card templates:
- Anime System Header: <b>[ TITLE // 한국어 부제 ]</b>
- Clean metadata lines with bold field labels and inline <code> tags
- Modern Telegram <blockquote expandable> blocks for technical breakdowns, gear stats, and combat logs
- Semantic badges and icons without clutter
- Strict caption length safety (<= 1024 chars for Telegram media captions) via safe_caption()
"""

from __future__ import annotations

from typing import Any, Optional
from config import RANK_EMOJI, RARITY_EMOJI
from models import Hunter, Inventory, Item, HuntResult
from game.rich_text import escape_html, safe_caption, Bold, Italic, InlineCode, Chain, Quote, PlainText


def build_profile_caption(hunter: Hunter, inventory: Inventory, full_name: str = "") -> str:
    """Aesthetic status window caption for /profile."""
    h_name = escape_html(full_name or hunter.hunter_name or f"Hunter #{hunter.user_id}")
    rank_icon = RANK_EMOJI.get(hunter.rank, "⚔️")
    title_str = escape_html(hunter.title or "None")

    weapon = inventory.get_equipped("weapon")
    armor = inventory.get_equipped("armor")
    accessory = inventory.get_equipped("accessory")
    w_name = escape_html(weapon.name) if weapon else "None"
    a_name = escape_html(armor.name) if armor else "None"
    acc_name = escape_html(accessory.name) if accessory else "None"

    return safe_caption(
        "<b>[ STATUS WINDOW // 상태창 ]</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name}\n"
        f"🏅 <b>Rank:</b> {rank_icon} {Bold(escape_html(f'{hunter.rank}-Rank')).to_html()} ┊ 📊 <b>Lv:</b> {InlineCode(escape_html(str(hunter.level))).to_html()}\n"
        f"🎖️ <b>Title:</b> {Italic(title_str).to_html()}\n"
        f"⚡ <b>Power:</b> {InlineCode(escape_html(f'{hunter.power:,}')).to_html()} ┊ 💰 <b>Gold:</b> {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()}\n\n"
        "<blockquote expandable>"
        "<b>📈 Core Attributes:</b>\n"
        f"• STR: {InlineCode(escape_html(str(hunter.str_stat))).to_html()} ┊ AGI: {InlineCode(escape_html(str(hunter.agi))).to_html()} ┊ VIT: {InlineCode(escape_html(str(hunter.vit))).to_html()}\n"
        f"• INT: {InlineCode(escape_html(str(hunter.int_stat))).to_html()} ┊ PER: {InlineCode(escape_html(str(hunter.per))).to_html()}\n"
        f"• HP: {InlineCode(escape_html(f'{hunter.hp}/{hunter.max_hp}')).to_html()} ┊ XP: {InlineCode(escape_html(f'{hunter.xp}/{hunter.xp_needed}')).to_html()}\n"
        f"• Gear: 🗡️ {w_name} ┊ 🛡️ {a_name} ┊ 💍 {acc_name}\n"
        "</blockquote>\n\n"
        + Quote(Italic("「 The System has acknowledged your awakening. 」")).to_html()
    )


def build_hunt_caption(hunter: Hunter, result: HuntResult) -> str:
    """Aesthetic combat resolution card caption for /hunt."""
    m_name = escape_html(result.monster.name)
    m_rank = escape_html(result.monster.rank)
    quota_str = InlineCode(escape_html(f"{hunter.daily_hunts}/20")).to_html()

    if result.victory:
        loot_line = ""
        if result.item_drop:
            i_name = escape_html(result.item_drop.name)
            i_rarity = escape_html(result.item_drop.rarity)
            loot_line = f"\n• 🎁 <b>Loot:</b> {InlineCode(f'[{i_rarity}]').to_html()} {Bold(i_name).to_html()}"

        shadow_prompt = ""
        if result.monster.rank in ("A", "S", "SS", "SSS", "Monarch"):
            shadow_prompt = "\n\n" + Quote(Chain(Bold("[ SHADOW EXTRACTION AVAILABLE ]"), Italic('Phrase: "ARISE" (일어나라)'), sep="\n")).to_html()

        return safe_caption(
            "<b>[ GATE RAID REPORT // 던전 클리어 ]</b>\n\n"
            f"🎯 <b>Target:</b> {Bold(m_name).to_html()} [{Bold(f'{m_rank}-Rank').to_html()}]\n"
            f"👤 <b>Hunter:</b> {Bold(escape_html(hunter.hunter_name)).to_html()} [Rank {Bold(escape_html(hunter.rank)).to_html()}]\n\n"
            "<blockquote expandable>"
            "<b>✅ RAID SUCCESSFUL:</b>\n"
            f"• Dealt: {InlineCode(escape_html(f'{result.damage_dealt:,} DMG')).to_html()} ┊ Taken: {InlineCode(escape_html(f'{result.damage_taken:,} DMG')).to_html()}\n"
            f"• Bounty: 💰 {InlineCode(escape_html(f'+{result.gold_gained:,} Gold')).to_html()} ┊ ✨ {InlineCode(escape_html(f'+{result.xp_gained:,} XP')).to_html()}"
            f"{loot_line}\n"
            f"• Vitality: {InlineCode(escape_html(f'{hunter.hp}/{hunter.max_hp} HP')).to_html()}\n"
            "</blockquote>"
            f"{shadow_prompt}\n\n"
            f"📊 <b>Daily Quota:</b> {quota_str} (1m CD)"
        )
    else:
        return safe_caption(
            "<b>[ GATE CASUALTY ALERT // 경고: 던전 공략 실패 ]</b>\n\n"
            f"🎯 <b>Monster:</b> {Bold(m_name).to_html()} [{Bold(f'{m_rank}-Rank').to_html()}]\n"
            f"👤 <b>Hunter:</b> {Bold(escape_html(hunter.hunter_name)).to_html()} [Rank {Bold(escape_html(hunter.rank)).to_html()}]\n\n"
            "<blockquote expandable>"
            "<b>❌ MISSION FAILED — CASUALTY</b>\n"
            f"• Dealt: {InlineCode(escape_html(f'{result.damage_dealt:,} DMG')).to_html()} ┊ Taken: {InlineCode(escape_html(f'{result.damage_taken:,} DMG')).to_html()}\n"
            f"• Lost: 💰 {InlineCode(escape_html(f'-{result.gold_lost:,} Gold')).to_html()}\n"
            f"• Consolation: ✨ {InlineCode(escape_html(f'+{result.xp_gained:,} XP')).to_html()}\n"
            f"• Vitality: {InlineCode(escape_html(f'{hunter.hp}/{hunter.max_hp} HP')).to_html()} (Potion needed)\n"
            "</blockquote>\n\n"
            f"📊 <b>Daily Quota:</b> {quota_str} (1m CD)"
        )


def build_explore_caption(
    hunter: Hunter,
    sector_info: dict,
    gold_reward: int,
    xp_reward: int,
    gift_item: Item | None,
    leveled_up: bool,
    new_rank: str | None,
    story: str,
    display_name: str = "",
) -> str:
    """Aesthetic expedition report caption for /explore."""
    s_name = escape_html(sector_info.get("name", "Unknown Sector").upper())
    d_name = escape_html(display_name or hunter.hunter_name or f"Hunter #{hunter.user_id}")
    story_esc = escape_html(story)
    quota_str = InlineCode(escape_html(f"{hunter.daily_explores}/3")).to_html()

    gift_block = ""
    if gift_item:
        g_name = escape_html(gift_item.name)
        g_rarity = escape_html(gift_item.rarity)
        g_stats = escape_html(gift_item.stat_summary())
        gift_block = f"\n• 🎁 <b>Artifact Found:</b> {InlineCode(f'[{g_rarity}]').to_html()} {Bold(g_name).to_html()} ({Italic(g_stats).to_html()})"

    ascend_block = ""
    if leveled_up or new_rank:
        asc_lines = []
        if leveled_up:
            asc_lines.append(f"⚡ <b>Level Up:</b> Reached Level {Bold(escape_html(str(hunter.level))).to_html()}!")
        if new_rank:
            asc_lines.append(f"👑 <b>Awakened:</b> {Bold(f'[{escape_html(new_rank)}] Hunter').to_html()}!")
        ascend_block = Quote(PlainText(" ".join(asc_lines))).to_html() + "\n\n"

    return safe_caption(
        f"{Bold(f'[ TACTICAL GATE RADAR // {s_name} ]').to_html()}\n\n"
        f"👤 <b>Scout:</b> {d_name} [Rank {Bold(escape_html(hunter.rank)).to_html()} ┊ Lv. {InlineCode(escape_html(str(hunter.level))).to_html()}]\n\n"
        "<blockquote expandable>"
        "<b>📜 Reconnaissance Log:</b>\n"
        f"{Italic(story_esc).to_html()}\n\n"
        f"• 💰 <b>Treasury Bounty:</b> {InlineCode(escape_html(f'+{gold_reward:,} Gold')).to_html()}\n"
        f"• ✨ <b>Exp Bounty:</b> {InlineCode(escape_html(f'+{xp_reward:,} XP')).to_html()}"
        f"{gift_block}\n"
        "</blockquote>\n\n"
        f"{ascend_block}"
        f"📊 <b>Daily Expeditions:</b> {quota_str} Completed (1h CD)"
    )


def build_inventory_caption(
    hunter: Hunter,
    inventory: Inventory,
    category: str = "weapon",
    notice: str | None = None,
) -> str:
    """Aesthetic inventory card caption for /inventory."""
    h_name = escape_html(hunter.hunter_name)
    cat_title = escape_html(category.title())
    total_items = len(inventory.items)

    weapon = inventory.get_equipped("weapon")
    armor = inventory.get_equipped("armor")
    accessory = inventory.get_equipped("accessory")
    w_str = escape_html(weapon.name) if weapon else "— None —"
    a_str = escape_html(armor.name) if armor else "— None —"
    acc_str = escape_html(accessory.name) if accessory else "— None —"

    notice_block = ""
    if notice:
        notice_block = Quote(Chain(Bold("⚡ System Notice:"), Italic(escape_html(notice)), sep=" ")).to_html() + "\n\n"

    return safe_caption(
        f"{Bold(f'[ SHADOW STORAGE // {cat_title.upper()} ]').to_html()}\n\n"
        f"👤 <b>Hunter:</b> {h_name} [Rank {Bold(escape_html(hunter.rank)).to_html()}]\n"
        f"💰 <b>Treasury:</b> {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()} ┊ 📦 <b>Stored Items:</b> {InlineCode(escape_html(str(total_items))).to_html()}\n\n"
        f"{notice_block}"
        "<blockquote expandable>"
        "<b>⚔️ Currently Bound Equipment:</b>\n"
        f"• 🗡️ Weapon: {Bold(w_str).to_html()}\n"
        f"• 🛡️ Armor: {Bold(a_str).to_html()}\n"
        f"• 💍 Accessory: {Bold(acc_str).to_html()}\n"
        "</blockquote>\n\n"
        "<i>Select tabs or equipment controls below:</i>"
    )


def build_shop_caption(
    hunter: Hunter,
    category: str = "menu",
    notice: str | None = None,
) -> str:
    """Aesthetic shop card caption for /shop."""
    h_name = escape_html(hunter.hunter_name)
    cat_title = "Central Depot" if category == "menu" else escape_html(category.title())

    notice_block = ""
    if notice:
        notice_block = Quote(Chain(Bold("✅ Purchase Confirmed:"), Italic(escape_html(notice)), sep=" ")).to_html() + "\n\n"

    return safe_caption(
        f"{Bold(f'[ EXCHANGE DEPOT // {cat_title.upper()} ]').to_html()}\n\n"
        f"👤 <b>Hunter:</b> {h_name} [Rank {Bold(escape_html(hunter.rank)).to_html()}]\n"
        f"💰 <b>Available Treasury:</b> {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()}\n\n"
        f"{notice_block}"
        "<blockquote expandable>"
        "<b>Association Procurement:</b>\n"
        "<i>Purchase graded weapons, defense armors, accessories, and restorative potions directly from Association vaults.</i>\n"
        "</blockquote>\n\n"
        "<i>Select an item category or equipment piece below:</i>"
    )


def build_tower_caption(
    hunter: Hunter,
    guardian: Any,
    result: Any | None = None,
    notice: str | None = None,
) -> str:
    """Aesthetic Demon Castle Spire card caption for /tower."""
    h_name = escape_html(hunter.hunter_name)
    g_name = escape_html(guardian.name) if guardian else "Floor Boss"
    keys_str = InlineCode(escape_html(f"{hunter.tower_keys}/3")).to_html()
    floor_str = InlineCode(escape_html(f"{hunter.tower_floor}/100")).to_html()

    if result:
        outcome_title = "✅ FLOOR CLEARED!" if result.victory else "☠️ CHALLENGER FALLEN!"
        loot_line = ""
        if result.item_drop:
            loot_line = f"\n• 🎁 <b>Drop:</b> {InlineCode(f'[{escape_html(result.item_drop.rarity)}]').to_html()} {Bold(escape_html(result.item_drop.name)).to_html()}"
        title_line = ""
        if result.title_unlocked:
            title_line = f"\n• 👑 <b>Title:</b> {Italic(escape_html(result.title_unlocked)).to_html()}"

        return safe_caption(
            "<b>[ DEMON CASTLE // TRIAL RESOLUTION ]</b>\n\n"
            f"👤 <b>Challenger:</b> {h_name} [Rank {Bold(escape_html(hunter.rank)).to_html()}]\n"
            f"📍 <b>Floor:</b> {floor_str} ┊ 🔑 <b>Keys:</b> {keys_str}\n\n"
            "<blockquote expandable>"
            f"{Bold(escape_html(outcome_title)).to_html()}\n"
            f"• Dealt: {InlineCode(escape_html(f'{result.damage_dealt:,} DMG')).to_html()} ┊ Taken: {InlineCode(escape_html(f'{result.damage_taken:,} DMG')).to_html()}\n"
            f"• Bounty: 💰 {InlineCode(escape_html(f'+{result.gold_gained:,} Gold')).to_html()} ┊ ✨ {InlineCode(escape_html(f'+{result.xp_gained:,} XP')).to_html()}"
            f"{loot_line}{title_line}\n"
            f"• Health: {InlineCode(escape_html(f'{hunter.hp}/{hunter.max_hp} HP')).to_html()}\n"
            "</blockquote>"
        )
    elif guardian:
        return safe_caption(
            "<b>[ DEMON CASTLE // TRIAL CHAMBER ]</b>\n\n"
            f"👤 <b>Challenger:</b> {h_name} [Rank {Bold(escape_html(hunter.rank)).to_html()}]\n"
            f"📍 <b>Floor:</b> {floor_str} ┊ 🔑 <b>Keys:</b> {keys_str}\n\n"
            "<blockquote expandable>"
            f"<b>Chamber Guardian:</b> {Bold(g_name).to_html()}\n"
            f"• Vitality: {InlineCode(escape_html(f'{guardian.hp:,} HP')).to_html()}\n"
            f"• Offense: {InlineCode(escape_html(f'{guardian.atk} ATK')).to_html()} ┊ Defense: {InlineCode(escape_html(f'{guardian.defense} DEF')).to_html()}\n"
            "</blockquote>\n\n"
            "<i>Expend 1 Demon Castle Key to challenge the guardian:</i>"
        )
    else:
        return safe_caption(
            "<b>[ DEMON CASTLE // TRIAL CHAMBER ]</b>\n\n"
            f"👤 <b>Challenger:</b> {h_name} [Rank {Bold(escape_html(hunter.rank)).to_html()}]\n"
            f"📍 <b>Floor:</b> {floor_str} ┊ 🔑 <b>Keys:</b> {keys_str}\n\n"
            "<blockquote expandable>"
            f"<b>Chamber Guardian:</b> {Bold(g_name).to_html()}\n"
            "• Status: <i>Awaiting Challenger</i>\n"
            "</blockquote>\n\n"
            "<i>Expend 1 Demon Castle Key to challenge the guardian:</i>"
        )


def build_quest_caption(hunter: Hunter) -> str:
    """Aesthetic daily quest card caption for /daily."""
    h_name = escape_html(hunter.hunter_name)
    all_done = (
        hunter.daily_quest_hunts >= 5 and
        hunter.daily_quest_explore >= 1 and
        hunter.daily_quest_duel >= 1 and
        hunter.daily_quest_use >= 1
    )
    status_tag = "✅ COMPLETED" if all_done else "⏳ IN PROGRESS"

    return safe_caption(
        "<b>[ DAILY QUEST // 강해지기 위한 준비 ]</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} [Rank {Bold(escape_html(hunter.rank)).to_html()}]\n"
        f"⚡ <b>Status:</b> {Bold(escape_html(status_tag)).to_html()}\n\n"
        "<blockquote expandable>"
        "<b>Mandatory Physical Conditioning:</b>\n"
        f"• ⚔️ Gate Hunts: {InlineCode(escape_html(f'{min(5, hunter.daily_quest_hunts)}/5')).to_html()}\n"
        f"• 🗺️ World Expeditions: {InlineCode(escape_html(f'{min(1, hunter.daily_quest_explore)}/1')).to_html()}\n"
        f"• 🤺 Hunter Duels: {InlineCode(escape_html(f'{min(1, hunter.daily_quest_duel)}/1')).to_html()}\n"
        f"• 🧪 Potion/Alchemy: {InlineCode(escape_html(f'{min(1, hunter.daily_quest_use)}/1')).to_html()}\n\n"
        "🎁 <b>Completion Reward:</b> <code>+3 Free Stat Points</code>\n"
        "</blockquote>\n\n"
        f"⚡ <b>Available Stat Points:</b> {InlineCode(escape_html(str(hunter.unspent_stat_points))).to_html()}\n"
        "<i>Allocate via /stats or buttons below:</i>"
    )


def build_forge_caption(
    hunter: Hunter,
    inventory: Inventory,
    selected_item: Item | None = None,
    notice: str | None = None,
) -> str:
    """Aesthetic forge card caption for /forge."""
    h_name = escape_html(hunter.hunter_name)

    notice_block = ""
    if notice:
        notice_block = Quote(Chain(Bold("🔥 Blacksmith Anvil:"), Italic(escape_html(notice)), sep=" ")).to_html() + "\n\n"

    if selected_item:
        enhancement_lvl = getattr(selected_item, "upgrade_level", getattr(selected_item, "enhancement", 0))
        target_block = (
            "<blockquote expandable>"
            "<b>Selected Gear for Enhancement:</b>\n"
            f"• Item: {Bold(escape_html(selected_item.name)).to_html()} {InlineCode(f'[{escape_html(selected_item.rarity)}]').to_html()}\n"
            f"• Refinement Level: {Bold(escape_html(f'+{enhancement_lvl}')).to_html()}\n"
            f"• Stats: {InlineCode(escape_html(selected_item.stat_summary())).to_html()}\n"
            "</blockquote>\n\n"
        )
    else:
        target_block = (
            "<blockquote expandable>"
            "<b>Enhancement & Synthesis Protocols:</b>\n"
            "• <i>Enhance gear from +1 to +10 for exponential stat boosts</i>\n"
            "• <i>Fuse duplicate equipment pieces to ascend rarity</i>\n"
            "</blockquote>\n\n"
        )

    return safe_caption(
        "<b>[ BLACKSMITH FORGE // 대장간 장비 강화 ]</b>\n\n"
        f"👤 <b>Artisan:</b> {h_name} [Rank {Bold(escape_html(hunter.rank)).to_html()}]\n"
        f"💰 <b>Treasury:</b> {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()}\n\n"
        f"{notice_block}"
        f"{target_block}"
        "<i>Select an item below to refine or synthesize:</i>"
    )


def build_help_caption() -> str:
    """Master /help operational manual caption."""
    return safe_caption(
        "<b>[ SYSTEM DIRECTIVE // 시스템 가이드 ]</b>\n\n"
        "<b>Solo Leveling Hunter System // Archives V2.5</b>\n\n"
        "<blockquote expandable>"
        "<b>⚡ Combat & Spire Directives:</b>\n"
        "• <code>/hunt</code> — Slay gate beasts for XP & items (1m CD, 20/day)\n"
        "• <code>/explore</code> — World map expedition (1h CD, 3/day)\n"
        "• <code>/tower</code> — 100-floor Demon Castle Spire (3 keys/day)\n"
        "• <code>/duel</code> — Challenge rival Hunter in groups\n\n"
        "<b>⚒️ Vault, Forge & Conditioning:</b>\n"
        "• <code>/profile</code> — Holographic status window & stats\n"
        "• <code>/inventory</code> — Dimensional storage & 1-tap equip\n"
        "• <code>/forge</code> — Enhance gear (+1 to +10) & fuse duplicates\n"
        "• <code>/daily</code> — Daily physical conditioning (+3 Stat Points)\n"
        "• <code>/stats</code> — Allocate stat points (STR, AGI, VIT, INT, PER)\n"
        "• <code>/use</code> — Consume potions, elixirs & scrolls\n"
        "• <code>/shop</code> — Hunter Exchange Depot (weapons & elixirs)\n"
        "• <code>/claim</code> — Daily System stipend (24h CD)\n"
        "• <code>/redeem</code> — Claim promotional & gift codes\n"
        "• <code>/guild</code> — Manage your Hunter Guild syndicate\n"
        "</blockquote>\n\n"
        + Quote(Italic("「 The System acknowledges those who strive to grow stronger. 」")).to_html()
    )


def build_help_rich() -> "RichDoc":
    """Structured main manual: TOC + collapsible sections; card photo embedded last.

    Content parity with build_help_caption() (same sections, same bullets);
    show_caption_above_media=True on the classic site -> text blocks BEFORE
    photo_block (migration rule 4).
    """
    from game.rich_message import (
        RichDoc, anchor, bullet_list, details, divider, heading, paragraph,
        photo_block, quote, toc,
    )

    sections = [
        ("⚡ Combat &amp; Spire Directives", "sec-combat", [
            "<code>/hunt</code> — Slay gate beasts for XP &amp; items (1m CD, 20/day)",
            "<code>/explore</code> — World map expedition (1h CD, 3/day)",
            "<code>/tower</code> — 100-floor Demon Castle Spire (3 keys/day)",
            "<code>/duel</code> — Challenge rival Hunter in groups",
        ]),
        ("⚒️ Vault, Forge &amp; Conditioning", "sec-vault", [
            "<code>/profile</code> — Holographic status window &amp; stats",
            "<code>/inventory</code> — Dimensional storage &amp; 1-tap equip",
            "<code>/forge</code> — Enhance gear (+1 to +10) &amp; fuse duplicates",
            "<code>/daily</code> — Daily physical conditioning (+3 Stat Points)",
            "<code>/stats</code> — Allocate stat points (STR, AGI, VIT, INT, PER)",
            "<code>/use</code> — Consume potions, elixirs &amp; scrolls",
            "<code>/shop</code> — Hunter Exchange Depot (weapons &amp; elixirs)",
            "<code>/claim</code> — Daily System stipend (24h CD)",
            "<code>/redeem</code> — Claim promotional &amp; gift codes",
            "<code>/guild</code> — Manage your Hunter Guild syndicate",
        ]),
    ]
    blocks = [
        heading(1, "[ SYSTEM DIRECTIVE // 시스템 가이드 ]"),
        paragraph("<b>Solo Leveling Hunter System // Archives V2.5</b>"),
        toc([(label, name) for label, name, _ in sections]),
        divider(),
    ]
    for label, name, items in sections:
        blocks.append(anchor(name))
        blocks.append(details(label, bullet_list(items)))
    blocks.append(quote(
        "<i>「 The System acknowledges those who strive to grow stronger. 」</i>",
        expandable=False,
    ))
    blocks.append(photo_block("help"))
    return RichDoc(*blocks)


def build_claim_caption(
    hunter: Hunter,
    reward_gold: int,
    reward_xp: int,
    streak: int = 1,
    leveled_up: bool = False,
    new_rank: str | None = None,
) -> str:
    """Aesthetic daily stipend caption for /claim."""
    h_name = escape_html(hunter.hunter_name)

    extra_lines = []
    if leveled_up:
        extra_lines.append(f"⚡ <b>LEVEL UP!</b> Reached {Bold(escape_html(f'Level {hunter.level}')).to_html()}")
    if new_rank:
        extra_lines.append(f"🔥 <b>RANK ADVANCEMENT!</b> Awakened as {Bold(f'[{escape_html(new_rank)}] Hunter').to_html()}")

    extra_block = ""
    if extra_lines:
        extra_block = "\n" + Quote(PlainText(" ".join(extra_lines))).to_html() + "\n"

    streak_line = f"• Login Streak: 🔥 {InlineCode(escape_html(f'{streak} Days')).to_html()}\n" if streak > 1 else ""

    return safe_caption(
        "<b>[ SYSTEM DAILY ALLOCATION // 보급품 지급 ]</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} [Rank {Bold(escape_html(hunter.rank)).to_html()}]\n\n"
        "<blockquote expandable>"
        "<b>✅ Daily Ration Dispatched:</b>\n"
        f"• EXP Bounty: ✨ {InlineCode(escape_html(f'+{reward_xp:,} XP')).to_html()}\n"
        f"• Treasury Bonus: 💰 {InlineCode(escape_html(f'+{reward_gold:,} G')).to_html()}\n"
        f"{streak_line}"
        f"• Total Vault: 💰 {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()}\n"
        f"• Current EXP: {InlineCode(escape_html(f'{hunter.xp:,} / {hunter.xp_needed:,} XP')).to_html()}\n"
        "</blockquote>\n"
        f"{extra_block}\n"
        + Quote(Italic("「 Return in 24 hours for your next allocation, Hunter. 」")).to_html()
    )


def build_start_welcome_caption(hunter: Hunter) -> str:
    """Aesthetic awakening welcome caption for /start."""
    h_name = escape_html(hunter.hunter_name)
    r_name = escape_html(hunter.rank)
    return safe_caption(
        "<b>[ SYSTEM AWAKENING NOTICE // 각성 확인 ]</b>\n\n"
        "<i>A new Player has been chosen by the System.</i>\n\n"
        f"👤 <b>Hunter:</b> {h_name}\n"
        f"⭐ <b>Awakened Rank:</b> {Bold(f'{r_name}-Rank').to_html()}\n"
        f"💪 <b>Combat Power:</b> {InlineCode(escape_html(f'{hunter.power:,}')).to_html()}\n\n"
        "<blockquote expandable>"
        "<b>Awakened Core Attributes:</b>\n"
        f"• STR: {InlineCode(escape_html(str(hunter.str_stat))).to_html()} ┊ AGI: {InlineCode(escape_html(str(hunter.agi))).to_html()}\n"
        f"• VIT: {InlineCode(escape_html(str(hunter.vit))).to_html()} ┊ INT: {InlineCode(escape_html(str(hunter.int_stat))).to_html()} ┊ PER: {InlineCode(escape_html(str(hunter.per))).to_html()}\n"
        "• Starter Weapon: 🗡️ <b>Rusty Short Sword</b>\n"
        f"• Initial Treasury: 💰 {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()}\n"
        "</blockquote>\n\n"
        + Quote(Italic("「 You have qualified to become a Player. 」")).to_html()
        + "\n\n<i>Use <code>/hunt</code> to enter your first gate or <code>/profile</code> to view your status.</i>"
    )


def build_start_existing_caption(hunter: Hunter) -> str:
    """Aesthetic returning hunter card caption for /start."""
    h_name = escape_html(hunter.hunter_name)
    return safe_caption(
        "<b>[ HUNTER RE-AUTHENTICATION // 헌터 인증 ]</b>\n\n"
        "<i>Welcome back, Player.</i>\n\n"
        f"👤 <b>Hunter:</b> {h_name}\n"
        f"⭐ <b>Rank:</b> {Bold(escape_html(f'{hunter.rank}-Rank')).to_html()} ┊ 📊 <b>Level:</b> {InlineCode(escape_html(str(hunter.level))).to_html()}\n"
        f"💪 <b>Combat Power:</b> {InlineCode(escape_html(f'{hunter.power:,}')).to_html()} ┊ 💰 <b>Gold:</b> {InlineCode(escape_html(f'{hunter.gold:,} G')).to_html()}\n\n"
        "<blockquote expandable>"
        "<b>Active Readiness:</b>\n"
        f"• Gate Hunts: {InlineCode(escape_html(f'{hunter.daily_hunts}/20')).to_html()}\n"
        f"• Demon Castle: Floor {InlineCode(escape_html(f'{hunter.tower_floor}/100')).to_html()} (🔑 {InlineCode(escape_html(f'{hunter.tower_keys}/3')).to_html()})\n"
        f"• Vitality: {InlineCode(escape_html(f'{hunter.hp}/{hunter.max_hp} HP')).to_html()}\n"
        "</blockquote>\n\n"
        "<i>Type <code>/hunt</code> to enter combat, or <code>/help</code> for all directives.</i>"
    )


def build_duel_challenge_caption(challenger: Hunter, opponent: Hunter) -> str:
    """Aesthetic challenge invitation card caption for /duel."""
    c_name = escape_html(challenger.display_full_name)
    o_name = escape_html(opponent.display_full_name)
    return safe_caption(
        "<b>[ COMBAT ARENA CHALLENGE // 대련 신청 ]</b>\n\n"
        f"💥 <b>Challenger:</b> {c_name} [Rank {Bold(escape_html(challenger.rank)).to_html()} ┊ Lv. {InlineCode(escape_html(str(challenger.level))).to_html()}]\n"
        f"🎯 <b>Challenged:</b> {o_name} [Rank {Bold(escape_html(opponent.rank)).to_html()} ┊ Lv. {InlineCode(escape_html(str(opponent.level))).to_html()}]\n\n"
        "<blockquote expandable>"
        "<b>Combat Arena Rules:</b>\n"
        "• Victor claims glory, bonus Gold & Awakening XP\n"
        f"• Only {Bold(o_name).to_html()} can accept or decline this duel\n"
        "</blockquote>\n\n"
        "<i>Respond to the challenge using the controls below:</i>"
    )


def build_duel_result_caption(result: Any) -> str:
    """Aesthetic combat resolution card caption for /duel."""
    winner_name = escape_html(result.winner.display_full_name)
    loser_name = escape_html(result.loser.display_full_name)
    lvl_line = ""
    if getattr(result, "winner_leveled_up", False) and getattr(result, "winner_new_level", None):
        lvl_line = f"\n• ⭐ <b>Ascension:</b> {winner_name} reached {Bold(escape_html(f'Level {result.winner_new_level}')).to_html()}!"

    w_dmg = result.challenger_damage_dealt if result.winner.user_id == result.challenger.user_id else result.opponent_damage_dealt
    l_dmg = result.opponent_damage_dealt if result.winner.user_id == result.challenger.user_id else result.challenger_damage_dealt

    return safe_caption(
        "<b>[ COMBAT ARENA RESOLUTION // 대련 결과 ]</b>\n\n"
        f"👑 <b>Victor:</b> {Bold(winner_name).to_html()} [Rank {Bold(escape_html(result.winner.rank)).to_html()}]\n"
        f"💀 <b>Defeated:</b> {Bold(loser_name).to_html()} [Rank {Bold(escape_html(result.loser.rank)).to_html()}]\n\n"
        "<blockquote expandable>"
        "<b>Combat Performance:</b>\n"
        f"• {winner_name}: {InlineCode(escape_html(f'{w_dmg:,} DMG')).to_html()} dealt\n"
        f"• {loser_name}: {InlineCode(escape_html(f'{l_dmg:,} DMG')).to_html()} dealt\n"
        f"• Spoils: 💰 {InlineCode(escape_html(f'+{result.winner_gold_gained:,} Gold')).to_html()} ┊ ✨ {InlineCode(escape_html(f'+{result.winner_xp_gained:,} XP')).to_html()}\n"
        f"• Consolation: ✨ {InlineCode(escape_html(f'+{result.loser_xp_gained:,} XP')).to_html()}"
        f"{lvl_line}\n"
        "</blockquote>\n\n"
        "<i>Outcome permanently archived in Hunter Arena records.</i>"
    )


def build_leaderboard_caption(category: str = "power") -> str:
    """Aesthetic caption for /leaderboard."""
    cat_titles = {
        "power": "Combat Power",
        "level": "Hunter Level",
        "wealth": "Gold Wealth",
        "victories": "Dungeon Victories",
        "trophies": "War Trophies",
    }
    cat_name = cat_titles.get(category, category.title())
    return safe_caption(
        f"{Bold(f'[ HALL OF FAME // {cat_name.upper()} ]').to_html()}\n\n"
        f"📊 <b>Category:</b> {InlineCode(escape_html(cat_name)).to_html()}\n\n"
        "<blockquote expandable>"
        "<b>Rankings Directory:</b>\n"
        "• Visual ranking matrix displayed on the HUD card above.\n"
        "• Switch classification tabs using the controls below.\n"
        "</blockquote>\n\n"
        "<i>Updated in real-time from Hunter Association records.</i>"
    )


def build_guild_caption(guild: Any, member_count: int, total_power: int, max_members: int = 15) -> str:
    """Aesthetic caption for /guild cards."""
    g_name = escape_html(guild.name)
    desc = escape_html(guild.description or "No description recorded.")
    return safe_caption(
        f"{Bold(f'[ GUILD REGISTRY // {g_name.upper()} ]').to_html()}\n\n"
        f"🏰 <b>Syndicate:</b> {Bold(g_name).to_html()} (ID: {InlineCode(escape_html(f'#{guild.guild_id}')).to_html()})\n"
        f"👥 <b>Roster:</b> {InlineCode(escape_html(f'{member_count}/{max_members}')).to_html()} ┊ ⚡ <b>Power:</b> {InlineCode(escape_html(f'{total_power:,}')).to_html()}\n"
        f"🏆 <b>War Score:</b> {InlineCode(escape_html(str(guild.war_score))).to_html()} (W: {InlineCode(escape_html(str(guild.war_wins))).to_html()} / L: {InlineCode(escape_html(str(guild.war_losses))).to_html()})\n\n"
        "<blockquote expandable>"
        f"📝 <b>Guild Creed:</b> {Italic(desc).to_html()}\n"
        "• Active Syndicate Perk: 🎁 <b>+10% EXP on all Hunts</b>\n"
        "</blockquote>\n\n"
        "<i>Use controls below to navigate guilds, view members, or declare war:</i>"
    )


def build_war_challenge_caption(
    sender_guild_name: str,
    target_guild_name: str,
    challenger_power: int,
    defender_power: int,
) -> str:
    """Aesthetic challenge caption for /guild war declaration."""
    s_name = escape_html(sender_guild_name)
    t_name = escape_html(target_guild_name)
    return safe_caption(
        "<b>[ GUILD WAR DECLARATION // 길드전 선포 ]</b>\n\n"
        f"🏰 <b>Challenger:</b> {Bold(s_name).to_html()} (⚡{InlineCode(escape_html(f'{challenger_power:,}')).to_html()})\n"
        f"🛡️ <b>Target:</b> {Bold(t_name).to_html()} (⚡{InlineCode(escape_html(f'{defender_power:,}')).to_html()})\n\n"
        "<blockquote expandable>"
        "<b>Notice to Opposing Sovereign:</b>\n"
        f"• {Bold(s_name).to_html()} has issued an official challenge to {Bold(t_name).to_html()}.\n"
        "• Target Sovereign must respond to initiate combat or forfeit.\n"
        "</blockquote>\n\n"
        "<i>Respond using the controls below:</i>"
    )


def build_war_status_caption(
    challenger_guild_name: str,
    defender_guild_name: str,
    challenger_wins: int,
    defender_wins: int,
    current_match: int,
    total_matches: int,
) -> str:
    """Aesthetic status caption for an active guild war in progress."""
    cg_name = escape_html(challenger_guild_name)
    dg_name = escape_html(defender_guild_name)
    return safe_caption(
        "<b>[ GUILD WAR IN PROGRESS // 길드전 진행 ]</b>\n\n"
        f"🏰 {Bold(cg_name).to_html()} [{InlineCode(escape_html(str(challenger_wins))).to_html()}] vs [{InlineCode(escape_html(str(defender_wins))).to_html()}] {Bold(dg_name).to_html()}\n\n"
        "<blockquote expandable>"
        f"• Current Engagement: {InlineCode(escape_html(f'{current_match}/{total_matches}')).to_html()} battles\n"
        "• Outcome updating in real-time.\n"
        "</blockquote>"
    )
