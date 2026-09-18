"""
/* Hallmark · component: explore_map_card · genre: atmospheric · theme: Midnight (Abyssal Monarch) */
game/explore_image.py — Solo Leveling Visual World Map & Exploration Card Renderer.

Renders a high-resolution (1000x1000) tactical fantasy world map showing:
- 6 dungeon territory sectors with atmospheric topography and radar pings
- Player's circular avatar pin with radar rings placed at their current exploration sector
- Tactical discovery report detailing lore encounters, generous Gold/XP rewards, and rare gifts
- Segmented daily quota meter (e.g. 1/3, 2/3, 3/3) and 1-hour cooldown telemetry.
"""

from __future__ import annotations

import io
import math
import os
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import RANKS
from game.font_manager import clean_and_normalize_name
from game.design_tokens import (
    CANVAS_TOP,
    CANVAS_BOTTOM,
    CANVAS_BORDER,
    SURFACE_BASE,
    SURFACE_ELEVATED,
    SURFACE_ACCENT,
    SURFACE_BORDER,
    SURFACE_BORDER_LIGHT,
    INK_PRIMARY,
    INK_SECONDARY,
    INK_MUTED,
    INK_CYAN,
    INK_SKY,
    INK_GOLD,
    INK_RED,
    INK_GREEN,
    INK_PURPLE,
    RANK_COLORS,
    RARITY_COLORS,
    draw_atmospheric_canvas,
    draw_hud_corners,
    draw_diamond,
    draw_coin_icon,
)
from models import Hunter, Item

WIDTH = 1000
HEIGHT = 1000

# 6 Strategic Territory Sectors across the Solo Leveling World
EXPLORE_SECTORS = [
    {
        "id": 0,
        "name": "Association HQ & Training Sanctum",
        "short_name": "Association Sanctum",
        "tier": "Tier E-D",
        "rank_req": "E",
        "color": (56, 189, 248),
        "x": 220,
        "y": 240,
        "coords": "GRID [37.56N, 126.97E]",
        "desc": "The fortified sanctuary of Korean Hunters. Low-tier gate rifts and association training vaults.",
    },
    {
        "id": 1,
        "name": "Red Gate: Frozen Monarch Tundra",
        "short_name": "Red Gate Tundra",
        "tier": "Tier C",
        "rank_req": "C",
        "color": (0, 229, 255),
        "x": 500,
        "y": 180,
        "coords": "GRID [42.12N, 128.05E]",
        "desc": "A catastrophic dimensional anomaly encasing the terrain in subzero blizzards and ice elves.",
    },
    {
        "id": 2,
        "name": "Demon Castle: Infernal Spire",
        "short_name": "Demon Castle",
        "tier": "Tier B",
        "rank_req": "B",
        "color": (239, 68, 68),
        "x": 780,
        "y": 240,
        "coords": "GRID [35.88N, 128.60E]",
        "desc": "A hundred-floor tower forged in demonic hellfire, guarded by Vulcan and Metus.",
    },
    {
        "id": 3,
        "name": "Double Dungeon: Temple of Cartenon",
        "short_name": "Cartenon Temple",
        "tier": "Tier A",
        "rank_req": "A",
        "color": (168, 85, 247),
        "x": 750,
        "y": 480,
        "coords": "GRID [33.50N, 126.52E]",
        "desc": "Subterranean temple of the Architect. Colossal stone statues enforce ancient commandments.",
    },
    {
        "id": 4,
        "name": "Jeju Island: Queen Ant Hive",
        "short_name": "Jeju Ant Hive",
        "tier": "Tier S",
        "rank_req": "S",
        "color": (245, 158, 11),
        "x": 470,
        "y": 530,
        "coords": "GRID [33.36N, 126.53E]",
        "desc": "Desolate island infested with mutated humanoid insectoids and the sovereign Ant Queen.",
    },
    {
        "id": 5,
        "name": "Dimensional Rift: Monarch's Abyss",
        "short_name": "Monarch's Abyss",
        "tier": "Tier SSS",
        "rank_req": "SSS",
        "color": (192, 132, 252),
        "x": 190,
        "y": 460,
        "coords": "GRID [00.00N, 00.00E]",
        "desc": "The cosmic fracture between Rulers and Monarchs. Infinite shadow mana cascades into reality.",
    },
]


