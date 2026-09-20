"""
game/shadows_image.py — Hallmark-Compliant Shadow Army Visual Card Renderer.

Renders high-definition visual cards for /shadows displaying the player's
Shadow Monarch Army, tier distribution, active soldiers, and army power.
"""

from __future__ import annotations

import io
import math
from typing import Optional
from PIL import Image, ImageDraw

from game.design_tokens import (
    CANVAS_BORDER,
    SURFACE_BASE,
    SURFACE_ELEVATED,
    SURFACE_BORDER,
    SURFACE_BORDER_LIGHT,
    INK_PRIMARY,
    INK_SECONDARY,
    INK_MUTED,
    INK_CYAN,
    INK_GOLD,
    INK_PURPLE,
    INK_GREEN,
    RANK_COLORS,
    RARITY_COLORS,
    draw_atmospheric_canvas,
    draw_hud_corners,
    draw_diamond,
    draw_system_bracket,
)
from game.font_manager import get_font_cascade, clean_and_normalize_name
from models import Hunter, UserShadow

WIDTH = 920
HEIGHT = 640

# Rarity stat multipliers for army power calculation
RARITY_POWER_VALUES = {
    "Common": 25,
    "Uncommon": 60,
    "Rare": 150,
    "Epic": 350,
    "Legendary": 800,
    "Mythic": 2000,
}


