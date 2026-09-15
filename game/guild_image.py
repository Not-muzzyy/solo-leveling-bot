"""
game/guild_image.py — Solo Leveling Visual Guild Card Renderer.

Generates a stylized, high-resolution RPG Guild Card image using Pillow,
showcasing the guild name, owner, members, and stats.
"""

from __future__ import annotations

import io
import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import GUILD_MAX_MEMBERS, RANKS
from game.font_manager import get_font_cascade, clean_and_normalize_name
from models import Guild, Hunter

# Canvas dimensions (860 x 720)
WIDTH = 860
HEIGHT = 720

# Color Palette (Solo Leveling Abyssal Blue HUD)
BG_TOP = (7, 11, 24)
BG_BOTTOM = (3, 6, 15)
HUD_CYAN = (0, 229, 255)
HUD_BLUE = (37, 99, 235)
GOLD_COLOR = (250, 204, 21)
GREEN_COLOR = (34, 197, 94)
TEXT_WHITE = (248, 250, 252)
TEXT_MUTED = (148, 163, 184)
TEXT_DIM = (71, 85, 105)
CARD_BG = (13, 20, 36, 235)
CARD_BORDER = (30, 58, 102)
GUILD_PURPLE = (168, 85, 247)

RANK_COLORS = {
    "E": (148, 163, 184), "D": (34, 197, 94), "C": (56, 189, 248),
    "B": (168, 85, 247), "A": (244, 63, 94), "S": (251, 191, 36),
    "SS": (245, 158, 11), "SSS": (239, 68, 68), "National Level": (236, 72, 153),
    "Monarch": (192, 132, 252),
}


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


def _get_fonts():
    bold = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    regular = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]
    return {
        "guild_name": _load_font(bold, 36),
        "subtitle": _load_font(bold, 14),
        "member_name": _load_font(bold, 15),
        "member_stat": _load_font(regular, 13),
        "stat_value": _load_font(bold, 18),
        "stat_label": _load_font(regular, 12),
        "body": _load_font(regular, 13),
        "body_bold": _load_font(bold, 13),
        "footer": _load_font(bold, 12),
        "small": _load_font(regular, 11),
    }


