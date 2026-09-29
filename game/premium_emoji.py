"""Curated Telegram Premium custom emoji for user-facing bot messages.

Only IDs in this registry may be rendered. Keys are stable semantic names;
callers must never provide an emoji ID or fallback text of their own.
"""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import Final, NamedTuple


class EmojiSpec(NamedTuple):
    emoji_id: str
    fallback: str


_REGISTRY_DATA = {
    "lightning": ("5312016608254762256", "⚡️"),
    "fire": ("5312241539987020022", "🔥"),
    "crown": ("5357107601584693888", "👑"),
    "diamond": ("5309958691854754293", "💎"),
    "money": ("5350452584119279096", "💰"),
    "trophy": ("5312315739842026755", "🏆"),
    "chart": ("5350305691942788490", "📈"),
    "folder": ("5357315181649076022", "📁"),
    "megaphone": ("5309984423003823246", "📣"),
    "note": ("5373251851074415873", "📝"),
    "calendar": ("5433614043006903194", "📆"),
    "search": ("5309965701241379366", "🔎"),
    "idea": ("5312536423851630001", "💡"),
    "warning": ("5379748062124056162", "❗️"),
    "news": ("5434144690511290129", "📰"),
    "coin": ("5377690785674175481", "🪙"),
    "game": ("5309950797704865693", "🎮"),
    "books": ("5350481781306958339", "📚"),
    "top": ("5418085807791545980", "🔝"),
    "heart": ("5312138559556164615", "❤️"),
    # Established semantic aliases used by bot feature messages.
    "system": ("5312016608254762256", "⚡️"),
    "gem": ("5309958691854754293", "💎"),
    "gold": ("5350452584119279096", "💰"),
    "growth": ("5350305691942788490", "📈"),
    "announce": ("5309984423003823246", "📣"),
    "rank": ("5418085807791545980", "🔝"),
}

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_ID_RE = re.compile(r"^[0-9]+$")


def _build_registry() -> MappingProxyType[str, EmojiSpec]:
    """Validate the checked-in allowlist once and expose it as immutable data."""
    registry: dict[str, EmojiSpec] = {}
    for key, pair in _REGISTRY_DATA.items():
        if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
            raise RuntimeError(f"Invalid Premium emoji registry key: {key!r}")
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise RuntimeError(f"Invalid Premium emoji registry entry for {key!r}")
        emoji_id, fallback = pair
        if not isinstance(emoji_id, str) or not _ID_RE.fullmatch(emoji_id) or int(emoji_id) <= 0:
            raise RuntimeError(f"Invalid Telegram custom emoji ID for {key!r}")
        if not isinstance(fallback, str) or not fallback:
            raise RuntimeError(f"Invalid Premium emoji fallback for {key!r}")
        registry[key] = EmojiSpec(emoji_id=emoji_id, fallback=fallback)
    return MappingProxyType(registry)


PREMIUM_EMOJI_REGISTRY: Final = _build_registry()
PREMIUM_EMOJI_IDS: Final = MappingProxyType({
    key: spec.emoji_id for key, spec in PREMIUM_EMOJI_REGISTRY.items()
})


def _spec(key: str) -> EmojiSpec:
    if not isinstance(key, str):
        raise TypeError("Premium emoji key must be a string")
    try:
        return PREMIUM_EMOJI_REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"Unknown Premium emoji key: {key!r}") from exc


def premium_emoji(key: str) -> str:
    """Return safe Telegram HTML for a registry emoji, including its fallback."""
    spec = _spec(key)
    return f'<tg-emoji emoji-id="{spec.emoji_id}">{spec.fallback}</tg-emoji>'


def fallback_emoji(key: str) -> str:
    """Return the registry's ordinary Unicode emoji fallback for ``key``."""
    return _spec(key).fallback


# Feature-section aliases keep call sites readable and make the shared visual
# vocabulary explicit. Alias values are fixed at import from the allowlist.
_SECTION_KEYS: Final = MappingProxyType({
    "start": "lightning",
    "profile": "crown",
    "hunt": "lightning",
    "explore": "fire",
    "claim": "calendar",
    "shop": "diamond",
    "inventory": "folder",
    "equipment": "diamond",
    "forge": "fire",
    "guild": "crown",
    "guild_war": "megaphone",
    "duel": "game",
    "quest": "note",
    "tower": "top",
    "shadows": "fire",
    "leaderboard": "trophy",
    "help": "books",
    "redeem": "coin",
    "admin": "megaphone",
})

for _section, _key in _SECTION_KEYS.items():
    if _key not in PREMIUM_EMOJI_REGISTRY:
        raise RuntimeError(f"Unknown Premium emoji key for section {_section!r}")

SECTION_EMOJIS: Final = MappingProxyType({
    section: premium_emoji(key) for section, key in _SECTION_KEYS.items()
})
SECTION_EMOJI_IDS: Final = MappingProxyType({
    section: PREMIUM_EMOJI_IDS[key] for section, key in _SECTION_KEYS.items()
})


def premium_emoji_id(key: str) -> str:
    """Return an allowlisted Telegram custom emoji ID by semantic key."""
    return _spec(key).emoji_id


def validate_premium_emoji_id(emoji_id: str) -> str:
    """Accept only a numeric custom emoji ID present in the curated registry."""
    if not isinstance(emoji_id, str) or not _ID_RE.fullmatch(emoji_id):
        raise ValueError("Custom emoji ID must be a numeric registry ID")
    if emoji_id not in PREMIUM_EMOJI_IDS.values():
        raise ValueError("Custom emoji ID is not in the Premium emoji registry")
    return emoji_id


def section_emoji(section: str) -> str:
    """Return a curated Premium emoji for a known bot feature section."""
    if not isinstance(section, str):
        raise TypeError("Section name must be a string")
    try:
        return SECTION_EMOJIS[section]
    except KeyError as exc:
        raise KeyError(f"Unknown bot emoji section: {section!r}") from exc


def section_fallback_emoji(section: str) -> str:
    """Return the ordinary Unicode fallback used by a known feature section."""
    if not isinstance(section, str):
        raise TypeError("Section name must be a string")
    try:
        key = _SECTION_KEYS[section]
    except KeyError as exc:
        raise KeyError(f"Unknown bot emoji section: {section!r}") from exc
    return fallback_emoji(key)


def section_emoji_id(section: str) -> str:
    """Return an allowlisted custom emoji ID for a known feature section."""
    if not isinstance(section, str):
        raise TypeError("Section name must be a string")
    try:
        return SECTION_EMOJI_IDS[section]
    except KeyError as exc:
        raise KeyError(f"Unknown bot emoji section: {section!r}") from exc
