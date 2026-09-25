"""
handlers/explore.py — /explore command handler.

Hunters explore the Solo Leveling world map up to 3 times per day (1-hour cooldown),
discovering regional lore, generous Gold & XP, and rare dimensional gift artifacts.
Renders an atmospheric Hallmark-standard world map with the hunter's profile picture.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Optional

from pyrogram import Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from channel_db import ChannelDB
from config import EXPLORE_COOLDOWN_SECONDS, DAILY_EXPLORE_LIMIT
from game.explore_image import render_explore_image, EXPLORE_SECTORS
from game.hunter import add_xp, check_rank_up
from game.photo_helper import fetch_user_pfp_image
from game.formatting import format_not_registered, format_not_registered_rich
from game.rich_text import escape_html
from game.captions import build_explore_caption, build_explore_rich
from game.rich_message import RichDoc, heading, paragraph, quote
from game.rich_send import photo_media, reply_rich
from game.shop import SHOP_ITEMS, create_item_from_shop
from models import Hunter, Item, Inventory

logger = logging.getLogger(__name__)

# Sector-specific dynamic discovery event narratives
SECTOR_EVENTS = {
    0: [
        "Infiltrated a sealed Association training vault and salvaged ancient mana crystals.",
        "Discovered a hidden supply cache left behind by White Tiger Guild scouts.",
        "Assisted Chairman Go Gun-hee's rapid response team in subduing an E-Rank surge.",
    ],
    1: [
        "Endured a fierce subzero blizzard and ambushed a patrol of Frost Monarch Ice Elves.",
        "Extracted a subterranean vein of Cryo-Mana Gems buried beneath the glacial frost.",
        "Discovered the frozen remains of an S-Rank beast's lair containing ancient armaments.",
    ],
    2: [
        "Breached Floor 50 of the Demon Castle and defeated Vulcan's demonic vanguard.",
        "Pillaged Metus the Necromancer's treasury amidst towers of burning hellfire.",
        "Extracted purified Demon Souls and forged a connection to the Monarch's domain.",
    ],
    3: [
        "Decoded the First Commandment of the God Statue within the Temple of Cartenon.",
        "Overcame the trial of the winged stone sentinels and claimed the Architect's relics.",
        "Discovered an ancient altar humming with the latent power of the Shadow Monarch.",
    ],
    4: [
        "Scouted the desolate coastline of Jeju Island and destroyed a mutated Ant Colony nest.",
        "Recovered discarded Japanese S-Rank gear from the historic raid battlefield.",
        "Assassinated an Elite Winged Ant Guard and extracted its crystallized venom gland.",
    ],
    5: [
        "Crossed the boundary into the Monarch's Abyss where cosmic shadow energy cascades.",
        "Surpassed the dimensional horizon and secured remnants of the Ruler's Divine Armaments.",
        "Conquered a primordial void rift and stabilized a dimensional passage.",
    ],
}

# Unique exploration gift artifacts that can be discovered
EXPLORATION_GIFTS = [
    {"name": "Ruler's Mana Pendant", "type": "accessory", "rarity": "Epic", "atk": 20, "def": 20, "hp": 80, "spd": 10},
    {"name": "Frost Monarch's Shard", "type": "weapon", "rarity": "Epic", "atk": 45, "def": 10, "hp": 40, "spd": 5},
    {"name": "Architect's Keystone", "type": "accessory", "rarity": "Legendary", "atk": 35, "def": 35, "hp": 150, "spd": 15},
    {"name": "Jeju Carapace Cuirass", "type": "armor", "rarity": "Epic", "atk": 10, "def": 45, "hp": 120, "spd": 0},
    {"name": "Shadow Vanguard Dagger", "type": "weapon", "rarity": "Rare", "atk": 30, "def": 5, "hp": 20, "spd": 12},
    {"name": "Abyssal Ring of Vitality", "type": "accessory", "rarity": "Rare", "atk": 10, "def": 15, "hp": 100, "spd": 5},
]


def _explore_keyboard() -> InlineKeyboardMarkup:
    """Buttons for exploration card."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎒 Dimensional Inventory", callback_data="inv_weapon", style=enums.ButtonStyle.PRIMARY),
            InlineKeyboardButton("🛒 Hunter Shop", callback_data="shop_menu", style=enums.ButtonStyle.PRIMARY),
        ],
        [
            InlineKeyboardButton("🏆 System Leaderboard", callback_data="lb_power"),
        ]
    ])


