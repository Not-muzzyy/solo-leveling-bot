"""
channel_db.py — Telegram Channel as persistent database.

Stores all game data as JSON messages in a private Telegram channel.
Uses an in-memory cache for fast reads, flushing changes via edit_message_text.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from pyrogram import Client, utils
from pyrogram.errors import RPCError

utils.MIN_CHANNEL_ID = -10099999999999

# Telegram caps messages at 4096 chars (core.telegram.org/bots/api); stay under with margin
INDEX_SOFT_LIMIT = 3900


def _chunk_dict(items: list[tuple[str, object]], limit: int) -> list[dict]:
    """Greedy-pack (key, value) pairs into dicts whose compact JSON fits `limit` chars."""
    parts: list[dict] = []
    current: dict = {}
    for key, value in items:
        probe = {**current, key: value}
        if current and len(json.dumps(probe, separators=(",", ":"))) > limit:
            parts.append(current)
            current = {key: value}
        else:
            current = probe
    if current:
        parts.append(current)
    return parts  # ponytail: a single entry larger than `limit` ships alone; entries here are ~70 chars


def _merge_index_parts(part_texts: list[str], scalars: dict) -> dict:
    """Merge sharded part-message JSON texts with the pinned shell's scalar keys."""
    merged: dict = {}
    for raw in part_texts:
        if raw:
            merged.update(json.loads(raw))
    merged.update(scalars)  # scalars win on key collision
    return merged

from models import Hunter, Item, Inventory, Guild, RedeemCode

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """In-memory cache for a single hunter's data."""

    hunter: Hunter
    inventory: Inventory
    hunter_msg_id: int
    inventory_msg_id: int


