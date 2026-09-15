"""
game/guild_image.py — Solo Leveling Visual Guild Card Renderer.

Generates a stylized, high-resolution RPG Guild Card image using Pillow,
showcasing the guild name, owner, top 5 hunters, and remaining members.
"""

from __future__ import annotations

import io
import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import GUILD_MAX_MEMBERS, RANKS
from game.font_manager import get_font_cascade, clean_and_normalize_name
from models import Guild, Hunter

# Canvas dimensions (860 x 820)
WIDTH = 860
HEIGHT = 820

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
        "section_header": _load_font(bold, 13),
        "owner_name": _load_font(bold, 18),
        "member_name": _load_font(bold, 15),
        "member_stat": _load_font(regular, 13),
        "stat_value": _load_font(bold, 18),
        "stat_label": _load_font(regular, 12),
        "body": _load_font(regular, 13),
        "body_bold": _load_font(bold, 13),
        "footer": _load_font(bold, 12),
        "small": _load_font(regular, 11),
        "small_bold": _load_font(bold, 11),
        "rank_badge": _load_font(bold, 12),
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
    pts = [
        (cx, cy - size),
        (cx + int(size * 0.8), cy - int(size * 0.5)),
        (cx + int(size * 0.7), cy + int(size * 0.3)),
        (cx, cy + size),
        (cx - int(size * 0.7), cy + int(size * 0.3)),
        (cx - int(size * 0.8), cy - int(size * 0.5)),
    ]
    draw.polygon(pts, fill=fill, outline=(200, 130, 255), width=1)


