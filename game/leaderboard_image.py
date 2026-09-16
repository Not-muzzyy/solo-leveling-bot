"""
game/leaderboard_image.py — Solo Leveling Visual Leaderboard Card Renderer.

Generates a stylized, high-resolution RPG Leaderboard Card image using Pillow,
showcasing the top-ranked hunters by Combat Power, Level, Wealth, or Victories.
Strictly displays players' real First Name and Last Name (never usernames),
with top-3 podium highlights and personal rank tracking.
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
    INK_GREEN,
    RANK_COLORS,
    draw_atmospheric_canvas,
    draw_hud_corners,
    draw_diamond,
    draw_coin_icon,
    draw_crown_icon,
)
from models import Hunter

# Canvas dimensions (860 x 1140)
WIDTH = 860
HEIGHT = 1140

HUD_CYAN = INK_CYAN
HUD_BLUE = (37, 99, 235)
HUD_SKY = INK_SKY
ALERT_RED = (239, 68, 68)
GOLD_COLOR = INK_GOLD
SILVER_COLOR = (226, 232, 240)
BRONZE_COLOR = (217, 119, 6)
GREEN_COLOR = INK_GREEN
PURPLE_COLOR = (168, 85, 247)
TEXT_WHITE = INK_PRIMARY
TEXT_MUTED = INK_SECONDARY
TEXT_DIM = INK_MUTED
CARD_BG = SURFACE_BASE
CARD_BORDER = SURFACE_BORDER

CATEGORIES = [
    ("power", "COMBAT POWER"),
    ("level", "HUNTER LEVEL"),
    ("wealth", "TREASURY WEALTH"),
    ("victories", "GATE VICTORIES"),
]


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
    """Hierarchy of fonts for leaderboard layout."""
    bold = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    regular = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]

    return {
        "title": _load_font(bold, 24),
        "subtitle": _load_font(bold, 14),
        "tag": _load_font(bold, 12),
        "name_first": _load_font(bold, 20),
        "name_podium": _load_font(bold, 17),
        "name_row": _load_font(bold, 15),
        "score_large": _load_font(bold, 20),
        "score_medium": _load_font(bold, 16),
        "score_small": _load_font(bold, 14),
        "body_bold": _load_font(bold, 13),
        "body": _load_font(regular, 13),
        "small_bold": _load_font(bold, 11),
        "small": _load_font(regular, 11),
        "footer": _load_font(bold, 12),
    }


def _draw_gradient_background(img: Image.Image) -> None:
    """Draw Hallmark atmospheric canvas ground with radial bloom for the Hall of Fame."""
    w, h = img.size
    draw_atmospheric_canvas(
        img,
        top_color=CANVAS_TOP,
        bottom_color=CANVAS_BOTTOM,
        bloom_cx=w // 2,
        bloom_cy=140,
        bloom_color=(250, 204, 21, 24),
        bloom_radius=280,
    )


def _draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 4, fill=HUD_CYAN) -> None:
    """Draw diamond vector element."""
    draw.polygon([(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)], fill=fill)


def _draw_tech_border(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int) -> None:
    """Draw tech HUD corner brackets and outer border."""
    draw.rectangle([x1, y1, x2, y2], outline=(25, 45, 80, 180), width=1)
    bracket_len = 24
    bracket_w = 3
    gold = GOLD_COLOR

    # Top-left
    draw.line([(x1, y1), (x1 + bracket_len, y1)], fill=gold, width=bracket_w)
    draw.line([(x1, y1), (x1, y1 + bracket_len)], fill=gold, width=bracket_w)
    # Top-right
    draw.line([(x2 - bracket_len, y1), (x2, y1)], fill=gold, width=bracket_w)
    draw.line([(x2, y1), (x2, y1 + bracket_len)], fill=gold, width=bracket_w)
    # Bottom-left
    draw.line([(x1, y2), (x1 + bracket_len, y2)], fill=gold, width=bracket_w)
    draw.line([(x1, y2), (x1, y2 - bracket_len)], fill=gold, width=bracket_w)
    # Bottom-right
    draw.line([(x2 - bracket_len, y2), (x2, y2)], fill=gold, width=bracket_w)
    draw.line([(x2, y2), (x2, y2 - bracket_len)], fill=gold, width=bracket_w)


def _draw_crown_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 12, fill=GOLD_COLOR) -> None:
    """Draw a vector royal crown icon for 1st place."""
    w = size
    h = int(size * 0.75)
    pts = [
        (cx - w, cy + h),
        (cx - w, cy - h // 2),
        (cx - w // 2, cy),
        (cx, cy - h),
        (cx + w // 2, cy),
        (cx + w, cy - h // 2),
        (cx + w, cy + h),
    ]
    draw.polygon(pts, fill=fill, outline=(255, 235, 120), width=1)
    # Crown jewels
    draw.ellipse([cx - 2, cy - h - 2, cx + 2, cy - h + 2], fill=(255, 255, 255))
    draw.ellipse([cx - w - 2, cy - h // 2 - 2, cx - w + 2, cy - h // 2 + 2], fill=(255, 255, 255))
    draw.ellipse([cx + w - 2, cy - h // 2 - 2, cx + w + 2, cy - h // 2 + 2], fill=(255, 255, 255))


def _get_metric_display(hunter: Hunter, category: str) -> tuple[str, str]:
    """
    Returns (score_number_string, score_unit_label) for a given category.
    """
    if category == "level":
        return f"Lv.{hunter.level}", f"{hunter.xp:,} EXP"
    elif category == "wealth":
        return f"{hunter.gold:,}", "GOLD"
    elif category == "victories":
        return f"{hunter.victories:,}", "VICTORIES"
    else:  # power (default)
        return f"{hunter.power:,}", "POWER"


def render_leaderboard_image(
    hunters: list[Hunter],
    category: str = "power",
    viewing_hunter: Optional[Hunter] = None,
    requesting_user_id: Optional[int] = None,
    current_user_id: Optional[int] = None,
) -> io.BytesIO:
    """
    Generate a high-definition static RPG Leaderboard Card.
    Strictly displays players' real First Name and Last Name.
    Highlights Top 3 podium, Ranks #4-#10, and user's personal rank card.
    Returns in-memory BytesIO buffer of the PNG file.
    """
    if requesting_user_id is None and current_user_id is not None:
        requesting_user_id = current_user_id

    # Allow passing viewing_hunter in 2nd position or category in 2nd position
    if isinstance(category, Hunter):
        viewing_hunter, category = category, "power"
    elif isinstance(viewing_hunter, str):
        category, viewing_hunter = viewing_hunter, None

    if isinstance(viewing_hunter, int):
        requesting_user_id = viewing_hunter
        viewing_hunter = None

    if viewing_hunter is None and requesting_user_id is not None:
        viewing_hunter = next((h for h in hunters if h.user_id == requesting_user_id), None)
    fonts = _get_fonts()
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    _draw_gradient_background(img)
    draw = ImageDraw.Draw(img)

    # Outer border
    _draw_tech_border(draw, 18, 18, WIDTH - 18, HEIGHT - 18)

    # ── 1. Top HUD Header ──
    sub_title = "SYSTEM PROTOCOL • GLOBAL POWER HIERARCHY"
    tb_sub = fonts["subtitle"].getbbox(sub_title)
    sub_w = tb_sub[2] - tb_sub[0]
    cx = WIDTH // 2
    _draw_diamond(draw, cx - sub_w // 2 - 14, 34, size=4, fill=GOLD_COLOR)
    _draw_diamond(draw, cx + sub_w // 2 + 14, 34, size=4, fill=GOLD_COLOR)
    draw.text((cx - sub_w // 2, 26), sub_title, font=fonts["subtitle"], fill=GOLD_COLOR)

    main_title = "HUNTER LEADERBOARD"
    tb = fonts["title"].getbbox(main_title)
    tw = tb[2] - tb[0]
    draw.text((WIDTH // 2 - tw // 2, 50), main_title, font=fonts["title"], fill=TEXT_WHITE)

    tag_text = "National Hunter Association Official Hall of Fame"
    tb_tag = fonts["small"].getbbox(tag_text)
    draw.text((WIDTH // 2 - (tb_tag[2] - tb_tag[0]) // 2, 82), tag_text, font=fonts["small"], fill=HUD_SKY)

    # ── 2. Category Indicator Tabs ──
    tab_y = 104
    tab_h = 36
    num_tabs = len(CATEGORIES)
    total_tabs_w = WIDTH - 64
    spacing = 8
    tab_w = (total_tabs_w - (num_tabs - 1) * spacing) // num_tabs

    for idx, (cat_key, cat_label) in enumerate(CATEGORIES):
        tx1 = 32 + idx * (tab_w + spacing)
        tx2 = tx1 + tab_w
        is_active = (cat_key == category)

        if is_active:
            tab_fill = (22, 38, 64, 240)
            tab_border = HUD_CYAN
            tab_text_color = HUD_CYAN
            border_w = 2
        else:
            tab_fill = (10, 16, 28, 200)
            tab_border = CARD_BORDER
            tab_text_color = TEXT_MUTED
            border_w = 1

        draw.rounded_rectangle([tx1, tab_y, tx2, tab_y + tab_h], radius=6, fill=tab_fill, outline=tab_border, width=border_w)
        tb_c = fonts["small_bold"].getbbox(cat_label)
        cw = tb_c[2] - tb_c[0]
        draw.text((tx1 + (tab_w - cw) // 2, tab_y + 10), cat_label, font=fonts["small_bold"], fill=tab_text_color)

    # ── 3. Top 3 Podium Cards ──
    # Rank #1 (Apex Hunter)
    y_p1 = 152
    h_p1 = 96
    top1 = hunters[0] if len(hunters) > 0 else None

    draw.rounded_rectangle([32, y_p1, WIDTH - 32, y_p1 + h_p1], radius=10, fill=(28, 24, 12, 240), outline=GOLD_COLOR, width=2)
    # Crown & 1ST badge
    draw.rounded_rectangle([46, y_p1 + 14, 114, y_p1 + h_p1 - 14], radius=8, fill=(48, 38, 14), outline=GOLD_COLOR, width=1)
    _draw_crown_icon(draw, 80, y_p1 + 34, size=12, fill=GOLD_COLOR)
    draw.text((64, y_p1 + 48), "1ST", font=fonts["subtitle"], fill=GOLD_COLOR)

    if top1:
        # Full Name (First + Last Name, rendered via FontCascade)
        cascade_1 = get_font_cascade(20, is_bold=True)
        cascade_1.draw_text(draw, (130, y_p1 + 18), top1.display_full_name, fill=TEXT_WHITE, max_w=420)

        # Rank badge + Level
        r_c1 = RANK_COLORS.get(top1.rank, GOLD_COLOR)
        badge_text_1 = f"[{top1.rank}-RANK]"
        tb_b1 = fonts["body_bold"].getbbox(badge_text_1)
        bw1 = tb_b1[2] - tb_b1[0]
        draw.text((130, y_p1 + 48), badge_text_1, font=fonts["body_bold"], fill=r_c1)
        draw.text((130 + bw1 + 14, y_p1 + 48), f"Level {top1.level}  •  {top1.victories:,} Hunts Succeeded", font=fonts["body"], fill=TEXT_MUTED)

        # Metric Score Right
        score_val_1, score_unit_1 = _get_metric_display(top1, category)
        tb_s1 = fonts["score_large"].getbbox(score_val_1)
        sw_1 = tb_s1[2] - tb_s1[0]
        draw.text((WIDTH - 50 - sw_1, y_p1 + 22), score_val_1, font=fonts["score_large"], fill=GOLD_COLOR)
        tb_u1 = fonts["small_bold"].getbbox(score_unit_1)
        uw_1 = tb_u1[2] - tb_u1[0]
        draw.text((WIDTH - 50 - uw_1, y_p1 + 50), score_unit_1, font=fonts["small_bold"], fill=HUD_SKY)
    else:
        draw.text((130, y_p1 + 36), "Vacant Throne", font=fonts["name_first"], fill=TEXT_MUTED)

    # Rank #2 (2nd Place)
    y_p2 = y_p1 + h_p1 + 10
    h_p2 = 78
    top2 = hunters[1] if len(hunters) > 1 else None

    draw.rounded_rectangle([32, y_p2, WIDTH - 32, y_p2 + h_p2], radius=8, fill=(18, 26, 42, 230), outline=SILVER_COLOR, width=1)
    draw.rounded_rectangle([46, y_p2 + 12, 114, y_p2 + h_p2 - 12], radius=6, fill=(26, 36, 56), outline=SILVER_COLOR, width=1)
    _draw_diamond(draw, 80, y_p2 + 25, size=4, fill=SILVER_COLOR)
    draw.text((64, y_p2 + 36), "2ND", font=fonts["body_bold"], fill=SILVER_COLOR)

    if top2:
        cascade_2 = get_font_cascade(17, is_bold=True)
        cascade_2.draw_text(draw, (130, y_p2 + 14), top2.display_full_name, fill=TEXT_WHITE, max_w=420)
        r_c2 = RANK_COLORS.get(top2.rank, SILVER_COLOR)
        badge_text_2 = f"[{top2.rank}-RANK]"
        tb_b2 = fonts["small_bold"].getbbox(badge_text_2)
        bw2 = tb_b2[2] - tb_b2[0]
        draw.text((130, y_p2 + 42), badge_text_2, font=fonts["small_bold"], fill=r_c2)
        draw.text((130 + bw2 + 12, y_p2 + 42), f"Level {top2.level}", font=fonts["small"], fill=TEXT_MUTED)

        score_val_2, score_unit_2 = _get_metric_display(top2, category)
        tb_s2 = fonts["score_medium"].getbbox(score_val_2)
        sw_2 = tb_s2[2] - tb_s2[0]
        draw.text((WIDTH - 50 - sw_2, y_p2 + 16), score_val_2, font=fonts["score_medium"], fill=SILVER_COLOR)
        tb_u2 = fonts["small_bold"].getbbox(score_unit_2)
        uw_2 = tb_u2[2] - tb_u2[0]
        draw.text((WIDTH - 50 - uw_2, y_p2 + 40), score_unit_2, font=fonts["small_bold"], fill=HUD_SKY)
    else:
        draw.text((130, y_p2 + 28), "Vacant", font=fonts["body_bold"], fill=TEXT_MUTED)

    # Rank #3 (3rd Place)
    y_p3 = y_p2 + h_p2 + 10
    h_p3 = 78
    top3 = hunters[2] if len(hunters) > 2 else None

    draw.rounded_rectangle([32, y_p3, WIDTH - 32, y_p3 + h_p3], radius=8, fill=(26, 20, 16, 230), outline=BRONZE_COLOR, width=1)
    draw.rounded_rectangle([46, y_p3 + 12, 114, y_p3 + h_p3 - 12], radius=6, fill=(38, 28, 20), outline=BRONZE_COLOR, width=1)
    _draw_diamond(draw, 80, y_p3 + 25, size=4, fill=BRONZE_COLOR)
    draw.text((64, y_p3 + 36), "3RD", font=fonts["body_bold"], fill=BRONZE_COLOR)

    if top3:
        cascade_3 = get_font_cascade(17, is_bold=True)
        cascade_3.draw_text(draw, (130, y_p3 + 14), top3.display_full_name, fill=TEXT_WHITE, max_w=420)
        r_c3 = RANK_COLORS.get(top3.rank, BRONZE_COLOR)
        badge_text_3 = f"[{top3.rank}-RANK]"
        tb_b3 = fonts["small_bold"].getbbox(badge_text_3)
        bw3 = tb_b3[2] - tb_b3[0]
        draw.text((130, y_p3 + 42), badge_text_3, font=fonts["small_bold"], fill=r_c3)
        draw.text((130 + bw3 + 12, y_p3 + 42), f"Level {top3.level}", font=fonts["small"], fill=TEXT_MUTED)

        score_val_3, score_unit_3 = _get_metric_display(top3, category)
        tb_s3 = fonts["score_medium"].getbbox(score_val_3)
        sw_3 = tb_s3[2] - tb_s3[0]
        draw.text((WIDTH - 50 - sw_3, y_p3 + 16), score_val_3, font=fonts["score_medium"], fill=BRONZE_COLOR)
        tb_u3 = fonts["small_bold"].getbbox(score_unit_3)
        uw_3 = tb_u3[2] - tb_u3[0]
        draw.text((WIDTH - 50 - uw_3, y_p3 + 40), score_unit_3, font=fonts["small_bold"], fill=HUD_SKY)
    else:
        draw.text((130, y_p3 + 28), "Vacant", font=fonts["body_bold"], fill=TEXT_MUTED)

    # ── 4. Ranks #4 through #10 Rows ──
    list_y = y_p3 + h_p3 + 14
    list_h = 490
    draw.rounded_rectangle([32, list_y, WIDTH - 32, list_y + list_h], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)

    # Header row inside container
    draw.text((50, list_y + 14), "[ ELITE HUNTERS #4 - #10 ]", font=fonts["tag"], fill=HUD_CYAN)
    draw.line([(48, list_y + 36), (WIDTH - 48, list_y + 36)], fill=CARD_BORDER, width=1)

    row_start_y = list_y + 42
    row_h = 58
    for idx in range(3, 10):
        pos = idx + 1
        ry = row_start_y + (idx - 3) * row_h
        h_entry = hunters[idx] if idx < len(hunters) else None

        # Subtle zebra striping for rows
        if idx % 2 == 0:
            draw.rounded_rectangle([44, ry + 2, WIDTH - 44, ry + row_h - 2], radius=6, fill=(16, 24, 40, 180))

        # Position Badge (#4, #5...)
        draw.rounded_rectangle([52, ry + 12, 92, ry + row_h - 12], radius=4, fill=(18, 28, 48), outline=CARD_BORDER)
        draw.text((60, ry + 17), f"#{pos}", font=fonts["small_bold"], fill=HUD_SKY)

        if h_entry:
            # Full Name (First + Last Name, rendered via FontCascade)
            cascade_row = get_font_cascade(15, is_bold=True)
            cascade_row.draw_text(draw, (108, ry + 11), h_entry.display_full_name, fill=TEXT_WHITE, max_w=400)

            # Hunter Rank & Level
            rk_c = RANK_COLORS.get(h_entry.rank, TEXT_MUTED)
            badge_text_e = f"[{h_entry.rank}-RANK]"
            tb_be = fonts["small_bold"].getbbox(badge_text_e)
            bwe = tb_be[2] - tb_be[0]
            draw.text((108, ry + 33), badge_text_e, font=fonts["small_bold"], fill=rk_c)
            draw.text((108 + bwe + 12, ry + 33), f"Level {h_entry.level}", font=fonts["small"], fill=TEXT_MUTED)

            # Score Right (neatly right-aligned)
            s_val, s_unit = _get_metric_display(h_entry, category)
            full_score_str = f"{s_val} {s_unit}"
            tb_fs = fonts["score_small"].getbbox(full_score_str)
            fsw = tb_fs[2] - tb_fs[0]
            draw.text((WIDTH - 56 - fsw, ry + 18), full_score_str, font=fonts["score_small"], fill=HUD_CYAN)
        else:
            draw.text((108, ry + 20), "— Vacant Position —", font=fonts["body"], fill=TEXT_DIM)

    # ── 5. Current User Standing Card ──
    user_y = list_y + list_h + 14
    user_h = 76
    draw.rounded_rectangle([32, user_y, WIDTH - 32, user_y + user_h], radius=8, fill=(16, 32, 52, 240), outline=HUD_CYAN, width=2)

    _draw_diamond(draw, 50, user_y + 24, size=4, fill=HUD_CYAN)
    draw.text((62, user_y + 14), "[ YOUR CURRENT SYSTEM RANK ]", font=fonts["small_bold"], fill=HUD_CYAN)

    if viewing_hunter:
        # Find viewing hunter's rank index in full sorted hunters list
        try:
            my_idx = next(i for i, h in enumerate(hunters) if h.user_id == viewing_hunter.user_id)
            my_rank_str = f"#{my_idx + 1}"
        except StopIteration:
            my_rank_str = "Unranked"

        cascade_standing = get_font_cascade(15, is_bold=True)
        vr_col = RANK_COLORS.get(viewing_hunter.rank, GOLD_COLOR)
        rank_name_str = f"{my_rank_str}  •  {viewing_hunter.display_full_name}"
        drawn_w = cascade_standing.draw_text(draw, (50, user_y + 40), rank_name_str, fill=TEXT_WHITE, max_w=400)

        badge_x = 50 + drawn_w + 16
        draw.text((badge_x, user_y + 42), f"[{viewing_hunter.rank}-Rank]  Lv.{viewing_hunter.level}", font=fonts["body_bold"], fill=vr_col)

        my_score, my_unit = _get_metric_display(viewing_hunter, category)
        tb_my = fonts["score_medium"].getbbox(f"{my_score} {my_unit}")
        mw = tb_my[2] - tb_my[0]
        draw.text((WIDTH - 50 - mw, user_y + 28), f"{my_score} {my_unit}", font=fonts["score_medium"], fill=GOLD_COLOR)
    else:
        draw.text((50, user_y + 38), "Awaken as a Hunter via /start to register on the leaderboard.", font=fonts["body"], fill=TEXT_MUTED)

    # ── 6. Bottom System Footer ──
    footer_text = "[ Only the strongest shall stand at the pinnacle of the System. ]"
    tb_f = fonts["footer"].getbbox(footer_text)
    fw = tb_f[2] - tb_f[0]
    draw.text((WIDTH // 2 - fw // 2, HEIGHT - 38), footer_text, font=fonts["footer"], fill=HUD_SKY)

    # Export PNG
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = f"leaderboard_{category}.png"
    return buf
