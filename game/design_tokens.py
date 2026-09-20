"""
game/design_tokens.py — Hallmark-Compliant Atmospheric Design System & Tokens.

Encodes opinionated anti-slop rules from the Hallmark design skill:
- Locked tokens across all image renderers (no mid-render improvisation)
- Atmospheric canvas ground with authentic radial blooms
- Elevated tonal surface hierarchy (SURFACE_1, SURFACE_2, SURFACE_3)
- Solid high-contrast ink typography (no gradient text, no italic headers)
- Handcrafted vector geometric icons (Crown, Skull, Lightning, Diamond, Coin, Shield)
  ensuring 0 missing-glyph tofu boxes (□) on any OS.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── Canvas & Surface Tokens (Atmospheric Dark Ground) ─────────────────────────
CANVAS_TOP = (7, 11, 24)          # Abyssal midnight navy
CANVAS_BOTTOM = (3, 5, 12)        # Near pitch black ground
CANVAS_BORDER = (24, 44, 78)       # Subtle outer HUD perimeter line

# Elevated Tonal Surfaces (Paper-1, Paper-2, Paper-3)
SURFACE_BASE = (11, 18, 34, 240)  # Primary container panel
SURFACE_ELEVATED = (18, 28, 52)   # Nested telemetry / slot card
SURFACE_ACCENT = (26, 42, 74)     # Highlight / active element surface
SURFACE_BORDER = (30, 56, 98)     # Deep technical border
SURFACE_BORDER_LIGHT = (48, 88, 148)  # Active / focused border

# ── Ink & Typography Tokens ──────────────────────────────────────────────────
INK_PRIMARY = (248, 250, 252)     # Solid high-contrast white
INK_SECONDARY = (148, 163, 184)   # Technical slate grey
INK_MUTED = (71, 85, 105)         # Dark slate metadata
INK_CYAN = (0, 229, 255)          # Primary electric system cyan
INK_SKY = (56, 189, 248)          # Secondary active sky blue
INK_GOLD = (250, 204, 21)         # Victorious gold / currency
INK_RED = (239, 68, 68)           # Gate alert / defeat crimson
INK_RED_DARK = (60, 16, 24)       # Defeat card background
INK_GREEN = (34, 197, 94)         # Health / victory emerald
INK_GREEN_DARK = (14, 48, 28)     # Victory card background
INK_PURPLE = (168, 85, 247)       # Arcane Monarch violet
MANA_BLUE = (0, 145, 234)         # Holographic MP mana blue
SILVER_COLOR = (226, 232, 240)    # Podium #2 Silver
BRONZE_COLOR = (217, 119, 6)      # Podium #3 Bronze
WAR_RED = (220, 38, 38)           # Guild war red
WAR_GOLD = (234, 179, 8)          # Guild war victory gold

# ── Rank Color Mapping ────────────────────────────────────────────────────────
RANK_COLORS = {
    "E": (148, 163, 184),             # Slate / Bronze
    "D": (34, 197, 94),               # Emerald Green
    "C": (56, 189, 248),              # Sky Blue
    "B": (168, 85, 247),              # Arcane Purple
    "A": (244, 63, 94),               # Crimson Red
    "S": (251, 191, 36),              # Radiant Gold
    "SS": (245, 158, 11),             # Deep Solar Gold
    "SSS": (239, 68, 68),             # Divine Blood Red
    "National Level": (236, 72, 153), # Electric Pink
    "Monarch": (192, 132, 252),       # Shadow Monarch Violet
}

# ── Rarity Color Mapping ──────────────────────────────────────────────────────
RARITY_COLORS = {
    "Common": (148, 163, 184),
    "Uncommon": (34, 197, 94),
    "Rare": (56, 189, 248),
    "Epic": (168, 85, 247),
    "Legendary": (251, 191, 36),
    "Mythic": (239, 68, 68),
}


# ── Atmospheric Canvas & Bloom Primitives ─────────────────────────────────────

def draw_atmospheric_canvas(
    img: Image.Image,
    top_color: Tuple[int, int, int] = CANVAS_TOP,
    bottom_color: Tuple[int, int, int] = CANVAS_BOTTOM,
    bloom_cx: Optional[int] = None,
    bloom_cy: Optional[int] = None,
    bloom_color: Tuple[int, int, int, int] = (0, 180, 255, 30),
    bloom_radius: int = 240,
    grid_spacing: int = 80,
) -> None:
    """
    Render a Hallmark atmospheric ground:
    1. Rich vertical gradient (deep navy to pitch black).
    2. Optional focal radial bloom (illuminates content naturally).
    3. Subtle technical alignment grid.
    """
    w, h = img.size
    draw = ImageDraw.Draw(img)

    # 1. Gradient ground
    for y in range(h):
        ratio = y / h
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

    # 2. Atmospheric Radial Bloom (if specified)
    if bloom_cx is not None and bloom_cy is not None and bloom_radius > 0:
        bloom_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        b_draw = ImageDraw.Draw(bloom_layer)
        b_draw.ellipse(
            [bloom_cx - bloom_radius, bloom_cy - bloom_radius, bloom_cx + bloom_radius, bloom_cy + bloom_radius],
            fill=bloom_color,
        )
        bloom_blurred = bloom_layer.filter(ImageFilter.GaussianBlur(bloom_radius // 3))
        img.alpha_composite(bloom_blurred)
        draw = ImageDraw.Draw(img)

    # 3. Micro Grid lines (low contrast, properly alpha-composited)
    if grid_spacing > 0:
        grid_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(grid_layer)
        for gx in range(grid_spacing // 2, w, grid_spacing):
            g_draw.line([(gx, 0), (gx, h)], fill=(40, 60, 95, 20), width=1)
        for gy in range(grid_spacing // 2, h, grid_spacing):
            g_draw.line([(0, gy), (w, gy)], fill=(40, 60, 95, 20), width=1)
        img.alpha_composite(grid_layer)


# ── Technical HUD Drawing Primitives ──────────────────────────────────────────

def draw_hud_corners(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    color: Tuple[int, int, int] = INK_CYAN,
    length: int = 20,
    width: int = 2,
) -> None:
    """Draw precision cybernetic HUD corner brackets."""
    x1, y1, x2, y2 = box

    # Top-Left
    draw.line([(x1, y1), (x1 + length, y1)], fill=color, width=width)
    draw.line([(x1, y1), (x1, y1 + length)], fill=color, width=width)

    # Top-Right
    draw.line([(x2 - length, y1), (x2, y1)], fill=color, width=width)
    draw.line([(x2, y1), (x2, y1 + length)], fill=color, width=width)

    # Bottom-Left
    draw.line([(x1, y2 - length), (x1, y2)], fill=color, width=width)
    draw.line([(x1, y2), (x1 + length, y2)], fill=color, width=width)

    # Bottom-Right
    draw.line([(x2 - length, y2), (x2, y2)], fill=color, width=width)
    draw.line([(x2, y2 - length), (x2, y2)], fill=color, width=width)


def draw_diamond(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    size: int = 5,
    fill: Tuple[int, int, int] = INK_CYAN,
) -> None:
    """Draw a geometric diamond vector accent."""
    draw.polygon([(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)], fill=fill)


def draw_coin_icon(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    r: int = 7,
) -> None:
    """Draw a multi-layered gold coin vector."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(250, 204, 21), outline=(217, 119, 6), width=1)
    draw.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], outline=(254, 240, 138), width=1)


