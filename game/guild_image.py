"""
/* Hallmark · component: guild_card · genre: atmospheric · theme: Midnight (Abyssal Monarch) */
game/guild_image.py — Solo Leveling Visual Guild Card Renderer.

Generates a stylized, high-resolution RPG Guild Card image using Pillow,
showcasing the guild name, ID, owner, top 5 hunters, and telemetry.
Fully aligned with the Hallmark Atmospheric Design System.
"""

from __future__ import annotations

import io
import math
import os
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import GUILD_MAX_MEMBERS, RANKS
from game.font_manager import get_font_cascade, clean_and_normalize_name, load_font
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
from models import Guild, Hunter

# Canvas dimensions (High-DPI 860 x 960)
WIDTH = 860
HEIGHT = 960


def _get_fonts() -> dict:
    bold = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    regular = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]
    mono = ["consola.ttf", "consolab.ttf", "cour.ttf"]

    return {
        "header_tag": load_font(bold, 12),
        "guild_name": load_font(bold, 30),
        "guild_id_badge": load_font(bold, 13),
        "subtitle": load_font(bold, 14),
        "section_header": load_font(bold, 13),
        "owner_name": load_font(bold, 18),
        "member_name": load_font(bold, 15),
        "stat_value": load_font(bold, 17),
        "stat_label": load_font(bold, 11),
        "body": load_font(regular, 13),
        "body_bold": load_font(bold, 13),
        "footer": load_font(bold, 11),
        "small": load_font(regular, 11),
        "small_bold": load_font(bold, 11),
        "rank_badge": load_font(bold, 12),
        "mono": load_font(mono, 12),
    }


def _draw_shield_crest(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 24) -> None:
    """Draw a stylized dual-layer Aegis Crest shield polygon."""
    # Outer shield
    pts_outer = [
        (cx, cy - size),
        (cx + int(size * 0.85), cy - int(size * 0.45)),
        (cx + int(size * 0.75), cy + int(size * 0.35)),
        (cx, cy + size + 2),
        (cx - int(size * 0.75), cy + int(size * 0.35)),
        (cx - int(size * 0.85), cy - int(size * 0.45)),
    ]
    draw.polygon(pts_outer, fill=(24, 18, 48), outline=INK_PURPLE, width=2)

    # Inner emblem
    inner_sz = int(size * 0.6)
    pts_inner = [
        (cx, cy - inner_sz),
        (cx + int(inner_sz * 0.8), cy - int(inner_sz * 0.35)),
        (cx + int(inner_sz * 0.7), cy + int(inner_sz * 0.3)),
        (cx, cy + inner_sz),
        (cx - int(inner_sz * 0.7), cy + int(inner_sz * 0.3)),
        (cx - int(inner_sz * 0.8), cy - int(inner_sz * 0.35)),
    ]
    draw.polygon(pts_inner, fill=INK_PURPLE, outline=INK_CYAN, width=1)
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=INK_PRIMARY)


