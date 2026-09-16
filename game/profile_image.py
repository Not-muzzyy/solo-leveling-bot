"""
game/profile_image.py — Solo Leveling System Status Window Image Renderer.

Enhanced with Hallmark Atmospheric design principles:
- Locked design tokens and elevated surface hierarchy (SURFACE_BASE, SURFACE_ELEVATED)
- Atmospheric radial bloom centered behind Hunter avatar
- High-contrast typography with authentic font cascade
- Precision vector icons (Rank rings, Gold coins, Diamonds, HUD brackets)
- Live stat telemetry with segmented gauges and duel records.
"""

from __future__ import annotations

import io
import math
import os
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import RANKS
from game.font_manager import get_font_cascade, clean_and_normalize_name
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
    draw_rounded_gauge,
)
from models import Hunter, Inventory, Item

# Canvas dimensions (High-DPI 860 x 1180)
WIDTH = 860
HEIGHT = 1180


def _load_font(font_names: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Attempt to load one of the specified TrueType fonts, falling back to default."""
    win_fonts = os.environ.get("WINDIR", "C:\\Windows") + "\\Fonts"
    candidates = []
    for name in font_names:
        candidates.append(os.path.join(win_fonts, name))
        candidates.append(name)

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
    """Retrieve styled fonts for different text hierarchies with Hallmark typography pairing."""
    bold_candidates = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    regular_candidates = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]
    mono_candidates = ["consola.ttf", "consolab.ttf", "cour.ttf"]

    return {
        "title": _load_font(bold_candidates, 30),
        "subtitle": _load_font(bold_candidates, 17),
        "header_tag": _load_font(bold_candidates, 13),
        "name": _load_font(bold_candidates, 34),
        "name_small": _load_font(bold_candidates, 26),
        "rank": _load_font(bold_candidates, 17),
        "body_bold": _load_font(bold_candidates, 15),
        "body": _load_font(regular_candidates, 14),
        "stat_val": _load_font(bold_candidates, 16),
        "stat_label": _load_font(bold_candidates, 14),
        "small": _load_font(regular_candidates, 12),
        "small_bold": _load_font(bold_candidates, 12),
        "mono": _load_font(mono_candidates, 13),
        "footer": _load_font(bold_candidates, 14),
    }


def _draw_card(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, radius: int = 10, fill=SURFACE_BASE, outline=SURFACE_BORDER) -> None:
    """Draw a styled atmospheric dark container card with subtle bevel outline."""
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=1)


def _draw_avatar(
    base: Image.Image,
    pfp_image: Optional[Image.Image],
    x: int,
    y: int,
    size: int = 96,
    rank: str = "E",
) -> None:
    """
    Draw a circular profile avatar with anti-aliasing and a rank-colored glowing ring.
    Falls back to a stylized Hunter silhouette if no PFP is provided.
    """
    mask_scale = 4
    high_size = size * mask_scale
    mask_high = Image.new("L", (high_size, high_size), 0)
    mask_draw = ImageDraw.Draw(mask_high)
    mask_draw.ellipse([0, 0, high_size - 1, high_size - 1], fill=255)
    mask = mask_high.resize((size, size), Image.Resampling.LANCZOS)

    if pfp_image:
        try:
            w, h = pfp_image.size
            dim = min(w, h)
            left = (w - dim) // 2
            top = (h - dim) // 2
            cropped = pfp_image.crop((left, top, left + dim, top + dim))
            avatar_resized = cropped.resize((size, size), Image.Resampling.LANCZOS).convert("RGBA")

            avatar_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            avatar_layer.paste(avatar_resized, (0, 0), mask=mask)
            base.alpha_composite(avatar_layer, (x, y))
        except Exception:
            pfp_image = None

    if not pfp_image:
        avatar_bg = Image.new("RGBA", (size, size), (15, 23, 42, 255))
        avatar_draw = ImageDraw.Draw(avatar_bg)
        center = size // 2
        avatar_draw.ellipse([center - 16, center - 26, center + 16, center + 6], fill=(56, 189, 248, 220))
        avatar_draw.chord([center - 32, center + 10, center + 32, center + 50], start=0, end=180, fill=(30, 58, 102, 240))
        avatar_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        avatar_layer.paste(avatar_bg, (0, 0), mask=mask)
        base.alpha_composite(avatar_layer, (x, y))

    # Glowing outer border ring matching rank color
    ring_color = RANK_COLORS.get(rank, INK_CYAN)
    draw = ImageDraw.Draw(base)
    draw.ellipse([x - 3, y - 3, x + size + 3, y + size + 3], outline=(ring_color[0], ring_color[1], ring_color[2], 90), width=1)
    draw.ellipse([x - 1, y - 1, x + size + 1, y + size + 1], outline=ring_color, width=2)


def _draw_stat_row(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    x: int,
    y: int,
    w: int,
    name: str,
    full_name: str,
    val: int,
    max_val: int = 40,
) -> None:
    """Render a single stat line with label, value, and segmented HUD gauge."""
    draw.text((x, y), name, font=fonts["stat_label"], fill=INK_SKY)
    draw.text((x + 45, y + 2), full_name, font=fonts["small"], fill=INK_SECONDARY)

    # Value
    val_str = str(val)
    val_bbox = fonts["stat_val"].getbbox(val_str)
    val_w = val_bbox[2] - val_bbox[0]
    draw.text((x + 160 - val_w, y), val_str, font=fonts["stat_val"], fill=INK_PRIMARY)

    # Bar gauge
    bar_x = x + 175
    bar_w = w - 175
    bar_h = 10
    bar_y = y + 5
    draw_rounded_gauge(draw, bar_x, bar_y, bar_w, bar_h, val, max(max_val, val), fill_color=INK_CYAN, bg_color=SURFACE_ELEVATED)


def render_profile_image(
    hunter: Hunter,
    inventory: Inventory,
    pfp_image: Optional[Image.Image] = None,
    full_name: Optional[str] = None,
) -> io.BytesIO:
    """
    Render a Solo Leveling Status Window image for the given hunter, inventory,
    optional profile photo, and full name (first + last name).
    Returns a BytesIO buffer containing the encoded PNG image.
    """
    base = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))

    # 1. Atmospheric Canvas Ground with radial bloom around identity card
    rank_color = RANK_COLORS.get(hunter.rank, INK_CYAN)
    bloom_tint = (rank_color[0], rank_color[1], rank_color[2], 26)
    draw_atmospheric_canvas(base, top_color=CANVAS_TOP, bottom_color=CANVAS_BOTTOM, bloom_cx=WIDTH // 2, bloom_cy=170, bloom_color=bloom_tint, bloom_radius=300)

    draw = ImageDraw.Draw(base)
    fonts = _get_fonts()

    # 2. Outer Tech HUD boundary
    margin = 32
    draw.rectangle([margin, margin, WIDTH - margin, HEIGHT - margin], outline=CANVAS_BORDER, width=1)
    draw_hud_corners(draw, (margin, margin, WIDTH - margin, HEIGHT - margin), color=INK_CYAN, length=28, width=3)

    # 3. Top System Header
    header_y = 52
    tag_text = "S Y S T E M   S T A T U S   W I N D O W"
    tag_bbox = fonts["header_tag"].getbbox(tag_text)
    tag_w = tag_bbox[2] - tag_bbox[0]
    center_x = WIDTH // 2

    draw_diamond(draw, center_x - tag_w // 2 - 20, header_y + 8, size=5, fill=INK_CYAN)
    draw_diamond(draw, center_x + tag_w // 2 + 20, header_y + 8, size=5, fill=INK_CYAN)

    draw.line([(center_x - 260, header_y + 8), (center_x - tag_w // 2 - 35, header_y + 8)], fill=(0, 180, 255, 120), width=1)
    draw.line([(center_x + tag_w // 2 + 35, header_y + 8), (center_x + 260, header_y + 8)], fill=(0, 180, 255, 120), width=1)
    draw.text((center_x - tag_w // 2, header_y), tag_text, font=fonts["header_tag"], fill=INK_CYAN)

    sub_notice = "OFFICIAL HUNTER ASSOCIATION REGISTRY // V2.6"
    sub_bbox = fonts["small"].getbbox(sub_notice)
    sub_w = sub_bbox[2] - sub_bbox[0]
    draw.text((center_x - sub_w // 2, header_y + 22), sub_notice, font=fonts["small"], fill=INK_SECONDARY)

    # 4. Identity Card (Avatar PFP, Name, Rank, Title)
    card1_y = 96
    card1_h = 140
    card_w = WIDTH - (margin + 20) * 2
    card_x = margin + 20
    _draw_card(draw, card_x, card1_y, card_x + card_w, card1_y + card1_h, radius=12)

    avatar_size = 96
    avatar_x = card_x + 22
    avatar_y = card1_y + (card1_h - avatar_size) // 2
    _draw_avatar(base, pfp_image, avatar_x, avatar_y, size=avatar_size, rank=hunter.rank)

    # Rank Badge (Right-aligned inside Card 1)
    rank_badge_text = f"{hunter.rank}-RANK"
    rank_bbox = fonts["rank"].getbbox(rank_badge_text)
    badge_text_w = rank_bbox[2] - rank_bbox[0]
    badge_w = max(130, badge_text_w + 36)
    badge_h = 44
    badge_x = card_x + card_w - badge_w - 24
    badge_y = card1_y + 28

    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
        radius=8,
        fill=(rank_color[0] // 5, rank_color[1] // 5, rank_color[2] // 5, 200),
        outline=rank_color,
        width=2,
    )
    draw.text((badge_x + (badge_w - badge_text_w) // 2, badge_y + 11), rank_badge_text, font=fonts["rank"], fill=rank_color)

    rank_cap = "HUNTER CLASS"
    cap_bbox = fonts["small_bold"].getbbox(rank_cap)
    cap_w = cap_bbox[2] - cap_bbox[0]
    draw.text((badge_x + (badge_w - cap_w) // 2, badge_y + 54), rank_cap, font=fonts["small_bold"], fill=INK_SECONDARY)

    # Text Block
    text_x = avatar_x + avatar_size + 20
    max_text_w = badge_x - text_x - 16

    raw_name = full_name.strip() if full_name and full_name.strip() else hunter.hunter_name
    primary_name = clean_and_normalize_name(raw_name)

    cascade_name = get_font_cascade(34, is_bold=True)
    cascade_name_small = get_font_cascade(26, is_bold=True)
    bb_name = cascade_name.getbbox(primary_name)
    w_name = bb_name[2] - bb_name[0]
    name_cascade = cascade_name_small if w_name > max_text_w else cascade_name
    name_cascade.draw_text(draw, (text_x, card1_y + 22), primary_name, fill=INK_PRIMARY, max_w=max_text_w)

    if full_name and full_name.strip().lower() != hunter.hunter_name.strip().lower():
        title_text = f"Hunter: {hunter.hunter_name} • {hunter.title}"
    else:
        title_text = f"Title: {hunter.title}"
    title_text = clean_and_normalize_name(title_text)

    cascade_title = get_font_cascade(13, is_bold=True)
    cascade_title.draw_text(draw, (text_x, card1_y + 60), title_text, fill=INK_SKY, max_w=max_text_w)

    user_tag = f"@{hunter.username}" if hunter.username else f"ID: {hunter.user_id}"
    draw.text((text_x, card1_y + 88), user_tag, font=fonts["small"], fill=INK_SECONDARY)

    # 5. Vitals & Progression (Level, Power, HP, XP)
    card2_y = card1_y + card1_h + 16
    card2_h = 175
    _draw_card(draw, card_x, card2_y, card_x + card_w, card2_y + card2_h, radius=12)

    weapon = inventory.get_equipped("weapon")
    armor = inventory.get_equipped("armor")
    accessory = inventory.get_equipped("accessory")
    equip_power = sum(
        (i.atk_bonus + i.def_bonus + i.hp_bonus + i.spd_bonus)
        for i in [weapon, armor, accessory]
        if i
    )

    # Left Column: Level
    draw.text((card_x + 24, card2_y + 18), "CURRENT LEVEL", font=fonts["small_bold"], fill=INK_SECONDARY)
    draw.text((card_x + 24, card2_y + 36), f"Lv. {hunter.level}", font=fonts["title"], fill=INK_CYAN)

    # Right Column: Power
    draw.text((card_x + card_w // 2, card2_y + 18), "COMBAT POWER", font=fonts["small_bold"], fill=INK_SECONDARY)
    power_str = f"{hunter.power}"
    draw.text((card_x + card_w // 2, card2_y + 36), power_str, font=fonts["title"], fill=INK_GOLD)
    if equip_power > 0:
        p_bbox = fonts["title"].getbbox(power_str)
        p_w = p_bbox[2] - p_bbox[0]
        draw.text((card_x + card_w // 2 + p_w + 10, card2_y + 46), f"(+{equip_power})", font=fonts["body_bold"], fill=INK_GREEN)

    draw.line([(card_x + 24, card2_y + 82), (card_x + card_w - 24, card2_y + 82)], fill=SURFACE_BORDER, width=1)

    # HP Progress Bar
    bar_width = card_w - 48
    hp_y = card2_y + 94
    draw.text((card_x + 24, hp_y), "HP", font=fonts["body_bold"], fill=INK_RED)
    hp_text = f"{hunter.hp} / {hunter.max_hp}"
    hp_bbox = fonts["body_bold"].getbbox(hp_text)
    hp_tw = hp_bbox[2] - hp_bbox[0]
    draw.text((card_x + card_w - 24 - hp_tw, hp_y), hp_text, font=fonts["body_bold"], fill=INK_PRIMARY)
    draw_rounded_gauge(draw, card_x + 24, hp_y + 20, bar_width, 10, hunter.hp, hunter.max_hp, fill_color=INK_RED, bg_color=SURFACE_ELEVATED)

    # XP Progress Bar
    xp_y = hp_y + 38
    draw.text((card_x + 24, xp_y), "EXP", font=fonts["body_bold"], fill=INK_SKY)
    xp_pct = int((hunter.xp / hunter.xp_needed) * 100) if hunter.xp_needed > 0 else 0
    xp_text = f"{hunter.xp} / {hunter.xp_needed}  ({xp_pct}%)"
    xp_bbox = fonts["body_bold"].getbbox(xp_text)
    xp_tw = xp_bbox[2] - xp_bbox[0]
    draw.text((card_x + card_w - 24 - xp_tw, xp_y), xp_text, font=fonts["body_bold"], fill=INK_PRIMARY)
    draw_rounded_gauge(draw, card_x + 24, xp_y + 20, bar_width, 10, hunter.xp, hunter.xp_needed, fill_color=INK_CYAN, bg_color=SURFACE_ELEVATED)

    # 6. Attributes / Stats Matrix
    card3_y = card2_y + card2_h + 16
    card3_h = 210
    _draw_card(draw, card_x, card3_y, card_x + card_w, card3_y + card3_h, radius=12)

    draw_diamond(draw, card_x + 30, card3_y + 26, size=4, fill=INK_SKY)
    draw.text((card_x + 42, card3_y + 16), "ABILITY MATRIX", font=fonts["subtitle"], fill=INK_SKY)

    stats_list = [
        ("STR", "Strength", hunter.str_stat),
        ("AGI", "Agility", hunter.agi),
        ("VIT", "Vitality", hunter.vit),
        ("INT", "Intelligence", hunter.int_stat),
        ("PER", "Perception", hunter.per),
    ]
    max_stat = max(max(s[2] for s in stats_list), 30)

    stat_row_y = card3_y + 48
    stat_spacing = 31
    for i, (code, full, val) in enumerate(stats_list):
        _draw_stat_row(draw, fonts, card_x + 24, stat_row_y + i * stat_spacing, card_w - 48, code, full, val, max_val=max_stat)

    # 7. Equipped Gear Slots
    card4_y = card3_y + card3_h + 16
    card4_h = 195
    _draw_card(draw, card_x, card4_y, card_x + card_w, card4_y + card4_h, radius=12)

    draw_diamond(draw, card_x + 30, card4_y + 26, size=4, fill=INK_SKY)
    draw.text((card_x + 42, card4_y + 16), "EQUIPMENT SLOTS", font=fonts["subtitle"], fill=INK_SKY)

    def draw_equip_slot(slot_name: str, item: Optional[Item], sy: int):
        slot_bg_w = card_w - 48
        draw.rounded_rectangle([card_x + 24, sy, card_x + 24 + slot_bg_w, sy + 38], radius=6, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER)

        draw.text((card_x + 36, sy + 11), f"[{slot_name}]", font=fonts["small_bold"], fill=INK_SKY)

        if item:
            r_color = RARITY_COLORS.get(item.rarity, INK_PRIMARY)
            draw.text((card_x + 140, sy + 10), item.name, font=fonts["body_bold"], fill=INK_PRIMARY)
            draw.text((card_x + 370, sy + 11), f"[{item.rarity}]", font=fonts["small_bold"], fill=r_color)

            summary = item.stat_summary() or "No Bonus"
            sum_bbox = fonts["small"].getbbox(summary)
            sum_w = sum_bbox[2] - sum_bbox[0]
            draw.text((card_x + 24 + slot_bg_w - sum_w - 14, sy + 11), summary, font=fonts["small"], fill=INK_GREEN)
        else:
            draw.text((card_x + 140, sy + 11), "-- Empty Slot --", font=fonts["small"], fill=INK_MUTED)

    gear_y = card4_y + 48
    draw_equip_slot("WEAPON", weapon, gear_y)
    draw_equip_slot("ARMOR", armor, gear_y + 46)
    draw_equip_slot("ACCESSORY", accessory, gear_y + 92)

    # 8. Records / Summary Badges (Including Duels & Gates)
    card5_y = card4_y + card4_h + 16
    card5_h = 120
    _draw_card(draw, card_x, card5_y, card_x + card_w, card5_y + card5_h, radius=12)

    col_w = (card_w - 30) // 4
    win_rate = "—"
    if hunter.total_hunts > 0:
        wr = (hunter.victories / hunter.total_hunts) * 100
        win_rate = f"{wr:.0f}%"

    gold_str = f"{hunter.gold:,} G"
    metrics = [
        ("TREASURY", gold_str, INK_GOLD),
        ("INVENTORY", f"{len(inventory.items)} Items", INK_PRIMARY),
        ("DUNGEON HUNTS", f"{hunter.total_hunts} ({win_rate})", INK_SKY),
        ("ARENA DUELS", f"{hunter.duel_wins}W - {hunter.duel_losses}L", INK_GREEN),
    ]

    for idx, (label, val_str, val_color) in enumerate(metrics):
        cx = card_x + 15 + idx * col_w
        cy = card5_y + 20

        draw.text((cx + 12, cy), label, font=fonts["small_bold"], fill=INK_SECONDARY)
        draw.text((cx + 12, cy + 22), val_str, font=fonts["body_bold"], fill=val_color)

        if idx == 0:
            val_bbox = fonts["body_bold"].getbbox(val_str)
            vw = val_bbox[2] - val_bbox[0]
            draw_coin_icon(draw, cx + 12 + vw + 12, cy + 30, r=6)

        if idx == 0:
            draw.text((cx + 12, cy + 46), "Available funds", font=fonts["small"], fill=INK_MUTED)
        elif idx == 1:
            equipped_count = sum(1 for i in inventory.items if i.is_equipped)
            draw.text((cx + 12, cy + 46), f"{equipped_count} Equipped", font=fonts["small"], fill=INK_MUTED)
        elif idx == 2:
            draw.text((cx + 12, cy + 46), f"W:{hunter.victories}  L:{hunter.defeats}", font=fonts["small"], fill=INK_MUTED)
        elif idx == 3:
            total_d = hunter.duel_wins + hunter.duel_losses
            d_rate = f"{(hunter.duel_wins / total_d * 100):.0f}% WR" if total_d > 0 else "Unranked"
            draw.text((cx + 12, cy + 46), f"PvP {d_rate}", font=fonts["small"], fill=INK_MUTED)

        if idx < 3:
            sep_x = cx + col_w - 4
            draw.line([(sep_x, cy + 4), (sep_x, cy + 64)], fill=SURFACE_BORDER, width=1)

    # 9. System Footer
    footer_text = "[ The System acknowledges those who strive to grow stronger. ]"
    f_bbox = fonts["footer"].getbbox(footer_text)
    f_w = f_bbox[2] - f_bbox[0]
    draw.text((center_x - f_w // 2, HEIGHT - margin - 36), footer_text, font=fonts["footer"], fill=INK_SKY)

    watermark = "SOLO LEVELING HUNTER SYSTEM // ATMOSPHERIC VERIFICATION V2.6"
    wm_bbox = fonts["small"].getbbox(watermark)
    wm_w = wm_bbox[2] - wm_bbox[0]
    draw.text((center_x - wm_w // 2, HEIGHT - margin - 18), watermark, font=fonts["small"], fill=INK_MUTED)

    buf = io.BytesIO()
    base.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = "profile.png"
    return buf
