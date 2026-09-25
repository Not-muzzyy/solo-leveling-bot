"""
handlers/arise.py — Shadow Monarch /arise Spawning, Guessing & /shadows Collection.

Handles:
- Group message counter (triggers wild shadow spawn every 250 messages).
- /arise <name> character guessing and shadow soldier extraction engine.
- /shadows army collection browser with Hallmark visual card & pagination.
- Superadmin management: /addshadow, /listshadows, /delshadow, /spawnshadow, /shadowstats.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
import time
from typing import Optional

from pyrogram import Client, filters, enums
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

import config
from config import (
    RARITIES,
    RARITY_EMOJI,
    SHADOW_SPAWN_MESSAGE_THRESHOLD,
    SHADOW_SPAWN_EXPIRY_SECONDS,
    SHADOW_EXTRACTION_REWARDS,
)
from game.font_manager import clean_and_normalize_name
from game.hunter import add_xp
from game.rich_text import escape_html, callback_button
from game.shadows_image import render_shadows_image, RARITY_POWER_VALUES
from models import Hunter, ShadowCharacter, UserShadow

logger = logging.getLogger(__name__)

# ── In-Memory Chat Telemetry & Active Spawns ─────────────────
# chat_id -> message_count since last spawn
_chat_message_counts: dict[int, int] = {}

# chat_id -> active spawn dict: {"character": ShadowCharacter, "spawned_at": float, "msg_id": int}
_active_spawns: dict[int, dict] = {}

# chat_id -> asyncio.Lock for atomic claim handling
_chat_locks: dict[int, asyncio.Lock] = {}


def _get_chat_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in _chat_locks:
        _chat_locks[chat_id] = asyncio.Lock()
    return _chat_locks[chat_id]


def is_superadmin(user_id: int) -> bool:
    """Verify if user is authorized superadmin or bot owner."""
    if not user_id:
        return False
    if config.OWNER_ID and user_id == config.OWNER_ID:
        return True
    return user_id in config.SUPERADMIN_IDS


def normalize_name_for_match(s: str) -> str:
    """
    Clean and normalize string for resilient character name matching.
    Lowercases, removes punctuation/hyphens/emojis, and collapses spaces.
    """
    if not s:
        return ""
    # Strip emojis and non-alphanumeric/non-hangul characters
    s = s.lower()
    s = re.sub(r"[^\w\s\uac00-\ud7a3]", " ", s)
    return " ".join(s.split())


GENERIC_TITLE_WORDS = {
    "commander", "shadow", "king", "beast", "knight", "general",
    "monarch", "lord", "chief", "leader", "captain", "marshal", "warlord", "soldier"
}


def match_character_name(guess: str, character: ShadowCharacter) -> bool:
    """
    Determine if user's guess matches the character name or any aliases.
    Supports case-insensitivity, stripped punctuation, and smart matching.
    """
    clean_guess = normalize_name_for_match(guess)
    if not clean_guess:
        return False

    # Check full primary name
    clean_primary = normalize_name_for_match(character.name)
    if clean_guess == clean_primary:
        return True

    # Check explicit aliases
    for alias in character.aliases:
        clean_alias = normalize_name_for_match(alias)
        if clean_guess == clean_alias:
            return True

    # Substring token match (e.g. 'Igris' in 'Blood-Red Commander Igris')
    # Must NOT be a generic title word like 'commander' or 'shadow'
    if len(clean_guess) >= 4 and clean_guess not in GENERIC_TITLE_WORDS:
        primary_tokens = clean_primary.split()
        if clean_guess in primary_tokens:
            return True
        for alias in character.aliases:
            if clean_guess in normalize_name_for_match(alias).split():
                return True

    return False



# ── Group Message Counter & Auto-Spawning ────────────────────

async def count_group_message(client: Client, message: Message) -> None:
    """
    Listen to incoming group messages and trigger a shadow spawn every 250 messages.
    """
    if not message.chat or message.chat.type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return

    # Ignore bot messages and service events
    if (message.from_user and message.from_user.is_bot) or message.service:
        return

    chat_id = message.chat.id
    current_count = _chat_message_counts.get(chat_id, 0) + 1
    _chat_message_counts[chat_id] = current_count

    if current_count >= SHADOW_SPAWN_MESSAGE_THRESHOLD:
        _chat_message_counts[chat_id] = 0
        asyncio.create_task(spawn_shadow_in_chat(client, chat_id))


async def spawn_shadow_in_chat(
    client: Client, chat_id: int, character_id: Optional[int] = None
) -> Optional[Message]:
    """
    Spawn a wild shadow entity into the specified group chat.
    """
    shadows_db = getattr(client, "shadows_db", None)
    if not shadows_db:
        return None

    # Check if there's already an active ungrabbed spawn
    now = time.time()
    existing_spawn = _active_spawns.get(chat_id)
    if existing_spawn:
        # If expired, clear it
        if now - existing_spawn.get("spawned_at", 0) > SHADOW_SPAWN_EXPIRY_SECONDS:
            _active_spawns.pop(chat_id, None)
        else:
            # Current spawn is still active
            return None

    # Select character
    if character_id:
        character = shadows_db.get_character(character_id)
    else:
        character = shadows_db.get_random_character(weighted=True)

    if not character:
        logger.debug(f"Cannot spawn shadow in chat {chat_id}: No characters in catalog.")
        return None

    r_emoji = RARITY_EMOJI.get(character.rarity, "⚪")
    caption = (
        "🌌 <b>A WILD SHADOW HAS APPEARED!</b>\n\n"
        "Guess the Solo Leveling character name from the image!\n"
        f"• <b>Rarity:</b> <code>[{character.rarity}]</code> {r_emoji}\n"
        "• <b>How to claim:</b> Type <code>/arise &lt;character name&gt;</code>\n\n"
        "⏱️ <i>You have 15 minutes before this rift closes!</i>"
    )

    try:
        if character.photo_file_id:
            spawn_msg = await client.send_photo(
                chat_id=chat_id,
                photo=character.photo_file_id,
                caption=caption,
                show_caption_above_media=True,
                parse_mode=enums.ParseMode.HTML,
            )
        else:
            spawn_msg = await client.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode=enums.ParseMode.HTML,
            )

        _active_spawns[chat_id] = {
            "character": character,
            "spawned_at": now,
            "msg_id": spawn_msg.id,
        }

        await shadows_db.record_spawn(character.id)
        logger.info(f"Spawned shadow '{character.name}' ({character.rarity}) in chat {chat_id}")
        return spawn_msg

    except Exception as exc:
        logger.error(f"Failed to spawn shadow in chat {chat_id}: {exc}")
        return None


# ── /arise Command Handler ───────────────────────────────────

async def handle_arise(client: Client, message: Message) -> None:
    """
    Handle /arise [character_name] command.
    Checks guess against currently active shadow entity and awards extraction.
    """
    user = message.from_user
    if not user:
        return

    chat_id = message.chat.id

    # Verify Hunter profile exists
    hunter: Optional[Hunter] = await client.db.get_hunter(user.id)
    if not hunter:
        await message.reply_text(
            "⚠️ <b>You must awaken first!</b> Use <b>/start</b> to create your Hunter profile before commanding shadows.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # Check for active spawn
    spawn_info = _active_spawns.get(chat_id)
    now = time.time()

    if not spawn_info or (now - spawn_info.get("spawned_at", 0) > SHADOW_SPAWN_EXPIRY_SECONDS):
        if spawn_info:
            _active_spawns.pop(chat_id, None)

        await message.reply_text(
            "ℹ️ <b>No active shadow rift right now!</b>\n"
            f"Wild shadows appear automatically every <b>{SHADOW_SPAWN_MESSAGE_THRESHOLD}</b> messages in this group. Keep chatting!",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    character: ShadowCharacter = spawn_info["character"]

    # Parse guess argument
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply_text(
            "💡 <b>How to claim:</b>\n"
            "Type <code>/arise &lt;character name&gt;</code> to claim this shadow!\n"
            f"Example: <code>/arise {character.name.split()[0]}</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    guess = parts[1].strip()

    # Match guess against character
    if not match_character_name(guess, character):
        await message.reply_text(
            "❌ <b>Incorrect name!</b> That's not this character's name. Look closely at the image and try again!",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # Atomic lock to prevent race condition between multiple players
    lock = _get_chat_lock(chat_id)
    async with lock:
        # Check if spawn is still active
        if chat_id not in _active_spawns:
            await message.reply_text(
                "⚡ <b>Already claimed!</b> Another hunter just extracted this shadow moments ago.",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        # Pop active spawn
        _active_spawns.pop(chat_id, None)

        shadows_db = getattr(client, "shadows_db", None)
        if not shadows_db:
            await message.reply_text("Error: Shadows database is not initialized.")
            return

        # Add shadow to hunter's collection
        user_shadow, is_new = await shadows_db.add_shadow_to_user(user.id, character)
        await shadows_db.record_claim(character.id)

        # Grant Gold & XP rewards
        rewards = SHADOW_EXTRACTION_REWARDS.get(
            character.rarity, {"gold": 500, "xp": 250}
        )
        gold_gain = rewards["gold"]
        xp_gain = rewards["xp"]

        hunter.gold += gold_gain
        leveled_up, new_rank = add_xp(hunter, xp_gain)
        await client.db.save_hunter(hunter)

        total_soldiers = await shadows_db.get_user_shadow_count(user.id)

    # Build victory announcement
    r_emoji = RARITY_EMOJI.get(character.rarity, "⚪")
    status_str = "✨ NEW DISCOVERY" if is_new else f"⚡ REINFORCED (Total: ×{user_shadow.count})"

    lvl_banner = ""
    if leveled_up:
        lvl_banner = f"\n🌟 <b>LEVEL UP!</b> Reached Level <b>{hunter.level}</b>!"
    if new_rank:
        lvl_banner += f"\n👑 <b>RANK UP!</b> Promoted to Rank <b>{new_rank}</b>!"

    victory_text = (
        f"🎉 <b>CONGRATULATIONS {user.mention}!</b>\n\n"
        f"You successfully acquired <b>{character.name}</b>!\n\n"
        f"• <b>Character:</b> <b>{character.name}</b>\n"
        f"• <b>Rarity:</b> <code>[{character.rarity}]</code> {r_emoji} ({status_str})\n"
        f"• <b>Bounty:</b> 💰 <code>+{gold_gain:,} Gold</code> ┊ ✨ <code>+{xp_gain:,} XP</code>\n"
        f"• <b>Your Shadow Army:</b> <code>{total_soldiers:,} Soldiers</code>"
        f"{lvl_banner}\n\n"
        "✨ <i>Use <b>/shadows</b> to view your collection!</i>"
    )

    await message.reply_text(victory_text, parse_mode=enums.ParseMode.HTML)


# ── /shadows Command & Interactive Army Browser ─────────────

async def handle_shadows(client: Client, message: Message) -> None:
    """
    Handle /shadows command.
    Renders high-definition Hallmark Army Card with interactive pagination buttons.
    """
    user = message.from_user
    if not user:
        return

    # Check for target user (support /shadows, /shadows @username, or reply)
    target_user_id = user.id
    target_user_name = user.first_name or "Hunter"

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user_id = message.reply_to_message.from_user.id
        target_user_name = message.reply_to_message.from_user.first_name or "Hunter"
    elif len(message.command) > 1:
        arg = message.command[1].strip()
        if arg.startswith("@"):
            h_obj = await client.db.get_hunter_by_username(arg)
            if not h_obj:
                await message.reply_text(
                    f"❌ <b>No registered Hunter found for</b> <code>{escape_html(arg)}</code>",
                    parse_mode=enums.ParseMode.HTML,
                )
                return
            target_user_id = h_obj.user_id
            target_user_name = h_obj.hunter_name
        elif arg.isdigit():
            target_user_id = int(arg)

    hunter: Optional[Hunter] = await client.db.get_hunter(target_user_id)
    if not hunter:
        await message.reply_text(
            "<b>[ SYSTEM REJECTED // 미등록 헌터 ]</b>\n\n"
            "This player is not yet awakened as a registered Hunter.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    shadows_db = getattr(client, "shadows_db", None)
    if not shadows_db:
        await message.reply_text("Error: Shadows database is not initialized.")
        return

    shadows = await shadows_db.get_user_shadows(target_user_id)

    # Sort shadows by rarity tier (Mythic -> Common) then count
    rarity_order = {r: i for i, r in enumerate(RARITIES[::-1])}
    shadows.sort(key=lambda s: (rarity_order.get(s.rarity, 0), s.count), reverse=True)

    page = 1
    page_size = 6
    total_pages = max(1, (len(shadows) + page_size - 1) // page_size)

    # Render Hallmark Card
    photo_buf = await asyncio.to_thread(
        render_shadows_image,
        hunter,
        shadows,
        page=page,
        total_pages=total_pages,
        filter_rarity=None,
    )

    caption = _build_shadows_caption(hunter, shadows, page, total_pages)
    keyboard = _build_shadows_keyboard(target_user_id, page, total_pages, filter_rarity=None)

    await message.reply_photo(
        photo=photo_buf,
        caption=caption,
        show_caption_above_media=True,
        reply_markup=keyboard,
        parse_mode=enums.ParseMode.HTML,
    )


def _build_shadows_caption(
    hunter: Hunter,
    shadows: list[UserShadow],
    page: int,
    total_pages: int,
    filter_rarity: Optional[str] = None,
) -> str:
    h_display = clean_and_normalize_name(hunter.hunter_name or f"Hunter #{hunter.user_id}")
    total_soldiers = sum(s.count for s in shadows)
    unique_count = len(shadows)

    page_size = 6
    start_idx = (page - 1) * page_size
    current_page_shadows = shadows[start_idx : start_idx + page_size]

    filter_tag = f" ┊ Filter: <code>{filter_rarity}</code>" if filter_rarity else ""

    lines = [
        f"👥 <b>{h_display}'s Shadow Army</b>",
        f"👑 <b>Rank {hunter.rank}</b> ┊ <b>Soldiers:</b> <code>{total_soldiers:,}</code> ┊ <b>Forms:</b> <code>{unique_count}</code> (Page {page}/{total_pages}){filter_tag}",
        "",
    ]

    if not current_page_shadows:
        lines.append("<i>You have not extracted any shadows yet!</i>")
    else:
        for s in current_page_shadows:
            r_emoji = RARITY_EMOJI.get(s.rarity, "⚪")
            lines.append(f"• <b>{s.name}</b> — <code>[{s.rarity}]</code> {r_emoji} (×{s.count})")

    lines.append("")
    lines.append("💡 <i>Claim wild shadows in chat with <b>/arise &lt;name&gt;</b></i>")

    return "\n".join(lines)


def _build_shadows_keyboard(
    target_user_id: int, page: int, total_pages: int, filter_rarity: Optional[str] = None
) -> Optional[InlineKeyboardMarkup]:
    """Build clean, single-row inline pagination buttons."""
    if total_pages <= 1:
        return None

    f_str = filter_rarity or "all"
    nav_row = []

    # Prev Button
    if page > 1:
        nav_row.append(
            callback_button(
                "◀ Prev",
                f"shadow_page_{target_user_id}_{page - 1}_{f_str}",
                style=enums.ButtonStyle.PRIMARY,
            )
        )
    else:
        nav_row.append(callback_button("◀", "shadow_noop"))

    # Page indicator
    nav_row.append(callback_button(f"{page} / {total_pages}", "shadow_noop"))

    # Next Button
    if page < total_pages:
        nav_row.append(
            callback_button(
                "Next ▶",
                f"shadow_page_{target_user_id}_{page + 1}_{f_str}",
                style=enums.ButtonStyle.PRIMARY,
            )
        )
    else:
        nav_row.append(callback_button("▶", "shadow_noop"))

    return InlineKeyboardMarkup([nav_row])


# ── Inline Callbacks for /shadows ───────────────────────────

async def shadows_callback(client: Client, query: CallbackQuery) -> None:
    """Handle pagination and filter callbacks for /shadows."""
    data = query.data
    if data == "shadow_noop":
        await query.answer()
        return

    shadows_db = getattr(client, "shadows_db", None)
    if not shadows_db:
        await query.answer("Shadows database unavailable.", show_alert=True)
        return

    # Parse callback: shadow_page_<uid>_<page>_<filter> OR shadow_filter_<uid>_<page>_<filter>
    parts = data.split("_")
    if len(parts) < 4:
        await query.answer()
        return

    action = parts[1]  # 'page' or 'filter'
    target_user_id = int(parts[2])
    requested_page = int(parts[3])
    raw_filter = parts[4] if len(parts) >= 5 else "all"
    filter_rarity = None if raw_filter == "all" else raw_filter.title()

    hunter = await client.db.get_hunter(target_user_id)
    if not hunter:
        await query.answer("Hunter not found.", show_alert=True)
        return

    all_shadows = await shadows_db.get_user_shadows(target_user_id)

    # Apply rarity filter if set
    if filter_rarity:
        filtered_shadows = [s for s in all_shadows if s.rarity.lower() == filter_rarity.lower()]
    else:
        filtered_shadows = all_shadows

    # Sort
    rarity_order = {r: i for i, r in enumerate(RARITIES[::-1])}
    filtered_shadows.sort(key=lambda s: (rarity_order.get(s.rarity, 0), s.count), reverse=True)

    page_size = 6
    total_pages = max(1, (len(filtered_shadows) + page_size - 1) // page_size)
    page = max(1, min(requested_page, total_pages))

    photo_buf = await asyncio.to_thread(
        render_shadows_image,
        hunter,
        filtered_shadows,
        page=page,
        total_pages=total_pages,
        filter_rarity=filter_rarity,
    )

    caption = _build_shadows_caption(hunter, filtered_shadows, page, total_pages, filter_rarity)
    keyboard = _build_shadows_keyboard(target_user_id, page, total_pages, filter_rarity=filter_rarity)

    try:
        await query.message.edit_media(
            media=InputMediaPhoto(photo_buf, caption=caption, parse_mode=enums.ParseMode.HTML),
            reply_markup=keyboard,
        )
        await query.answer()
    except Exception as exc:
        logger.warning(f"Could not update shadows card: {exc}")
        await query.answer()


# ── Superadmin Commands ──────────────────────────────────────

async def handle_add_shadow(client: Client, message: Message) -> None:
    """
    Superadmin command: /addshadow <rarity> <name> [| aliases]
    Must reply to an image or send with an attached photo.
    """
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("<b>[ ACCESS DENIED ]</b> Superadmin clearance required.")
        return

    shadows_db = getattr(client, "shadows_db", None)
    if not shadows_db:
        await message.reply_text("Error: Shadows database is not initialized.")
        return

    # Extract photo from replied-to message or current message
    photo_file_id = ""
    if message.reply_to_message and message.reply_to_message.photo:
        photo_file_id = message.reply_to_message.photo.file_id
    elif message.photo:
        photo_file_id = message.photo.file_id

    if not photo_file_id:
        await message.reply_text(
            "<b>[ COMMAND SYNTAX ERROR // 사진 누락 ]</b>\n\n"
            "<blockquote expandable>"
            "To add a shadow character, you must <b>reply to an image</b> or <b>attach a photo</b>!\n\n"
            "<b>Syntax:</b>\n"
            "<code>/addshadow &lt;Rarity&gt; &lt;Character Name&gt; [| alias1, alias2]</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/addshadow Legendary Blood-Red Commander Igris | Igris, 핏빛의 이그리트</code>\n\n"
            "<b>Valid Rarities:</b>\n"
            f"{', '.join(RARITIES)}"
            "</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # Extract command text (from message text or photo caption)
    text = message.text or message.caption or ""
    parts = text.strip().split(maxsplit=2)
    if len(parts) < 3:
        await message.reply_text(
            "<b>[ MISSING ARGUMENTS ]</b>\n"
            "Syntax: <code>/addshadow &lt;Rarity&gt; &lt;Name&gt; [| aliases]</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    raw_rarity = parts[1].strip().title()
    if raw_rarity not in RARITIES:
        await message.reply_text(
            f"<b>[ INVALID RARITY ]</b> Must be one of:\n{', '.join(RARITIES)}",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    name_and_aliases = parts[2].strip()
    if "|" in name_and_aliases:
        name_part, alias_part = name_and_aliases.split("|", 1)
        name = name_part.strip()
        aliases = [a.strip() for a in alias_part.split(",") if a.strip()]
    else:
        name = name_and_aliases
        aliases = []

    # Forward or upload image to the shadows database channel to persist permanent file_id
    channel_id = shadows_db.channel_id
    if channel_id:
        try:
            chan_msg = await client.send_photo(
                chat_id=channel_id,
                photo=photo_file_id,
                caption=f"SHADOW_CHARACTER // {name} [{raw_rarity}]",
            )
            # Use permanent channel file_id
            if chan_msg.photo:
                photo_file_id = chan_msg.photo.file_id
        except Exception as exc:
            logger.warning(f"Could not forward photo to shadows channel: {exc}")

    # Register in ShadowsDB
    char = await shadows_db.add_character(
        name=name,
        rarity=raw_rarity,
        photo_file_id=photo_file_id,
        aliases=aliases,
        created_by=user.id,
    )

    r_emoji = RARITY_EMOJI.get(char.rarity, "⚪")
    alias_str = ", ".join(char.aliases) if char.aliases else "None"

    confirm_text = (
        "<b>[ SYSTEM REGISTRY // SHADOW CHARACTER ENROLLED ]</b>\n"
        "<b>새로운 그림자 개체 등록 완료</b>\n\n"
        "<blockquote expandable>"
        f"• <b>Character ID:</b> <code>#{char.id}</code>\n"
        f"• <b>Entity Name:</b> <b>{char.name}</b>\n"
        f"• <b>Rarity Tier:</b> <code>[{char.rarity}]</code> {r_emoji}\n"
        f"• <b>Accepted Aliases:</b> <i>{escape_html(alias_str)}</i>\n"
        f"• <b>Media Status:</b> <code>Persisted & Active</code>\n"
        "</blockquote>\n\n"
        "✨ <i>This shadow will now spawn randomly every 250 messages or via <b>/spawnshadow</b>!</i>"
    )

    await message.reply_text(confirm_text, parse_mode=enums.ParseMode.HTML)


async def handle_list_shadows(client: Client, message: Message) -> None:
    """Superadmin command: /listshadows [page] — Display registered characters."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("<b>[ ACCESS DENIED ]</b> Superadmin clearance required.")
        return

    shadows_db = getattr(client, "shadows_db", None)
    if not shadows_db:
        await message.reply_text("Error: Shadows database is not initialized.")
        return

    chars = shadows_db.list_characters()
    if not chars:
        await message.reply_text(
            "<b>[ SHADOW CATALOG EMPTY ]</b>\nNo characters registered yet. Use <code>/addshadow</code> to enroll characters!",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    page = 1
    if len(message.command) > 1 and message.command[1].isdigit():
        page = int(message.command[1])

    page_size = 10
    total_pages = max(1, (len(chars) + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start = (page - 1) * page_size
    page_chars = chars[start : start + page_size]

    lines = []
    for c in page_chars:
        r_emoji = RARITY_EMOJI.get(c.rarity, "⚪")
        lines.append(
            f"• <code>#{c.id:02d}</code> <b>{c.name}</b> [{c.rarity}] {r_emoji}\n"
            f"  └ Spawns: <code>{c.times_spawned}</code> ┊ Claims: <code>{c.times_claimed}</code>"
        )

    roster_str = "\n".join(lines)
    text = (
        "<b>[ SHADOW CATALOG // REGISTERED CHARACTERS ]</b>\n"
        f"<b>Page {page} of {total_pages} (Total: {len(chars)} Characters)</b>\n\n"
        f"<blockquote expandable>\n{roster_str}\n</blockquote>\n\n"
        "<i>Use /addshadow to add more, /delshadow &lt;id&gt; to remove.</i>"
    )

    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)


async def handle_del_shadow(client: Client, message: Message) -> None:
    """Superadmin command: /delshadow <id> — Remove a character from the catalog."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("<b>[ ACCESS DENIED ]</b> Superadmin clearance required.")
        return

    shadows_db = getattr(client, "shadows_db", None)
    if not shadows_db:
        await message.reply_text("Error: Shadows database is not initialized.")
        return

    if len(message.command) < 2 or not message.command[1].isdigit():
        await message.reply_text("Syntax: <code>/delshadow &lt;character_id&gt;</code>", parse_mode=enums.ParseMode.HTML)
        return

    char_id = int(message.command[1])
    target = shadows_db.get_character(char_id)
    if not target:
        await message.reply_text(f"Character #{char_id} not found in catalog.", parse_mode=enums.ParseMode.HTML)
        return

    success = await shadows_db.delete_character(char_id)
    if success:
        await message.reply_text(
            f"<b>[ CHARACTER DELETED ]</b>\nRemoved <b>{target.name}</b> [#{char_id}] from the shadow pool.",
            parse_mode=enums.ParseMode.HTML,
        )
    else:
        await message.reply_text(f"Could not delete character #{char_id}.")


async def handle_spawn_shadow(client: Client, message: Message) -> None:
    """Superadmin command: /spawnshadow [id] — Instantly force-spawn a shadow in chat."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("<b>[ ACCESS DENIED ]</b> Superadmin clearance required.")
        return

    char_id = None
    if len(message.command) > 1 and message.command[1].isdigit():
        char_id = int(message.command[1])

    # Clear any active spawn to allow force-spawn
    _active_spawns.pop(message.chat.id, None)

    msg = await spawn_shadow_in_chat(client, message.chat.id, character_id=char_id)
    if not msg:
        await message.reply_text(
            "<b>[ SPAWN FAILED ]</b> Ensure characters are registered in the catalog via <code>/addshadow</code>.",
            parse_mode=enums.ParseMode.HTML,
        )


async def handle_shadow_stats(client: Client, message: Message) -> None:
    """Superadmin command: /shadowstats — Display system spawning & extraction telemetry."""
    user = message.from_user
    if not user or not is_superadmin(user.id):
        await message.reply_text("<b>[ ACCESS DENIED ]</b> Superadmin clearance required.")
        return

    shadows_db = getattr(client, "shadows_db", None)
    if not shadows_db:
        await message.reply_text("Error: Shadows database is not initialized.")
        return

    stats = shadows_db.get_stats()
    chat_count = _chat_message_counts.get(message.chat.id, 0)
    active = "Yes" if message.chat.id in _active_spawns else "No"

    text = (
        "<b>[ SHADOW MONARCH // TELEMETRY DOSSIER ]</b>\n\n"
        "<blockquote expandable>"
        f"• <b>Database Channel ID:</b> <code>{stats.get('channel_id')}</code>\n"
        f"• <b>Registered Characters:</b> <code>{stats.get('total_characters')}</code>\n"
        f"• <b>Monarch Hunters Indexed:</b> <code>{stats.get('total_users')}</code>\n"
        f"• <b>Worldwide Spawns:</b> <code>{stats.get('total_spawns')}</code>\n"
        f"• <b>Worldwide Extractions:</b> <code>{stats.get('total_claims')}</code>\n"
        f"• <b>Current Chat Count:</b> <code>{chat_count} / {SHADOW_SPAWN_MESSAGE_THRESHOLD}</code>\n"
        f"• <b>Active Spawn Nearby:</b> <code>{active}</code>\n"
        "</blockquote>"
    )

    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
