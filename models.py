"""
models.py — Core data models for the Hunter RPG system.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Hunter:
    """Represents a player's Hunter profile."""

    user_id: int
    username: str
    hunter_name: str
    level: int = 1
    rank: str = "E"
    xp: int = 0
    xp_needed: int = 100
    gold: int = 100
    hp: int = 100
    max_hp: int = 100
    str_stat: int = 7
    agi: int = 7
    vit: int = 7
    int_stat: int = 7
    per: int = 7
    power: int = 35
    title: str = "Novice Hunter"
    weapon_id: Optional[int] = None
    armor_id: Optional[int] = None
    accessory_id: Optional[int] = None
    total_hunts: int = 0
    victories: int = 0
    defeats: int = 0
    duel_wins: int = 0
    duel_losses: int = 0
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    guild_id: Optional[int] = None  # guild_id they belong to (= owner_id if owner)
    guild_war_wins: int = 0
    guild_war_losses: int = 0
    # ── Daily Quotas & Cooldown Persistence ───────────────
    daily_hunts: int = 0
    last_hunt_date: str = ""
    last_hunt_time: float = 0.0
    daily_explores: int = 0
    last_explore_date: str = ""
    last_explore_time: float = 0.0
    current_explore_node: int = 0
    # ── Demon Castle Tower ────────────────────────────────
    tower_floor: int = 1
    tower_highest_floor: int = 0
    tower_keys: int = 3
    last_tower_date: str = ""
    # ── System Daily Quests & Free Attributes ─────────────
    unspent_stat_points: int = 0
    daily_quest_hunts: int = 0
    daily_quest_explore: int = 0
    daily_quest_duel: int = 0
    daily_quest_use: int = 0
    daily_quest_claimed: bool = False
    last_quest_date: str = ""

    def check_and_reset_daily(self) -> None:
        """Check if UTC calendar date has changed and reset daily quotas accordingly."""
        from datetime import datetime, timezone
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.last_hunt_date != today_str:
            self.daily_hunts = 0
            self.last_hunt_date = today_str
        if self.last_explore_date != today_str:
            self.daily_explores = 0
            self.last_explore_date = today_str
        if self.last_tower_date != today_str:
            self.tower_keys = 3
            self.last_tower_date = today_str
        if self.last_quest_date != today_str:
            self.daily_quest_hunts = 0
            self.daily_quest_explore = 0
            self.daily_quest_duel = 0
            self.daily_quest_use = 0
            self.daily_quest_claimed = False
            self.last_quest_date = today_str

    @property
    def display_full_name(self) -> str:
        """Return the hunter's real First Name + Last Name, avoiding usernames and normalizing fancy fonts."""
        from game.font_manager import clean_and_normalize_name
        fn = (self.first_name or "").strip()
        ln = (self.last_name or "").strip()
        if fn and ln:
            raw = f"{fn} {ln}"
        elif fn:
            raw = fn
        elif ln:
            raw = ln
        else:
            raw = (self.hunter_name or f"Hunter #{self.user_id}").strip()
        return clean_and_normalize_name(raw)

    @property
    def combat_power(self) -> int:
        """Alias for power stat to represent total combat power."""
        return self.power

    @property
    def exp(self) -> int:
        """Alias for xp."""
        return self.xp

    def recalculate_power(self) -> None:
        """Recalculate total power from base stats."""
        self.power = self.str_stat + self.agi + self.vit + self.int_stat + self.per

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        d = asdict(self)
        d["type"] = "hunter"
        return d

    def to_json(self) -> str:
        """Serialize to compact JSON string."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict) -> Hunter:
        """Deserialize from dictionary with safe field filtering."""
        import dataclasses
        d = dict(data)
        d.pop("type", None)
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, text: str) -> Hunter:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(text))


@dataclass
class Item:
    """Represents an item in a Hunter's inventory."""

    id: int
    name: str
    type: str  # weapon / armor / accessory / consumable / material
    rarity: str = "Common"
    atk_bonus: int = 0
    def_bonus: int = 0
    hp_bonus: int = 0
    spd_bonus: int = 0
    is_equipped: bool = False
    upgrade_level: int = 0

    @property
    def display_name(self) -> str:
        """Formatted item name with upgrade prefix if enhanced (+1, +2, etc.)."""
        if self.upgrade_level > 0:
            return f"+{self.upgrade_level} {self.name}"
        return self.name

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Item:
        """Deserialize from dictionary with safe field filtering."""
        import dataclasses
        d = dict(data)
        item_type = d.get("type", "weapon")
        d.pop("type", None)
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        filtered.setdefault("type", item_type)
        return cls(**filtered)

    def stat_summary(self) -> str:
        """Return a compact stat string like '+5 ATK, +3 DEF'."""
        parts: list[str] = []
        if self.atk_bonus:
            parts.append(f"+{self.atk_bonus} ATK")
        if self.def_bonus:
            parts.append(f"+{self.def_bonus} DEF")
        if self.hp_bonus:
            parts.append(f"+{self.hp_bonus} HP")
        if self.spd_bonus:
            parts.append(f"+{self.spd_bonus} SPD")
        return ", ".join(parts) if parts else "No bonuses"


