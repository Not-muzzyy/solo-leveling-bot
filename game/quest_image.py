"""
game/quest_image.py — Solo Leveling System Daily Quest Board Renderer.

Generates a Hallmark-standard 860x960 System Quest Card:
- Holographic cyan/electric blue System Quest Window
- 4 conditioning quest checklists with progress bars
- Reward preview: Free Stat Points, Gold, XP, Blessed Gift Box
- Attributes breakdown with unspent stat points counter
"""

from __future__ import annotations

import io
from typing import Optional
from PIL import Image, ImageDraw

from game.font_manager import get_font_cascade
from game.design_tokens import (
    CANVAS_TOP,
    CANVAS_BOTTOM,
    CANVAS_BORDER,
    SURFACE_BASE,
    SURFACE_ELEVATED,
    SURFACE_BORDER,
    INK_PRIMARY,
    INK_SECONDARY,
    INK_MUTED,
    INK_CYAN,
    INK_SKY,
    INK_GOLD,
    INK_GREEN,
    INK_RED,
    draw_atmospheric_canvas,
    draw_hud_corners,
    draw_diamond,
    draw_coin_icon,
)
from models import Hunter

WIDTH = 860
HEIGHT = 960


def render_quest_image(
    hunter: Hunter,
    notice: Optional[str] = None,
) -> io.BytesIO:
    """Render a high-resolution Hallmark System Daily Quest Card."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), CANVAS_TOP)

    # 1. Atmospheric Canvas with glowing cyan/electric blue System bloom
    draw_atmospheric_canvas(
        img,
        top_color=(8, 14, 28),
        bottom_color=(4, 7, 16),
        bloom_cx=WIDTH // 2,
        bloom_cy=140,
        bloom_color=(0, 210, 255, 38),
        bloom_radius=300,
        grid_spacing=60,
    )

    draw = ImageDraw.Draw(img)

    # Outer border & cybernetic HUD corners
    draw.rectangle([10, 10, WIDTH - 10, HEIGHT - 10], outline=CANVAS_BORDER, width=1)
    draw_hud_corners(draw, (10, 10, WIDTH - 10, HEIGHT - 10), color=INK_CYAN, length=24, width=2)

    # Fonts
    font_eyebrow = get_font_cascade(11, is_bold=True)
    font_title = get_font_cascade(26, is_bold=True)
    font_subtitle = get_font_cascade(13, is_bold=False)
    font_section = get_font_cascade(14, is_bold=True)
    font_body_bold = get_font_cascade(14, is_bold=True)
    font_body = get_font_cascade(13, is_bold=False)
    font_badge = get_font_cascade(11, is_bold=True)
    font_footer = get_font_cascade(11, is_bold=True)

    # ── Header ───────────────────────────────────────────────
    header_y = 28
    draw_diamond(draw, 34, header_y + 8, size=4, fill=INK_CYAN)
    font_eyebrow.draw_text(
        draw, (46, header_y + 2),
        "SYSTEM DIRECTIVE // MANDATORY DAILY PROTOCOL // ARCHIVES V2.5",
        fill=INK_CYAN,
    )

    # Status Pill
    all_done = (
        hunter.daily_quest_hunts >= 5 and
        hunter.daily_quest_explore >= 1 and
        hunter.daily_quest_duel >= 1 and
        hunter.daily_quest_use >= 1
    )
    if hunter.daily_quest_claimed:
        st_text = "STATUS // CLAIMED"
        st_col = INK_GREEN
    elif all_done:
        st_text = "STATUS // COMPLETED"
        st_col = INK_GOLD
    else:
        st_text = "STATUS // IN PROGRESS"
        st_col = INK_CYAN

    draw.rounded_rectangle([WIDTH - 190, header_y, WIDTH - 30, header_y + 22], radius=4, fill=SURFACE_ELEVATED, outline=st_col, width=1)
    draw_diamond(draw, WIDTH - 176, header_y + 11, size=3, fill=st_col)
    font_badge.draw_text(draw, (WIDTH - 162, header_y + 5), st_text, fill=INK_PRIMARY)

    font_title.draw_text(draw, (34, header_y + 26), "DAILY QUEST : PREPARATION TO BE STRONG", fill=INK_PRIMARY)
    font_subtitle.draw_text(
        draw, (34, header_y + 64),
        "Complete all physical conditioning objectives before midnight UTC to claim stat points.",
        fill=INK_SECONDARY,
    )

    draw.line([(34, header_y + 92), (WIDTH - 34, header_y + 92)], fill=SURFACE_BORDER, width=1)
    draw.line([(34, header_y + 92), (220, header_y + 92)], fill=INK_CYAN, width=2)

    # ── Hunter Overview & Unspent Stat Points ────────────────
    info_y = 132
    info_h = 66
    draw.rounded_rectangle([34, info_y, WIDTH - 34, info_y + info_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)

    h_name = hunter.display_full_name if hasattr(hunter, "display_full_name") and hunter.display_full_name else hunter.hunter_name
    font_body_bold.draw_text(draw, (50, info_y + 14), f"HUNTER: {h_name} [Rank {hunter.rank}]", fill=INK_PRIMARY)
    font_body.draw_text(
        draw, (50, info_y + 38),
        f"STR {hunter.str_stat} ┊ AGI {hunter.agi} ┊ VIT {hunter.vit} ┊ INT {hunter.int_stat} ┊ PER {hunter.per} ┊ Power: {hunter.power}",
        fill=INK_SECONDARY,
    )

    # Unspent Stat Points Pill (Right)
    sp_col = INK_GOLD if hunter.unspent_stat_points > 0 else INK_MUTED
    sp_box_x = WIDTH - 220
    draw.rounded_rectangle([sp_box_x, info_y + 14, WIDTH - 50, info_y + 52], radius=6, fill=SURFACE_ELEVATED, outline=sp_col, width=1)
    draw_diamond(draw, sp_box_x + 14, info_y + 33, size=4, fill=sp_col)
    font_body_bold.draw_text(draw, (sp_box_x + 26, info_y + 22), f"STAT PTS: {hunter.unspent_stat_points}", fill=sp_col)

    # ── Notice Banner ─────────────────────────────────────────
    curr_y = info_y + info_h + 14
    if notice:
        n_col = INK_GREEN if "CLAIMED" in notice or "ALLOCATED" in notice else INK_CYAN
        draw.rounded_rectangle([34, curr_y, WIDTH - 34, curr_y + 38], radius=6, fill=SURFACE_ELEVATED, outline=n_col, width=1)
        draw_diamond(draw, 50, curr_y + 19, size=4, fill=n_col)
        clean_notice = notice.replace("🎁", "").replace("⚡", "").replace("✅", "").strip()
        font_body_bold.draw_text(draw, (64, curr_y + 11), clean_notice, fill=n_col, max_w=WIDTH - 120)
        curr_y += 52

    # ── 4 Daily Conditioning Objectives Panel ────────────────
    quest_y = curr_y
    quest_h = 420
    draw.rounded_rectangle([34, quest_y, WIDTH - 34, quest_y + quest_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
    draw_hud_corners(draw, (34, quest_y, WIDTH - 34, quest_y + quest_h), color=INK_CYAN, length=16, width=1)

    draw_diamond(draw, 50, quest_y + 18, size=4, fill=INK_CYAN)
    font_section.draw_text(draw, (64, quest_y + 11), "MANDATORY PHYSICAL CONDITIONING DIRECTIVES", fill=INK_PRIMARY)
    draw.line([(50, quest_y + 36), (WIDTH - 50, quest_y + 36)], fill=SURFACE_BORDER, width=1)

    tasks = [
        (
            "1. GATE MONSTER EXTERMINATION",
            "Exterminate at least 5 dungeon gate beasts via /hunt",
            hunter.daily_quest_hunts,
            5,
            INK_GOLD,
        ),
        (
            "2. UNCHARTED WORLD EXPEDITION",
            "Venture into mysterious territories via /explore",
            hunter.daily_quest_explore,
            1,
            INK_SKY,
        ),
        (
            "3. COMBAT SIMULATION DUEL",
            "Engage in a competitive duel against a rival hunter via /duel",
            hunter.daily_quest_duel,
            1,
            INK_RED,
        ),
        (
            "4. ALCHEMY & VITALITY RECOVERY",
            "Consume a recovery potion, elixir, or scroll via /use or /heal",
            hunter.daily_quest_use,
            1,
            INK_GREEN,
        ),
    ]

    ty = quest_y + 50
    for title, desc, curr, target, col in tasks:
        done = curr >= target
        border_col = INK_GREEN if done else SURFACE_BORDER
        draw.rounded_rectangle([50, ty, WIDTH - 50, ty + 78], radius=6, fill=SURFACE_ELEVATED, outline=border_col, width=1)

        # Checkbox square
        cb_x = 68
        cb_y = ty + 16
        draw.rounded_rectangle([cb_x, cb_y, cb_x + 20, cb_y + 20], radius=3, fill=SURFACE_BASE, outline=INK_GREEN if done else INK_MUTED)
        if done:
            font_body_bold.draw_text(draw, (cb_x + 4, cb_y + 1), "✓", fill=INK_GREEN)

        # Task title & description
        font_body_bold.draw_text(draw, (cb_x + 30, ty + 12), title, fill=col if not done else INK_GREEN)
        font_body.draw_text(draw, (cb_x + 30, ty + 32), desc, fill=INK_SECONDARY)

        # Progress count (Right)
        progress_text = f"{min(curr, target)} / {target}"
        status_label = "COMPLETED" if done else progress_text
        lbl_col = INK_GREEN if done else INK_PRIMARY
        font_body_bold.draw_text(draw, (WIDTH - 170, ty + 14), status_label, fill=lbl_col)

        # Progress bar
        bar_w = WIDTH - 128
        bar_h = 8
        draw.rounded_rectangle([cb_x, ty + 58, cb_x + bar_w, ty + 58 + bar_h], radius=2, fill=SURFACE_BASE)
        ratio = min(1.0, curr / target)
        if ratio > 0:
            draw.rounded_rectangle([cb_x, ty + 58, cb_x + int(bar_w * ratio), ty + 58 + bar_h], radius=2, fill=INK_GREEN if done else col)

        ty += 90

    # ── Completion Reward Box ────────────────────────────────
    rew_y = quest_y + quest_h + 14
    rew_h = 160
    draw.rounded_rectangle([34, rew_y, WIDTH - 34, rew_y + rew_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)

    draw_diamond(draw, 50, rew_y + 18, size=4, fill=INK_GOLD)
    font_section.draw_text(draw, (64, rew_y + 11), "SYSTEM COMPLETION REWARDS (RESET DAILY AT 00:00 UTC)", fill=INK_PRIMARY)
    draw.line([(50, rew_y + 36), (WIDTH - 50, rew_y + 36)], fill=SURFACE_BORDER, width=1)

    rewards = [
        ("⚡ +3 STAT POINTS", "Allocate freely into attributes", INK_GOLD),
        ("💰 +600 GOLD", "Deposited to Hunter treasury", INK_GOLD),
        ("✨ +250 XP", "Accelerate rank progression", INK_CYAN),
        ("🎁 BLESSED BOX", "Contains elixirs or rare gear", INK_GREEN),
    ]

    rx = 50
    rw_box_w = (WIDTH - 100 - (len(rewards) - 1) * 10) // len(rewards)
    for r_title, r_desc, r_col in rewards:
        draw.rounded_rectangle([rx, rew_y + 48, rx + rw_box_w, rew_y + 140], radius=4, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER, width=1)
        font_body_bold.draw_text(draw, (rx + 10, rew_y + 60), r_title, fill=r_col)
        font_body.draw_text(draw, (rx + 10, rew_y + 88), r_desc, fill=INK_SECONDARY, max_w=rw_box_w - 20)
        rx += rw_box_w + 10

    # ── Footer ────────────────────────────────────────────────
    footer_y = HEIGHT - 46
    draw.line([(34, footer_y), (WIDTH - 34, footer_y)], fill=SURFACE_BORDER, width=1)
    quote = "「 THE SYSTEM REWARDS DILIGENCE WITH BOUNDLESS TRANSCENDENCE 」"
    font_footer.draw_text(draw, (WIDTH // 2 - 215, footer_y + 12), quote, fill=INK_CYAN)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
