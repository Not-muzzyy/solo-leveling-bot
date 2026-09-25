"""Regression tests for the 2026-09 stability fixes. Run: python -m pytest tests/ -v"""

import asyncio

# Ensure event loop exists on Python 3.12+ / 3.14+ before pyrogram imports
# (same bootstrap as main.py:14-18)
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import json
import time

from channel_db import CacheEntry, ChannelDB
from models import Hunter, Inventory


def _db_with_hunter(username: str = "JohnDoe", user_id: int = 42) -> ChannelDB:
    db = ChannelDB(bot=None, channel_id=0)
    h = Hunter(user_id=user_id, username=username, hunter_name="John")
    db._cache[user_id] = CacheEntry(
        hunter=h, inventory=Inventory(user_id=user_id),
        hunter_msg_id=1, inventory_msg_id=2,
    )
    return db


def test_get_hunter_by_username():
    db = _db_with_hunter()
    assert asyncio.run(db.get_hunter_by_username("johndoe")) is db._cache[42].hunter
    assert asyncio.run(db.get_hunter_by_username("@JohnDoe")) is db._cache[42].hunter
    assert asyncio.run(db.get_hunter_by_username("  nobody  ")) is None
    assert asyncio.run(db.get_hunter_by_username("@")) is None


def test_claim_last_claim_time_backcompat():
    # legacy JSON without the field must deserialize with the default
    old = Hunter.from_json('{"user_id":1,"username":"u","hunter_name":"n","type":"hunter"}')
    assert old.last_claim_time == 0.0
    old.last_claim_time = 1000.0
    assert Hunter.from_json(old.to_json()).last_claim_time == 1000.0


def test_claim_cooldown_check():
    from handlers.claim import _check_cooldown
    h = Hunter(user_id=1, username="u", hunter_name="n", last_claim_time=0.0)
    assert _check_cooldown(h, 1) is None
    h.last_claim_time = time.time()
    assert (_check_cooldown(h, 1) or 0) > 86000
    h.last_claim_time = time.time() - 86401
    assert _check_cooldown(h, 1) is None
