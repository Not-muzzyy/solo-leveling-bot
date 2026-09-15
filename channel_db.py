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

from pyrogram import Client
from pyrogram.errors import RPCError

from models import Hunter, Item, Inventory, Guild

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
        self._locks: dict[int, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        # ── Guild storage ─────────────────────────────────
        self._guild_cache: dict[int, Guild] = {}  # guild_id → Guild
        self._guild_index: dict[str, dict] = {}   # name.lower() → {guild_msg_id, owner_id}
        self._user_guild_map: dict[int, int] = {}  # user_id → guild_id

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
            # Try to get pinned message via getChatPinnedMessage approach:
            # We'll send a test and look for pinned, or just create fresh
            chat = await self.bot.get_chat(self.channel_id)

            if chat.pinned_message:
                self._index_msg_id = chat.pinned_message.message_id
                try:
                    raw = chat.pinned_message.text
                    full_index = json.loads(raw)
                    full_index.pop("type", None)
                    self._guild_index = full_index.pop("guild_names", {})
                    self._index = full_index
                    logger.info(
                        f"Loaded index with {len(self._index)} hunters, {len(self._guild_index)} guilds."
                    )
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        "Pinned message is not valid index JSON. Creating new index."
                    )
                    self._index = {}
                    await self._update_index_message()
            else:
                # First run: create index message
                logger.info("No pinned message found. Creating index...")
                await self._create_index_message()

        except RPCError as e:
            logger.error(f"Failed to initialize ChannelDB: {e}")
            raise

        # Populate cache from channel messages
        await self._load_all_hunters()
        await self._load_all_guilds()
        # Build user→guild map from cached hunters
        for uid, entry in self._cache.items():
            if entry.hunter.guild_id:
                self._user_guild_map[uid] = entry.hunter.guild_id
        logger.info(f"ChannelDB initialized. {len(self._cache)} hunters, {len(self._guild_cache)} guilds cached.")

    async def _create_index_message(self) -> None:
        """Create and pin the index message."""
        index_data = {"type": "index"}
        msg = await self.bot.send_message(
            chat_id=self.channel_id,
            text=json.dumps(index_data, separators=(",", ":")),
        )
        self._index_msg_id = msg.message_id
        self._index = {}
        try:
            await self.bot.pin_chat_message(
                chat_id=self.channel_id,
                message_id=msg.message_id,
                disable_notification=True,
            )
        except RPCError as e:
            logger.warning(f"Could not pin index message: {e}")

    async def _update_index_message(self) -> None:
        """Update the pinned index message with current mappings."""
        if not self._index_msg_id:
            return

        data = {"type": "index", "guild_names": self._guild_index, **self._index}
        try:
            await self.bot.edit_message_text(
                chat_id=self.channel_id,
                message_id=self._index_msg_id,
                text=json.dumps(data, separators=(",", ":")),
            )
        except RPCError as e:
            # "Message is not modified" is fine — means data is already up to date
            if "not modified" not in str(e).lower():
                logger.error(f"Failed to update index: {e}")

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

        # Forward to self to read content (copy_message returns the text)
        # Actually, we use the trick of forwarding to the same channel
        # and reading, then deleting. But a simpler approach:
        # Use bot.forward_message to a temp read — but we can't read forwarded
        # text directly from the API response.
        #
        # Best approach: copy the message, read it, delete the copy.
        try:
            copied = await self.bot.copy_message(
                chat_id=self.channel_id,
                from_chat_id=self.channel_id,
                message_id=hunter_msg_id,
            )
            # copy_message returns MessageId, not Message with text.
            # We need forward_message instead, which returns Message with text.
            hunter_fwd = await self.bot.forward_message(
                chat_id=self.channel_id,
                from_chat_id=self.channel_id,
                message_id=hunter_msg_id,
            )
            hunter = Hunter.from_json(hunter_fwd.text)

            inv_fwd = await self.bot.forward_message(
                chat_id=self.channel_id,
                from_chat_id=self.channel_id,
                message_id=inv_msg_id,
            )
            inventory = Inventory.from_json(inv_fwd.text)

            # Delete the forwarded copies to keep channel clean
            try:
                await self.bot.delete_message(self.channel_id, copied.message_id)
                await self.bot.delete_message(self.channel_id, hunter_fwd.message_id)
                await self.bot.delete_message(self.channel_id, inv_fwd.message_id)
            except TelegramError:
                pass  # Non-critical

            self._cache[user_id] = CacheEntry(
                hunter=hunter,
                inventory=inventory,
                hunter_msg_id=hunter_msg_id,
                inventory_msg_id=inv_msg_id,
            )
        except Exception as e:
            logger.error(f"Error loading hunter {user_id}: {e}")

    # ── Guild Initialization ──────────────────────────────

    async def _load_all_guilds(self) -> None:
        """Load all guild data from channel into cache."""
        for name_key, mapping in self._guild_index.items():
            guild_msg_id = mapping["guild_msg_id"]
            try:
                fwd = await self.bot.forward_message(
                    chat_id=self.channel_id,
                    from_chat_id=self.channel_id,
                    message_id=guild_msg_id,
                )
                guild = Guild.from_json(fwd.text)
                try:
                    await self.bot.delete_message(self.channel_id, fwd.message_id)
                except RPCError:
                    pass
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
            self._guild_index[guild.name.lower()] = {
                "guild_msg_id": guild_msg.message_id,
                "owner_id": guild.owner_id,
            }
            await self._update_index_message()

            # 3. Cache
            self._guild_cache[guild.guild_id] = guild
            for uid in guild.members:
                self._user_guild_map[uid] = guild.guild_id
            logger.info(f"Created guild: {guild.name} (ID: {guild.guild_id})")

    async def save_guild(self, guild_id: int) -> None:
        """Flush cached guild data to channel."""
        guild = self._guild_cache.get(guild_id)
        if not guild:
            return

        name_key = guild.name.lower()
        mapping = self._guild_index.get(name_key)
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

    async def get_guild(self, guild_id: int) -> Optional[Guild]:
        """Get guild from cache."""
        return self._guild_cache.get(guild_id)

    async def get_guild_by_name(self, name: str) -> Optional[Guild]:
        """Look up guild by name."""
        name_key = name.lower()
        mapping = self._guild_index.get(name_key)
        if not mapping:
            return None
        # Find guild in cache by owner_id from mapping
        owner_id = mapping["owner_id"]
        return self._guild_cache.get(owner_id)

    async def get_user_guild(self, user_id: int) -> Optional[Guild]:
        """Get the guild a user belongs to."""
        guild_id = self._user_guild_map.get(user_id)
        if guild_id:
            return self._guild_cache.get(guild_id)
        return None

    async def guild_name_exists(self, name: str) -> bool:
        """Check if a guild name is already taken."""
        return name.lower() in self._guild_index

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
        await self.save_guild(guild_id)
        await self.save_hunter(user_id)
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
        await self.save_guild(guild_id)
        await self.save_hunter(user_id)
        return True

    async def delete_guild(self, guild_id: int) -> None:
        """Delete a guild entirely — clears all members and removes from channel."""
        guild = self._guild_cache.get(guild_id)
        if not guild:
            return

        name_key = guild.name.lower()
        mapping = self._guild_index.get(name_key)

        # 1. Delete channel message
        if mapping:
            try:
                await self.bot.delete_message(self.channel_id, mapping["guild_msg_id"])
            except RPCError:
                pass
            del self._guild_index[name_key]

        # 2. Clear all members' guild_id
        for uid in guild.members:
            entry = self._cache.get(uid)
            if entry:
                entry.hunter.guild_id = None
                await self.save_hunter(uid)
            self._user_guild_map.pop(uid, None)

        # 3. Remove from cache
        del self._guild_cache[guild_id]
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

    async def create_hunter(
        self, hunter: Hunter, starter_item: Item
    ) -> None:
        """
        Register a new hunter:
        1. Send hunter JSON message
        2. Create inventory with starter item, send inventory JSON message
        3. Update index message
        4. Populate cache
        """
        async with self._global_lock:
            user_id = hunter.user_id

            # 1. Send hunter data
            hunter_msg = await self.bot.send_message(
                chat_id=self.channel_id,
                text=hunter.to_json(),
            )

            # 2. Create inventory with starter item
            inventory = Inventory(user_id=user_id)
            inventory.add_item(starter_item)

            # Equip the starter weapon
            starter_item.is_equipped = True
            hunter.weapon_id = starter_item.id

            inv_msg = await self.bot.send_message(
                chat_id=self.channel_id,
                text=inventory.to_json(),
            )

            # 3. Update index
            self._index[str(user_id)] = {
                "hunter_msg_id": hunter_msg.message_id,
                "inv_msg_id": inv_msg.message_id,
            }
            await self._update_index_message()

            # Also save the hunter again since weapon_id was set
            await self.bot.edit_message_text(
                chat_id=self.channel_id,
                message_id=hunter_msg.message_id,
                text=hunter.to_json(),
            )

            # 4. Cache
            self._cache[user_id] = CacheEntry(
                hunter=hunter,
                inventory=inventory,
                hunter_msg_id=hunter_msg.message_id,
                inventory_msg_id=inv_msg.message_id,
            )
            logger.info(f"Created hunter: {hunter.hunter_name} (ID: {user_id})")

    async def save_hunter(self, user_id: int | Hunter) -> None:
        """Flush cached hunter data to channel."""
        if hasattr(user_id, "user_id"):
            user_id = user_id.user_id
        entry = self._cache.get(user_id)
        if not entry:
            return

        async with self._get_lock(user_id):
            try:
                await self.bot.edit_message_text(
                    chat_id=self.channel_id,
                    message_id=entry.hunter_msg_id,
                    text=entry.hunter.to_json(),
                )
            except RPCError as e:
                if "not modified" not in str(e).lower():
                    logger.error(f"Failed to save hunter {user_id}: {e}")

    async def save_inventory(self, user_id: int) -> None:
        """Flush cached inventory to channel."""
        entry = self._cache.get(user_id)
        if not entry:
            return

        async with self._get_lock(user_id):
            try:
                await self.bot.edit_message_text(
                    chat_id=self.channel_id,
                    message_id=entry.inventory_msg_id,
                    text=entry.inventory.to_json(),
                )
            except RPCError as e:
                if "not modified" not in str(e).lower():
                    logger.error(f"Failed to save inventory {user_id}: {e}")

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
