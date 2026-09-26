"""
handlers/help.py — /help command handler.

Provides an atmospheric, image-based Operational Manual card (Hallmark standard)
outlining all available commands, gameplay mechanics, rank progression, and drop rates.
Supports interactive topic tabs (Combat, Forge, Quests, Guilds, Ranks, Admin)
both via inline buttons and /help <topic> commands.
In group chats, directs users to open the guide in private chat (PM) to avoid chat clutter.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from pyrogram import Client, enums
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from config import OWNER_ID, SUPERADMIN_IDS
from game.captions import build_help_caption, build_help_rich
from game.help_image import generate_help_image
from game.rich_message import (
    RawRichDoc, RichDoc, anchor, bullet_list, details, divider, footer,
    heading, number_list, paragraph, quote, toc,
)
from game.rich_send import edit_rich, photo_media, reply_rich, send_rich
from game.rich_text import escape_html

logger = logging.getLogger(__name__)

HELP_CAPTION = build_help_caption()

HELP_FALLBACK_TEXT = (
    "<b>[ SYSTEM DIRECTIVE // 시스템 가이드 ]</b>\n\n"
    "<b>Solo Leveling Hunter System // Archives V2.5</b>\n\n"
    "<blockquote expandable>"
    "⚔️ <b>Combat & Spire Directives:</b>\n"
    "• <code>/hunt</code> — Slay gate beasts for XP & items (1m CD, 20/day)\n"
    "• <code>/explore</code> — World map expedition (1h CD, 3/day)\n"
    "• <code>/tower</code> — 100-floor Demon Castle Spire (3 keys/day)\n"
    "• <code>/duel</code> — Challenge rival Hunter in groups\n\n"
    "⚒️ <b>Vault, Forge & Conditioning:</b>\n"
    "• <code>/start</code> — Awaken as a Hunter & claim starter weapon\n"
    "• <code>/profile</code> — Status matrix & equipped gear\n"
    "• <code>/inventory</code> — Dimensional storage & 1-tap equip\n"
    "• <code>/forge</code> — Enhance gear (+1 to +10) & fuse duplicates\n"
    "• <code>/daily</code> — Daily physical conditioning (+3 Stat Points)\n"
    "• <code>/stats</code> — Allocate stat points (STR, AGI, VIT, INT, PER)\n"
    "• <code>/use</code> / <code>/heal</code> — Consume potions & elixirs\n"
    "• <code>/shop</code> — Exchange Depot (weapons, armors & potions)\n"
    "• <code>/leaderboard</code> — Hall of Fame rankings\n"
    "• <code>/claim</code> — Daily System stipend (24h CD)\n"
    "• <code>/redeem &lt;CODE&gt;</code> — Claim promotional codes\n"
    "• <code>/guild</code> — Manage syndicate & declare wars\n\n"
    "👑 <b>Shadow Monarch Army:</b>\n"
    "• <code>/arise &lt;name&gt;</code> — Extract wild shadows spawned in group rifts\n"
    "• <code>/shadows</code> — Inspect your Shadow Monarch Army collection\n\n"
    "⭐ <b>Hunter Rank Progression:</b>\n"
    "E → D → C → B → A → S → SS → SSS → National Level → Monarch\n\n"
    "💎 <b>Item Rarity Spectrum:</b>\n"
    "⚪ Common (50%) → 🟢 Uncommon (25%) → 🔵 Rare (15%) → 🟣 Epic (7%) → 🟡 Legendary (2.5%) → 🔴 Mythic (0.5%)\n"
    "</blockquote>\n\n"
    "<blockquote><i>「 The System acknowledges those who strive to grow stronger. 」</i></blockquote>"
)

# ── TOPIC DETAIL TEXTS ────────────────────────────────────────────────────────
TOPIC_TEXTS = {
    "combat": (
        "<b>[ SYSTEM DIRECTIVE // COMBAT & SPIRE ]</b>\n\n"
        "<blockquote expandable>"
        "🚪 <b>Dimensional Gate Hunts (<code>/hunt</code>)</b>\n"
        "• Slay gate monsters ranging from E-Rank beasts to S-Rank Calamities.\n"
        "• <b>Cooldown:</b> 1 minute ┊ <b>Daily Limit:</b> 20 hunts/day.\n"
        "• Drops: Hunter XP, Gold, Weapons, Armor, Rings, Potions & Ores.\n"
        "• Monsters deal damage to your HP! Monitor vitality and drink potions via <code>/use</code> or <code>/heal</code>.\n\n"
        "🗺️ <b>Uncharted World Map Expeditions (<code>/explore</code>)</b>\n"
        "• Embark across 12 mysterious nodes on the global expedition map.\n"
        "• <b>Cooldown:</b> 1 hour ┊ <b>Daily Limit:</b> 3 expeditions/day.\n"
        "• Discover rich Gold caches, experience surges, and Blessed Mystery Boxes.\n\n"
        "🏰 <b>Demon Castle Spire (<code>/tower</code> or <code>/trial</code>)</b>\n"
        "• 100-Floor Instant Dungeon of descending demon fiends.\n"
        "• <b>Keys:</b> 3 Demon Castle Keys daily (replenished at 00:00 UTC).\n"
        "• Defeat milestone bosses for permanent legendary titles & relic gear:\n"
        "  - <b>Floor 10:</b> Cerberus (<i>Hell Gatekeeper Vanquisher</i>)\n"
        "  - <b>Floor 25:</b> Demonic Knight Commander\n"
        "  - <b>Floor 50:</b> Flame Monarch Vulcan (<i>Flame Conqueror</i>)\n"
        "  - <b>Floor 75:</b> Archfiend Metus\n"
        "  - <b>Floor 100:</b> Demon King Baran (<i>Demon King Vanquisher</i>)\n\n"
        "🤺 <b>Hunter Duels (<code>/duel</code>)</b>\n"
        "• Challenge another hunter in group chats by replying to their message with <code>/duel</code>.\n"
        "</blockquote>"
    ),
    "forge": (
        "<b>[ SYSTEM DIRECTIVE // FORGE & ALCHEMY ]</b>\n\n"
        "<blockquote expandable>"
        "🔨 <b>Equipment Enhancement (<code>/forge</code>, <code>/craft</code>, <code>/upgrade</code>)</b>\n"
        "• Enhance equippable weapons, armor, and accessories from <b>+1 to +10</b>.\n"
        "• Each enhancement level amplifies the item's stats by <b>+15%</b>!\n"
        "• <b>Cost:</b> Gold + 1 Crafting Catalyst (Refined Iron Ore, Crystals).\n"
        "• <b>Success Spectrum:</b>\n"
        "  - <b>+1 to +3:</b> 100% → 85% (Safe Zone)\n"
        "  - <b>+4 to +6:</b> 75% → 50% (Steady Progression)\n"
        "  - <b>+7 to +10:</b> 40% → 15% (High Risk: 40% downgrade chance on failure!)\n\n"
        "🔮 <b>Rarity Fusion Crucible</b>\n"
        "• Transmute <b>3 unequipped items of the same rarity</b> + 1 catalyst.\n"
        "• Produces <b>1 new item of the NEXT rarity tier</b>, scaled to your level:\n"
        "  - 3 Common → 1 Uncommon\n"
        "  - 3 Uncommon → 1 Rare\n"
        "  - 3 Rare → 1 Epic\n"
        "  - 3 Epic → 1 Legendary\n\n"
        "🧪 <b>Dimensional Alchemy (<code>/use</code>, <code>/heal</code>)</b>\n"
        "• Drink Health Potions to restore lost vitality.\n"
        "• Consume Elixirs and Scrolls to permanently augment STR, AGI, VIT, and Max HP.\n"
        "• Use <code>/heal</code> for an instant 1-tap potion consumption.\n"
        "</blockquote>"
    ),
    "quests": (
        "<b>[ SYSTEM DIRECTIVE // DAILY CONDITIONING ]</b>\n\n"
        "<blockquote expandable>"
        "🏋️ <b>Daily Physical Conditioning (<code>/daily</code>)</b>\n"
        "<i>「 The System demands daily physical conditioning. Failure is not an option. 」</i>\n\n"
        "Complete 4 mandatory daily directives before 00:00 UTC:\n"
        "1. ⚔️ Slay at least 5 gate monsters (<code>/hunt</code>)\n"
        "2. 🗺️ Undertake at least 1 world expedition (<code>/explore</code>)\n"
        "3. 🤺 Engage in at least 1 combat duel (<code>/duel</code>)\n"
        "4. 🧪 Drink at least 1 recovery potion or elixir (<code>/use</code> or <code>/heal</code>)\n\n"
        "🎁 <b>Daily Quest Completion Rewards:</b>\n"
        "• <b>+3 Free Stat Points</b> to invest freely into your attributes!\n"
        "• <b>+600 Gold</b> & <b>+250 XP</b>\n"
        "• <b>1 Blessed Mystery Gift Box</b> containing rare elixirs or gear.\n\n"
        "⚡ <b>Attribute Matrix (<code>/stats</code>, <code>/addstat</code>)</b>\n"
        "• <b>STR (Strength):</b> Boosts base physical attack and strike damage.\n"
        "• <b>AGI (Agility):</b> Elevates movement speed, critical rates, and evasion.\n"
        "• <b>VIT (Vitality):</b> Hardens defense & <b>increases Max HP (+5 HP per VIT)</b>.\n"
        "• <b>INT (Intelligence):</b> Deepens mana flow and supernatural ability power.\n"
        "• <b>PER (Perception):</b> Sharpened senses to detect weakness and rare loot.\n"
        "• Freely invest via <code>/addstat &lt;str|agi|vit|int|per&gt; &lt;pts&gt;</code> or buttons in <code>/stats</code>.\n"
        "</blockquote>"
    ),
    "guild": (
        "<b>[ SYSTEM DIRECTIVE // GUILD SYNDICATES ]</b>\n\n"
        "<blockquote expandable>"
        "👑 <b>Hunter Guild Syndicates (<code>/guild</code>)</b>\n"
        "• Band together with comrades to dominate global leaderboards.\n"
        "• <b>Passive Syndicate Buff:</b> All members receive <b>+10% bonus EXP</b> on all hunts!\n\n"
        "📜 <b>Syndicate Directives:</b>\n"
        "• <code>/guild create &lt;name&gt;</code> — Establish a guild (Cost: 500 Gold, max 15 members).\n"
        "• <code>/guild join &lt;name&gt;</code> — Join an existing syndicate.\n"
        "• <code>/guild info</code> — Display your guild card, war score, and roster.\n"
        "• <code>/guild top</code> — View the top syndicates on the Guild Leaderboard.\n"
        "• <code>/guild leave</code> — Depart your current syndicate.\n"
        "• <code>/guild war &lt;name&gt;</code> — Challenge an opposing syndicate to a war.\n\n"
        "🎁 <b>Mutual Aid Gifting (<code>/gift</code>)</b>\n"
        "• <code>/gift item &lt;id&gt;</code> — Transfer weapons or armor to a guild comrade.\n"
        "• <code>/gift gold &lt;amount&gt;</code> — Send gold funds to help comrades grow stronger.\n"
        "</blockquote>"
    ),
    "tiers": (
        "<b>[ SYSTEM DIRECTIVE // ASCENSION & TIERS ]</b>\n\n"
        "<blockquote expandable>"
        "⭐ <b>Hunter Rank Progression:</b>\n"
        "• <b>E-Rank:</b> Level 1+ (The Awakened Novice)\n"
        "• <b>D-Rank:</b> Level 10+ (Novice Raider)\n"
        "• <b>C-Rank:</b> Level 20+ (Gate Veteran)\n"
        "• <b>B-Rank:</b> Level 35+ (Elite Striker)\n"
        "• <b>A-Rank:</b> Level 50+ (Raid Master)\n"
        "• <b>S-Rank:</b> Level 70+ (National Asset)\n"
        "• <b>SS-Rank:</b> Level 85+ (Transcendent Hunter)\n"
        "• <b>SSS-Rank:</b> Level 95+ (Apex Sovereign)\n"
        "• <b>National Level:</b> Level 100+ (Living Calamity)\n"
        "• <b>Monarch:</b> Level 120+ (Shadow Monarch Sovereign)\n\n"
        "💎 <b>Item Rarity Spectrum & Drop Probabilities:</b>\n"
        "• ⚪ <b>Common:</b> 50.0% — Basic dungeon gear & smelting iron\n"
        "• 🟢 <b>Uncommon:</b> 25.0% — Hardened steel & tempered bows\n"
        "• 🔵 <b>Rare:</b> 15.0% — Boss drops & enchanted accessories\n"
        "• 🟣 <b>Epic:</b> 7.0% — High-mana crystalline artifacts\n"
        "• 🟡 <b>Legendary:</b> 2.5% — Sovereign-forged ancient relics\n"
        "• 🔴 <b>Mythic:</b> 0.5% — Divine dimensional armaments\n"
        "</blockquote>"
    ),
    "shadows": (
        "<b>[ SYSTEM DIRECTIVE // SHADOW MONARCH ARISE ]</b>\n\n"
        "<blockquote expandable>"
        "👥 <b>Dimensional Rifts & Spawning</b>\n"
        "• As hunters converse in group chats, dimensional rifts manifest every <b>250 messages</b>!\n"
        "• A wild shadow soldier appears with an encrypted True Name and displayed image.\n\n"
        "🗣️ <b>Extracting Shadows (<code>/arise &lt;name&gt;</code>)</b>\n"
        "• Be the first hunter in the group to type <code>/arise &lt;character name&gt;</code>.\n"
        "• Correctly commanding its true name extracts the shadow entity into your army!\n"
        "• Grants massive <b>Gold & XP extraction bounties</b> scaled to its rarity.\n\n"
        "👑 <b>Reviewing Your Army (<code>/shadows</code>)</b>\n"
        "• Inspect your complete Shadow Monarch Army, soldier counts, and army power.\n"
        "• Interactive pagination and rarity filters (Mythic, Legendary, Epic).\n"
        "• View other players' armies with <code>/shadows @username</code>.\n"
        "</blockquote>"
    ),
    "admin": (
        "<b>[ SYSTEM DIRECTIVE // SUPERADMIN CONSOLE ]</b>\n\n"
        "<blockquote expandable>"
        "👑 <b>Hunter Administration:</b>\n"
        "• <code>/admin</code> — Show admin guide and permissions\n"
        "• <code>/addgold &lt;user_id|@user&gt; &lt;amount&gt;</code> — Grant gold currency\n"
        "• <code>/setgold &lt;user_id|@user&gt; &lt;amount&gt;</code> — Set gold balance\n"
        "• <code>/addxp &lt;user_id|@user&gt; &lt;amount&gt;</code> — Grant experience points\n"
        "• <code>/setlevel &lt;user_id|@user&gt; &lt;level&gt;</code> — Set hunter level\n"
        "• <code>/inspect &lt;user_id|@user&gt;</code> — Inspect full database record\n\n"
        "🎟️ <b>Redeem Gift Codes:</b>\n"
        "• <code>/createcode gold &lt;CODE&gt; &lt;amount&gt; [max_uses]</code> — Create gold gift code\n"
        "• <code>/createcode item &lt;CODE&gt; &lt;item_id&gt; [max_uses]</code> — Create item gift code\n"
        "• <code>/listcodes</code> — Inspect active promotional codes\n"
        "• <code>/deletecode &lt;CODE&gt;</code> — Revoke a promotional gift code\n\n"
        "👥 <b>Shadow Catalog:</b>\n"
        "• <code>/addshadow &lt;Rarity&gt; &lt;Name&gt; [| aliases]</code> — Enroll character\n"
        "• <code>/listshadows [page]</code> — Inspect catalog characters\n"
        "• <code>/delshadow &lt;id&gt;</code> — Remove character from pool\n"
        "• <code>/spawnshadow [id]</code> — Force rift spawn in chat\n"
        "• <code>/shadowstats</code> — Global rift telemetry\n"
        "</blockquote>"
    ),
}

# ── RICH MESSAGE CONTENTS (Bot API 10.1+ send_rich_message) ──────────────────
# Static HTML for the new Rich Message format: real headings, tables, dividers,
# blockquotes. Fallback to TOPIC_TEXTS (plain HTML) lives at each send site.


def _topic_rich(title: str, *blocks: str) -> str:
    """Wrap topic blocks in the standard SYSTEM DIRECTIVE rich frame (validated)."""
    return RichDoc(
        heading(1, f"[ SYSTEM DIRECTIVE // {title} ]"),
        divider(),
        *blocks,
        footer("Solo Leveling Hunter System // Archives V2.5"),
    ).validate()


def _sec(title: str, *items: str) -> list[str]:
    """Collapsible section toggle + bullet list (classic copy preserved verbatim)."""
    return [details(title, bullet_list(list(items)))]


TOPIC_RICH = {
    "tiers": (
        "<h1>[ SYSTEM DIRECTIVE // ASCENSION &amp; TIERS ]</h1>"
        "<hr/>"
        "<details><summary>⭐ Hunter Rank Progression</summary>"
        "<table>"
        "<tr><th>Rank</th><th>Requirement</th></tr>"
        "<tr><td><b>E-Rank</b></td><td>Level 1+ — The Awakened Novice</td></tr>"
        "<tr><td><b>D-Rank</b></td><td>Level 10+ — Novice Raider</td></tr>"
        "<tr><td><b>C-Rank</b></td><td>Level 20+ — Gate Veteran</td></tr>"
        "<tr><td><b>B-Rank</b></td><td>Level 35+ — Elite Striker</td></tr>"
        "<tr><td><b>A-Rank</b></td><td>Level 50+ — Raid Master</td></tr>"
        "<tr><td><b>S-Rank</b></td><td>Level 70+ — National Asset</td></tr>"
        "<tr><td><b>SS-Rank</b></td><td>Level 85+ — Transcendent Hunter</td></tr>"
        "<tr><td><b>SSS-Rank</b></td><td>Level 95+ — Apex Sovereign</td></tr>"
        "<tr><td><b>National Level</b></td><td>Level 100+ — Living Calamity</td></tr>"
        "<tr><td><b>Monarch</b></td><td>Level 120+ — Shadow Monarch Sovereign</td></tr>"
        "</table></details>"
        "<details><summary>💎 Item Rarity Spectrum &amp; Drop Probabilities</summary>"
        "<table>"
        "<tr><th>Rarity</th><th>Drop Rate</th><th>Loot Profile</th></tr>"
        "<tr><td>⚪ <b>Common</b></td><td>50.0%</td><td>Basic dungeon gear &amp; smelting iron</td></tr>"
        "<tr><td>🟢 <b>Uncommon</b></td><td>25.0%</td><td>Hardened steel &amp; tempered bows</td></tr>"
        "<tr><td>🔵 <b>Rare</b></td><td>15.0%</td><td>Boss drops &amp; enchanted accessories</td></tr>"
        "<tr><td>🟣 <b>Epic</b></td><td>7.0%</td><td>High-mana crystalline artifacts</td></tr>"
        "<tr><td>🟡 <b>Legendary</b></td><td>2.5%</td><td>Sovereign-forged ancient relics</td></tr>"
        "<tr><td>🔴 <b>Mythic</b></td><td>0.5%</td><td>Divine dimensional armaments</td></tr>"
        "</table></details>"
        "<hr/>"
        "<blockquote>「 The System acknowledges those who strive to grow stronger. 」</blockquote>"
        "<footer>Solo Leveling Hunter System // Archives V2.5</footer>"
    ),
    "combat": _topic_rich(
        "COMBAT &amp; SPIRE",
        *_sec("🚪 Dimensional Gate Hunts (<code>/hunt</code>)",
              "Slay gate monsters ranging from E-Rank beasts to S-Rank Calamities.",
              "<b>Cooldown:</b> 1 minute ┊ <b>Daily Limit:</b> 20 hunts/day.",
              "Drops: Hunter XP, Gold, Weapons, Armor, Rings, Potions &amp; Ores.",
              "Monsters deal damage to your HP! Monitor vitality and drink potions via <code>/use</code> or <code>/heal</code>."),
        *_sec("🗺️ Uncharted World Map Expeditions (<code>/explore</code>)",
              "Embark across 12 mysterious nodes on the global expedition map.",
              "<b>Cooldown:</b> 1 hour ┊ <b>Daily Limit:</b> 3 expeditions/day.",
              "Discover rich Gold caches, experience surges, and Blessed Mystery Boxes."),
        *_sec("🏰 Demon Castle Spire (<code>/tower</code> or <code>/trial</code>)",
              "100-Floor Instant Dungeon of descending demon fiends.",
              "<b>Keys:</b> 3 Demon Castle Keys daily (replenished at 00:00 UTC).",
              "Defeat milestone bosses for permanent legendary titles &amp; relic gear:",
              "<b>Floor 10:</b> Cerberus (<i>Hell Gatekeeper Vanquisher</i>)",
              "<b>Floor 25:</b> Demonic Knight Commander",
              "<b>Floor 50:</b> Flame Monarch Vulcan (<i>Flame Conqueror</i>)",
              "<b>Floor 75:</b> Archfiend Metus",
              "<b>Floor 100:</b> Demon King Baran (<i>Demon King Vanquisher</i>)"),
        *_sec("🤺 Hunter Duels (<code>/duel</code>)",
              "Challenge another hunter in group chats by replying to their message with <code>/duel</code>."),
    ),
    "forge": _topic_rich(
        "FORGE &amp; ALCHEMY",
        *_sec("🔨 Equipment Enhancement (<code>/forge</code>, <code>/craft</code>, <code>/upgrade</code>)",
              "Enhance equippable weapons, armor, and accessories from <b>+1 to +10</b>.",
              "Each enhancement level amplifies the item's stats by <b>+15%</b>!",
              "<b>Cost:</b> Gold + 1 Crafting Catalyst (Refined Iron Ore, Crystals).",
              "<b>Success Spectrum:</b>",
              "<b>+1 to +3:</b> 100% → 85% (Safe Zone)",
              "<b>+4 to +6:</b> 75% → 50% (Steady Progression)",
              "<b>+7 to +10:</b> 40% → 15% (High Risk: 40% downgrade chance on failure!)"),
        *_sec("🔮 Rarity Fusion Crucible",
              "Transmute <b>3 unequipped items of the same rarity</b> + 1 catalyst.",
              "Produces <b>1 new item of the NEXT rarity tier</b>, scaled to your level:",
              "3 Common → 1 Uncommon",
              "3 Uncommon → 1 Rare",
              "3 Rare → 1 Epic",
              "3 Epic → 1 Legendary"),
        *_sec("🧪 Dimensional Alchemy (<code>/use</code>, <code>/heal</code>)",
              "Drink Health Potions to restore lost vitality.",
              "Consume Elixirs and Scrolls to permanently augment STR, AGI, VIT, and Max HP.",
              "Use <code>/heal</code> for an instant 1-tap potion consumption."),
    ),
    "quests": _topic_rich(
        "DAILY CONDITIONING",
        details(
            "🏋️ Daily Physical Conditioning (<code>/daily</code>)",
            paragraph("<i>「 The System demands daily physical conditioning. Failure is not an option. 」</i>")
            + paragraph("Complete 4 mandatory daily directives before 00:00 UTC:")
            + number_list([
                "⚔️ Slay at least 5 gate monsters (<code>/hunt</code>)",
                "🗺️ Undertake at least 1 world expedition (<code>/explore</code>)",
                "🤺 Engage in at least 1 combat duel (<code>/duel</code>)",
                "🧪 Drink at least 1 recovery potion or elixir (<code>/use</code> or <code>/heal</code>)",
            ]),
        ),
        *_sec("🎁 Daily Quest Completion Rewards:",
              "<b>+3 Free Stat Points</b> to invest freely into your attributes!",
              "<b>+600 Gold</b> &amp; <b>+250 XP</b>",
              "<b>1 Blessed Mystery Gift Box</b> containing rare elixirs or gear."),
        *_sec("⚡ Attribute Matrix (<code>/stats</code>, <code>/addstat</code>)",
              "<b>STR (Strength):</b> Boosts base physical attack and strike damage.",
              "<b>AGI (Agility):</b> Elevates movement speed, critical rates, and evasion.",
              "<b>VIT (Vitality):</b> Hardens defense &amp; <b>increases Max HP (+5 HP per VIT)</b>.",
              "<b>INT (Intelligence):</b> Deepens mana flow and supernatural ability power.",
              "<b>PER (Perception):</b> Sharpened senses to detect weakness and rare loot.",
              "Freely invest via <code>/addstat &lt;str|agi|vit|int|per&gt; &lt;pts&gt;</code> or buttons in <code>/stats</code>."),
    ),
    "guild": _topic_rich(
        "GUILD SYNDICATES",
        *_sec("👑 Hunter Guild Syndicates (<code>/guild</code>)",
              "Band together with comrades to dominate global leaderboards.",
              "<b>Passive Syndicate Buff:</b> All members receive <b>+10% bonus EXP</b> on all hunts!"),
        *_sec("📜 Syndicate Directives:",
              "<code>/guild create &lt;name&gt;</code> — Establish a guild (Cost: 500 Gold, max 15 members).",
              "<code>/guild join &lt;name&gt;</code> — Join an existing syndicate.",
              "<code>/guild info</code> — Display your guild card, war score, and roster.",
              "<code>/guild top</code> — View the top syndicates on the Guild Leaderboard.",
              "<code>/guild leave</code> — Depart your current syndicate.",
              "<code>/guild war &lt;name&gt;</code> — Challenge an opposing syndicate to a war."),
        *_sec("🎁 Mutual Aid Gifting (<code>/gift</code>)",
              "<code>/gift item &lt;id&gt;</code> — Transfer weapons or armor to a guild comrade.",
              "<code>/gift gold &lt;amount&gt;</code> — Send gold funds to help comrades grow stronger."),
    ),
    "shadows": _topic_rich(
        "SHADOW MONARCH ARISE",
        *_sec("👥 Dimensional Rifts &amp; Spawning",
              "As hunters converse in group chats, dimensional rifts manifest every <b>250 messages</b>!",
              "A wild shadow soldier appears with an encrypted True Name and displayed image."),
        *_sec("🗣️ Extracting Shadows (<code>/arise &lt;name&gt;</code>)",
              "Be the first hunter in the group to type <code>/arise &lt;character name&gt;</code>.",
              "Correctly commanding its true name extracts the shadow entity into your army!",
              "Grants massive <b>Gold &amp; XP extraction bounties</b> scaled to its rarity."),
        *_sec("👑 Reviewing Your Army (<code>/shadows</code>)",
              "Inspect your complete Shadow Monarch Army, soldier counts, and army power.",
              "Interactive pagination and rarity filters (Mythic, Legendary, Epic).",
              "View other players' armies with <code>/shadows @username</code>."),
    ),
    "admin": _topic_rich(
        "SUPERADMIN CONSOLE",
        *_sec("👑 Hunter Administration:",
              "<code>/admin</code> — Show admin guide and permissions",
              "<code>/addgold &lt;user_id|@user&gt; &lt;amount&gt;</code> — Grant gold currency",
              "<code>/setgold &lt;user_id|@user&gt; &lt;amount&gt;</code> — Set gold balance",
              "<code>/addxp &lt;user_id|@user&gt; &lt;amount&gt;</code> — Grant experience points",
              "<code>/setlevel &lt;user_id|@user&gt; &lt;level&gt;</code> — Set hunter level",
              "<code>/inspect &lt;user_id|@user&gt;</code> — Inspect full database record"),
        *_sec("🎟️ Redeem Gift Codes:",
              "<code>/createcode gold &lt;CODE&gt; &lt;amount&gt; [max_uses]</code> — Create gold gift code",
              "<code>/createcode item &lt;CODE&gt; &lt;item_id&gt; [max_uses]</code> — Create item gift code",
              "<code>/listcodes</code> — Inspect active promotional codes",
              "<code>/deletecode &lt;CODE&gt;</code> — Revoke a promotional gift code"),
        *_sec("👥 Shadow Catalog:",
              "<code>/addshadow &lt;Rarity&gt; &lt;Name&gt; [| aliases]</code> — Enroll character",
              "<code>/listshadows [page]</code> — Inspect catalog characters",
              "<code>/delshadow &lt;id&gt;</code> — Remove character from pool",
              "<code>/spawnshadow [id]</code> — Force rift spawn in chat",
              "<code>/shadowstats</code> — Global rift telemetry"),
    ),
}


def _help_pm_keyboard() -> InlineKeyboardMarkup:
    """Master action buttons for help screen in private chat."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚔️ Combat & Spire", callback_data="help_combat"),
            InlineKeyboardButton("⚒️ Forge & Gear", callback_data="help_forge"),
        ],
        [
            InlineKeyboardButton("📋 Quests & Stats", callback_data="help_quests"),
            InlineKeyboardButton("🏰 Guilds & War", callback_data="help_guild"),
        ],
        [
            InlineKeyboardButton("👑 Shadows & Arise", callback_data="help_shadows"),
            InlineKeyboardButton("💎 Ranks & Drops", callback_data="help_tiers"),
        ],
        [
            InlineKeyboardButton("🎒 Inventory", callback_data="inv_weapon"),
            InlineKeyboardButton("🛒 Hunter Shop", callback_data="shop_menu"),
        ]
    ])


def _topic_keyboard(active_topic: str) -> InlineKeyboardMarkup:
    """Action buttons when viewing a specific help topic page."""
    buttons = [
        [
            InlineKeyboardButton("⚔️ Combat", callback_data="help_combat"),
            InlineKeyboardButton("⚒️ Forge", callback_data="help_forge"),
            InlineKeyboardButton("📋 Quests", callback_data="help_quests"),
            InlineKeyboardButton("👑 Shadows", callback_data="help_shadows"),
        ],
        [
            InlineKeyboardButton("🏰 Guilds", callback_data="help_guild"),
            InlineKeyboardButton("💎 Ranks", callback_data="help_tiers"),
            InlineKeyboardButton("🔙 Master Manual", callback_data="help_main"),
        ],
    ]

    # Contextual quick-launch buttons depending on the topic
    if active_topic == "combat":
        buttons.append([
            InlineKeyboardButton("🏰 Challenge Demon Castle", callback_data="tower_menu"),
            InlineKeyboardButton("🏆 System Hall of Fame", callback_data="lb_power"),
        ])
    elif active_topic == "forge":
        buttons.append([
            InlineKeyboardButton("⚒️ Open Blacksmith Forge", callback_data="forge_menu"),
            InlineKeyboardButton("🎒 Dimensional Inventory", callback_data="inv_weapon"),
        ])
    elif active_topic == "quests":
        buttons.append([
            InlineKeyboardButton("📋 Daily Quest Board", callback_data="quest_menu"),
            InlineKeyboardButton("⚡ Allocate Stat Points", callback_data="stats_menu"),
        ])
    elif active_topic == "guild":
        buttons.append([
            InlineKeyboardButton("🏆 Guild Leaderboard", callback_data="glb_trophies"),
        ])

    return InlineKeyboardMarkup(buttons)