def draw_lightning_icon(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    fill: Tuple[int, int, int] = INK_GOLD,
    scale: float = 1.0,
) -> None:
    """Draw a razor-sharp lightning bolt vector."""
    pts = [
        (cx + int(2 * scale), cy - int(8 * scale)),
        (cx - int(5 * scale), cy - int(1 * scale)),
        (cx - int(1 * scale), cy - int(1 * scale)),
        (cx - int(3 * scale), cy + int(8 * scale)),
        (cx + int(5 * scale), cy + int(1 * scale)),
        (cx + int(1 * scale), cy + int(1 * scale)),
    ]
    draw.polygon(pts, fill=fill)


def draw_crown_icon(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    fill: Tuple[int, int, int] = INK_GOLD,
    scale: float = 1.0,
) -> None:
    """Draw a royal crown vector."""
    w = int(14 * scale)
    h = int(10 * scale)
    pts = [
        (cx - w, cy - int(h * 0.6)),
        (cx - int(w * 0.45), cy),
        (cx, cy - h),
        (cx + int(w * 0.45), cy),
        (cx + w, cy - int(h * 0.6)),
        (cx + int(w * 0.75), cy + int(h * 0.7)),
        (cx - int(w * 0.75), cy + int(h * 0.7)),
    ]
    draw.polygon(pts, fill=fill)
    r = max(1, int(2 * scale))
    draw.ellipse([cx - w - r, cy - int(h * 0.6) - r, cx - w + r, cy - int(h * 0.6) + r], fill=fill)
    draw.ellipse([cx - r, cy - h - r, cx + r, cy - h + r], fill=fill)
    draw.ellipse([cx + w - r, cy - int(h * 0.6) - r, cx + w + r, cy - int(h * 0.6) + r], fill=fill)