@dataclass
class Inventory:
    """A Hunter's complete inventory, stored as a single channel message."""

    user_id: int
    items: list[Item] = field(default_factory=list)
    _next_id: int = 1

    def add_item(self, item: Item) -> Item:
        """Add an item, auto-assigning an ID."""
        item.id = self._next_id
        self._next_id += 1
        self.items.append(item)
        return item

    def remove_item(self, item_id: int) -> Optional[Item]:
        """Remove and return an item by ID, or None if not found."""
        for i, item in enumerate(self.items):
            if item.id == item_id:
                return self.items.pop(i)
        return None

    def get_item(self, item_id: int) -> Optional[Item]:
        """Find item by ID."""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def get_equipped(self, item_type: str) -> Optional[Item]:
        """Get the currently equipped item of a given type."""
        for item in self.items:
            if item.type == item_type and item.is_equipped:
                return item
        return None

    def get_by_type(self, item_type: str) -> list[Item]:
        """Get all items of a specific type."""
        return [i for i in self.items if i.type == item_type]

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dictionary."""
        return {
            "type": "inventory",
            "user_id": self.user_id,
            "next_id": self._next_id,
            "items": [item.to_dict() for item in self.items],
        }

    def to_json(self) -> str:
        """Serialize to compact JSON string."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict) -> Inventory:
        """Deserialize from dictionary."""
        inv = cls(
            user_id=data["user_id"],
            _next_id=data.get("next_id", 1),
        )
        inv.items = [Item.from_dict(i) for i in data.get("items", [])]
        return inv

    @classmethod
    def from_json(cls, text: str) -> Inventory:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(text))


@dataclass
class Monster:
    """A randomly generated monster for hunting encounters."""

    name: str
    level: int
    rank: str
    hp: int
    attack: int
    defense: int
    xp_reward: int
    gold_reward: int
    loot_table: list[dict] = field(default_factory=list)


@dataclass
class HuntResult:
    """The outcome of a hunt encounter."""

    victory: bool
    monster: Monster
    damage_dealt: int
    damage_taken: int
    xp_gained: int
    gold_gained: int
    critical_hit: bool = False
    item_drop: Optional[Item] = None
    special_event: Optional[str] = None
    leveled_up: bool = False
    new_level: Optional[int] = None
    ranked_up: bool = False
    new_rank: Optional[str] = None
    gold_lost: int = 0


@dataclass
class DuelResult:
    """The outcome of a PvP duel encounter between two hunters."""

    challenger: Hunter
    opponent: Hunter
    winner: Hunter
    loser: Hunter
    winner_is_challenger: bool
    challenger_damage_dealt: int
    opponent_damage_dealt: int
    challenger_hp_left: int
    opponent_hp_left: int
    challenger_max_hp: int
    opponent_max_hp: int
    challenger_crits: int = 0
    opponent_crits: int = 0
    total_rounds: int = 1
    winner_xp_gained: int = 0
    winner_gold_gained: int = 0
    loser_xp_gained: int = 0
    winner_leveled_up: bool = False
    winner_new_level: Optional[int] = None
    winner_ranked_up: bool = False
    winner_new_rank: Optional[str] = None


@dataclass
class Guild:
    """Represents a Hunter Guild — social grouping with up to 15 members."""

    guild_id: int          # unique ID = owner's user_id
    name: str
    owner_id: int
    members: list[int] = field(default_factory=list)  # user_ids, max 15
    description: str = ""
    created_at: float = 0.0
    war_score: int = 0     # persistent war points, affects leaderboard ranking
    war_wins: int = 0      # total wars won
    war_losses: int = 0    # total wars lost

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "type": "guild",
            "guild_id": self.guild_id,
            "name": self.name,
            "owner_id": self.owner_id,
            "members": self.members,
            "description": self.description,
            "created_at": self.created_at,
            "war_score": self.war_score,
            "war_wins": self.war_wins,
            "war_losses": self.war_losses,
        }

    def to_json(self) -> str:
        """Serialize to compact JSON string."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict) -> Guild:
        """Deserialize from dictionary with safe field filtering."""
        import dataclasses
        d = dict(data)
        d.pop("type", None)
        # backward compat: defaults for missing war fields
        d.setdefault("war_score", 0)
        d.setdefault("war_wins", 0)
        d.setdefault("war_losses", 0)
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, text: str) -> Guild:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(text))


@dataclass
class RedeemCode:
    """Represents a promo / gift redemption code."""

    code: str                      # Normalized uppercase code (e.g. "SHADOW100K")
    reward_type: str               # "gold" | "item" | "xp"
    reward_value: dict | int       # int if gold/xp; serialized Item dict if item
    max_uses: int = 1              # Max claims across all hunters (0 or -1 = unlimited)
    claimed_by: list[int] = field(default_factory=list)  # List of hunter user_ids
    created_by: int = 0            # Telegram user_id of creator
    created_at: float = 0.0        # Creation timestamp
    description: str = ""          # Optional label / campaign note

    @property
    def is_depleted(self) -> bool:
        """Check if code has reached its maximum claim limit."""
        if self.max_uses <= 0:
            return False
        return len(self.claimed_by) >= self.max_uses

    @property
    def remaining_uses(self) -> int | str:
        """Return remaining claims available, or 'Unlimited'."""
        if self.max_uses <= 0:
            return "Unlimited"
        return max(0, self.max_uses - len(self.claimed_by))

    def has_claimed(self, user_id: int) -> bool:
        """Check if a specific hunter has already claimed this code."""
        return user_id in self.claimed_by

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "type": "redeem_code",
            "code": self.code.strip().upper(),
            "reward_type": self.reward_type,
            "reward_value": self.reward_value,
            "max_uses": self.max_uses,
            "claimed_by": self.claimed_by,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "description": self.description,
        }

    def to_json(self) -> str:
        """Serialize to compact JSON string."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict) -> RedeemCode:
        """Deserialize from dictionary with safe field filtering."""
        import dataclasses
        d = dict(data)
        d.pop("type", None)
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, text: str) -> RedeemCode:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(text))