async def send_help_card_to_chat(client: Client, chat_id: int) -> bool:
    """Generate and transmit the visual Operational Manual card to a chat/user."""
    try:
        photo_buf = await asyncio.to_thread(generate_help_image)
        await send_rich(
            client, chat_id, build_help_rich(),
            reply_markup=_help_pm_keyboard(),
            media=[photo_media("help", photo_buf)],
            fallback=lambda: client.send_photo(
                chat_id=chat_id,
                photo=photo_buf,
                caption=HELP_CAPTION,
                reply_markup=_help_pm_keyboard(),
                parse_mode=enums.ParseMode.HTML,
                show_caption_above_media=True,
            ),
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to send visual help card to {chat_id}: {e}; using text fallback.")
        try:
            await client.send_message(
                chat_id=chat_id,
                text=HELP_FALLBACK_TEXT,
                reply_markup=_help_pm_keyboard(),
                parse_mode=enums.ParseMode.HTML,
            )
            return True
        except Exception:
            return False


async def handle(client: Client, message: Message) -> None:
    """Handle the /help command. Supports /help <topic> and directs groups to PM."""
    user = message.from_user
    chat = message.chat
    if not user or not chat:
        return

    is_group = chat.type in ["group", "supergroup"]

    if is_group:
        me = await client.get_me()
        bot_user = me.username or "solo_leveling_hunter_bot"
        pm_url = f"https://t.me/{bot_user}?start=help"

        gc_text = (
            "<b>[ SYSTEM DIRECTIVE // OPERATIONAL MANUAL ]</b>\n"
            "<b>시스템 안내 // 매뉴얼 전송</b>\n\n"
            f"👤 <b>Hunter:</b> <b>{escape_html(user.first_name)}</b>\n\n"
            "<blockquote expandable>"
            "<b>Notice: Group Chat Optimization Protocol</b>\n"
            "• To keep group communications clear and uncluttered, the high-definition\n"
            "  operational manual archives are opened directly in private chat.\n"
            "</blockquote>\n\n"
            "<i>Tap below to review directives and mechanics in private chat:</i>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Open Guide in Bot PM", url=pm_url, style=enums.ButtonStyle.PRIMARY)]
        ])
        gc_doc = RichDoc(
            heading(1, "[ SYSTEM DIRECTIVE // OPERATIONAL MANUAL ]"),
            paragraph("시스템 안내 // 매뉴얼 전송"),
            paragraph(f"👤 <b>Hunter:</b> <b>{escape_html(user.first_name)}</b>"),
            quote(
                "<b>Notice: Group Chat Optimization Protocol</b><br>"
                "• To keep group communications clear and uncluttered, the high-definition<br>"
                "  operational manual archives are opened directly in private chat.",
                expandable=True,
            ),
            paragraph("<i>Tap below to review directives and mechanics in private chat:</i>"),
        )
        await reply_rich(
            message, gc_doc, reply_markup=keyboard,
            fallback=lambda: message.reply_text(
                gc_text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML),
        )
        return

    # In PM: Check if a specific topic argument was passed (e.g., /help forge)
    args = message.command[1:] if len(message.command) > 1 else []
    if args:
        topic_arg = args[0].lower().strip()
        topic_key = None
        if topic_arg in ["combat", "hunt", "tower", "trial", "duel", "explore"]:
            topic_key = "combat"
        elif topic_arg in ["forge", "craft", "upgrade", "fuse", "potions", "potion", "alchemy", "use", "heal"]:
            topic_key = "forge"
        elif topic_arg in ["quest", "quests", "daily", "stats", "stat", "addstat"]:
            topic_key = "quests"
        elif topic_arg in ["guild", "guilds", "war", "gift"]:
            topic_key = "guild"
        elif topic_arg in ["tiers", "rank", "ranks", "rarity", "rarities"]:
            topic_key = "tiers"
        elif topic_arg in ["admin", "superadmin", "owner"] and user.id in SUPERADMIN_IDS:
            topic_key = "admin"

        if topic_key and topic_key in TOPIC_TEXTS:
            # send_rich preserves this site's fresh-send semantics (no reply quote);
            # plan said reply_rich - ruled send_rich to avoid a UX change.
            await send_rich(
                client, chat.id, RawRichDoc(TOPIC_RICH[topic_key]),
                reply_markup=_topic_keyboard(topic_key),
                fallback=lambda: message.reply_text(
                    TOPIC_TEXTS[topic_key], reply_markup=_topic_keyboard(topic_key),
                    parse_mode=enums.ParseMode.HTML),
            )
            return

    # Default PM response: Send the master visual manual card
    try:
        photo_buf = await asyncio.to_thread(generate_help_image)
        await reply_rich(
            message, build_help_rich(),
            reply_markup=_help_pm_keyboard(),
            media=[photo_media("help", photo_buf)],
            fallback=lambda: message.reply_photo(
                photo=photo_buf,
                caption=HELP_CAPTION,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_help_pm_keyboard(),
                show_caption_above_media=True,
            ),
        )
    except Exception as e:
        logger.warning(f"Failed to reply with help photo: {e}")
        await message.reply_text(HELP_FALLBACK_TEXT, reply_markup=_help_pm_keyboard(), parse_mode=enums.ParseMode.HTML)


