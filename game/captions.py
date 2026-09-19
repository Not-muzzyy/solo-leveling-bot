"""
game/captions.py — Reusable Telegram Rich Text Caption Templates (HTML Mode).

Implements aesthetic, structured card templates in accordance with telegram_rich_text_formatting.md:
- Header banner: <b>╭━━━「 ICON TITLE 」━━━╮</b>
- Bold field labels: <b>👤 Hunter:</b> Name [Rank <b>E</b>]
- Escaped dynamic data and <code> tags for stats & numbers
- Semantic <blockquote> blocks for lore, status matrices, and combat reports
- Footer banner: <b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>
- Strict caption length safety (<= 1024 chars for Telegram media captions) via safe_caption()
"""

from __future__ import annotations

from typing import Any, Optional
from config import RANK_EMOJI, RARITY_EMOJI
from models import Hunter, Inventory, Item, HuntResult
from game.rich_text import escape_html, safe_caption


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
        "<b>╭━━━「 ⚔️ HUNTER STATUS MATRIX 」━━━╮</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name}\n"
        f"🏅 <b>Rank:</b> {rank_icon} <b>{hunter.rank}-Rank</b> ┊ 📊 <b>Lv:</b> <code>{hunter.level}</code>\n"
        f"🎖️ <b>Title:</b> <i>{title_str}</i>\n"
        f"⚡ <b>Power:</b> <code>{hunter.power:,}</code> ┊ 💰 <b>Gold:</b> <code>{hunter.gold:,} G</code>\n\n"
        "<blockquote>"
        "<b>📈 Core Attributes:</b>\n"
        f"• STR: <code>{hunter.str_stat}</code> ┊ AGI: <code>{hunter.agi}</code> ┊ VIT: <code>{hunter.vit}</code>\n"
        f"• INT: <code>{hunter.int_stat}</code> ┊ PER: <code>{hunter.per}</code>\n"
        f"• HP: <code>{hunter.hp}/{hunter.max_hp}</code> ┊ XP: <code>{hunter.xp}/{hunter.xp_needed}</code>\n"
        f"• Gear: 🗡️ {w_name} ┊ 🛡️ {a_name} ┊ 💍 {acc_name}\n"
        "</blockquote>\n\n"
        "<blockquote><i>「 The System has acknowledged your awakening. 」</i></blockquote>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )


