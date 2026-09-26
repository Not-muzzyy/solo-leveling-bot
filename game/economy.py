"""Shared claim and shop operations used by Telegram handlers and the Mini App API."""

from __future__ import annotations

import asyncio
import copy
import math
import random
import time
from collections import OrderedDict
from dataclasses import dataclass

from game.hunter import add_xp
from game.shop import create_item_from_shop, get_shop_item
from models import Hunter, Item

CLAIM_COOLDOWN_SECONDS = 24 * 60 * 60
_action_locks: dict[int, asyncio.Lock] = {}
_purchase_results: OrderedDict[tuple[int, str], "PurchaseResult"] = OrderedDict()
_MAX_REMEMBERED_PURCHASES = 2048


class GameActionError(Exception):
    """A safe, user-facing failure from a game action."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ClaimResult:
    hunter: Hunter
    claimed: bool
    remaining_seconds: int = 0
    gold_reward: int = 0
    xp_reward: int = 0
    leveled_up: bool = False
    new_rank: str | None = None


@dataclass
class PurchaseResult:
    item: Item
    price: int
    gold_remaining: int


def _get_action_lock(user_id: int) -> asyncio.Lock:
    lock = _action_locks.get(user_id)
    if lock is None:
        lock = _action_locks[user_id] = asyncio.Lock()
    return lock


def claim_remaining(hunter: Hunter, now: float | None = None) -> int:
    now = now if now is not None else time.time()
    last_claim = hunter.last_claim_time or 0.0
    remaining = CLAIM_COOLDOWN_SECONDS - (now - last_claim) if last_claim else 0
    return math.ceil(remaining) if remaining > 0 else 0


def _restore_hunter(hunter: Hunter, snapshot: dict) -> None:
    hunter.__dict__.clear()
    hunter.__dict__.update(snapshot)


async def claim_daily_reward(db, user_id: int) -> ClaimResult:
    """Apply and persist a daily reward under the same lock used by the shop."""
    async with _get_action_lock(user_id):
        hunter = await db.get_hunter(user_id)
        if not hunter:
            raise GameActionError("hunter_not_found", "Awaken as a Hunter before claiming rewards.")

        remaining = claim_remaining(hunter)
        if remaining:
            return ClaimResult(hunter=hunter, claimed=False, remaining_seconds=remaining)

        snapshot = copy.deepcopy(hunter.__dict__)
        now = time.time()
        gold_reward = 50 + hunter.level * 10 + random.randint(-10, 20)
        xp_reward = 30 + hunter.level * 8 + random.randint(-5, 15)

        hunter.last_claim_time = now
        hunter.gold += gold_reward
        leveled_up, new_rank = add_xp(hunter, xp_reward)

        try:
            saved = await db.save_hunter(user_id)
        except Exception as exc:
            saved = False
            save_error = exc
        else:
            save_error = None

        if not saved:
            _restore_hunter(hunter, snapshot)
            # Restore the cached Telegram record if the write outcome was uncertain.
            try:
                await db.save_hunter(user_id)
            except Exception:
                pass
            raise GameActionError("storage_error", "Telegram storage did not confirm the claim. Please refresh and try again.") from save_error

        return ClaimResult(
            hunter=hunter,
            claimed=True,
            gold_reward=gold_reward,
            xp_reward=xp_reward,
            leveled_up=leveled_up,
            new_rank=new_rank,
        )


def _restore_inventory(inventory, items: list[Item], next_id: int) -> None:
    inventory.items = items
    inventory._next_id = next_id


async def purchase_shop_item(db, user_id: int, item_key: str, request_id: str | None = None) -> PurchaseResult:
    """Purchase an item with serialized balance checks and compensating saves."""
    request_id = request_id or f"callback-{time.time_ns()}"
    cache_key = (user_id, request_id)

    async with _get_action_lock(user_id):
        previous = _purchase_results.get(cache_key)
        if previous:
            _purchase_results.move_to_end(cache_key)
            return copy.deepcopy(previous)

        hunter = await db.get_hunter(user_id)
        inventory = await db.get_inventory(user_id)
        if not hunter or not inventory:
            raise GameActionError("hunter_not_found", "Awaken as a Hunter before shopping.")

        shop_entry = get_shop_item(item_key)
        if not shop_entry:
            raise GameActionError("item_not_found", "That item is not in the Hunter Shop.")

        price = int(shop_entry["price"])
        if hunter.gold < price:
            raise GameActionError("insufficient_gold", f"Need {price:,} Gold; your treasury has {hunter.gold:,}.")

        hunter_snapshot = copy.deepcopy(hunter.__dict__)
        old_items = copy.deepcopy(inventory.items)
        old_next_id = inventory._next_id
        item = create_item_from_shop(shop_entry)
        hunter.gold -= price
        inventory.add_item(item)

        try:
            inventory_saved = await db.save_inventory(user_id)
            if not inventory_saved:
                raise RuntimeError("Inventory write was not confirmed")
            hunter_saved = await db.save_hunter(user_id)
            if not hunter_saved:
                raise RuntimeError("Hunter write was not confirmed")
        except Exception as exc:
            _restore_hunter(hunter, hunter_snapshot)
            _restore_inventory(inventory, old_items, old_next_id)
            rollback_ok = False
            try:
                inventory_ok = await db.save_inventory(user_id)
                hunter_ok = await db.save_hunter(user_id)
                rollback_ok = inventory_ok and hunter_ok
            except Exception:
                pass
            detail = "Purchase was not saved. Please refresh before trying again."
            if not rollback_ok:
                detail = "Purchase storage is uncertain. Please contact a bot admin before retrying."
            raise GameActionError("storage_error", detail) from exc

        result = PurchaseResult(item=item, price=price, gold_remaining=hunter.gold)
        _purchase_results[cache_key] = copy.deepcopy(result)
        if len(_purchase_results) > _MAX_REMEMBERED_PURCHASES:
            _purchase_results.popitem(last=False)
        return result