def _load_font(font_names: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    win_fonts = os.environ.get("WINDIR", "C:\\Windows") + "\\Fonts"
    candidates = [os.path.join(win_fonts, n) for n in font_names] + list(font_names)
    for path in candidates:
        try:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        except Exception:
            continue
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _get_fonts() -> dict:
    bold = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    regular = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]
    mono = ["consola.ttf", "consolab.ttf", "cour.ttf"]

    return {
        "title": _load_font(bold, 28),
        "subtitle": _load_font(bold, 18),
        "header_tag": _load_font(bold, 13),
        "body_bold": _load_font(bold, 15),
        "body": _load_font(regular, 14),
        "event_text": _load_font(regular, 15),
        "node_title": _load_font(bold, 13),
        "node_sub": _load_font(mono, 11),
        "stat_val": _load_font(bold, 17),
        "small": _load_font(regular, 12),
        "small_bold": _load_font(bold, 12),
        "mono": _load_font(mono, 13),
    }


def _draw_tactical_grid(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, step: int = 40) -> None:
    """Draw subtle cyber-topographic coordinate grid lines."""
    grid_color = (20, 36, 68, 60)
    for x in range(x1, x2, step):
        draw.line([(x, y1), (x, y2)], fill=grid_color, width=1)
    for y in range(y1, y2, step):
        draw.line([(x1, y), (x2, y)], fill=grid_color, width=1)


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    pt1: Tuple[int, int],
    pt2: Tuple[int, int],
    dash_len: int = 8,
    gap_len: int = 6,
    color: Tuple[int, int, int, int] = (40, 80, 140, 150),
    width: int = 2,
) -> None:
    """Draw a dashed vector path between two sector waypoints."""
    x1, y1 = pt1
    x2, y2 = pt2
    dist = math.hypot(x2 - x1, y2 - y1)
    if dist <= 0:
        return
    dx = (x2 - x1) / dist
    dy = (y2 - y1) / dist

    curr = 0.0
    while curr < dist:
        end = min(curr + dash_len, dist)
        sx = int(x1 + dx * curr)
        sy = int(y1 + dy * curr)
        ex = int(x1 + dx * end)
        ey = int(y1 + dy * end)
        draw.line([(sx, sy), (ex, ey)], fill=color, width=width)
        curr += dash_len + gap_len


def _draw_player_avatar_pin(
    base: Image.Image,
    pfp_image: Optional[Image.Image],
    node_x: int,
    node_y: int,
    pin_radius: int = 36,
    rank: str = "E",
    player_name: str = "Hunter",
    fonts: dict = None,
) -> None:
    """
    Render player's circular avatar pin hovering above their active sector coordinates:
    - Downward needle points directly to the sector waypoint node
    - Glowing sonar / radar rings centered on the avatar
    - Rank-colored metallic bezel
    - Anti-aliased circular profile photo (or hunter silhouette)
    - HUD identification callout banner above pin
    """
    draw = ImageDraw.Draw(base, "RGBA")
    rank_col = RANK_COLORS.get(rank, INK_CYAN)

    # Pin center hovers directly above the waypoint node
    center_x = node_x
    center_y = node_y - pin_radius - 22

    # 1. Pulsing radar sonar waves
    for r_offset, alpha in [(48, 30), (38, 55), (28, 90)]:
        r = pin_radius + r_offset - 12
        draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            outline=(rank_col[0], rank_col[1], rank_col[2], alpha),
            width=2,
        )

    # 2. Downward pointer needle pointing directly to node_y
    draw.polygon(
        [
            (center_x - 8, center_y + pin_radius - 2),
            (center_x + 8, center_y + pin_radius - 2),
            (node_x, node_y - 2),
        ],
        fill=(rank_col[0], rank_col[1], rank_col[2], 240),
    )

    # 3. Avatar rendering with 4x supersampling mask
    dia = pin_radius * 2
    mask_scale = 4
    high_size = dia * mask_scale
    mask_high = Image.new("L", (high_size, high_size), 0)
    mask_draw = ImageDraw.Draw(mask_high)
    mask_draw.ellipse([0, 0, high_size - 1, high_size - 1], fill=255)
    mask = mask_high.resize((dia, dia), Image.Resampling.LANCZOS)

    top_left_x = center_x - pin_radius
    top_left_y = center_y - pin_radius

    if pfp_image:
        try:
            w, h = pfp_image.size
            dim = min(w, h)
            left = (w - dim) // 2
            top = (h - dim) // 2
            cropped = pfp_image.crop((left, top, left + dim, top + dim))
            avatar_resized = cropped.resize((dia, dia), Image.Resampling.LANCZOS).convert("RGBA")

            avatar_layer = Image.new("RGBA", (dia, dia), (0, 0, 0, 0))
            avatar_layer.paste(avatar_resized, (0, 0), mask=mask)
            base.alpha_composite(avatar_layer, (top_left_x, top_left_y))
        except Exception:
            pfp_image = None

    if not pfp_image:
        avatar_bg = Image.new("RGBA", (dia, dia), (15, 23, 42, 255))
        avatar_draw = ImageDraw.Draw(avatar_bg)
        c = dia // 2
        avatar_draw.ellipse([c - 12, c - 20, c + 12, c + 4], fill=(56, 189, 248, 220))
        avatar_draw.chord([c - 24, c + 8, c + 24, c + 38], start=0, end=180, fill=(30, 58, 102, 240))
        avatar_layer = Image.new("RGBA", (dia, dia), (0, 0, 0, 0))
        avatar_layer.paste(avatar_bg, (0, 0), mask=mask)
        base.alpha_composite(avatar_layer, (top_left_x, top_left_y))

    # Outer bezel rings
    draw = ImageDraw.Draw(base, "RGBA")
    draw.ellipse(
        [top_left_x - 3, top_left_y - 3, top_left_x + dia + 3, top_left_y + dia + 3],
        outline=(rank_col[0], rank_col[1], rank_col[2], 100),
        width=1,
    )
    draw.ellipse(
        [top_left_x, top_left_y, top_left_x + dia, top_left_y + dia],
        outline=rank_col,
        width=3,
    )

    # Identification banner above avatar
    if fonts:
        tag_text = f"ACTIVE EXPEDITION: {player_name.upper()}"
        bbox = fonts["mono"].getbbox(tag_text)
        bw = (bbox[2] - bbox[0]) + 16
        bh = 22
        bx1 = center_x - bw // 2
        by1 = top_left_y - 30
        draw.rounded_rectangle([bx1, by1, bx1 + bw, by1 + bh], radius=4, fill=(8, 14, 28, 230), outline=rank_col, width=1)
        draw.text((bx1 + 8, by1 + 4), tag_text, font=fonts["mono"], fill=INK_PRIMARY)