def render_shadows_image(
    hunter: Hunter,
    shadows: list[UserShadow],
    page: int = 1,
    total_pages: int = 1,
    filter_rarity: Optional[str] = None,
    notice: Optional[str] = None,
) -> io.BytesIO:
    """
    Render a clean, high-definition 920 × 640 px Hallmark Shadow Army Card.
    Returns in-memory PNG BytesIO.
    """
    img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 6, 18))

    # 1. Atmospheric Monarch Canvas with violet radial bloom (pure dark ground)
    draw_atmospheric_canvas(
        img,
        top_color=(16, 8, 28),
        bottom_color=(5, 3, 10),
        bloom_cx=WIDTH // 2,
        bloom_cy=140,
        bloom_color=(168, 85, 247, 36),
        bloom_radius=340,
        grid_spacing=0,
    )

    draw = ImageDraw.Draw(img)

    # Outer border & cybernetic HUD corners
    draw.rectangle([10, 10, WIDTH - 10, HEIGHT - 10], outline=CANVAS_BORDER, width=1)
    draw_hud_corners(draw, (10, 10, WIDTH - 10, HEIGHT - 10), color=INK_PURPLE, length=24, width=2)

    # Fonts
    font_eyebrow = get_font_cascade(11, is_bold=True)
    font_title = get_font_cascade(24, is_bold=True)
    font_subtitle = get_font_cascade(12, is_bold=False)
    font_body_bold = get_font_cascade(15, is_bold=True)
    font_body = get_font_cascade(12, is_bold=False)
    font_stat_val = get_font_cascade(20, is_bold=True)
    font_badge = get_font_cascade(11, is_bold=True)
    font_footer = get_font_cascade(11, is_bold=False)

    # ── Header ───────────────────────────────────────────────
    draw_diamond(draw, 34, 38, size=4, fill=INK_PURPLE)
    font_eyebrow.draw_text(
        draw,
        (46, 32),
        "SOLO LEVELING // SHADOW ARMY COLLECTION",
        fill=INK_PURPLE,
    )

    # Title & Rank
    h_name = clean_and_normalize_name(hunter.hunter_name or f"Hunter #{hunter.user_id}")
    font_title.draw_text(draw, (34, 48), h_name, fill=INK_PRIMARY)

    title_w = font_title.getbbox(h_name)[2] - font_title.getbbox(h_name)[0]
    rank_color = RANK_COLORS.get(hunter.rank, INK_CYAN)

    # Rank Badge
    badge_x = 34 + title_w + 14
    badge_w = 68
    badge_h = 24
    draw.rounded_rectangle([badge_x, 52, badge_x + badge_w, 52 + badge_h], radius=4, fill=SURFACE_ELEVATED, outline=rank_color, width=1)
    rank_str = f"RANK {hunter.rank}"
    rw = font_badge.getbbox(rank_str)[2] - font_badge.getbbox(rank_str)[0]
    font_badge.draw_text(draw, (badge_x + (badge_w - rw) // 2, 56), rank_str, fill=rank_color)

    # Subtitle
    sub_text = f"Level {hunter.level} ┊ {hunter.title or 'Shadow Monarch'}"
    font_subtitle.draw_text(draw, (34, 78), sub_text, fill=INK_SECONDARY)

    # ── Simplified Summary Metrics (Y: 104 to 160) ─────────────
    panel_y = 104
    panel_h = 56
    draw.rounded_rectangle([34, panel_y, WIDTH - 34, panel_y + panel_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
    draw_hud_corners(draw, (34, panel_y, WIDTH - 34, panel_y + panel_h), color=INK_PURPLE, length=12, width=1)

    total_soldiers = sum(s.count for s in shadows)
    unique_species = len(shadows)

    metrics = [
        ("TOTAL SOLDIERS", f"{total_soldiers:,}", INK_PURPLE),
        ("UNIQUE FORMS", f"{unique_species}", INK_CYAN),
        ("PAGE", f"{page} / {max(total_pages, 1)}", INK_GOLD),
    ]

    col_w = (WIDTH - 68) // len(metrics)
    for i, (label, val, val_col) in enumerate(metrics):
        cx = 34 + i * col_w + col_w // 2
        font_badge.draw_text(draw, (cx, panel_y + 10), label, fill=INK_MUTED, anchor="mt")
        font_stat_val.draw_text(draw, (cx, panel_y + 26), val, fill=val_col, anchor="mt")
        if i < len(metrics) - 1:
            sep_x = 34 + (i + 1) * col_w
            draw.line([(sep_x, panel_y + 12), (sep_x, panel_y + panel_h - 12)], fill=SURFACE_BORDER, width=1)

    # ── Optional Notice Banner ────────────────────────────────
    roster_y = 174
    if notice:
        draw.rounded_rectangle([34, roster_y, WIDTH - 34, roster_y + 30], radius=6, fill=SURFACE_ELEVATED, outline=INK_PURPLE, width=1)
        draw_diamond(draw, 50, roster_y + 15, size=4, fill=INK_PURPLE)
        font_body_bold.draw_text(draw, (64, roster_y + 7), notice, fill=INK_CYAN, max_w=WIDTH - 120)
        roster_y += 38

    # ── Active Shadow Soldiers Grid (3 Columns × 2 Rows = 6 Cards) ─
    page_size = 6
    start_idx = (page - 1) * page_size
    current_page_shadows = shadows[start_idx : start_idx + page_size]

    cols = 3
    rows = 2
    grid_gap_x = 14
    grid_gap_y = 14
    total_grid_w = WIDTH - 68
    card_w = (total_grid_w - (cols - 1) * grid_gap_x) // cols
    card_h = 196 if not notice else 176

    if not current_page_shadows:
        # Empty state panel
        empty_h = 360
        draw.rounded_rectangle([34, roster_y, WIDTH - 34, roster_y + empty_h], radius=10, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
        draw_hud_corners(draw, (34, roster_y, WIDTH - 34, roster_y + empty_h), color=INK_PURPLE, length=16, width=1)
        font_title.draw_text(
            draw,
            (WIDTH // 2, roster_y + 120),
            "NO SHADOW SOLDIERS EXTRACTED YET",
            fill=INK_PRIMARY,
            anchor="mt",
        )
        font_body.draw_text(
            draw,
            (WIDTH // 2, roster_y + 165),
            "Wild shadows appear every 250 group messages.",
            fill=INK_SECONDARY,
            anchor="mt",
        )
        font_body_bold.draw_text(
            draw,
            (WIDTH // 2, roster_y + 195),
            "Claim them with:  /arise <character name>",
            fill=INK_PURPLE,
            anchor="mt",
        )
    else:
        for idx, shadow in enumerate(current_page_shadows):
            col = idx % cols
            row = idx // cols
            cx = 34 + col * (card_w + grid_gap_x)
            cy = roster_y + row * (card_h + grid_gap_y)

            r_color = RARITY_COLORS.get(shadow.rarity, INK_MUTED)

            # Soldier Card Background
            draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=8, fill=SURFACE_BASE, outline=r_color, width=1)

            # Accent top bar in rarity color
            draw.rounded_rectangle([cx, cy, cx + card_w, cy + 4], radius=2, fill=r_color)

            # Rarity Badge
            draw_diamond(draw, cx + 16, cy + 22, size=4, fill=r_color)
            font_badge.draw_text(draw, (cx + 26, cy + 16), shadow.rarity.upper(), fill=r_color)

            # Multiplier Pill (Top Right)
            mult_str = f"×{shadow.count}"
            mw = font_badge.getbbox(mult_str)[2] - font_badge.getbbox(mult_str)[0]
            pill_w = mw + 16
            draw.rounded_rectangle(
                [cx + card_w - pill_w - 12, cy + 12, cx + card_w - 12, cy + 30],
                radius=4,
                fill=SURFACE_ELEVATED,
                outline=SURFACE_BORDER,
                width=1,
            )
            font_badge.draw_text(
                draw,
                (cx + card_w - pill_w - 4, cy + 16),
                mult_str,
                fill=INK_GOLD if shadow.count > 1 else INK_PRIMARY,
            )

            # Divider line
            draw.line([(cx + 14, cy + 42), (cx + card_w - 14, cy + 42)], fill=SURFACE_BORDER, width=1)

            # Character Name
            c_name = clean_and_normalize_name(shadow.name)
            font_body_bold.draw_text(draw, (cx + 14, cy + 54), c_name, fill=INK_PRIMARY, max_w=card_w - 28)

            # Count info
            cnt_text = f"Extracted: {shadow.count} soldiers" if shadow.count > 1 else "Extracted: 1 soldier"
            font_subtitle.draw_text(draw, (cx + 14, cy + 96), cnt_text, fill=INK_SECONDARY)

            # Bottom Rarity Pill
            badge_box_h = 28
            b_y = cy + card_h - badge_box_h - 12
            draw.rounded_rectangle(
                [cx + 14, b_y, cx + card_w - 14, b_y + badge_box_h],
                radius=4,
                fill=SURFACE_ELEVATED,
                outline=r_color,
                width=1,
            )
            type_text = f"{shadow.rarity.upper()} SHADOW"
            font_badge.draw_text(
                draw,
                (cx + card_w // 2, b_y + 8),
                type_text,
                fill=r_color,
                anchor="mt",
            )

    # ── Footer ────────────────────────────────────────────────
    footer_y = HEIGHT - 36
    footer_text = f"SOLO LEVELING ┊ PAGE {page} OF {max(total_pages, 1)}"
    font_footer.draw_text(draw, (WIDTH // 2, footer_y), footer_text, fill=INK_MUTED, anchor="mt")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