def _draw_gradient_background(img: Image.Image) -> None:
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for y in range(h):
        ratio = y / h
        r = int(BG_TOP[0] * (1 - ratio) + BG_BOTTOM[0] * ratio)
        g = int(BG_TOP[1] * (1 - ratio) + BG_BOTTOM[1] * ratio)
        b = int(BG_TOP[2] * (1 - ratio) + BG_BOTTOM[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse([w // 2 - 250, -60, w // 2 + 250, 200], fill=(168, 85, 247, 25))
    glow_draw.ellipse([w // 2 - 180, -30, w // 2 + 180, 130], fill=(0, 229, 255, 18))
    glow = glow.filter(ImageFilter.GaussianBlur(35))
    img.alpha_composite(glow)


def _draw_tech_border(draw: ImageDraw.ImageDraw, x1, y1, x2, y2) -> None:
    draw.rectangle([x1, y1, x2, y2], outline=(25, 45, 80, 180), width=1)
    blen, bw = 24, 3
    for corners in [
        ((x1, y1), (x1 + blen, y1), (x1, y1 + blen)),
        ((x2 - blen, y1), (x2, y1), (x2, y1 + blen)),
        ((x1, y2), (x1 + blen, y2), (x1, y2 - blen)),
        ((x2 - blen, y2), (x2, y2), (x2, y2 - blen)),
    ]:
        draw.line([corners[0], corners[1]], fill=GOLD_COLOR, width=bw)
        draw.line([corners[0], corners[2]], fill=GOLD_COLOR, width=bw)


def _draw_shield_icon(draw: ImageDraw.ImageDraw, cx, cy, size=18, fill=GUILD_PURPLE) -> None:
    """Draw a vector shield icon."""
    pts = [
        (cx, cy - size),
        (cx + int(size * 0.8), cy - int(size * 0.5)),
        (cx + int(size * 0.7), cy + int(size * 0.3)),
        (cx, cy + size),
        (cx - int(size * 0.7), cy + int(size * 0.3)),
        (cx - int(size * 0.8), cy - int(size * 0.5)),
    ]
    draw.polygon(pts, fill=fill, outline=(200, 130, 255), width=1)


def _draw_member_row(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    x: int,
    y: int,
    hunter: Hunter,
    is_owner: bool,
    width: int = 350,
) -> int:
    """Draw a single member row. Returns y offset for next row."""
    rank_color = RANK_COLORS.get(hunter.rank, TEXT_MUTED)
    role_icon = "👑" if is_owner else "⚔️"
    role_text = "OWNER" if is_owner else "MEMBER"

    # Row background
    draw.rounded_rectangle([x, y, x + width, y + 36], radius=6, fill=(20, 30, 50, 180), outline=(35, 55, 85, 120))

    # Role badge
    role_bg = GOLD_COLOR if is_owner else HUD_CYAN
    draw.rounded_rectangle([x + 6, y + 6, x + 68, y + 30], radius=4, fill=(*role_bg, 60), outline=(*role_bg, 150))
    draw.text((x + 37, y + 8), role_text, font=fonts["small"], fill=role_bg, anchor="mt")

    # Name
    name = clean_and_normalize_name(hunter.display_full_name)
    draw.text((x + 80, y + 4), name, font=fonts["member_name"], fill=TEXT_WHITE)

    # Rank + Level
    rank_label = f"Lv.{hunter.level} {hunter.rank}"
    draw.text((x + width - 10, y + 4), rank_label, font=fonts["member_stat"], fill=rank_color, anchor="rt")

    # Power
    draw.text((x + 80, y + 20), f"Power: {hunter.power:,}", font=fonts["small"], fill=TEXT_DIM)

    return y + 42


def render_guild_image(
    guild: Guild,
    members: list[Hunter],
    total_power: int,
) -> io.BytesIO:
    """Render the guild card image."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    _draw_gradient_background(img)
    draw = ImageDraw.Draw(img)
    fonts = _get_fonts()

    # Outer tech border
    _draw_tech_border(draw, 20, 20, WIDTH - 20, HEIGHT - 20)

    # Title area — shield icon + guild name
    _draw_shield_icon(draw, 80, 65, size=24, fill=GUILD_PURPLE)
    draw.text((115, 45), guild.name, font=fonts["guild_name"], fill=TEXT_WHITE)
    draw.text((115, 88), "HUNTER GUILD", font=fonts["subtitle"], fill=HUD_CYAN)

    # Stats bar
    stats_y = 120
    stats = [
        (f"{len(guild.members)}/{GUILD_MAX_MEMBERS}", "MEMBERS"),
        (f"{total_power:,}", "TOTAL POWER"),
        ("+10%", "XP BONUS"),
    ]
    stat_x = 60
    for val, label in stats:
        # Stat card background
        draw.rounded_rectangle([stat_x, stats_y, stat_x + 180, stats_y + 52], radius=6, fill=(18, 28, 48, 200), outline=(35, 55, 85, 100))
        draw.text((stat_x + 90, stats_y + 8), val, font=fonts["stat_value"], fill=GOLD_COLOR, anchor="mt")
        draw.text((stat_x + 90, stats_y + 32), label, font=fonts["stat_label"], fill=TEXT_MUTED, anchor="mt")
        stat_x += 200

    # Description
    desc_y = 190
    if guild.description:
        draw.text((60, desc_y), f"📝 {guild.description}", font=fonts["body"], fill=TEXT_MUTED)
        desc_y += 30

    # Members header
    members_y = desc_y + 10
    draw.line([(60, members_y), (WIDTH - 60, members_y)], fill=(30, 50, 80, 150), width=1)
    members_y += 10
    draw.text((60, members_y), "📋 GUILD ROSTER", font=fonts["subtitle"], fill=HUD_CYAN)
    members_y += 25

    # Member list
    for h in sorted(members, key=lambda x: (x.user_id != guild.owner_id, -x.power)):
        if members_y > HEIGHT - 60:
            break
        is_owner = h.user_id == guild.owner_id
        members_y = _draw_member_row(draw, fonts, 60, members_y, h, is_owner, width=WIDTH - 120)

    # Footer
    draw.text(
        (WIDTH // 2, HEIGHT - 40),
        "「 A Guild grows stronger with every Hunter that joins. 」",
        font=fonts["footer"],
        fill=TEXT_DIM,
        anchor="mt",
    )

    # Convert to PNG bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    buf.seek(0)
    return buf
