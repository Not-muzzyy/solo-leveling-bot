"""Authenticated JSON API for the Telegram Mini App, sharing the bot's ChannelDB."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import BOT_TOKEN, MINIAPP_ALLOWED_ORIGINS
from game.economy import GameActionError, claim_daily_reward, claim_remaining, purchase_shop_item
from game.shop import SHOP_ITEMS
from models import Guild, Hunter

api_app = FastAPI(title="Solo Leveling Mini App API", docs_url=None, redoc_url=None)
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=MINIAPP_ALLOWED_ORIGINS or ["http://localhost:5173"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Telegram-Init-Data"],
    allow_credentials=False,
)


class PurchasePayload(BaseModel):
    item_key: str = Field(min_length=1, max_length=80)
    request_id: str = Field(min_length=8, max_length=100)


def _unauthorized(message: str = "Open this app from Telegram to continue.") -> HTTPException:
    return HTTPException(status_code=401, detail={"code": "unauthorized", "message": message})


def _validate_init_data(raw_init_data: str) -> int:
    if not raw_init_data or not BOT_TOKEN:
        raise _unauthorized()

    try:
        pairs = parse_qsl(raw_init_data, keep_blank_values=True, strict_parsing=True)
        if len({key for key, _ in pairs}) != len(pairs):
            raise ValueError("duplicate field")
        fields = dict(pairs)
        received_hash = fields.pop("hash", "")
        if not received_hash:
            raise ValueError("missing hash")

        auth_date = int(fields["auth_date"])
        now = int(time.time())
        if auth_date > now + 30 or now - auth_date > 24 * 60 * 60:
            raise ValueError("expired init data")

        data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash):
            raise ValueError("hash mismatch")

        user = json.loads(fields["user"])
        user_id = int(user["id"])
        if user_id <= 0:
            raise ValueError("invalid user")
        return user_id
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise _unauthorized("Telegram authorization is invalid or expired.")


async def telegram_user_id(x_telegram_init_data: str = Header(default="")) -> int:
    return _validate_init_data(x_telegram_init_data)


def _db(request: Request):
    bot = getattr(request.app.state, "bot", None)
    db = getattr(bot, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail={"code": "starting", "message": "Hunter System is starting. Try again shortly."})
    return db


def _hunter_summary(hunter: Hunter) -> dict:
    return {
        "display_name": hunter.display_full_name,
        "rank": hunter.rank,
        "level": hunter.level,
        "xp": hunter.xp,
        "xp_needed": hunter.xp_needed,
        "gold": hunter.gold,
        "power": hunter.power,
        "last_claim_time": hunter.last_claim_time,
        "claim_remaining_seconds": claim_remaining(hunter),
        "guild_id": hunter.guild_id,
    }


async def _guild_view(db, guild: Guild) -> dict:
    members = []
    member_hunters: list[Hunter] = []
    for user_id in guild.members:
        hunter = await db.get_hunter(user_id)
        if not hunter:
            continue
        member_hunters.append(hunter)
        members.append({
            "display_name": hunter.display_full_name,
            "role": "owner" if user_id == guild.owner_id else "member",
            "rank": hunter.rank,
            "level": hunter.level,
            "power": hunter.power,
        })

    owner = await db.get_hunter(guild.owner_id)
    total_power = sum(member.power for member in member_hunters)
    return {
        "id": guild.guild_id,
        "name": guild.name,
        "description": guild.description or "No description recorded.",
        "owner_name": owner.display_full_name if owner else "Unknown Hunter",
        "member_count": len(member_hunters),
        "max_members": 15,
        "total_power": total_power,
        "average_level": round(sum(member.level for member in member_hunters) / len(member_hunters), 1) if member_hunters else 0,
        "total_gold": sum(member.gold for member in member_hunters),
        "war_score": guild.war_score,
        "war_wins": guild.war_wins,
        "war_losses": guild.war_losses,
        "xp_bonus_percent": 10,
        "members": members,
    }


def _raise_action_error(exc: GameActionError) -> HTTPException:
    status = {
        "hunter_not_found": 404,
        "item_not_found": 404,
        "claim_cooldown": 409,
        "insufficient_gold": 409,
        "storage_error": 503,
    }.get(exc.code, 400)
    return HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message})


@api_app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@api_app.get("/api/v1/me")
async def get_me(request: Request, user_id: int = Depends(telegram_user_id)) -> dict:
    db = _db(request)
    hunter = await db.get_hunter(user_id)
    if not hunter:
        raise HTTPException(status_code=404, detail={"code": "hunter_not_found", "message": "Awaken as a Hunter in the bot before opening the Mini App."})

    inventory = await db.get_inventory(user_id)
    guild = await db.get_user_guild(user_id)
    return {
        "hunter": _hunter_summary(hunter),
        "inventory_count": len(inventory.items) if inventory else 0,
        "guild": await _guild_view(db, guild) if guild else None,
    }


@api_app.post("/api/v1/claim")
async def claim(request: Request, user_id: int = Depends(telegram_user_id)) -> dict:
    try:
        result = await claim_daily_reward(_db(request), user_id)
    except GameActionError as exc:
        raise _raise_action_error(exc)
    if not result.claimed:
        raise HTTPException(
            status_code=409,
            detail={"code": "claim_cooldown", "message": "Daily ration already collected.", "remaining_seconds": result.remaining_seconds},
        )
    return {
        "gold_reward": result.gold_reward,
        "xp_reward": result.xp_reward,
        "leveled_up": result.leveled_up,
        "new_rank": result.new_rank,
        "hunter": _hunter_summary(result.hunter),
    }


@api_app.get("/api/v1/shop/catalog")
async def shop_catalog(user_id: int = Depends(telegram_user_id)) -> dict:
    del user_id  # Authentication is required even though the catalog is public game data.
    return {
        "categories": ["weapon", "armor", "accessory", "consumable", "material"],
        "items": [
            {
                "key": item["key"],
                "name": item["name"],
                "type": item["type"],
                "rarity": item["rarity"],
                "price": item["price"],
                "stats": {"attack": item["atk"], "defense": item["def"], "hp": item["hp"], "speed": item["spd"]},
            }
            for item in SHOP_ITEMS
        ],
    }


@api_app.post("/api/v1/shop/purchases")
async def buy_item(payload: PurchasePayload, request: Request, user_id: int = Depends(telegram_user_id)) -> dict:
    try:
        result = await purchase_shop_item(_db(request), user_id, payload.item_key, payload.request_id)
    except GameActionError as exc:
        raise _raise_action_error(exc)
    hunter = await _db(request).get_hunter(user_id)
    return {
        "item": {
            "id": result.item.id,
            "name": result.item.name,
            "type": result.item.type,
            "rarity": result.item.rarity,
            "stats": {
                "attack": result.item.atk_bonus,
                "defense": result.item.def_bonus,
                "hp": result.item.hp_bonus,
                "speed": result.item.spd_bonus,
            },
        },
        "price": result.price,
        "hunter": _hunter_summary(hunter),
    }


@api_app.get("/api/v1/guilds")
async def list_guilds(
    request: Request,
    sort: str = Query(default="power", pattern="^(power|level|gold|members)$"),
    user_id: int = Depends(telegram_user_id),
) -> dict:
    del user_id
    db = _db(request)
    guilds = await db.get_all_guilds()
    views = [await _guild_view(db, guild) for guild in guilds]
    sort_keys = {
        "power": ("total_power", "average_level", "total_gold"),
        "level": ("average_level", "total_power", "member_count"),
        "gold": ("total_gold", "total_power", "average_level"),
        "members": ("member_count", "total_power", "average_level"),
    }
    views.sort(key=lambda row: tuple(row[key] for key in sort_keys[sort]), reverse=True)
    return {"sort": sort, "guilds": views[:50]}


@api_app.get("/api/v1/guilds/{guild_id}")
async def get_guild(guild_id: int, request: Request, user_id: int = Depends(telegram_user_id)) -> dict:
    del user_id
    db = _db(request)
    guild = await db.get_guild(guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail={"code": "guild_not_found", "message": "Guild not found."})
    return await _guild_view(db, guild)