def _draw_crown_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 10, fill=INK_GOLD) -> None:
    """Draw a handcrafted vector imperial crown icon."""
    w = size
    h = int(size * 0.75)
    pts = [
        (cx - w, cy + h), (cx - w, cy - h // 2), (cx - w // 2, cy),
        (cx, cy - h), (cx + w // 2, cy), (cx + w, cy - h // 2), (cx + w, cy + h),
    ]
    draw.polygon(pts, fill=fill, outline=(255, 240, 160), width=1)
    draw.ellipse([cx - 2, cy - h - 2, cx + 2, cy - h + 2], fill=INK_PRIMARY)


def _draw_lightning_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 8, fill=INK_CYAN) -> None:
    """Draw a sharp vector lightning bolt."""
    pts = [
        (cx + 1, cy - size),
        (cx - size // 2, cy),
        (cx, cy),
        (cx - 2, cy + size),
        (cx + size // 2 + 1, cy - 1),
        (cx + 1, cy - 1),
    ]
    draw.polygon(pts, fill=fill)


def _draw_owner_card(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    hunter: Hunter,
    y: int,
) -> int:
    """Draw the prominent guild sovereign (owner) card."""
    h_card = 62
    # Gold-trimmed surface container
    draw.rounded_rectangle([40, y, WIDTH - 40, y + h_card], radius=8, fill=SURFACE_BASE, outline=INK_GOLD, width=1)

    # Crown icon & Owner badge
    _draw_crown_icon(draw, 68, y + 22, size=11, fill=INK_GOLD)
    draw.rounded_rectangle([86, y + 10, 162, y + 28], radius=4, fill=(45, 36, 12), outline=INK_GOLD, width=1)
    draw.text((124, y + 12), "SOVEREIGN", font=fonts["small_bold"], fill=INK_GOLD, anchor="mt")

    # Sovereign Name
    cascade = get_font_cascade(18, is_bold=True)
    cascade.draw_text(draw, (86, y + 33), hunter.display_full_name, fill=INK_PRIMARY, max_w=340)

    # Rank badge
    rank_color = RANK_COLORS.get(hunter.rank, INK_GOLD)
    rank_text = f"[{hunter.rank}-RANK]"
    name_w = cascade.get_width(hunter.display_full_name, max_w=340)
    rank_x = 86 + name_w + 12
    draw.text((rank_x, y + 35), rank_text, font=fonts["rank_badge"], fill=rank_color)
    draw.text((rank_x + 64, y + 35), f"Lv.{hunter.level}", font=fonts["small"], fill=INK_SECONDARY)

    # Power right-aligned with vector lightning icon
    power_val = f"{hunter.power:,}"
    tb_p = fonts["stat_value"].getbbox(power_val)
    pw = tb_p[2] - tb_p[0]
    _draw_lightning_icon(draw, WIDTH - 60 - pw - 12, y + 22, size=7, fill=INK_GOLD)
    draw.text((WIDTH - 60 - pw, y + 14), power_val, font=fonts["stat_value"], fill=INK_GOLD)

    # Base Stats summary
    stats_str = f"STR {hunter.str_stat}  •  AGI {hunter.agi}  •  VIT {hunter.vit}  •  INT {hunter.int_stat}  •  PER {hunter.per}"
    draw.text((WIDTH - 60, y + 42), stats_str, font=fonts["small"], fill=INK_MUTED, anchor="rt")

    return y + h_card + 14


def _draw_top5_row(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    x: int,
    y: int,
    rank_pos: int,
    hunter: Hunter,
    width: int = 740,
) -> int:
    """Draw a top 5 member row with rank position badge."""
    row_h = 38

    # Row container on elevated surface
    draw.rounded_rectangle([x, y, x + width, y + row_h], radius=6, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER, width=1)

    # Position badge (#1, #2, etc.)
    badge_colors = {
        1: INK_GOLD,
        2: (226, 232, 240),
        3: (217, 119, 6),
        4: INK_CYAN,
        5: INK_CYAN,
    }
    badge_color = badge_colors.get(rank_pos, INK_CYAN)
    draw.rounded_rectangle([x + 6, y + 6, x + 42, y + row_h - 6], radius=4, fill=(*badge_color[:3], 40), outline=(*badge_color[:3], 180))
    draw.text((x + 24, y + 9), f"#{rank_pos}", font=fonts["small_bold"], fill=badge_color, anchor="mt")

    # Name with font cascade
    name_x = x + 54
    cascade = get_font_cascade(14, is_bold=True)
    cascade.draw_text(draw, (name_x, y + 8), hunter.display_full_name, fill=INK_PRIMARY, max_w=310)

    # Rank Badge after name
    name_w = cascade.get_width(hunter.display_full_name, max_w=310)
    rank_color = RANK_COLORS.get(hunter.rank, INK_SECONDARY)
    draw.text((name_x + name_w + 10, y + 9), f"[{hunter.rank}]", font=fonts["small"], fill=rank_color)

    # Level and Power on the right with vector lightning icon
    draw.text((x + width - 12, y + 6), f"Lv.{hunter.level}", font=fonts["small"], fill=INK_SECONDARY, anchor="rt")
    pwr_text = f"{hunter.power:,}"
    tb_w = fonts["small_bold"].getbbox(pwr_text)
    pw = tb_w[2] - tb_w[0]
    _draw_lightning_icon(draw, x + width - 12 - pw - 10, y + 27, size=5, fill=INK_CYAN)
    draw.text((x + width - 12, y + 21), pwr_text, font=fonts["small_bold"], fill=INK_CYAN, anchor="rt")

    return y + row_h + 5


def render_guild_image(
    guild: Guild,
    members: list[Hunter],
    total_power: int,
) -> io.BytesIO:
    """
    Render a high-resolution Hallmark Atmospheric Guild Card.
    Strictly follows Hallmark anti-AI-slop design rules:
    - Locked tokens, elevated surface hierarchy, authentic radial bloom
    - Pure Roman typography, anti-tofu font cascade, vector crests and crowns
    - Prominent Guild ID badge in title header and footer system signature.
    """
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))

    # 1. Atmospheric Canvas with Arcane / Cyan Radial Bloom (grid_spacing=0 for clean velvet finish)
    draw_atmospheric_canvas(
        img,
        top_color=CANVAS_TOP,
        bottom_color=CANVAS_BOTTOM,
        bloom_cx=WIDTH // 2,
        bloom_cy=85,
        bloom_color=(168, 85, 247, 32),
        bloom_radius=220,
        grid_spacing=0,
    )
    draw = ImageDraw.Draw(img)
    fonts = _get_fonts()

    # 2. Outer Technical HUD Framing
    draw.rectangle([20, 20, WIDTH - 20, HEIGHT - 20], outline=CANVAS_BORDER, width=1)
    draw_hud_corners(draw, (20, 20, WIDTH - 20, HEIGHT - 20), color=INK_CYAN, length=24, width=2)

    # 3. System Header & Guild Crest
    draw_diamond(draw, 122, 38, size=4, fill=INK_CYAN)
    draw.text((134, 32), "GUILD REGISTRY // 길드 정보", font=fonts["header_tag"], fill=INK_CYAN)
    _draw_shield_crest(draw, 68, 64, size=24)

    # Guild Name via Font Cascade
    cascade_title = get_font_cascade(26, is_bold=True)
    cascade_title.draw_text(draw, (116, 52), guild.name, fill=INK_PRIMARY, max_w=460)
    title_w = cascade_title.get_width(guild.name, max_w=460)

    # Guild ID Badge
    id_x = 116 + title_w + 14
    id_text = f"ID: #{guild.guild_id}"
    tb_id = fonts["guild_id_badge"].getbbox(id_text)
    id_w = tb_id[2] - tb_id[0] + 16
    draw.rounded_rectangle([id_x, 56, id_x + id_w, 78], radius=4, fill=SURFACE_ELEVATED, outline=INK_CYAN, width=1)
    draw.text((id_x + 8, 59), id_text, font=fonts["guild_id_badge"], fill=INK_CYAN)

    # 4. Tactical Telemetry Quad (4 Elevated Surface Cards)
    stats_y = 106
    quad_w = 175
    gap = 18
    quad_x = 45

    telemetry = [
        (f"{len(guild.members)}/{GUILD_MAX_MEMBERS}", "ROSTER", INK_PRIMARY),
        (f"{total_power:,}", "COMBAT POWER", INK_GOLD),
        (f"{guild.war_wins}W - {guild.war_losses}L", "WAR RECORD", INK_SKY),
        ("+10%", "XP BUFF", INK_GREEN),
    ]

    for val, label, color in telemetry:
        draw.rounded_rectangle([quad_x, stats_y, quad_x + quad_w, stats_y + 54], radius=6, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER, width=1)
        draw.text((quad_x + quad_w // 2, stats_y + 9), val, font=fonts["stat_value"], fill=color, anchor="mt")
        draw.text((quad_x + quad_w // 2, stats_y + 34), label, font=fonts["stat_label"], fill=INK_MUTED, anchor="mt")
        quad_x += quad_w + gap

    y = stats_y + 68

    # 5. Guild Directive / Description (if set)
    if guild.description:
        desc_h = 36
        draw.rounded_rectangle([40, y, WIDTH - 40, y + desc_h], radius=6, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
        desc_text = f"\"{guild.description}\""
        draw.text((56, y + 10), desc_text, font=fonts["body"], fill=INK_SECONDARY)
        y += desc_h + 14

    # 6. Sort members: Sovereign (owner) first, then remaining by power descending
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

    # 7. Guild Sovereign Card
    if owner:
        draw_diamond(draw, 48, y + 9, size=4, fill=INK_GOLD)
        draw.text((58, y), "GUILD SOVEREIGN & FOUNDER", font=fonts["section_header"], fill=INK_GOLD)
        y += 22
        y = _draw_owner_card(draw, fonts, owner, y)

    # 8. Elite Vanguard (Top 5 Members)
    if top5:
        draw_diamond(draw, 48, y + 9, size=4, fill=INK_CYAN)
        draw.text((58, y), "ELITE VANGUARD (HIGHEST POWER)", font=fonts["section_header"], fill=INK_CYAN)
        y += 22

        container_top = y
        container_h = len(top5) * 43 + 10
        draw.rounded_rectangle([40, container_top, WIDTH - 40, container_top + container_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)

        y = container_top + 6
        for i, h in enumerate(top5):
            y = _draw_top5_row(draw, fonts, 50, y, i + 1, h, width=WIDTH - 100)

        y = container_top + container_h + 14

    # 9. Remaining Members Summary
    if remaining:
        rem_count = len(remaining)
        rem_power = sum(h.power for h in remaining)
        rem_text = f"Allied Reserve: {rem_count} additional hunter(s) deployed  •  Combined Power: {rem_power:,}"
        draw.rounded_rectangle([40, y, WIDTH - 40, y + 32], radius=6, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER, width=1)
        draw.text((WIDTH // 2, y + 9), rem_text, font=fonts["small"], fill=INK_MUTED, anchor="mt")

    # 10. Hallmark Verification Signature Footer
    draw.line([(40, HEIGHT - 46), (WIDTH - 40, HEIGHT - 46)], fill=CANVAS_BORDER, width=1)
    footer_text = f"SYSTEM REGISTRY  //  HUNTER GUILD ARCHIVE  •  ID #{guild.guild_id}  •  ALL RIGHTS RESERVED"
    draw.text(
        (WIDTH // 2, HEIGHT - 32),
        footer_text,
        font=fonts["footer"],
        fill=INK_MUTED,
        anchor="mt",
    )

    # Convert to PNG buffer
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    buf.seek(0)
    return buf