async def callback(client: Client, query: CallbackQuery) -> None:
    """Handle inline button topic navigation for /help."""
    user = query.from_user
    if not user:
        await query.answer()
        return

    data = query.data

    if data == "help_main":
        await query.answer("Opening Master Manual...")
        caption = HELP_CAPTION
        photo_buf = await asyncio.to_thread(generate_help_image)
        if query.message:
            if query.message.photo:
                # classic-origin message -> verbatim classic media edit on fallback
                fallback = lambda: query.edit_message_media(
                    media=InputMediaPhoto(media=photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
                    reply_markup=_help_pm_keyboard(),
                )
            else:
                fallback = lambda: query.message.reply_photo(
                    photo=photo_buf,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=_help_pm_keyboard(),
                    show_caption_above_media=True,
                )
            await edit_rich(
                client, query.message.chat.id, query.message.id, build_help_rich(),
                reply_markup=_help_pm_keyboard(),
                media=[photo_media("help", photo_buf)],
                fallback=fallback,
            )
        return

    # Topic navigation: help_combat, help_forge, help_quests, help_guild, help_tiers, help_admin
    topic = data.replace("help_", "")
    if topic in TOPIC_TEXTS:
        await query.answer()
        text = TOPIC_TEXTS[topic]
        keyboard = _topic_keyboard(topic)
        if query.message and query.message.photo:
            # Send as clean text reply to preserve formatting
            await query.message.reply_text(text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)
            return
        if not query.message:
            return

        async def _classic_topic_edit():
            # verbatim classic path: plain edit, then fresh reply on edit failure
            try:
                await query.edit_message_text(text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)
            except Exception as e:
                logger.warning(f"plain edit failed for topic {topic}: {e}; sending fresh reply.")
                await query.message.reply_text(text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)

        await edit_rich(
            client, query.message.chat.id, query.message.id,
            RawRichDoc(TOPIC_RICH[topic]),
            reply_markup=keyboard,
            fallback=_classic_topic_edit,
        )
        return

    await query.answer()