def render_explore_image(
    hunter: Hunter,
    sector_id: int,
    event_story: str,
    gold_reward: int,
    xp_reward: int,
    gift_item: Optional[Item] = None,
    pfp_image: Optional[Image.Image] = None,
    player_display_name: str = "",
) -> io.BytesIO:
    """
    Render a complete Hallmark-compliant World Map Exploration Card.
    Returns in-memory PNG BytesIO.
    """
    # 1. Base Canvas Ground with radial bloom centered near active sector
    active_sector = EXPLORE_SECTORS[sector_id % len(EXPLORE_SECTORS)]
    bloom_x = active_sector["x"]
    bloom_y = active_sector["y"]

    base = Image.new("RGBA", (WIDTH, HEIGHT), CANVAS_TOP)
    draw = ImageDraw.Draw(base, "RGBA")

    # Gradient background
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(CANVAS_TOP[0] * (1 - ratio) + CANVAS_BOTTOM[0] * ratio)
        g = int(CANVAS_TOP[1] * (1 - ratio) + CANVAS_BOTTOM[1] * ratio)
        b = int(CANVAS_TOP[2] * (1 - ratio) + CANVAS_BOTTOM[2] * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b, 255))

    # Atmospheric bloom over active sector
    bloom_img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    bloom_draw = ImageDraw.Draw(bloom_img)
    sec_col = active_sector["color"]
    bloom_radius = 220
    bloom_draw.ellipse(
        [bloom_x - bloom_radius, bloom_y - bloom_radius, bloom_x + bloom_radius, bloom_y + bloom_radius],
        fill=(sec_col[0], sec_col[1], sec_col[2], 55),
    )
    blurred_bloom = bloom_img.filter(ImageFilter.GaussianBlur(radius=75))
    base.alpha_composite(blurred_bloom)

    draw = ImageDraw.Draw(base, "RGBA")

    # Outer HUD Perimeter & Corners
    draw.rectangle([20, 20, WIDTH - 20, HEIGHT - 20], outline=CANVAS_BORDER, width=1)
    draw_hud_corners(draw, (20, 20, WIDTH - 20, HEIGHT - 20), color=INK_CYAN, length=16, width=2)

    fonts = _get_fonts()

    # Top Header Bar
    draw.text((42, 38), "SYSTEM EXPEDITION GRID", font=fonts["title"], fill=INK_PRIMARY)
    draw.text((44, 74), "DIMENSIONAL TERRITORY CARTOGRAPHY // VER 3.2", font=fonts["mono"], fill=INK_CYAN)

    status_tag = "LIVE TELEMETRY: ACTIVE"
    s_bbox = fonts["mono"].getbbox(status_tag)
    s_w = s_bbox[2] - s_bbox[0] + 20
    draw.rounded_rectangle([WIDTH - 45 - s_w, 42, WIDTH - 45, 68], radius=4, fill=(16, 28, 54, 220), outline=SURFACE_BORDER_LIGHT)
    draw.text((WIDTH - 35 - s_w, 48), status_tag, font=fonts["mono"], fill=INK_GREEN)

    # ── MAP DISPLAY AREA (y: 110 to 620) ──────────────────────────────────────
    map_x1, map_y1, map_x2, map_y2 = 35, 105, WIDTH - 35, 615
    draw.rounded_rectangle([map_x1, map_y1, map_x2, map_y2], radius=10, fill=(9, 15, 30, 210), outline=SURFACE_BORDER, width=1)
    _draw_tactical_grid(draw, map_x1, map_y1, map_x2, map_y2, step=45)

    # Draw dashed route paths connecting the 6 sectors in a loop
    for i in range(len(EXPLORE_SECTORS)):
        s_curr = EXPLORE_SECTORS[i]
        s_next = EXPLORE_SECTORS[(i + 1) % len(EXPLORE_SECTORS)]
        is_active_path = (i == sector_id or (i + 1) % len(EXPLORE_SECTORS) == sector_id)
        path_color = (0, 229, 255, 180) if is_active_path else (38, 64, 110, 110)
        _draw_dashed_line(draw, (s_curr["x"], s_curr["y"]), (s_next["x"], s_next["y"]), color=path_color, width=2 if is_active_path else 1)

    # Draw all sector waypoint nodes
    for sec in EXPLORE_SECTORS:
        sx, sy = sec["x"], sec["y"]
        is_active = (sec["id"] == sector_id)
        sc = sec["color"]

        # Outer glow ring
        outer_r = 16 if is_active else 10
        draw.ellipse([sx - outer_r, sy - outer_r, sx + outer_r, sy + outer_r], fill=(sc[0], sc[1], sc[2], 60 if is_active else 25), outline=sc if is_active else (sc[0], sc[1], sc[2], 120), width=2)

        # Core node
        core_r = 6 if is_active else 4
        draw.ellipse([sx - core_r, sy - core_r, sx + core_r, sy + core_r], fill=INK_PRIMARY if is_active else sc)

        # Node Label
        label_y = sy + (20 if is_active else 14)
        draw.text((sx, label_y), sec["short_name"], font=fonts["node_title"], fill=INK_PRIMARY if is_active else INK_SECONDARY, anchor="mt")
        draw.text((sx, label_y + 16), sec["tier"], font=fonts["node_sub"], fill=sc if is_active else INK_MUTED, anchor="mt")

    # Render player avatar pin at active sector coordinates
    resolved_name = player_display_name or hunter.hunter_name or "Hunter"
    _draw_player_avatar_pin(
        base=base,
        pfp_image=pfp_image,
        node_x=active_sector["x"],
        node_y=active_sector["y"],
        pin_radius=36,
        rank=hunter.rank,
        player_name=resolved_name,
        fonts=fonts,
    )

    draw = ImageDraw.Draw(base, "RGBA")

    # ── EXPEDITION DISCOVERY & REWARD PANEL (y: 630 to 965) ───────────────────
    panel_x1, panel_y1, panel_x2, panel_y2 = 35, 630, WIDTH - 35, 965
    draw.rounded_rectangle([panel_x1, panel_y1, panel_x2, panel_y2], radius=10, fill=SURFACE_BASE, outline=SURFACE_BORDER_LIGHT, width=1)
    draw_hud_corners(draw, (panel_x1, panel_y1, panel_x2, panel_y2), color=INK_CYAN, length=12, width=2)

    # Panel Top Row: Sector Identification & Daily Quota Meter
    draw.text((panel_x1 + 20, panel_y1 + 18), "SECTOR DISCOVERY DOSSIER", font=fonts["header_tag"], fill=INK_CYAN)
    sec_headline = f"{active_sector['name'].upper()} // [{active_sector['tier']}]"
    draw.text((panel_x1 + 20, panel_y1 + 38), sec_headline, font=fonts["subtitle"], fill=INK_PRIMARY)

    # Segmented Daily Quota Gauge [1/3, 2/3, 3/3]
    q_x = panel_x2 - 230
    q_y = panel_y1 + 24
    draw.text((q_x, q_y), "DAILY QUOTA", font=fonts["mono"], fill=INK_MUTED)
    exp_count = min(3, hunter.daily_explores)
    for i in range(3):
        box_x = q_x + 95 + (i * 38)
        box_fill = INK_CYAN if (i < exp_count) else (20, 32, 54, 200)
        box_outline = INK_CYAN if (i < exp_count) else SURFACE_BORDER
        draw.rounded_rectangle([box_x, q_y - 2, box_x + 30, q_y + 18], radius=3, fill=box_fill, outline=box_outline)
        draw.text((box_x + 10, q_y + 1), str(i + 1), font=fonts["small_bold"], fill=(7, 11, 24) if (i < exp_count) else INK_MUTED)

    draw.line([(panel_x1 + 20, panel_y1 + 72), (panel_x2 - 20, panel_y1 + 72)], fill=SURFACE_BORDER, width=1)

    # Event Narrative Box
    event_box_y = panel_y1 + 84
    draw.rounded_rectangle([panel_x1 + 20, event_box_y, panel_x2 - 20, event_box_y + 82], radius=6, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER)
    draw.text((panel_x1 + 34, event_box_y + 12), "EXPEDITION LOG:", font=fonts["header_tag"], fill=INK_GOLD)
    # Draw event narrative
    draw.text((panel_x1 + 34, event_box_y + 32), event_story, font=fonts["event_text"], fill=INK_PRIMARY)
    draw.text((panel_x1 + 34, event_box_y + 56), f"Territory Context: {active_sector['desc']}", font=fonts["small"], fill=INK_SECONDARY)

    # Rewards & Discovery Gifts Area (y: 810 to 890)
    rewards_y = panel_y1 + 180
    draw.rounded_rectangle([panel_x1 + 20, rewards_y, panel_x2 - 20, rewards_y + 80], radius=6, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER)

    # Gold Reward Pill
    gold_x = panel_x1 + 35
    draw_coin_icon(draw, gold_x + 14, rewards_y + 40, r=13)
    draw.text((gold_x + 36, rewards_y + 18), "EXPEDITION GOLD", font=fonts["small_bold"], fill=INK_MUTED)
    draw.text((gold_x + 36, rewards_y + 36), f"+{gold_reward:,} Gold", font=fonts["stat_val"], fill=INK_GOLD)

    # XP Reward Pill
    xp_x = panel_x1 + 240
    draw_diamond(draw, xp_x + 14, rewards_y + 40, size=11, fill=INK_CYAN)
    draw.text((xp_x + 34, rewards_y + 18), "HUNTER EXP", font=fonts["small_bold"], fill=INK_MUTED)
    draw.text((xp_x + 34, rewards_y + 36), f"+{xp_reward:,} XP", font=fonts["stat_val"], fill=INK_CYAN)

    # Gift / Artifact Discovery Pill (if discovered)
    gift_x = panel_x1 + 440
    if gift_item:
        rarity_col = RARITY_COLORS.get(gift_item.rarity, INK_PURPLE)
        draw.text((gift_x + 10, rewards_y + 18), "DISCOVERY: ARTIFACT ACQUIRED", font=fonts["small_bold"], fill=INK_GOLD)
        draw.text((gift_x + 10, rewards_y + 36), f"{gift_item.name} [{gift_item.rarity}]", font=fonts["body_bold"], fill=rarity_col)
        draw.text((gift_x + 10, rewards_y + 56), gift_item.stat_summary(), font=fonts["small"], fill=INK_SECONDARY)
    else:
        draw.text((gift_x + 10, rewards_y + 18), "DISCOVERY: RESOURCES EXTRACTED", font=fonts["small_bold"], fill=INK_CYAN)
        draw.text((gift_x + 10, rewards_y + 36), "Dimensional Crystals Secured", font=fonts["body_bold"], fill=INK_SECONDARY)
        draw.text((gift_x + 10, rewards_y + 56), "No unrecorded artifacts located in this sweep", font=fonts["small"], fill=INK_MUTED)

    # Bottom Telemetry Footer
    footer_y = panel_y1 + 276
    telemetry_str = f"HUNTER: {resolved_name.upper()} | RANK: [{hunter.rank}] | LV: {hunter.level} | POWER: {hunter.power:,}"
    draw.text((panel_x1 + 24, footer_y), telemetry_str, font=fonts["mono"], fill=INK_SECONDARY)

    timer_str = "RECHARGE: 1 HOUR | QUOTA: 3 SWEEPS / DAY"
    draw.text((panel_x2 - 24, footer_y), timer_str, font=fonts["mono"], fill=INK_SKY, anchor="ra")

    # Output PNG buffer
    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