async def handle(client: Client, message: Message) -> None:
    """Handle /explore command — 3x daily limit with 1-hour cooldown and visual map card."""
    user = message.from_user
    if not user:
        return

    db: ChannelDB = client.db

    # 1. Registration Check
    hunter = await db.get_hunter(user.id)
    if not hunter:
        await reply_rich(
            message, format_not_registered_rich(),
            fallback=lambda: message.reply_text(format_not_registered(), parse_mode=enums.ParseMode.HTML),
        )
        return

    # 2. Check and reset daily quota if UTC calendar day changed
    hunter.check_and_reset_daily()

    # 3. Daily Quota Limit Check (Max 3/day)
    h_name = escape_html(hunter.hunter_name)
    if hunter.daily_explores >= DAILY_EXPLORE_LIMIT:
        await reply_rich(
            message,
            RichDoc(
                heading(1, "[ DAILY EXPEDITIONS EXHAUSTED // 탐색 한도 초과 ]"),
                paragraph(
                    f"👤 <b>Hunter:</b> {h_name} (<code>{hunter.user_id}</code>)<br>"
                    f"📊 <b>Expeditions Today:</b> <code>{hunter.daily_explores} / {DAILY_EXPLORE_LIMIT}</code> Completed"
                ),
                quote(
                    "The System's dimensional territory radar requires overnight recalibration.<br>"
                    "Your 3 daily exploration permits will reset at midnight UTC.<br><br>"
                    "💡 <i>You can continue training and earning loot with <code>/hunt</code> (1 min CD)!</i>",
                    expandable=True,
                ),
            ),
            fallback=lambda: message.reply_text(
                "<b>[ DAILY EXPEDITIONS EXHAUSTED // 탐색 한도 초과 ]</b>\n\n"
                f"👤 <b>Hunter:</b> {h_name} (<code>{hunter.user_id}</code>)\n"
                f"📊 <b>Expeditions Today:</b> <code>{hunter.daily_explores} / {DAILY_EXPLORE_LIMIT}</code> Completed\n\n"
                "<blockquote expandable>"
                "The System's dimensional territory radar requires overnight recalibration.\n"
                "Your 3 daily exploration permits will reset at midnight UTC.\n\n"
                "💡 <i>You can continue training and earning loot with <code>/hunt</code> (1 min CD)!</i>"
                "</blockquote>",
                parse_mode=enums.ParseMode.HTML,
            ),
        )
        return

    # 4. Cooldown Check (1 Hour)
    now = time.time()
    last_exp = hunter.last_explore_time or 0.0
    if last_exp > 0:
        elapsed = now - last_exp
        if elapsed < EXPLORE_COOLDOWN_SECONDS:
            rem = int(EXPLORE_COOLDOWN_SECONDS - elapsed)
            hours = rem // 3600
            mins = (rem % 3600) // 60
            secs = rem % 60
            timer_str = f"{mins}m {secs:02d}s" if hours == 0 else f"{hours}h {mins:02d}m"
            await reply_rich(
                message,
                RichDoc(
                    heading(1, "[ EXPEDITION RADAR RECHARGING // 탐색 레이더 충전 중 ]"),
                    paragraph(
                        f"👤 <b>Hunter:</b> {h_name}<br>"
                        f"⏱️ <b>Next Expedition Ready In:</b> <code>{timer_str}</code>"
                    ),
                    quote(
                        "Your survey squad is analyzing satellite telemetry from the last sector.<br>"
                        f"Expeditions remaining today: <b>{DAILY_EXPLORE_LIMIT - hunter.daily_explores} / {DAILY_EXPLORE_LIMIT}</b>",
                        expandable=True,
                    ),
                ),
                fallback=lambda: message.reply_text(
                    "<b>[ EXPEDITION RADAR RECHARGING // 탐색 레이더 충전 중 ]</b>\n\n"
                    f"👤 <b>Hunter:</b> {h_name}\n"
                    f"⏱️ <b>Next Expedition Ready In:</b> <code>{timer_str}</code>\n\n"
                    "<blockquote expandable>"
                    "Your survey squad is analyzing satellite telemetry from the last sector.\n"
                    f"Expeditions remaining today: <b>{DAILY_EXPLORE_LIMIT - hunter.daily_explores} / {DAILY_EXPLORE_LIMIT}</b>\n"
                    "</blockquote>",
                    parse_mode=enums.ParseMode.HTML,
                ),
            )
            return

    # 5. Determine Current Exploration Sector
    sector_id = hunter.current_explore_node % len(EXPLORE_SECTORS)
    sector_info = EXPLORE_SECTORS[sector_id]
    event_list = SECTOR_EVENTS.get(sector_id, SECTOR_EVENTS[0])
    event_story = random.choice(event_list)

    # 6. Calculate Generous Rewards
    # Generous Gold: 350-900 Gold based on hunter level & sector tier
    gold_reward = 350 + (hunter.level * 35) + (sector_id * 40) + random.randint(30, 120)
    # Generous XP: 250-650 XP
    xp_reward = 220 + (hunter.level * 28) + (sector_id * 35) + random.randint(20, 80)

    hunter.gold += gold_reward
    leveled_up, new_rank = add_xp(hunter, xp_reward)

    # 7. Check for Random Gift Discovery (~40% chance)
    gift_item: Optional[Item] = None
    inventory = await db.get_inventory(user.id)
    if not inventory:
        inventory = Inventory(user_id=user.id)

    if random.random() < 0.40:
        # Either pick from exploration unique gifts or a shop weapon/armor
        if random.random() < 0.60:
            gift_tpl = random.choice(EXPLORATION_GIFTS)
            gift_item = Item(
                id=0,
                name=gift_tpl["name"],
                type=gift_tpl["type"],
                rarity=gift_tpl["rarity"],
                atk_bonus=gift_tpl.get("atk", 0),
                def_bonus=gift_tpl.get("def", 0),
                hp_bonus=gift_tpl.get("hp", 0),
                spd_bonus=gift_tpl.get("spd", 0),
            )
        else:
            shop_entry = random.choice(SHOP_ITEMS)
            gift_item = create_item_from_shop(shop_entry)

        inventory.add_item(gift_item)

    # 8. Update Hunter Progress & Cooldown
    hunter.daily_explores += 1
    hunter.daily_quest_explore += 1
    hunter.last_explore_time = now
    # Advance to next sector for subsequent exploration
    hunter.current_explore_node = (sector_id + 1) % len(EXPLORE_SECTORS)

    # Save to channel database
    await db.save_all(user.id)

    # 9. Fetch Profile Photo (PFP) Asynchronously
    pfp_image = await fetch_user_pfp_image(client, user.id, user_obj=user)

    # 10. Render Hallmark Exploration Map Card
    first_name = (user.first_name or "").strip()
    last_name = (user.last_name or "").strip()
    full_name = f"{first_name} {last_name}".strip() if last_name else first_name
    display_name = full_name or hunter.hunter_name or f"Hunter #{user.id}"

    try:
        photo_buf = await asyncio.to_thread(
            render_explore_image,
            hunter,
            sector_id,
            event_story,
            gold_reward,
            xp_reward,
            gift_item,
            pfp_image,
            display_name,
        )

        caption = build_explore_caption(
            hunter=hunter,
            sector_info=sector_info,
            gold_reward=gold_reward,
            xp_reward=xp_reward,
            gift_item=gift_item,
            leveled_up=leveled_up,
            new_rank=new_rank,
            story=event_story,
            display_name=display_name,
        )

        await reply_rich(
            message,
            build_explore_rich(
                hunter=hunter,
                sector_info=sector_info,
                gold_reward=gold_reward,
                xp_reward=xp_reward,
                gift_item=gift_item,
                leveled_up=leveled_up,
                new_rank=new_rank,
                story=event_story,
                display_name=display_name,
                photo_first=False,
            ),
            reply_markup=_explore_keyboard(),
            media=[photo_media("explore", photo_buf)],
            fallback=lambda: message.reply_photo(
                photo=photo_buf,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_explore_keyboard(),
                show_caption_above_media=True,
            ),
        )
        logger.info(f"Hunter {user.id} explored sector {sector_id} (+{gold_reward}g, +{xp_reward}xp, gift: {bool(gift_item)})")
    except Exception as exc:
        logger.error("Failed to render explore map image: %s", exc, exc_info=True)
        # Fallback text response
        fallback_caption = build_explore_caption(
            hunter=hunter,
            sector_info=sector_info,
            gold_reward=gold_reward,
            xp_reward=xp_reward,
            gift_item=gift_item,
            leveled_up=leveled_up,
            new_rank=new_rank,
            story=event_story,
            display_name=display_name,
        )
        await reply_rich(
            message,
            build_explore_rich(
                hunter=hunter,
                sector_info=sector_info,
                gold_reward=gold_reward,
                xp_reward=xp_reward,
                gift_item=gift_item,
                leveled_up=leveled_up,
                new_rank=new_rank,
                story=event_story,
                display_name=display_name,
            ),
            reply_markup=_explore_keyboard(),
            fallback=lambda: message.reply_text(
                fallback_caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=_explore_keyboard(),
            ),
        )