def build_hunt_caption(hunter: Hunter, result: HuntResult) -> str:
    """Aesthetic combat resolution card caption for /hunt."""
    m_name = escape_html(result.monster.name)
    m_rank = escape_html(result.monster.rank)
    quota_str = f"<code>{hunter.daily_hunts}/20</code>"

    if result.victory:
        loot_line = ""
        if result.item_drop:
            i_name = escape_html(result.item_drop.name)
            i_rarity = escape_html(result.item_drop.rarity)
            loot_line = f"\n• 🎁 <b>Loot:</b> <code>[{i_rarity}]</code> <b>{i_name}</b>"

        return safe_caption(
            "<b>╭━━━「 ⚔️ DUNGEON HUNT REPORT 」━━━╮</b>\n\n"
            f"🎯 <b>Target:</b> <b>{m_name}</b> [<b>{m_rank}-Rank</b>]\n"
            f"👤 <b>Hunter:</b> <b>{escape_html(hunter.hunter_name)}</b> [Rank <b>{hunter.rank}</b>]\n\n"
            "<blockquote>"
            "<b>✅ VICTORY ACHIEVED!</b>\n"
            f"• Dealt: <code>{result.damage_dealt} DMG</code> ┊ Taken: <code>{result.damage_taken} DMG</code>\n"
            f"• Bounty: 💰 <code>+{result.gold_gained:,} Gold</code> ┊ ✨ <code>+{result.xp_gained:,} XP</code>"
            f"{loot_line}\n"
            f"• Vitality: <code>{hunter.hp}/{hunter.max_hp} HP</code>\n"
            "</blockquote>\n\n"
            f"📊 <b>Daily Limit:</b> {quota_str} (1m CD)\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
        )
    else:
        return safe_caption(
            "<b>╭━━━「 ☠️ COMBAT CASUALTY REPORT 」━━━╮</b>\n\n"
            f"🎯 <b>Monster:</b> <b>{m_name}</b> [<b>{m_rank}-Rank</b>]\n"
            f"👤 <b>Hunter:</b> <b>{escape_html(hunter.hunter_name)}</b> [Rank <b>{hunter.rank}</b>]\n\n"
            "<blockquote>"
            "<b>❌ MISSION FAILED — DEFEAT</b>\n"
            f"• Dealt: <code>{result.damage_dealt} DMG</code> ┊ Taken: <code>{result.damage_taken} DMG</code>\n"
            f"• Lost: 💰 <code>-{result.gold_lost:,} Gold</code>\n"
            f"• Consolation: ✨ <code>+{result.xp_gained:,} XP</code>\n"
            f"• Vitality: <code>{hunter.hp}/{hunter.max_hp} HP</code> (Potion/Heal needed)\n"
            "</blockquote>\n\n"
            f"📊 <b>Daily Limit:</b> {quota_str} (1m CD)\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
    quota_str = f"<code>{hunter.daily_explores}/3</code>"

    gift_block = ""
    if gift_item:
        g_name = escape_html(gift_item.name)
        g_rarity = escape_html(gift_item.rarity)
        g_stats = escape_html(gift_item.stat_summary())
        gift_block = f"\n• 🎁 <b>Artifact Found:</b> <code>[{g_rarity}]</code> <b>{g_name}</b> (<i>{g_stats}</i>)"

    ascend_block = ""
    if leveled_up or new_rank:
        asc_lines = []
        if leveled_up:
            asc_lines.append(f"⚡ <b>Level Up:</b> Hunter reached Level <b>{hunter.level}</b>!")
        if new_rank:
            asc_lines.append(f"👑 <b>Rank Awakening:</b> Awakened as <b>[{escape_html(new_rank)}] Hunter</b>!")
        ascend_block = f"<blockquote>{' '.join(asc_lines)}</blockquote>\n\n"

    return safe_caption(
        f"<b>╭━━━「 🗺️ SYSTEM EXPEDITION // {s_name} 」━━━╮</b>\n\n"
        f"👤 <b>Scout:</b> {d_name} [Rank <b>{hunter.rank}</b> | Lv. <code>{hunter.level}</code>]\n\n"
        "<blockquote>"
        "<b>📜 Field Reconnaissance:</b>\n"
        f"<i>{story_esc}</i>\n\n"
        f"• 💰 <b>Treasury Bounty:</b> <code>+{gold_reward:,} Gold</code>\n"
        f"• ✨ <b>Exp Bounty:</b> <code>+{xp_reward:,} XP</code>"
        f"{gift_block}\n"
        "</blockquote>\n\n"
        f"{ascend_block}"
        f"📊 <b>Daily Expeditions:</b> {quota_str} Completed (1h CD)\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
        notice_block = f"<blockquote><b>⚡ System Notice:</b> <i>{escape_html(notice)}</i></blockquote>\n\n"

    return safe_caption(
        f"<b>╭━━━「 🎒 DIMENSIONAL INVENTORY // {cat_title} 」━━━╮</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} [Rank <b>{hunter.rank}</b>]\n"
        f"💰 <b>Treasury:</b> <code>{hunter.gold:,} G</code> ┊ 📦 <b>Stored Items:</b> <code>{total_items}</code>\n\n"
        f"{notice_block}"
        "<blockquote>"
        "<b>⚔️ Currently Bound Equipment:</b>\n"
        f"• 🗡️ Weapon: <b>{w_str}</b>\n"
        f"• 🛡️ Armor: <b>{a_str}</b>\n"
        f"• 💍 Accessory: <b>{acc_str}</b>\n"
        "</blockquote>\n\n"
        "<i>Tap the buttons below to switch tabs or manage gear:</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
        notice_block = f"<blockquote><b>✅ Purchase Confirmed:</b> <i>{escape_html(notice)}</i></blockquote>\n\n"

    return safe_caption(
        f"<b>╭━━━「 🛒 HUNTER EXCHANGE DEPOT // {cat_title} 」━━━╮</b>\n\n"
        f"👤 <b>Customer:</b> {h_name} [Rank <b>{hunter.rank}</b>]\n"
        f"💰 <b>Available Treasury:</b> <code>{hunter.gold:,} G</code>\n\n"
        f"{notice_block}"
        "<blockquote>"
        "<b>System Black Market:</b>\n"
        "<i>Purchase graded weapons, defense armors, accessories, and restorative potions directly from Association vaults.</i>\n"
        "</blockquote>\n\n"
        "<i>Select an item category or equipment piece below:</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
    keys_str = f"<code>{hunter.tower_keys}/3</code>"
    floor_str = f"<code>{hunter.tower_floor}/100</code>"

    if result:
        outcome_title = "✅ FLOOR CLEARED!" if result.victory else "☠️ CHALLENGER FALLEN!"
        loot_line = ""
        if result.item_drop:
            loot_line = f"\n• 🎁 <b>Drop:</b> <code>[{escape_html(result.item_drop.rarity)}]</code> <b>{escape_html(result.item_drop.name)}</b>"
        title_line = ""
        if result.title_unlocked:
            title_line = f"\n• 👑 <b>Title:</b> <i>{escape_html(result.title_unlocked)}</i>"

        return safe_caption(
            "<b>╭━━━「 🏰 DEMON CASTLE SPIRE // RESOLUTION 」━━━╮</b>\n\n"
            f"👤 <b>Challenger:</b> {h_name} [Rank <b>{hunter.rank}</b>]\n"
            f"📍 <b>Floor:</b> {floor_str} ┊ 🔑 <b>Keys:</b> {keys_str}\n\n"
            "<blockquote>"
            f"<b>{outcome_title}</b>\n"
            f"• Dealt: <code>{result.damage_dealt} DMG</code> ┊ Taken: <code>{result.damage_taken} DMG</code>\n"
            f"• Bounty: 💰 <code>+{result.gold_gained:,} Gold</code> ┊ ✨ <code>+{result.xp_gained:,} XP</code>"
            f"{loot_line}{title_line}\n"
            f"• Health: <code>{hunter.hp}/{hunter.max_hp} HP</code>\n"
            "</blockquote>\n\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
        )
    else:
        return safe_caption(
            "<b>╭━━━「 🏰 DEMON CASTLE SPIRE // CHAMBER 」━━━╮</b>\n\n"
            f"👤 <b>Challenger:</b> {h_name} [Rank <b>{hunter.rank}</b>]\n"
            f"📍 <b>Floor:</b> {floor_str} ┊ 🔑 <b>Keys:</b> {keys_str}\n\n"
            "<blockquote>"
            f"<b>Chamber Guardian:</b> <b>{g_name}</b>\n"
            f"• Vitality: <code>{guardian.hp:,} HP</code>\n"
            f"• Offense: <code>{guardian.atk} ATK</code> ┊ Defense: <code>{guardian.defense} DEF</code>\n"
            "</blockquote>\n\n"
            "<i>Tap below to expend 1 Key and battle the guardian:</i>\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
        "<b>╭━━━「 📋 DAILY PHYSICAL CONDITIONING 」━━━╮</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} [Rank <b>{hunter.rank}</b>]\n"
        f"⚡ <b>Status:</b> <b>{status_tag}</b>\n\n"
        "<blockquote>"
        "<b>Mandatory Directives (Penalty upon failure):</b>\n"
        f"• ⚔️ Gate Hunts: <code>{min(5, hunter.daily_quest_hunts)}/5</code>\n"
        f"• 🗺️ World Expeditions: <code>{min(1, hunter.daily_quest_explore)}/1</code>\n"
        f"• 🤺 Hunter Duels: <code>{min(1, hunter.daily_quest_duel)}/1</code>\n"
        f"• 🧪 Potion/Alchemy: <code>{min(1, hunter.daily_quest_use)}/1</code>\n\n"
        "🎁 <b>Completion Reward:</b> <code>+3 Free Stat Points</code>\n"
        "</blockquote>\n\n"
        f"⚡ <b>Available Stat Points:</b> <code>{hunter.unspent_stat_points}</code>\n"
        "<i>Allocate via /stats or buttons below:</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
        notice_block = f"<blockquote><b>🔥 Blacksmith Anvil:</b> <i>{escape_html(notice)}</i></blockquote>\n\n"

    if selected_item:
        enhancement_lvl = getattr(selected_item, "upgrade_level", getattr(selected_item, "enhancement", 0))
        target_block = (
            "<blockquote>"
            "<b>Selected Gear for Enhancement:</b>\n"
            f"• Item: <b>{escape_html(selected_item.name)}</b> <code>[{escape_html(selected_item.rarity)}]</code>\n"
            f"• Refinement Level: <b>+{enhancement_lvl}</b>\n"
            f"• Stats: <code>{escape_html(selected_item.stat_summary())}</code>\n"
            "</blockquote>\n\n"
        )
    else:
        target_block = (
            "<blockquote>"
            "<b>Enhancement & Synthesis Protocols:</b>\n"
            "• <i>Enhance gear from +1 to +10 for exponential stat boosts</i>\n"
            "• <i>Fuse duplicate equipment pieces to ascend rarity</i>\n"
            "</blockquote>\n\n"
        )

    return safe_caption(
        "<b>╭━━━「 ⚒️ BLACKSMITH'S ANVIL & SYNTHESIS 」━━━╮</b>\n\n"
        f"👤 <b>Artisan:</b> {h_name} [Rank <b>{hunter.rank}</b>]\n"
        f"💰 <b>Treasury:</b> <code>{hunter.gold:,} G</code>\n\n"
        f"{notice_block}"
        f"{target_block}"
        "<i>Select an item below to refine or synthesize:</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )


def build_help_caption() -> str:
    """Master /help operational manual caption."""
    return safe_caption(
        "<b>╭━━━「 📖 SYSTEM OPERATIONAL MANUAL 」━━━╮</b>\n\n"
        "<b>Solo Leveling Hunter System // Archives V2.5</b>\n\n"
        "<blockquote>"
        "<b>⚡ Combat & Spire Directives:</b>\n"
        "• <code>/hunt</code> — Slay gate beasts for XP & items (1m CD, 20/day)\n"
        "• <code>/explore</code> — World map expedition (1h CD, 3/day)\n"
        "• <code>/tower</code> — 100-floor Demon Castle Spire (3 keys/day)\n"
        "• <code>/duel</code> — Challenge rival Hunter in groups\n"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>⚒️ Vault, Forge & Conditioning:</b>\n"
        "• <code>/profile</code> — Holographic status window & stats\n"
        "• <code>/inventory</code> — Dimensional storage & 1-tap equip\n"
        "• <code>/forge</code> — Enhance gear (+1 to +10) & fuse duplicates\n"
        "• <code>/daily</code> — Daily physical conditioning (+3 Stat Points)\n"
        "• <code>/stats</code> — Allocate stat points (STR, AGI, VIT, INT, PER)\n"
        "• <code>/use</code> — Consume potions, elixirs & scrolls\n"
        "• <code>/shop</code> — Hunter Exchange Depot (weapons & elixirs)\n"
        "• <code>/claim</code> — Daily System stipend (24h CD)\n"
        "• <code>/redeem</code> — Claim System promotional & gift codes\n"
        "• <code>/guild</code> — Manage your Hunter Guild syndicate\n"
        "</blockquote>\n\n"
        "<blockquote><i>「 The System acknowledges those who strive to grow stronger. 」</i></blockquote>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )


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
        extra_lines.append(f"⚡ <b>LEVEL UP!</b> Reached <b>Level {hunter.level}</b>")
    if new_rank:
        extra_lines.append(f"🔥 <b>RANK ADVANCEMENT!</b> Awakened as <b>[{escape_html(new_rank)}] Hunter</b>")

    extra_block = ""
    if extra_lines:
        extra_block = f"\n<blockquote>{' '.join(extra_lines)}</blockquote>\n"

    streak_line = f"• Login Streak: 🔥 <code>{streak} Days</code>\n" if streak > 1 else ""

    return safe_caption(
        "<b>╭━━━「 💰 SYSTEM DAILY STIPEND 」━━━╮</b>\n\n"
        f"👤 <b>Hunter:</b> {h_name} [Rank <b>{hunter.rank}</b>]\n\n"
        "<blockquote>"
        "<b>✅ Daily Ration Dispatched:</b>\n"
        f"• EXP Bounty: ✨ <code>+{reward_xp:,} XP</code>\n"
        f"• Treasury Bonus: 💰 <code>+{reward_gold:,} G</code>\n"
        f"{streak_line}"
        f"• Total Vault: 💰 <code>{hunter.gold:,} G</code>\n"
        f"• Current EXP: <code>{hunter.xp:,} / {hunter.xp_needed:,} XP</code>\n"
        "</blockquote>\n"
        f"{extra_block}\n"
        "<blockquote><i>「 Return in 24 hours for your next allocation, Hunter. 」</i></blockquote>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )


def build_start_welcome_caption(hunter: Hunter) -> str:
    """Aesthetic awakening welcome caption for /start."""
    h_name = escape_html(hunter.hunter_name)
    r_name = escape_html(hunter.rank)
    return safe_caption(
        "<b>╭━━━「 ⚡ SYSTEM AWAKENING NOTICE 」━━━╮</b>\n\n"
        "<i>A new Player has been chosen by the System.</i>\n\n"
        f"👤 <b>Hunter:</b> {h_name}\n"
        f"⭐ <b>Awakened Rank:</b> <b>{r_name}-Rank</b>\n"
        f"💪 <b>Combat Power:</b> <code>{hunter.power:,}</code>\n\n"
        "<blockquote>"
        "<b>Awakened Core Attributes:</b>\n"
        f"• STR: <code>{hunter.str_stat}</code> ┊ AGI: <code>{hunter.agi}</code>\n"
        f"• VIT: <code>{hunter.vit}</code> ┊ INT: <code>{hunter.int_stat}</code> ┊ PER: <code>{hunter.per}</code>\n"
        "• Starter Weapon: 🗡️ <b>Rusty Short Sword</b>\n"
        f"• Initial Treasury: 💰 <code>{hunter.gold:,} G</code>\n"
        "</blockquote>\n\n"
        "<blockquote><i>「 You have qualified to become a Player. 」</i></blockquote>\n\n"
        "<i>Use <code>/hunt</code> to enter your first gate or <code>/profile</code> to view your status.</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )


def build_start_existing_caption(hunter: Hunter) -> str:
    """Aesthetic returning hunter card caption for /start."""
    h_name = escape_html(hunter.hunter_name)
    return safe_caption(
        "<b>╭━━━「 ⚡ HUNTER SYSTEM CONNECTED 」━━━╮</b>\n\n"
        "<i>Welcome back, Player.</i>\n\n"
        f"👤 <b>Hunter:</b> {h_name}\n"
        f"⭐ <b>Rank:</b> <b>{hunter.rank}-Rank</b> ┊ 📊 <b>Level:</b> <code>{hunter.level}</code>\n"
        f"💪 <b>Combat Power:</b> <code>{hunter.power:,}</code> ┊ 💰 <b>Gold:</b> <code>{hunter.gold:,} G</code>\n\n"
        "<blockquote>"
        "<b>Active Readiness:</b>\n"
        f"• Gate Hunts: <code>{hunter.daily_hunts}/20</code>\n"
        f"• Demon Castle: Floor <code>{hunter.tower_floor}/100</code> (🔑 <code>{hunter.tower_keys}/3</code>)\n"
        f"• Vitality: <code>{hunter.hp}/{hunter.max_hp} HP</code>\n"
        "</blockquote>\n\n"
        "<i>Type <code>/hunt</code> to enter combat, or <code>/help</code> for all directives.</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )


def build_duel_challenge_caption(challenger: Hunter, opponent: Hunter) -> str:
    """Aesthetic challenge invitation card caption for /duel."""
    c_name = escape_html(challenger.display_full_name)
    o_name = escape_html(opponent.display_full_name)
    return safe_caption(
        "<b>╭━━━「 ⚔️ HUNTER DUEL CHALLENGE 」━━━╮</b>\n\n"
        f"💥 <b>Challenger:</b> {c_name} [Rank <b>{challenger.rank}</b> ┊ Lv. <code>{challenger.level}</code>]\n"
        f"🎯 <b>Challenged:</b> {o_name} [Rank <b>{opponent.rank}</b> ┊ Lv. <code>{opponent.level}</code>]\n\n"
        "<blockquote>"
        "<b>Combat Arena Staking:</b>\n"
        "• Victor claims glory, bonus Gold & Awakening XP\n"
        f"• Only <b>{o_name}</b> can accept or decline this duel\n"
        "</blockquote>\n\n"
        "<i>Tap the buttons below to respond to the challenge:</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )


def build_duel_result_caption(result: Any) -> str:
    """Aesthetic combat resolution card caption for /duel."""
    winner_name = escape_html(result.winner.display_full_name)
    loser_name = escape_html(result.loser.display_full_name)
    lvl_line = ""
    if getattr(result, "winner_leveled_up", False) and getattr(result, "winner_new_level", None):
        lvl_line = f"\n• ⭐ <b>Ascension:</b> {winner_name} reached <b>Level {result.winner_new_level}</b>!"

    w_dmg = result.challenger_damage_dealt if result.winner.user_id == result.challenger.user_id else result.opponent_damage_dealt
    l_dmg = result.opponent_damage_dealt if result.winner.user_id == result.challenger.user_id else result.challenger_damage_dealt

    return safe_caption(
        "<b>╭━━━「 ⚔️ ARENA DUEL RESOLUTION 」━━━╮</b>\n\n"
        f"👑 <b>Victor:</b> <b>{winner_name}</b> [Rank <b>{result.winner.rank}</b>]\n"
        f"💀 <b>Defeated:</b> <b>{loser_name}</b> [Rank <b>{result.loser.rank}</b>]\n\n"
        "<blockquote>"
        "<b>Combat Performance:</b>\n"
        f"• {winner_name}: <code>{w_dmg:,} DMG</code> dealt\n"
        f"• {loser_name}: <code>{l_dmg:,} DMG</code> dealt\n"
        f"• Spoils: 💰 <code>+{result.winner_gold_gained:,} Gold</code> ┊ ✨ <code>+{result.winner_xp_gained:,} XP</code>\n"
        f"• Consolation: ✨ <code>+{result.loser_xp_gained:,} XP</code>"
        f"{lvl_line}\n"
        "</blockquote>\n\n"
        "<i>Combat outcome archived in official Hunter Arena records.</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
        f"<b>╭━━━「 🏆 SYSTEM LEADERBOARD // {cat_name.upper()} 」━━━╮</b>\n\n"
        f"📊 <b>Category:</b> <code>{escape_html(cat_name)}</code>\n\n"
        "<blockquote>"
        "<b>Rankings Directory:</b>\n"
        "• Visual ranking matrix displayed on the HUD card above.\n"
        "• Switch classification tabs using the controls below.\n"
        "</blockquote>\n\n"
        "<i>Updated in real-time from Hunter Association records.</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )


def build_guild_caption(guild: Any, member_count: int, total_power: int, max_members: int = 15) -> str:
    """Aesthetic caption for /guild cards."""
    g_name = escape_html(guild.name)
    desc = escape_html(guild.description or "No description recorded.")
    return safe_caption(
        f"<b>╭━━━「 🏰 GUILD DIRECTORY // {g_name.upper()} 」━━━╮</b>\n\n"
        f"🏰 <b>Syndicate:</b> <b>{g_name}</b> (ID: <code>#{guild.guild_id}</code>)\n"
        f"👥 <b>Roster:</b> <code>{member_count}/{max_members}</code> ┊ ⚡ <b>Power:</b> <code>{total_power:,}</code>\n"
        f"🏆 <b>War Score:</b> <code>{guild.war_score}</code> (W: <code>{guild.war_wins}</code> / L: <code>{guild.war_losses}</code>)\n\n"
        "<blockquote>"
        f"📝 <b>Guild Creed:</b> <i>{desc}</i>\n"
        "• Active Syndicate Perk: 🎁 <b>+10% EXP on all Hunts</b>\n"
        "</blockquote>\n\n"
        "<i>Use controls below to navigate guilds, view members, or declare war:</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
        "<b>╭━━━「 ⚔️ GUILD WAR DECLARATION 」━━━╮</b>\n\n"
        f"🏰 <b>Challenger:</b> <b>{s_name}</b> (⚡<code>{challenger_power:,}</code>)\n"
        f"🛡️ <b>Target:</b> <b>{t_name}</b> (⚡<code>{defender_power:,}</code>)\n\n"
        "<blockquote>"
        "<b>Notice to Opposing Sovereign:</b>\n"
        f"• <b>{s_name}</b> has issued an official challenge to <b>{t_name}</b>.\n"
        "• Target Sovereign must respond to initiate combat or forfeit.\n"
        "</blockquote>\n\n"
        "<i>Respond using the controls below:</i>\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
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
        "<b>╭━━━「 ⚔️ GUILD WAR IN PROGRESS 」━━━╮</b>\n\n"
        f"🏰 <b>{cg_name}</b> [<code>{challenger_wins}</code>] vs [<code>{defender_wins}</code>] <b>{dg_name}</b>\n\n"
        "<blockquote>"
        f"• Current Engagement: <code>{current_match}/{total_matches}</code> battles\n"
        "• Outcome updating in real-time."
        "</blockquote>\n\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )
