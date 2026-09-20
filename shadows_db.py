"""
shadows_db.py — Dedicated Channel Database for /arise and /shadows.

Stores the Solo Leveling character catalog, photo media references, and
individual hunter shadow armies in a private Telegram channel.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Optional

from pyrogram import Client
from pyrogram.errors import FloodWait

import config
from config import RARITIES, RARITY_WEIGHTS
from models import ShadowCharacter, UserShadow

logger = logging.getLogger(__name__)


class ShadowsDB:
    """
    Dedicated persistent database for the Shadow Monarch System.

    Channel Layout:
    - Pinned Message: INDEX — JSON containing catalog_msg_id, user_id → msg_id mappings, and telemetry.
    - Catalog Message: JSON list of all registered ShadowCharacter definitions.
    - User Messages: Per-hunter JSON list of UserShadow army collections.
    """

    def __init__(self, bot: Client, channel_id: Optional[int] = None) -> None:
        self.bot = bot
        # Use dedicated channel; fall back to DATA_CHANNEL_ID if SHADOWS_CHANNEL_ID is unset
        if channel_id is not None:
            self.channel_id = channel_id
        else:
            self.channel_id = config.SHADOWS_CHANNEL_ID or config.DATA_CHANNEL_ID
        self._index_msg_id: Optional[int] = None
        self._catalog_msg_id: Optional[int] = None

        # In-memory fast caches
        self._characters: dict[int, ShadowCharacter] = {}  # id -> ShadowCharacter
        self._user_shadows: dict[int, dict[int, UserShadow]] = {}  # user_id -> {char_id: UserShadow}
        self._user_msg_map: dict[int, int] = {}  # user_id -> msg_id in channel

        # Global stats
        self._total_spawns: int = 0
        self._total_claims: int = 0

        # Concurrency locks
        self._global_lock = asyncio.Lock()
        self._user_locks: dict[int, asyncio.Lock] = {}

    def _get_user_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._user_locks:
            self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]

    # ── Initialization & Recovery ─────────────────────────────

    async def initialize(self) -> None:
        """Initialize connection to the shadow database channel and load caches."""
        if not self.channel_id:
            logger.warning("ShadowsDB: No channel_id configured. Operating in in-memory mode only.")
            return

        logger.info(f"Initializing ShadowsDB on channel {self.channel_id}...")

        try:
            chat = await self.bot.get_chat(self.channel_id)
            pinned_id = chat.pinned_message.id if chat.pinned_message else None

            # Search early messages if pinned_message is not cached
            if not pinned_id:
                early_msgs = await self.bot.get_messages(self.channel_id, list(range(1, 20)))
                for m in early_msgs:
                    if m and m.text and '"type":"shadows_index"' in m.text:
                        pinned_id = m.id
                        try:
                            await self.bot.pin_chat_message(self.channel_id, m.id, disable_notification=True)
                        except Exception:
                            pass
                        break

            if pinned_id:
                self._index_msg_id = pinned_id
                pinned_msg = await self.bot.get_messages(self.channel_id, pinned_id)
                raw_text = (
                    pinned_msg.text
                    if pinned_msg and pinned_msg.text
                    else (chat.pinned_message.text if chat.pinned_message else "")
                )
                if raw_text and '"type":"shadows_index"' in raw_text:
                    try:
                        index_data = json.loads(raw_text)
                        self._catalog_msg_id = index_data.get("catalog_msg_id")
                        raw_users = index_data.get("users", {})
                        self._user_msg_map = {int(k): int(v) for k, v in raw_users.items() if str(k).isdigit()}
                        stats = index_data.get("stats", {})
                        self._total_spawns = stats.get("total_spawns", 0)
                        self._total_claims = stats.get("total_claims", 0)
                        logger.info(
                            f"ShadowsDB index loaded: {len(self._user_msg_map)} users indexed. "
                            f"Catalog msg_id: {self._catalog_msg_id}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to parse ShadowsDB index: {e}")
            else:
                # First-run initialization: create pinned index
                logger.info("No ShadowsDB index found. Creating fresh index message...")
                init_index = {
                    "type": "shadows_index",
                    "version": 1,
                    "catalog_msg_id": None,
                    "users": {},
                    "stats": {"total_characters": 0, "total_spawns": 0, "total_claims": 0},
                }
                msg = await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=json.dumps(init_index, indent=2),
                )
                self._index_msg_id = msg.id
                try:
                    await self.bot.pin_chat_message(self.channel_id, msg.id, disable_notification=True)
                except Exception as exc:
                    logger.warning(f"Could not pin ShadowsDB index message: {exc}")

            # Load character catalog
            await self._load_catalog()

        except Exception as err:
            logger.error(f"Error during ShadowsDB initialization: {err}", exc_info=True)

    async def _flush_index(self) -> None:
        """Write current index state to pinned message in channel."""
        if not self.channel_id or not self._index_msg_id:
            return

        index_data = {
            "type": "shadows_index",
            "version": 1,
            "catalog_msg_id": self._catalog_msg_id,
            "users": {str(uid): mid for uid, mid in self._user_msg_map.items()},
            "stats": {
                "total_characters": len(self._characters),
                "total_spawns": self._total_spawns,
                "total_claims": self._total_claims,
            },
        }

        try:
            await self.bot.edit_message_text(
                chat_id=self.channel_id,
                message_id=self._index_msg_id,
                text=json.dumps(index_data, indent=2),
            )
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
            await self.bot.edit_message_text(
                chat_id=self.channel_id,
                message_id=self._index_msg_id,
                text=json.dumps(index_data, indent=2),
            )
        except Exception as e:
            logger.error(f"Failed to flush ShadowsDB index: {e}")

    # ── Character Catalog Operations ──────────────────────────

    async def _load_catalog(self) -> None:
        """Fetch and populate character catalog from channel."""
        if not self.channel_id or not self._catalog_msg_id:
            return

        try:
            msg = await self.bot.get_messages(self.channel_id, self._catalog_msg_id)
            if msg and msg.text:
                data = json.loads(msg.text)
                chars_list = data.get("characters", [])
                for item in chars_list:
                    sc = ShadowCharacter.from_dict(item)
                    self._characters[sc.id] = sc
                logger.info(f"Loaded {len(self._characters)} shadow characters from catalog.")
        except Exception as e:
            logger.error(f"Failed to load ShadowsDB character catalog: {e}")

    async def _flush_catalog(self) -> None:
        """Flush in-memory character catalog to the database channel."""
        if not self.channel_id:
            return

        payload = {
            "type": "shadow_catalog",
            "updated_at": time.time(),
            "characters": [c.to_dict() for c in self._characters.values()],
        }
        text = json.dumps(payload, indent=2)

        if self._catalog_msg_id:
            try:
                await self.bot.edit_message_text(
                    chat_id=self.channel_id,
                    message_id=self._catalog_msg_id,
                    text=text,
                )
                return
            except Exception:
                pass

        # If editing fails or no catalog msg exists, create a new one
        try:
            msg = await self.bot.send_message(chat_id=self.channel_id, text=text)
            self._catalog_msg_id = msg.id
            await self._flush_index()
        except Exception as e:
            logger.error(f"Failed to create new catalog message: {e}")

    async def add_character(
        self,
        name: str,
        rarity: str,
        photo_file_id: str,
        aliases: Optional[list[str]] = None,
        created_by: int = 0,
    ) -> ShadowCharacter:
        """Register a new character in the shadow catalog."""
        async with self._global_lock:
            next_id = max(self._characters.keys(), default=0) + 1
            clean_aliases = [a.strip() for a in (aliases or []) if a.strip()]

            # Auto-generate common normalized aliases if not already included
            lower_name = name.strip().lower()
            if lower_name not in [a.lower() for a in clean_aliases]:
                clean_aliases.append(name.strip())

            char = ShadowCharacter(
                id=next_id,
                name=name.strip(),
                rarity=rarity.title(),
                photo_file_id=photo_file_id,
                aliases=clean_aliases,
                created_by=created_by,
                created_at=time.time(),
                times_spawned=0,
                times_claimed=0,
            )

            self._characters[next_id] = char
            await self._flush_catalog()
            logger.info(f"Added shadow character #{char.id}: {char.name} [{char.rarity}]")
            return char

    def get_character(self, char_id: int) -> Optional[ShadowCharacter]:
        """Fetch character by ID."""
        return self._characters.get(char_id)

    def list_characters(self) -> list[ShadowCharacter]:
        """Return all registered characters sorted by ID."""
        return sorted(self._characters.values(), key=lambda c: c.id)

    async def delete_character(self, char_id: int) -> bool:
        """Delete a character from the catalog."""
        async with self._global_lock:
            if char_id in self._characters:
                del self._characters[char_id]
                await self._flush_catalog()
                return True
            return False

    def get_random_character(self, weighted: bool = True) -> Optional[ShadowCharacter]:
        """Pick a random character from the pool for spawning."""
        chars = list(self._characters.values())
        if not chars:
            return None

        if not weighted:
            return random.choice(chars)

        # Weighted selection based on rarity tiers
        rarity_weights_map = dict(zip(RARITIES, RARITY_WEIGHTS))
        weights = [rarity_weights_map.get(c.rarity, 10.0) for c in chars]
        return random.choices(chars, weights=weights, k=1)[0]

    async def record_spawn(self, char_id: int) -> None:
        """Increment spawn telemetry for a character."""
        char = self._characters.get(char_id)
        if char:
            char.times_spawned += 1
        self._total_spawns += 1
        asyncio.create_task(self._flush_catalog())

    async def record_claim(self, char_id: int) -> None:
        """Increment claim telemetry for a character."""
        char = self._characters.get(char_id)
        if char:
            char.times_claimed += 1
        self._total_claims += 1
        asyncio.create_task(self._flush_catalog())

    # ── User Shadow Army Operations ───────────────────────────

    async def _load_user_shadows(self, user_id: int) -> None:
        """Load player shadow army from channel message."""
        msg_id = self._user_msg_map.get(user_id)
        if not self.channel_id or not msg_id:
            self._user_shadows[user_id] = {}
            return

        try:
            msg = await self.bot.get_messages(self.channel_id, msg_id)
            if msg and msg.text:
                data = json.loads(msg.text)
                army = {}
                for raw in data.get("shadows", []):
                    us = UserShadow.from_dict(raw)
                    army[us.character_id] = us
                self._user_shadows[user_id] = army
        except Exception as e:
            logger.error(f"Failed to load shadows for user {user_id}: {e}")
            self._user_shadows[user_id] = {}

    async def _flush_user_shadows(self, user_id: int) -> None:
        """Flush player's shadow army to their channel message."""
        if not self.channel_id:
            return

        army = self._user_shadows.get(user_id, {})
        payload = {
            "type": "user_shadows",
            "user_id": user_id,
            "updated_at": time.time(),
            "shadows": [s.to_dict() for s in army.values()],
        }
        text = json.dumps(payload, indent=2)

        msg_id = self._user_msg_map.get(user_id)
        if msg_id:
            try:
                await self.bot.edit_message_text(
                    chat_id=self.channel_id,
                    message_id=msg_id,
                    text=text,
                )
                return
            except Exception:
                pass

        # Send new message and update index
        try:
            msg = await self.bot.send_message(chat_id=self.channel_id, text=text)
            self._user_msg_map[user_id] = msg.id
            await self._flush_index()
        except Exception as e:
            logger.error(f"Failed to save shadow army for user {user_id}: {e}")

    async def get_user_shadows(self, user_id: int) -> list[UserShadow]:
        """Retrieve all shadow soldiers owned by a hunter."""
        lock = self._get_user_lock(user_id)
        async with lock:
            if user_id not in self._user_shadows:
                await self._load_user_shadows(user_id)
            return list(self._user_shadows.get(user_id, {}).values())

    async def get_user_shadow_count(self, user_id: int) -> int:
        """Return total number of shadow soldiers owned (sum of duplicates)."""
        shadows = await self.get_user_shadows(user_id)
        return sum(s.count for s in shadows)

    async def add_shadow_to_user(
        self, user_id: int, character: ShadowCharacter
    ) -> tuple[UserShadow, bool]:
        """
        Add an extracted shadow to a player's army.
        Returns (UserShadow, is_first_time_acquired).
        """
        lock = self._get_user_lock(user_id)
        async with lock:
            if user_id not in self._user_shadows:
                await self._load_user_shadows(user_id)

            army = self._user_shadows[user_id]
            now = time.time()

            if character.id in army:
                existing = army[character.id]
                existing.count += 1
                existing.last_acquired = now
                if character.photo_file_id:
                    existing.photo_file_id = character.photo_file_id
                is_first = False
                res = existing
            else:
                new_shadow = UserShadow(
                    character_id=character.id,
                    name=character.name,
                    rarity=character.rarity,
                    count=1,
                    first_acquired=now,
                    last_acquired=now,
                    photo_file_id=character.photo_file_id,
                )
                army[character.id] = new_shadow
                is_first = True
                res = new_shadow

            # Asynchronously flush to channel in background
            asyncio.create_task(self._flush_user_shadows(user_id))
            return res, is_first

    def get_stats(self) -> dict:
        """Return global telemetry and stats."""
        return {
            "total_characters": len(self._characters),
            "total_users": len(self._user_msg_map),
            "total_spawns": self._total_spawns,
            "total_claims": self._total_claims,
            "channel_id": self.channel_id,
        }