def draw_skull_icon(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    fill: Tuple[int, int, int] = (254, 202, 202),
    bg: Tuple[int, int, int] = INK_RED_DARK,
    scale: float = 1.0,
) -> None:
    """Draw a defeat skull vector."""
    rw = int(9 * scale)
    rh = int(9 * scale)
    draw.ellipse([cx - rw, cy - rh, cx + rw, cy], fill=fill)
    jw = int(5 * scale)
    jh = int(8 * scale)
    draw.rounded_rectangle([cx - jw, cy - int(2 * scale), cx + jw, cy + jh], radius=max(1, int(2 * scale)), fill=fill)
    er = max(1, int(2 * scale))
    draw.ellipse([cx - int(4 * scale) - er, cy - int(3 * scale) - er, cx - int(4 * scale) + er, cy - int(3 * scale) + er], fill=bg)
    draw.ellipse([cx + int(4 * scale) - er, cy - int(3 * scale) - er, cx + int(4 * scale) + er, cy - int(3 * scale) + er], fill=bg)


def draw_swords_icon(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    fill: Tuple[int, int, int] = INK_CYAN,
) -> None:
    """Draw crossed blades vector."""
    draw.line([(cx - 7, cy - 7), (cx + 7, cy + 7)], fill=fill, width=2)
    draw.line([(cx - 6, cy - 2), (cx - 2, cy - 6)], fill=fill, width=2)
    draw.line([(cx + 7, cy - 7), (cx - 7, cy + 7)], fill=fill, width=2)
    draw.line([(cx + 6, cy - 2), (cx + 2, cy - 6)], fill=fill, width=2)


def draw_rounded_gauge(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    current: int,
    maximum: int,
    fill_color: Tuple[int, int, int],
    bg_color: Tuple[int, int, int] = (18, 28, 48),
) -> None:
    """Draw a smooth rounded HUD progress gauge."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=bg_color)
    if maximum > 0 and current > 0:
        pct = min(1.0, max(0.0, current / maximum))
        fill_w = max(h, int(w * pct))
        draw.rounded_rectangle([x, y, x + fill_w, y + h], radius=h // 2, fill=fill_color)


def draw_shield_icon(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    fill: Tuple[int, int, int] = INK_CYAN,
    scale: float = 1.0,
) -> None:
    """Draw a vector guardian defense shield."""
    w = int(8 * scale)
    h = int(10 * scale)
    pts = [
        (cx - w, cy - h),
        (cx + w, cy - h),
        (cx + w, cy + int(h * 0.2)),
        (cx, cy + h),
        (cx - w, cy + int(h * 0.2)),
    ]
    draw.polygon(pts, fill=fill)
    # Highlight rim
    inner_pts = [
        (cx - w + 2, cy - h + 2),
        (cx + w - 2, cy - h + 2),
        (cx + w - 2, cy + int(h * 0.15)),
        (cx, cy + h - 2),
        (cx - w + 2, cy + int(h * 0.15)),
    ]
    draw.polygon(inner_pts, outline=(fill[0] // 2, fill[1] // 2, fill[2] // 2), width=1)


def draw_anvil_icon(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    size: int = 24,
    fill: Tuple[int, int, int] = (245, 158, 11),
) -> None:
    """Draw vector blacksmith anvil silhouette."""
    # Top horn & face
    draw.polygon([
        (cx - size, cy - size // 3),
        (cx + size, cy - size // 3),
        (cx + size - 6, cy + size // 6),
        (cx - size + 8, cy + size // 6),
    ], fill=fill)
    # Waist & base
    draw.polygon([
        (cx - size // 2, cy + size // 6),
        (cx + size // 2, cy + size // 6),
        (cx + size * 2 // 3, cy + size * 2 // 3),
        (cx - size * 2 // 3, cy + size * 2 // 3),
    ], fill=fill)


def draw_system_bracket(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    color: Tuple[int, int, int] = INK_CYAN,
    length: int = 16,
    width: int = 2,
) -> None:
    """Draw futuristic Solo Leveling System HUD brackets [ ... ]."""
    draw_hud_corners(draw, box, color=color, length=length, width=width)


def draw_hp_mp_bars(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    hp: int,
    max_hp: int,
    mp: Optional[int] = None,
    max_mp: Optional[int] = None,
    h: int = 14,
) -> None:
    """Draw anime-accurate dual HP (Emerald) and MP (Azure Mana) vitals bars."""
    # 1. HP Bar
    draw_rounded_gauge(draw, x, y, w, h, hp, max_hp, fill_color=INK_GREEN, bg_color=(12, 32, 20))
    
    # 2. MP Bar (if specified)
    if mp is not None and max_mp is not None and max_mp > 0:
        draw_rounded_gauge(draw, x, y + h + 6, w, h, mp, max_mp, fill_color=MANA_BLUE, bg_color=(10, 24, 48))

