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

from telegram import Bot
from telegram.error import TelegramError

from models import Hunter, Item, Inventory

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

    def __init__(self, bot: Bot, channel_id: int) -> None:
        self.bot = bot
        self.channel_id = channel_id
        self._cache: dict[int, CacheEntry] = {}
        self._index_msg_id: Optional[int] = None
        self._index: dict[str, dict] = {}  # str(user_id) → {hunter_msg_id, inv_msg_id}
        self._locks: dict[int, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

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
                    self._index = json.loads(raw)
                    self._index.pop("type", None)
                    logger.info(
                        f"Loaded index with {len(self._index)} hunters."
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

        except TelegramError as e:
            logger.error(f"Failed to initialize ChannelDB: {e}")
            raise

        # Populate cache from channel messages
        await self._load_all_hunters()
        logger.info(f"ChannelDB initialized. {len(self._cache)} hunters cached.")

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
        except TelegramError as e:
            logger.warning(f"Could not pin index message: {e}")

    async def _update_index_message(self) -> None:
        """Update the pinned index message with current mappings."""
        if not self._index_msg_id:
            return

        data = {"type": "index", **self._index}
        try:
            await self.bot.edit_message_text(
                chat_id=self.channel_id,
                message_id=self._index_msg_id,
                text=json.dumps(data, separators=(",", ":")),
            )
        except TelegramError as e:
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

    # ── CRUD Operations ──────────────────────────────────

    async def get_hunter(self, user_id: int) -> Optional[Hunter]:
        """Get hunter from cache."""
        entry = self._cache.get(user_id)
        return entry.hunter if entry else None

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

    async def save_hunter(self, user_id: int) -> None:
        """Flush cached hunter data to channel."""
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
            except TelegramError as e:
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
            except TelegramError as e:
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