def _draw_crown_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 10, fill=GOLD_COLOR) -> None:
    w = size
    h = int(size * 0.75)
    pts = [
        (cx - w, cy + h), (cx - w, cy - h // 2), (cx - w // 2, cy),
        (cx, cy - h), (cx + w // 2, cy), (cx + w, cy - h // 2), (cx + w, cy + h),
    ]
    draw.polygon(pts, fill=fill, outline=(255, 235, 120), width=1)
    draw.ellipse([cx - 2, cy - h - 2, cx + 2, cy - h + 2], fill=(255, 255, 255))


def _draw_section_header(draw: ImageDraw.ImageDraw, fonts: dict, y: int, text: str, icon_color=HUD_CYAN) -> int:
    """Draw a section header line. Returns y after the header."""
    draw.line([(60, y), (WIDTH - 60, y)], fill=(30, 50, 80, 150), width=1)
    y += 8
    draw.text((60, y), text, font=fonts["section_header"], fill=icon_color)
    return y + 22


def _draw_owner_card(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    hunter: Hunter,
    y: int,
) -> int:
    """Draw the prominent guild owner card. Returns y after the card."""
    h_card = 56
    # Gold-bordered owner card
    draw.rounded_rectangle([40, y, WIDTH - 40, y + h_card], radius=10, fill=(28, 24, 12, 240), outline=GOLD_COLOR, width=2)

    # Crown icon
    _draw_crown_icon(draw, 72, y + 20, size=10, fill=GOLD_COLOR)

    # OWNER badge
    draw.rounded_rectangle([92, y + 8, 160, y + 28], radius=4, fill=(48, 38, 14), outline=GOLD_COLOR, width=1)
    draw.text((126, y + 10), "OWNER", font=fonts["small_bold"], fill=GOLD_COLOR, anchor="mt")

    # Name
    cascade = get_font_cascade(18, is_bold=True)
    cascade.draw_text(draw, (92, y + 30), hunter.display_full_name, fill=TEXT_WHITE, max_w=350)

    # Rank badge
    rank_color = RANK_COLORS.get(hunter.rank, GOLD_COLOR)
    rank_text = f"[{hunter.rank}-RANK]"
    draw.text((92, y + 30), "", font=fonts["body"], fill=TEXT_WHITE)  # placeholder for cascade
    tb_r = fonts["rank_badge"].getbbox(rank_text)
    rw = tb_r[2] - tb_r[0]
    rank_x = 92 + cascade.get_width(hunter.display_full_name, max_w=350) + 14
    draw.text((rank_x, y + 33), rank_text, font=fonts["rank_badge"], fill=rank_color)
    draw.text((rank_x + rw + 10, y + 33), f"Lv.{hunter.level}", font=fonts["small"], fill=TEXT_MUTED)

    # Power right-aligned
    power_str = f"⚡ {hunter.power:,}"
    tb_p = fonts["stat_value"].getbbox(power_str)
    pw = tb_p[2] - tb_p[0]
    draw.text((WIDTH - 60 - pw, y + 14), power_str, font=fonts["stat_value"], fill=GOLD_COLOR)

    # Stats summary
    stats_str = f"STR {hunter.str_stat}  •  AGI {hunter.agi}  •  VIT {hunter.vit}  •  INT {hunter.int_stat}  •  PER {hunter.per}"
    draw.text((WIDTH - 60, y + 40), stats_str, font=fonts["small"], fill=TEXT_DIM, anchor="rt")

    return y + h_card + 10


def _draw_top5_row(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    x: int,
    y: int,
    rank_pos: int,
    hunter: Hunter,
    width: int = 740,
) -> int:
    """Draw a top 5 member row with rank position badge. Returns y offset."""
    row_h = 38

    # Row background with subtle highlight
    draw.rounded_rectangle([x, y, x + width, y + row_h], radius=6, fill=(18, 28, 48, 200), outline=(35, 55, 85, 120))

    # Position badge (#1, #2, etc.)
    badge_colors = {
        1: GOLD_COLOR, 2: (226, 232, 240), 3: (217, 119, 6),
        4: HUD_CYAN, 5: HUD_CYAN,
    }
    badge_color = badge_colors.get(rank_pos, HUD_CYAN)
    draw.rounded_rectangle([x + 6, y + 6, x + 42, y + row_h - 6], radius=4, fill=(*badge_color, 50), outline=(*badge_color, 180))
    draw.text((x + 24, y + 9), f"#{rank_pos}", font=fonts["small_bold"], fill=badge_color, anchor="mt")

    # Name
    name_x = x + 54
    cascade = get_font_cascade(14, is_bold=True)
    cascade.draw_text(draw, (name_x, y + 5), hunter.display_full_name, fill=TEXT_WHITE, max_w=320)

    # Rank + Level
    rank_color = RANK_COLORS.get(hunter.rank, TEXT_MUTED)
    rank_text = f"[{hunter.rank}]"
    draw.text((x + width - 10, y + 5), f"Lv.{hunter.level}", font=fonts["small"], fill=TEXT_MUTED, anchor="rt")
    draw.text((x + width - 10, y + 20), f"⚡ {hunter.power:,}", font=fonts["small_bold"], fill=HUD_CYAN, anchor="rt")

    # Rank badge after name
    name_w = cascade.get_width(hunter.display_full_name, max_w=320)
    draw.text((name_x + name_w + 8, y + 7), rank_text, font=fonts["small"], fill=rank_color)

    return y + row_h + 4


def _draw_compact_row(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    x: int,
    y: int,
    hunter: Hunter,
    width: int = 740,
) -> int:
    """Draw a compact member row for remaining members. Returns y offset."""
    row_h = 30
    draw.rounded_rectangle([x, y, x + width, y + row_h], radius=4, fill=(16, 24, 40, 150))

    rank_color = RANK_COLORS.get(hunter.rank, TEXT_MUTED)
    draw.text((x + 10, y + 4), hunter.display_full_name, font=fonts["member_name"], fill=TEXT_WHITE, max_w=300)
    draw.text((x + width - 10, y + 4), f"Lv.{hunter.level} [{hunter.rank}]  ⚡{hunter.power:,}", font=fonts["small"], fill=TEXT_MUTED, anchor="rt")

    return y + row_h + 3


def render_guild_image(
    guild: Guild,
    members: list[Hunter],
    total_power: int,
) -> io.BytesIO:
    """Render the guild card image with owner, top 5, and remaining members."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    _draw_gradient_background(img)
    draw = ImageDraw.Draw(img)
    fonts = _get_fonts()

    # Outer tech border
    _draw_tech_border(draw, 20, 20, WIDTH - 20, HEIGHT - 20)

    # ── Title area ──
    _draw_shield_icon(draw, 80, 65, size=24, fill=GUILD_PURPLE)
    draw.text((115, 45), guild.name, font=fonts["guild_name"], fill=TEXT_WHITE)
    draw.text((115, 88), "HUNTER GUILD", font=fonts["subtitle"], fill=HUD_CYAN)

    # ── Stats bar ──
    stats_y = 120
    stats = [
        (f"{len(guild.members)}/{GUILD_MAX_MEMBERS}", "MEMBERS"),
        (f"{total_power:,}", "TOTAL POWER"),
        ("+10%", "XP BONUS"),
    ]
    stat_x = 60
    for val, label in stats:
        draw.rounded_rectangle([stat_x, stats_y, stat_x + 180, stats_y + 52], radius=6, fill=(18, 28, 48, 200), outline=(35, 55, 85, 100))
        draw.text((stat_x + 90, stats_y + 8), val, font=fonts["stat_value"], fill=GOLD_COLOR, anchor="mt")
        draw.text((stat_x + 90, stats_y + 32), label, font=fonts["stat_label"], fill=TEXT_MUTED, anchor="mt")
        stat_x += 200

    # ── Description ──
    desc_y = 185
    if guild.description:
        draw.text((60, desc_y), f"📝 {guild.description}", font=fonts["body"], fill=TEXT_MUTED)
        desc_y += 28

    # ── Sort members: owner first, then by power ──
    owner = None
    others = []
    for h in members:
        if h.user_id == guild.owner_id:
            owner = h
        else:
            others.append(h)
    others.sort(key=lambda h: -h.power)

    top5 = others[:5]
    remaining = others[5:]

    # ── Owner Card ──
    y = desc_y + 6
    if owner:
        y = _draw_owner_card(draw, fonts, owner, y)

    # ── Top 5 Section ──
    if top5:
        y = _draw_section_header(draw, fonts, y, "🏆 TOP 5 HUNTERS", icon_color=GOLD_COLOR)

        # Top 5 container
        container_top = y
        container_h = len(top5) * 42 + 8
        draw.rounded_rectangle([40, container_top, WIDTH - 40, container_top + container_h], radius=8, fill=CARD_BG, outline=HUD_CYAN, width=1)

        y = container_top + 6
        for i, h in enumerate(top5):
            y = _draw_top5_row(draw, fonts, 50, y, i + 1, h, width=WIDTH - 100)

        y = container_top + container_h + 8

    # ── Remaining Members ──
    if remaining:
        y = _draw_section_header(draw, fonts, y, "📋 OTHER MEMBERS")

        for h in remaining:
            if y > HEIGHT - 60:
                break
            y = _draw_compact_row(draw, fonts, 60, y, h, width=WIDTH - 120)

    # ── Footer ──
    draw.text(
        (WIDTH // 2, HEIGHT - 36),
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