class ChannelDB:
    """
    Uses a private Telegram channel as persistent storage.

    Layout:
    - Message #1 (pinned): INDEX — JSON mapping user_id → {hunter_msg_id, inv_msg_id}
    - Message #N: Hunter JSON or Inventory JSON
    """

    def __init__(self, bot: Client, channel_id: int) -> None:
        self.bot = bot
        self.channel_id = channel_id
        self._cache: dict[int, CacheEntry] = {}
        self._index_msg_id: Optional[int] = None
        self._index: dict[str, dict] = {}  # str(user_id) → {hunter_msg_id, inv_msg_id}
        self._index_meta: dict = {}        # non-hunter keys from the index (foreign schema fields, preserved on write)
        self._locks: dict[int, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        # ── Guild storage ─────────────────────────────────
        self._guild_cache: dict[int, Guild] = {}  # guild_id → Guild
        self._guild_index: dict[str, dict] = {}   # name.lower() → {guild_msg_id, owner_id}
        self._user_guild_map: dict[int, int] = {}  # user_id → guild_id
        # ── Redeem codes storage ──────────────────────────
        self._redeem_codes: dict[str, RedeemCode] = {}  # CODE.upper() → RedeemCode
        self._redeem_msg_id: Optional[int] = None
        # ── Sharded index + guild war state ───────────────
        self._index_part_ids: list[int] = []     # sharded index part message ids
        self._index_write_lock = asyncio.Lock()  # serializes index writes (parts must not interleave)
        self._war_msg_id: Optional[int] = None   # guild-war state message (Task 8)

    def _get_lock(self, user_id: int) -> asyncio.Lock:
        """Get or create a per-user write lock."""
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    # ── Initialization ────────────────────────────────────

    async def initialize(self) -> None:
        """
        Load the index from the pinned message and populate the cache.
        If no pinned message exists (first run), create the index.
        """
        logger.info("Initializing ChannelDB...")

        try:
            chat = await self.bot.get_chat(self.channel_id)

            pinned_id = chat.pinned_message.id if chat.pinned_message else None
            # If not reported in chat.pinned_message, search early messages for existing index
            if not pinned_id:
                early_msgs = await self.bot.get_messages(self.channel_id, list(range(1, 15)))
                for m in early_msgs:
                    if m and m.text and '"type":"index"' in m.text:
                        pinned_id = m.id
                        try:
                            await self.bot.pin_chat_message(self.channel_id, m.id, disable_notification=True)
                        except Exception:
                            pass
                        break

            if pinned_id:
                self._index_msg_id = pinned_id
                # Explicitly fetch the message text to avoid empty pinned_message cache
                pinned_msg = await self.bot.get_messages(self.channel_id, pinned_id)
                raw = ""
                if pinned_msg and pinned_msg.text and '"type"' in pinned_msg.text:
                    raw = pinned_msg.text
                elif chat.pinned_message and chat.pinned_message.text:
                    raw = chat.pinned_message.text
                elif pinned_msg and pinned_msg.text:
                    raw = pinned_msg.text

                try:
                    full_index = json.loads(raw)
                    part_ids = full_index.pop("parts", None)
                    if part_ids:
                        try:
                            part_msgs = await self.bot.get_messages(self.channel_id, part_ids)
                            texts = [m.text for m in part_msgs if m and m.text]
                            full_index = _merge_index_parts(texts, full_index)
                            self._index_part_ids = [m.id for m in part_msgs if m and m.text]
                        except Exception as pexc:
                            logger.error(f"Failed to load index part messages: {pexc}")
                    full_index.pop("type", None)
                    self._guild_index = full_index.pop("guild_names", {})
                    full_index.pop("guild_ids", None)
                    self._redeem_msg_id = full_index.pop("redeem_msg_id", None)
                    self._war_msg_id = full_index.pop("war_msg_id", None)
                    # Partition: only numeric, hunter-shaped entries are hunter
                    # records; anything else (foreign schema keys like
                    # namespace/schema_version/shards) is meta, preserved on write.
                    self._index = {
                        k: v for k, v in full_index.items()
                        if k.isdigit() and isinstance(v, dict) and "hunter_msg_id" in v
                    }
                    self._index_meta = {k: v for k, v in full_index.items() if k not in self._index}
                    logger.info(
                        f"Loaded index with {len(self._index)} hunters, {len(self._guild_index)} guilds."
                    )
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning(
                        f"Pinned message {pinned_id} is not valid JSON ({exc}). Re-creating index..."
                    )
                    self._index = {}
                    self._index_meta = {}
                    self._index_msg_id = None
                    await self._create_index_message()
            else:
                # First run: create index message
                logger.info("No pinned message found. Creating index...")
                await self._create_index_message()

            # Recovery scan: If index is empty, scan channel messages 1 to 100 to self-heal
            if not self._index:
                logger.info("Index is empty. Performing channel scan to discover existing hunters...")
                recovered_hunters = {}
                recovered_invs = {}
                recovered_guilds = {}
                for batch_start in range(1, 101, 50):
                    batch_msgs = await self.bot.get_messages(self.channel_id, list(range(batch_start, batch_start + 50)))
                    for bm in batch_msgs:
                        if not bm or not bm.text:
                            continue
                        try:
                            b_data = json.loads(bm.text)
                        except Exception:
                            continue
                        m_type = b_data.get("type")
                        if m_type == "inventory":
                            u = b_data.get("user_id")
                            if u:
                                recovered_invs[str(u)] = bm.id
                        elif m_type == "guild":
                            g_name = b_data.get("name", "").strip().lower()
                            if g_name:
                                recovered_guilds[g_name] = {
                                    "guild_msg_id": bm.id,
                                    "owner_id": b_data.get("owner_id"),
                                    "guild_id": b_data.get("guild_id"),
                                }
                        elif "user_id" in b_data and "level" in b_data:
                            u = b_data.get("user_id")
                            if u:
                                recovered_hunters[str(u)] = bm.id

                for u_str, h_mid in recovered_hunters.items():
                    if u_str in recovered_invs:
                        self._index[u_str] = {
                            "hunter_msg_id": h_mid,
                            "inv_msg_id": recovered_invs[u_str],
                        }
                if recovered_guilds:
                    self._guild_index.update(recovered_guilds)
                if self._index or self._guild_index:
                    logger.info(f"Self-healed index: recovered {len(self._index)} hunters, {len(self._guild_index)} guilds.")
                    await self._update_index_message()

        except RPCError as e:
            logger.error(f"Failed to initialize ChannelDB: {e}")
            raise

        # Populate cache from channel messages
        await self._load_all_hunters()
        await self._load_all_guilds()
        await self._load_all_redeem_codes()

        # Build user→guild map and synchronize hunter <-> guild relationships
        self._user_guild_map.clear()

        # 1. Map all confirmed guild members to their guild and ensure cached hunter has guild_id set
        for guild in self._guild_cache.values():
            for uid in guild.members:
                self._user_guild_map[uid] = guild.guild_id
                entry = self._cache.get(uid)
                if entry and entry.hunter.guild_id != guild.guild_id:
                    entry.hunter.guild_id = guild.guild_id

        # 2. Check cached hunters: reconcile orphaned or desynchronized guild IDs
        for uid, entry in self._cache.items():
            gid = entry.hunter.guild_id
            if gid:
                guild = self._guild_cache.get(gid)
                if not guild:
                    # Guild does not exist anymore; clear orphaned ID
                    entry.hunter.guild_id = None
                elif uid not in guild.members:
                    if len(guild.members) < 15:
                        guild.members.append(uid)
                        self._user_guild_map[uid] = gid
                    else:
                        entry.hunter.guild_id = None

        logger.info(f"ChannelDB initialized. {len(self._cache)} hunters, {len(self._guild_cache)} guilds cached.")

    async def _create_index_message(self) -> None:
        """Create and pin the index message."""
        index_data = {"type": "index"}
        msg = await self.bot.send_message(
            chat_id=self.channel_id,
            text=json.dumps(index_data, separators=(",", ":")),
        )
        self._index_msg_id = msg.id
        try:
            await self.bot.pin_chat_message(
                chat_id=self.channel_id,
                message_id=msg.id,
                disable_notification=True,
            )
        except RPCError as e:
            logger.warning(f"Could not pin index message: {e}")

    async def _update_index_message(self) -> None:
        """Update the pinned index (sharded into part messages when over the size limit)."""
        if not self._index_msg_id:
            await self._create_index_message()
            return

        async with self._index_write_lock:
            guild_ids_map = {
                str(m.get("guild_id", m.get("owner_id"))): {
                    "name": name,
                    "guild_msg_id": m["guild_msg_id"],
                    "owner_id": m.get("owner_id"),
                    "guild_id": m.get("guild_id", m.get("owner_id")),
                }
                for name, m in self._guild_index.items()
                if m.get("guild_id") or m.get("owner_id")
            }

            data = {
                "type": "index",
                "guild_names": self._guild_index,
                "guild_ids": guild_ids_map,
                **self._index_meta,
                **self._index,
            }
            if self._redeem_msg_id:
                data["redeem_msg_id"] = self._redeem_msg_id
            if self._war_msg_id:
                data["war_msg_id"] = self._war_msg_id

            full_text = json.dumps(data, separators=(",", ":"))
            if len(full_text) <= INDEX_SOFT_LIMIT:
                if not await self._edit_index_text(full_text):
                    return  # edit failed — keep parts intact so the shell stays loadable
                if self._index_part_ids:
                    await self._delete_index_parts()
                return

            # Overflow: pinned message becomes a shell pointing at part messages
            shell = {"type": "index"}
            for k in ("redeem_msg_id", "war_msg_id"):
                if k in data:
                    shell[k] = data.pop(k)

            chunks = _chunk_dict(list(data.items()), INDEX_SOFT_LIMIT)
            part_ids: list[int] = []
            for i, chunk in enumerate(chunks):
                text = json.dumps(chunk, separators=(",", ":"))
                old_id = self._index_part_ids[i] if i < len(self._index_part_ids) else None
                if old_id:
                    try:
                        await self.bot.edit_message_text(
                            chat_id=self.channel_id, message_id=old_id, text=text
                        )
                        part_ids.append(old_id)
                        continue
                    except RPCError as e:
                        if "not modified" in str(e).lower():
                            part_ids.append(old_id)
                            continue
                        logger.warning(f"Index part {old_id} invalid, re-posting: {e}")
                new_msg = await self.bot.send_message(chat_id=self.channel_id, text=text)
                part_ids.append(new_msg.id)

            stale = self._index_part_ids[len(part_ids):]
            if stale:
                try:
                    await self.bot.delete_messages(self.channel_id, stale)
                except RPCError:
                    pass
            self._index_part_ids = part_ids
            shell["parts"] = part_ids
            await self._edit_index_text(json.dumps(shell, separators=(",", ":")))

    async def _edit_index_text(self, text: str) -> bool:
        """Edit the pinned index message with recreate-on-deletion fallback.

        Returns True when the message (or its replacement) carries `text`,
        False when the edit failed for a transient reason (caller must not
        delete anything that message still references).
        """
        try:
            await self.bot.edit_message_text(
                chat_id=self.channel_id, message_id=self._index_msg_id, text=text
            )
            return True
        except RPCError as e:
            err_str = str(e).lower()
            if "not modified" in err_str:
                return True
            if "message_id_invalid" in err_str or "message not found" in err_str:
                logger.warning(f"Index message {self._index_msg_id} invalid/deleted. Re-creating...")
                await self._create_index_message()
                await self.bot.edit_message_text(
                    chat_id=self.channel_id, message_id=self._index_msg_id, text=text
                )
                return True
            logger.error(f"Failed to update index: {e}")
            return False

    async def _delete_index_parts(self) -> None:
        if self._index_part_ids:
            try:
                await self.bot.delete_messages(self.channel_id, self._index_part_ids)
            except RPCError:
                pass
            self._index_part_ids = []

    async def set_war_msg_id(self, msg_id: Optional[int]) -> None:
        """Record (or clear) the guild-war state message id in the pinned index."""
        self._war_msg_id = msg_id
        await self._update_index_message()

    async def _load_all_hunters(self) -> None:
        """Load all hunter data from channel into cache."""
        for uid_str, mapping in self._index.items():
            user_id = int(uid_str)
            try:
                await self._load_hunter_from_channel(user_id, mapping)
            except Exception as e:
                logger.error(f"Failed to load hunter {user_id}: {e}")

    async def _load_hunter_from_channel(
        self, user_id: int, mapping: dict
    ) -> None:
        """Load a single hunter + inventory from their channel messages."""
        hunter_msg_id = mapping["hunter_msg_id"]
        inv_msg_id = mapping["inv_msg_id"]

        try:
            hunter_msg = await self.bot.get_messages(self.channel_id, hunter_msg_id)
            if not hunter_msg or not hunter_msg.text:
                logger.warning(f"Could not read hunter message {hunter_msg_id} for user {user_id}")
                return
            hunter = Hunter.from_json(hunter_msg.text)

            inv_msg = await self.bot.get_messages(self.channel_id, inv_msg_id)
            if not inv_msg or not inv_msg.text:
                logger.warning(f"Could not read inventory message {inv_msg_id} for user {user_id}")
                return
            inventory = Inventory.from_json(inv_msg.text)

            self._cache[user_id] = CacheEntry(
                hunter=hunter,
                inventory=inventory,
                hunter_msg_id=hunter_msg_id,
                inventory_msg_id=inv_msg_id,
            )
            # Synchronize guild_id in index
            if str(user_id) in self._index:
                self._index[str(user_id)]["guild_id"] = hunter.guild_id
        except Exception as e:
            logger.error(f"Error loading hunter {user_id}: {e}")

    # ── Guild Initialization ──────────────────────────────

    async def _load_all_guilds(self) -> None:
        """Load all guild data from channel into cache."""
        for name_key, mapping in self._guild_index.items():
            guild_msg_id = mapping["guild_msg_id"]
            try:
                msg = await self.bot.get_messages(self.channel_id, guild_msg_id)
                if msg and msg.text:
                    guild = Guild.from_json(msg.text)
                    self._guild_cache[guild.guild_id] = guild
            except Exception as e:
                logger.error(f"Failed to load guild '{name_key}': {e}")

    # ── Guild CRUD Operations ────────────────────────────

    async def create_guild(self, guild: Guild) -> None:
        """Create a new guild and persist to channel."""
        async with self._global_lock:
            # 1. Send guild data as channel message
            guild_msg = await self.bot.send_message(
                chat_id=self.channel_id,
                text=guild.to_json(),
            )

            # 2. Update guild index
            name_key = guild.name.strip().lower()
            self._guild_index[name_key] = {
                "guild_msg_id": guild_msg.id,
                "owner_id": guild.owner_id,
                "guild_id": guild.guild_id,
            }
            await self._update_index_message()

            # 3. Cache
            self._guild_cache[guild.guild_id] = guild
            for uid in guild.members:
                self._user_guild_map[uid] = guild.guild_id
                entry = self._cache.get(uid)
                if entry:
                    entry.hunter.guild_id = guild.guild_id
            logger.info(f"Created guild: {guild.name} (ID: {guild.guild_id})")

    async def save_guild(self, guild_id: int) -> None:
        """Flush cached guild data to channel."""
        guild = self._guild_cache.get(guild_id)
        if not guild:
            return

        name_key = guild.name.strip().lower()
        mapping = self._guild_index.get(name_key)
        if not mapping:
            for k, m in self._guild_index.items():
                if m.get("guild_id") == guild_id or m.get("owner_id") == guild.owner_id:
                    mapping = m
                    break
        if not mapping:
            return

        try:
            await self.bot.edit_message_text(
                chat_id=self.channel_id,
                message_id=mapping["guild_msg_id"],
                text=guild.to_json(),
            )
        except RPCError as e:
            if "not modified" not in str(e).lower():
                logger.error(f"Failed to save guild {guild_id}: {e}")

    async def get_guild_by_id(self, guild_id: int) -> Optional[Guild]:
        """Get guild by numeric ID."""
        # 1. Direct cache lookup
        if guild_id in self._guild_cache:
            return self._guild_cache[guild_id]
        # 2. Search index mapping
        for m in self._guild_index.values():
            if m.get("guild_id") == guild_id or m.get("owner_id") == guild_id:
                gid = m.get("guild_id", m.get("owner_id"))
                if gid in self._guild_cache:
                    return self._guild_cache[gid]
        return None

    async def get_guild(self, guild_id: int) -> Optional[Guild]:
        """Get guild from cache by ID."""
        return await self.get_guild_by_id(guild_id)

    async def get_guild_by_name(self, name: str) -> Optional[Guild]:
        """Look up guild by name (case-insensitive) or by ID string."""
        clean = name.strip()
        if clean.isdigit():
            g = await self.get_guild_by_id(int(clean))
            if g:
                return g
        name_key = clean.lower()
        # Direct lookup across cached guilds first
        for g in self._guild_cache.values():
            if g.name.strip().lower() == name_key:
                return g
        # Fallback to index mapping
        mapping = self._guild_index.get(name_key)
        if mapping:
            gid = mapping.get("guild_id", mapping.get("owner_id"))
            if gid in self._guild_cache:
                return self._guild_cache[gid]
        return None

    async def get_user_guild(self, user_id: int) -> Optional[Guild]:
        """Get the guild a user belongs to with resilient multi-tier lookup."""
        # 1. Check user->guild map
        guild_id = self._user_guild_map.get(user_id)
        if guild_id and guild_id in self._guild_cache:
            return self._guild_cache[guild_id]

        # 2. Check cached hunter's guild_id
        entry = self._cache.get(user_id)
        if entry and entry.hunter.guild_id and entry.hunter.guild_id in self._guild_cache:
            self._user_guild_map[user_id] = entry.hunter.guild_id
            return self._guild_cache[entry.hunter.guild_id]

        # 3. Check membership in any cached guild
        for g in self._guild_cache.values():
            if user_id in g.members:
                self._user_guild_map[user_id] = g.guild_id
                if entry:
                    entry.hunter.guild_id = g.guild_id
                return g

        return None

    async def guild_name_exists(self, name: str) -> bool:
        """Check if a guild name is already taken."""
        name_key = name.strip().lower()
        if name_key in self._guild_index:
            return True
        for g in self._guild_cache.values():
            if g.name.strip().lower() == name_key:
                return True
        return False

    async def add_guild_member(self, guild_id: int, user_id: int) -> bool:
        """Add a member to a guild. Returns False if guild full or not found."""
        guild = self._guild_cache.get(guild_id)
        if not guild or user_id in guild.members:
            return False
        if len(guild.members) >= 15:
            return False
        guild.members.append(user_id)
        self._user_guild_map[user_id] = guild_id
        # Update hunter's guild_id
        entry = self._cache.get(user_id)
        if entry:
            entry.hunter.guild_id = guild_id
        if str(user_id) in self._index:
            self._index[str(user_id)]["guild_id"] = guild_id
        await self.save_guild(guild_id)
        await self.save_hunter(user_id)
        await self._update_index_message()
        return True

    async def remove_guild_member(self, guild_id: int, user_id: int) -> bool:
        """Remove a member from a guild."""
        guild = self._guild_cache.get(guild_id)
        if not guild or user_id not in guild.members:
            return False
        guild.members.remove(user_id)
        self._user_guild_map.pop(user_id, None)
        # Clear hunter's guild_id
        entry = self._cache.get(user_id)
        if entry:
            entry.hunter.guild_id = None
        if str(user_id) in self._index:
            self._index[str(user_id)]["guild_id"] = None
        await self.save_guild(guild_id)
        await self.save_hunter(user_id)
        await self._update_index_message()
        return True

    async def delete_guild(self, guild_id: int) -> None:
        """Delete a guild entirely — clears all members and removes from channel."""
        guild = self._guild_cache.get(guild_id)
        if not guild:
            return

        name_key = guild.name.strip().lower()
        mapping = self._guild_index.pop(name_key, None)
        if not mapping:
            for k, m in list(self._guild_index.items()):
                if m.get("guild_id") == guild_id or m.get("owner_id") == guild.owner_id:
                    mapping = self._guild_index.pop(k, None)
                    break

        # 1. Delete channel message
        if mapping and "guild_msg_id" in mapping:
            try:
                await self.bot.delete_messages(self.channel_id, mapping["guild_msg_id"])
            except RPCError:
                pass

        # 2. Clear all members' guild_id
        for uid in list(guild.members):
            entry = self._cache.get(uid)
            if entry:
                entry.hunter.guild_id = None
                await self.save_hunter(uid)
            if str(uid) in self._index:
                self._index[str(uid)]["guild_id"] = None
            self._user_guild_map.pop(uid, None)

        # 3. Remove from cache
        self._guild_cache.pop(guild_id, None)
        await self._update_index_message()
        logger.info(f"Deleted guild: {guild.name} (ID: {guild_id})")

    # ── CRUD Operations ──────────────────────────────────

    async def get_hunter(self, user_id: int) -> Optional[Hunter]:
        """Get hunter from cache."""
        entry = self._cache.get(user_id)
        return entry.hunter if entry else None

    async def get_all_hunters(self) -> list[Hunter]:
        """Get all cached hunters."""
        return [entry.hunter for entry in self._cache.values()]

    async def get_all_guilds(self) -> list[Guild]:
        """Get all cached guilds."""
        return list(self._guild_cache.values())

    async def get_inventory(self, user_id: int) -> Optional[Inventory]:
        """Get inventory from cache."""
        entry = self._cache.get(user_id)
        return entry.inventory if entry else None

    async def hunter_exists(self, user_id: int) -> bool:
        """Check if a hunter is registered."""
        return user_id in self._cache

    async def get_hunter_by_username(self, username: str) -> Optional[Hunter]:
        """Look up a hunter by Telegram username (case-insensitive, optional @)."""
        clean = username.strip().lstrip("@").lower()
        if not clean:
            return None
        for entry in self._cache.values():
            h = entry.hunter
            if h.username and h.username.lower() == clean:
                return h
        return None

    async def create_hunter(
        self, hunter: Hunter, starter_item: Item
    ) -> None:
        """
        Register a new hunter:
        1. Equip starter item on hunter
        2. Send hunter JSON message
        3. Send inventory JSON message
        4. Update index message
        5. Populate cache
        """
        async with self._global_lock:
            user_id = hunter.user_id

            # Guard against duplicate message creation
            if user_id in self._cache:
                logger.warning(f"Hunter {user_id} already exists in cache. Updating instead of duplicating.")
                await self.save_hunter(hunter)
                return
            if str(user_id) in self._index:
                logger.warning(f"Hunter {user_id} already in index. Re-loading instead of duplicating.")
                await self._load_hunter_from_channel(user_id, self._index[str(user_id)])
                return

            # Create inventory and equip the starter weapon before sending
            inventory = Inventory(user_id=user_id)
            inventory.add_item(starter_item)
            starter_item.is_equipped = True
            hunter.weapon_id = starter_item.id

            # 1. Send hunter data
            hunter_msg = await self.bot.send_message(
                chat_id=self.channel_id,
                text=hunter.to_json(),
            )

            # 2. Send inventory data
            inv_msg = await self.bot.send_message(
                chat_id=self.channel_id,
                text=inventory.to_json(),
            )

            # 3. Update index
            self._index[str(user_id)] = {
                "hunter_msg_id": hunter_msg.id,
                "inv_msg_id": inv_msg.id,
                "guild_id": hunter.guild_id,
            }
            await self._update_index_message()

            # 4. Cache
            self._cache[user_id] = CacheEntry(
                hunter=hunter,
                inventory=inventory,
                hunter_msg_id=hunter_msg.id,
                inventory_msg_id=inv_msg.id,
            )
            logger.info(f"Created hunter: {hunter.hunter_name} (ID: {user_id})")

    async def save_hunter(self, user_or_id: int | Hunter) -> bool:
        """Flush cached hunter data to channel."""
        if isinstance(user_or_id, Hunter):
            user_id = user_or_id.user_id
            if user_id in self._cache:
                self._cache[user_id].hunter = user_or_id
        elif hasattr(user_or_id, "user_id"):
            user_id = user_or_id.user_id
        else:
            user_id = user_or_id

        entry = self._cache.get(user_id)
        if not entry:
            return False

        if str(user_id) in self._index:
            self._index[str(user_id)]["guild_id"] = entry.hunter.guild_id

        async with self._get_lock(user_id):
            try:
                await self.bot.edit_message_text(
                    chat_id=self.channel_id,
                    message_id=entry.hunter_msg_id,
                    text=entry.hunter.to_json(),
                )
                return True
            except RPCError as e:
                err_str = str(e).lower()
                if "not modified" in err_str:
                    return True
                if "message_id_invalid" in err_str or "message not found" in err_str:
                    logger.warning(f"Hunter message {entry.hunter_msg_id} was deleted/invalid. Re-posting hunter {user_id}...")
                    new_msg = await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=entry.hunter.to_json(),
                    )
                    entry.hunter_msg_id = new_msg.id
                    if str(user_id) in self._index:
                        self._index[str(user_id)]["hunter_msg_id"] = new_msg.id
                    else:
                        self._index[str(user_id)] = {"hunter_msg_id": new_msg.id, "inv_msg_id": entry.inventory_msg_id}
                    await self._update_index_message()
                    return True
                else:
                    logger.error(f"Failed to save hunter {user_id}: {e}")
                    return False

    async def save_inventory(self, user_id: int) -> bool:
        """Flush cached inventory to channel."""
        entry = self._cache.get(user_id)
        if not entry:
            return False

        async with self._get_lock(user_id):
            try:
                await self.bot.edit_message_text(
                    chat_id=self.channel_id,
                    message_id=entry.inventory_msg_id,
                    text=entry.inventory.to_json(),
                )
                return True
            except RPCError as e:
                err_str = str(e).lower()
                if "not modified" in err_str:
                    return True
                if "message_id_invalid" in err_str or "message not found" in err_str:
                    logger.warning(f"Inventory message {entry.inventory_msg_id} was deleted/invalid. Re-posting inventory {user_id}...")
                    new_msg = await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=entry.inventory.to_json(),
                    )
                    entry.inventory_msg_id = new_msg.id
                    if str(user_id) in self._index:
                        self._index[str(user_id)]["inv_msg_id"] = new_msg.id
                    else:
                        self._index[str(user_id)] = {"hunter_msg_id": entry.hunter_msg_id, "inv_msg_id": new_msg.id}
                    await self._update_index_message()
                    return True
                else:
                    logger.error(f"Failed to save inventory {user_id}: {e}")
                    return False

    async def save_all(self, user_id: int) -> None:
        """Flush both hunter and inventory to channel."""
        await self.save_hunter(user_id)
        await self.save_inventory(user_id)

    async def add_item(self, user_id: int, item: Item) -> Item:
        """Add an item to a hunter's inventory and save."""
        entry = self._cache.get(user_id)
        if not entry:
            raise ValueError(f"Hunter {user_id} not found in cache")

        entry.inventory.add_item(item)
        await self.save_inventory(user_id)
        return item

    async def equip_item(self, user_id: int, item_id: int) -> Optional[Item]:
        """
        Equip an item. Unequips any currently equipped item of the same type.
        Returns the newly equipped item, or None if not found.
        """
        entry = self._cache.get(user_id)
        if not entry:
            return None

        item = entry.inventory.get_item(item_id)
        if not item:
            return None

        # Unequip current item of same type
        current = entry.inventory.get_equipped(item.type)
        if current:
            current.is_equipped = False

        # Equip new item
        item.is_equipped = True

        # Update hunter's equipment slot reference
        if item.type == "weapon":
            entry.hunter.weapon_id = item.id
        elif item.type == "armor":
            entry.hunter.armor_id = item.id
        elif item.type == "accessory":
            entry.hunter.accessory_id = item.id

        # Save both
        await self.save_all(user_id)
        return item

    async def remove_item(self, user_id: int, item_id: int) -> Optional[Item]:
        """Remove an item from a hunter's inventory and save."""
        entry = self._cache.get(user_id)
        if not entry:
            return None
        removed = entry.inventory.remove_item(item_id)
        if removed:
            await self.save_inventory(user_id)
        return removed

    # ── Redeem Code Storage ──────────────────────────────

    async def _load_all_redeem_codes(self) -> None:
        """Load all promo redeem codes from channel message into memory."""
        if not self._redeem_msg_id:
            return

        try:
            msg = await self.bot.get_messages(self.channel_id, self._redeem_msg_id)
            if msg and msg.text:
                payload = json.loads(msg.text)
                codes_dict = payload.get("codes", {})
                self._redeem_codes = {
                    code_key.upper(): RedeemCode.from_dict(c_data)
                    for code_key, c_data in codes_dict.items()
                }
                logger.info(f"Loaded {len(self._redeem_codes)} promo redeem codes.")
        except Exception as e:
            logger.error(f"Failed to load redeem codes: {e}")

    async def _save_redeem_codes(self) -> None:
        """Flush in-memory redeem codes to the dedicated channel message."""
        codes_dict = {
            code_key: code_obj.to_dict()
            for code_key, code_obj in self._redeem_codes.items()
        }
        payload = {
            "type": "redeem_codes",
            "codes": codes_dict,
        }
        text = json.dumps(payload, separators=(",", ":"))

        if not self._redeem_msg_id:
            try:
                msg = await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=text,
                )
                self._redeem_msg_id = msg.id
                await self._update_index_message()
            except RPCError as e:
                logger.error(f"Failed to create redeem codes message: {e}")
            return

        try:
            await self.bot.edit_message_text(
                chat_id=self.channel_id,
                message_id=self._redeem_msg_id,
                text=text,
            )
        except RPCError as e:
            err_str = str(e).lower()
            if "not modified" in err_str:
                return
            if "message_id_invalid" in err_str or "message not found" in err_str:
                logger.warning("Redeem message was deleted/invalid. Re-posting...")
                self._redeem_msg_id = None
                await self._save_redeem_codes()
            else:
                logger.error(f"Failed to save redeem codes: {e}")

    async def create_redeem_code(self, code: RedeemCode) -> None:
        """Register and persist a new promo redeem code."""
        async with self._global_lock:
            key = code.code.strip().upper()
            code.code = key
            self._redeem_codes[key] = code
            await self._save_redeem_codes()
            logger.info(f"Created redeem code: {key} (Type: {code.reward_type})")

    async def get_redeem_code(self, code_str: str) -> Optional[RedeemCode]:
        """Look up a promo code (case-insensitive)."""
        return self._redeem_codes.get(code_str.strip().upper())

    async def get_all_redeem_codes(self) -> list[RedeemCode]:
        """Retrieve all registered promo codes."""
        return list(self._redeem_codes.values())

    async def delete_redeem_code(self, code_str: str) -> bool:
        """Revoke and delete a promo code."""
        async with self._global_lock:
            key = code_str.strip().upper()
            if key in self._redeem_codes:
                del self._redeem_codes[key]
                await self._save_redeem_codes()
                return True
            return False

    async def claim_redeem_code(
        self, code_str: str, user_id: int
    ) -> tuple[bool, str, Optional[RedeemCode]]:
        """
        Atomically validate and claim a promo code for a hunter.
        Returns (success, message, code_obj_or_None).
        """
        async with self._global_lock:
            key = code_str.strip().upper()
            code = self._redeem_codes.get(key)
            if not code:
                return False, "❌ Invalid or unrecognized System Code.", None

            if code.has_claimed(user_id):
                return False, "⚠️ You have already redeemed this System Code!", code

            if code.is_depleted:
                return False, "❌ This System Code has reached its maximum claim limit!", code

            # Mark claimed
            code.claimed_by.append(user_id)
            await self._save_redeem_codes()
            return True, "Success", code
