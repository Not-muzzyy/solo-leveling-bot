"""
game/hunt_image.py — Solo Leveling Combat Result Image Card Generator.

Enhanced with Hallmark Atmospheric design principles:
- Locked design tokens and elevated surface hierarchy (SURFACE_BASE, SURFACE_ELEVATED)
- Atmospheric radial bloom tailored to victory (emerald) or defeat (crimson)
- Handcrafted vector crown and skull icons for outcome landmarks
- Clean asymmetric dual-panel telemetry
- Precision HUD corner brackets and high-contrast typography.
"""

from __future__ import annotations

import io
import os
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

from config import RANK_EMOJI, RARITY_EMOJI
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
    INK_RED_DARK,
    INK_GREEN,
    INK_GREEN_DARK,
    INK_PURPLE,
    RANK_COLORS,
    RARITY_COLORS,
    draw_atmospheric_canvas,
    draw_hud_corners,
    draw_diamond,
    draw_coin_icon,
    draw_crown_icon,
    draw_skull_icon,
    draw_rounded_gauge,
)
from models import Hunter, Monster, HuntResult, Item

# Dimensions: 800 x 450 (Crisp 16:9 banner)
WIDTH = 800
HEIGHT = 450


def _load_font(font_names: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load system font with fallbacks."""
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
    """Hierarchy of crisp fonts for 16:9 combat result card."""
    bold_fonts = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    reg_fonts = ["segoeui.ttf", "arial.ttf", "calibri.ttf"]
    return {
        "title_large": _load_font(bold_fonts, 28),
        "title": _load_font(bold_fonts, 19),
        "header": _load_font(bold_fonts, 16),
        "sub": _load_font(bold_fonts, 13),
        "body_bold": _load_font(bold_fonts, 14),
        "body": _load_font(reg_fonts, 13),
        "small_bold": _load_font(bold_fonts, 12),
        "small": _load_font(reg_fonts, 11),
    }


def _draw_left_panel(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    hunter: Hunter,
    monster: Monster,
    is_victory: bool,
):
    """Draw left panel showing Monster Target and Hunter Status."""
    x = 22
    y = 40
    w = 260
    h = 388

    draw.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)

    # ── 1. Target Monster Box ──
    draw.text((x + 14, y + 12), "[ GATE TARGET ]", font=fonts["small_bold"], fill=INK_RED)

    # Rank Badge
    r_color = RANK_COLORS.get(monster.rank, INK_CYAN)
    r_text = f"{monster.rank}-RANK"
    r_bbox = fonts["small_bold"].getbbox(r_text)
    rw = r_bbox[2] - r_bbox[0]
    draw.rounded_rectangle(
        [x + w - rw - 24, y + 10, x + w - 12, y + 30],
        radius=4,
        fill=(r_color[0] // 5, r_color[1] // 5, r_color[2] // 5),
        outline=r_color,
    )
    draw.text((x + w - rw - 18, y + 13), r_text, font=fonts["small_bold"], fill=r_color)

    # Monster Name
    m_name = monster.name
    if len(m_name) > 20:
        m_name = m_name[:18] + "..."
    draw.text((x + 14, y + 38), m_name, font=fonts["title"], fill=INK_PRIMARY)

    # Level & Stats
    draw.text((x + 14, y + 70), f"Lv.{monster.level}", font=fonts["body_bold"], fill=INK_SKY)
    draw.text((x + 70, y + 71), f"• ATK {monster.attack}  DEF {monster.defense}", font=fonts["small"], fill=INK_SECONDARY)

    # Monster HP Bar
    bar_x = x + 14
    bar_y = y + 120
    bar_w = w - 28
    bar_h = 12

    draw.text((bar_x, bar_y - 18), "MONSTER HP", font=fonts["small_bold"], fill=INK_RED)
    if is_victory:
        hp_str = f"0/{monster.hp} (SLAIN)"
        fill_val = 0
    else:
        rem_hp = max(1, int(monster.hp * 0.25))
        hp_str = f"{rem_hp}/{monster.hp}"
        fill_val = rem_hp

    hp_bbox = fonts["small_bold"].getbbox(hp_str)
    draw.text(
        (x + w - 14 - (hp_bbox[2] - hp_bbox[0]), bar_y - 18),
        hp_str,
        font=fonts["small_bold"],
        fill=INK_SECONDARY if is_victory else INK_RED,
    )

    draw_rounded_gauge(draw, bar_x, bar_y, bar_w, bar_h, fill_val, monster.hp, fill_color=INK_RED, bg_color=SURFACE_ELEVATED)

    # Center Divider
    draw.line([(x + 14, y + 160), (x + w - 14, y + 160)], fill=SURFACE_BORDER, width=1)

    # ── 2. Engaged Hunter Box ──
    draw.text((x + 14, y + 175), "[ ENGAGED HUNTER ]", font=fonts["small_bold"], fill=INK_CYAN)

    h_rank_color = RANK_COLORS.get(hunter.rank, INK_GOLD)
    hr_text = f"{hunter.rank}-RANK"
    hr_bbox = fonts["small_bold"].getbbox(hr_text)
    hr_w = hr_bbox[2] - hr_bbox[0]
    draw.rounded_rectangle(
        [x + w - hr_w - 24, y + 173, x + w - 12, y + 193],
        radius=4,
        fill=(h_rank_color[0] // 5, h_rank_color[1] // 5, h_rank_color[2] // 5),
        outline=h_rank_color,
    )
    draw.text((x + w - hr_w - 18, y + 176), hr_text, font=fonts["small_bold"], fill=h_rank_color)

    h_name = hunter.display_full_name if hasattr(hunter, "display_full_name") and hunter.display_full_name else hunter.hunter_name
    cascade_hunt = get_font_cascade(18, is_bold=True)
    cascade_hunt.draw_text(draw, (x + 14, y + 202), h_name, fill=INK_PRIMARY, max_w=w - 28)

    draw.text((x + 14, y + 236), f"Level: {hunter.level}", font=fonts["body_bold"], fill=INK_SKY)
    draw.text((x + 14, y + 262), f"Combat Power: {hunter.power:,}", font=fonts["body_bold"], fill=INK_GOLD)

    # Hunter HP Status
    h_bar_y = y + 316
    draw.text((bar_x, h_bar_y - 18), "HUNTER HP", font=fonts["small_bold"], fill=INK_CYAN)
    if is_victory:
        h_hp_str = f"{hunter.hp}/{hunter.max_hp}"
        h_fill_val = hunter.hp
        bar_fill_color = INK_GREEN
    else:
        h_hp_str = f"0/{hunter.max_hp} (EXHAUSTED)"
        h_fill_val = 0
        bar_fill_color = INK_RED

    h_hp_bbox = fonts["small_bold"].getbbox(h_hp_str)
    draw.text(
        (x + w - 14 - (h_hp_bbox[2] - h_hp_bbox[0]), h_bar_y - 18),
        h_hp_str,
        font=fonts["small_bold"],
        fill=INK_PRIMARY if is_victory else INK_RED,
    )
    draw_rounded_gauge(draw, bar_x, h_bar_y, bar_w, bar_h, h_fill_val, hunter.max_hp, fill_color=bar_fill_color, bg_color=SURFACE_ELEVATED)

    # Hunter Gold with coin vector
    draw_coin_icon(draw, x + 20, y + 360, r=6)
    draw.text((x + 32, y + 353), f"Treasury: {hunter.gold:,} G", font=fonts["small"], fill=INK_SECONDARY)


def render_hunt_image(hunter: Hunter, result: HuntResult) -> io.BytesIO:
    """
    Generate a high-definition static 16:9 banner image for the /hunt command.
    Renders crystal-clear VICTORY or DEFEAT status with combat stats, rewards, and loot.
    Returns in-memory BytesIO buffer of the PNG file.
    """
    fonts = _get_fonts()
    monster = result.monster
    is_vic = result.victory

    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    bloom_tint = (34, 197, 94, 25) if is_vic else (239, 68, 68, 25)
    draw_atmospheric_canvas(img, top_color=CANVAS_TOP, bottom_color=CANVAS_BOTTOM, bloom_cx=WIDTH - 250, bloom_cy=HEIGHT // 2, bloom_color=bloom_tint, bloom_radius=220)

    draw = ImageDraw.Draw(img)

    # Outer tech border and corner brackets
    m = 10
    draw.rectangle([m, m, WIDTH - m, HEIGHT - m], outline=CANVAS_BORDER)
    glow_color = INK_CYAN if is_vic else INK_RED
    draw_hud_corners(draw, (m, m, WIDTH - m, HEIGHT - m), color=glow_color, length=22, width=2)

    # ── Top HUD Header ──
    header_text = "SYSTEM COMBAT RESOLUTION // VICTORY" if is_vic else "SYSTEM COMBAT RESOLUTION // DEFEAT"
    acc_color = INK_GREEN if is_vic else INK_RED

    tb = fonts["sub"].getbbox(header_text)
    tw = tb[2] - tb[0]
    cx = WIDTH // 2
    draw_diamond(draw, cx - tw // 2 - 14, 24, size=4, fill=acc_color)
    draw_diamond(draw, cx + tw // 2 + 14, 24, size=4, fill=acc_color)
    draw.text((cx - tw // 2, 16), header_text, font=fonts["sub"], fill=acc_color)

    # ── Draw Left Panel (Monster & Hunter Cards) ──
    _draw_left_panel(draw, fonts, hunter, monster, is_vic)

    # ── Draw Right Panel (Battle Outcome & Rewards) ──
    rx = 298
    ry = 40
    rw = WIDTH - rx - 22
    rh = 388

    draw.rounded_rectangle([rx, ry, rx + rw, ry + rh], radius=10, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)

    # ── Outcome Banner Header Box ──
    banner_h = 76
    banner_bg = INK_GREEN_DARK if is_vic else INK_RED_DARK
    banner_outline = INK_GREEN if is_vic else INK_RED
    draw.rounded_rectangle([rx + 12, ry + 12, rx + rw - 12, ry + 12 + banner_h], radius=8, fill=banner_bg, outline=banner_outline, width=2)

    if is_vic:
        draw_crown_icon(draw, rx + 38, ry + 50, fill=INK_GOLD, scale=1.1)
        draw.text((rx + 64, ry + 20), "VICTORY  •  WON", font=fonts["title_large"], fill=INK_GOLD)
        draw.text((rx + 65, ry + 54), "GATE CLEARED • TARGET ANNIHILATED", font=fonts["small_bold"], fill=INK_GREEN)
    else:
        draw_skull_icon(draw, rx + 38, ry + 50, fill=(254, 202, 202), bg=INK_RED_DARK, scale=1.1)
        draw.text((rx + 64, ry + 20), "DEFEATED  •  LOST", font=fonts["title_large"], fill=(254, 202, 202))
        draw.text((rx + 65, ry + 54), "DUNGEON FAILED • HUNTER OVERWHELMED", font=fonts["small_bold"], fill=INK_RED)

    # ── Combat Performance Row ──
    perf_y = ry + 98
    draw.text((rx + 16, perf_y), f"Damage Dealt: {result.damage_dealt:,} DMG", font=fonts["body_bold"], fill=INK_PRIMARY)
    if result.critical_hit:
        crit_bbox = fonts["small_bold"].getbbox("CRITICAL HIT!")
        cw = crit_bbox[2] - crit_bbox[0]
        crit_x = rx + 225
        draw.rounded_rectangle([crit_x, perf_y - 2, crit_x + cw + 14, perf_y + 18], radius=4, fill=(40, 32, 10), outline=INK_GOLD)
        draw.text((crit_x + 7, perf_y), "CRITICAL HIT!", font=fonts["small_bold"], fill=INK_GOLD)

    taken_str = f"Damage Taken: -{result.damage_taken:,} HP"
    t_bbox = fonts["small_bold"].getbbox(taken_str)
    draw.text((rx + rw - 16 - (t_bbox[2] - t_bbox[0]), perf_y), taken_str, font=fonts["small_bold"], fill=INK_RED)

    draw.line([(rx + 14, perf_y + 24), (rx + rw - 14, perf_y + 24)], fill=SURFACE_BORDER, width=1)

    cur_y = perf_y + 36

    if is_vic:
        # EXP & Gold boxes side-by-side
        box_w = (rw - 36) // 2
        # EXP Box
        draw.rounded_rectangle([rx + 14, cur_y, rx + 14 + box_w, cur_y + 44], radius=6, fill=SURFACE_ELEVATED, outline=INK_SKY, width=1)
        draw_diamond(draw, rx + 26, cur_y + 22, size=3, fill=INK_CYAN)
        draw.text((rx + 36, cur_y + 7), "EXPERIENCE", font=fonts["small"], fill=INK_SECONDARY)
        draw.text((rx + 36, cur_y + 22), f"+{result.xp_gained:,} EXP", font=fonts["body_bold"], fill=INK_CYAN)

        # Gold Box with coin vector
        draw.rounded_rectangle([rx + 22 + box_w, cur_y, rx + 22 + box_w * 2, cur_y + 44], radius=6, fill=SURFACE_ELEVATED, outline=INK_GOLD, width=1)
        draw_coin_icon(draw, rx + 34 + box_w, cur_y + 22, r=6)
        draw.text((rx + 44 + box_w, cur_y + 7), "GOLD BOUNTY", font=fonts["small"], fill=INK_SECONDARY)
        draw.text((rx + 44 + box_w, cur_y + 22), f"+{result.gold_gained:,} G", font=fonts["body_bold"], fill=INK_GOLD)

        cur_y += 56

        # Level Up or Rank Up Banner
        if result.leveled_up:
            draw.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 38], radius=6, fill=INK_GREEN_DARK, outline=INK_GREEN, width=1)
            draw_diamond(draw, rx + 26, cur_y + 19, size=4, fill=INK_GREEN)
            draw.text((rx + 38, cur_y + 10), f"LEVEL UP! Advanced to Level {result.new_level}", font=fonts["body_bold"], fill=INK_GREEN)
            cur_y += 48
        elif result.ranked_up:
            rk_c = RANK_COLORS.get(result.new_rank or "E", INK_GOLD)
            draw.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 38], radius=6, fill=(38, 28, 14), outline=rk_c, width=1)
            draw_diamond(draw, rx + 26, cur_y + 19, size=4, fill=rk_c)
            draw.text((rx + 38, cur_y + 10), f"RANK UP! Promoted to {result.new_rank}-Rank Hunter", font=fonts["body_bold"], fill=rk_c)
            cur_y += 48

        # Loot Item Drop
        if result.item_drop:
            item = result.item_drop
            rc = RARITY_COLORS.get(item.rarity, INK_PRIMARY)
            draw.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 50], radius=6, fill=SURFACE_ELEVATED, outline=rc, width=1)
            draw_diamond(draw, rx + 26, cur_y + 25, size=4, fill=rc)
            type_label = item.type.capitalize()
            draw.text((rx + 38, cur_y + 9), f"LOOT DROP : {item.name}", font=fonts["body_bold"], fill=INK_PRIMARY)
            draw.text((rx + 38, cur_y + 28), f"[{item.rarity}] {type_label} • {item.stat_summary()}", font=fonts["small_bold"], fill=rc)
            cur_y += 60

        # Special Event Notice
        if result.special_event:
            ev = result.special_event.encode("ascii", "ignore").decode().strip() or result.special_event
            if len(ev) > 52:
                ev = ev[:49] + "..."
            draw.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 32], radius=6, fill=SURFACE_ELEVATED, outline=INK_SKY, width=1)
            draw_diamond(draw, rx + 24, cur_y + 16, size=3, fill=INK_SKY)
            draw.text((rx + 34, cur_y + 8), ev, font=fonts["small_bold"], fill=INK_SKY)
            cur_y += 42

    else:
        # Defeat: Penalties & Consolation
        box_w = (rw - 36) // 2
        # Treasury Penalty Box
        draw.rounded_rectangle([rx + 14, cur_y, rx + 14 + box_w, cur_y + 46], radius=6, fill=INK_RED_DARK, outline=INK_RED, width=1)
        draw_diamond(draw, rx + 26, cur_y + 23, size=3, fill=INK_RED)
        draw.text((rx + 36, cur_y + 8), "TREASURY PENALTY", font=fonts["small"], fill=INK_SECONDARY)
        draw.text((rx + 36, cur_y + 24), f"-{result.gold_lost:,} G Lost", font=fonts["body_bold"], fill=INK_RED)

        # Consolation EXP Box
        draw.rounded_rectangle([rx + 22 + box_w, cur_y, rx + 22 + box_w * 2, cur_y + 46], radius=6, fill=SURFACE_ELEVATED, outline=INK_SKY, width=1)
        draw_diamond(draw, rx + 34 + box_w, cur_y + 23, size=3, fill=INK_SKY)
        draw.text((rx + 44 + box_w, cur_y + 8), "SURVIVAL EXP", font=fonts["small"], fill=INK_SECONDARY)
        draw.text((rx + 44 + box_w, cur_y + 24), f"+{result.xp_gained:,} EXP", font=fonts["body_bold"], fill=INK_SKY)

        cur_y += 60

        # System Advice Card
        advice_h = 100
        draw.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + advice_h], radius=6, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
        draw_diamond(draw, rx + 26, cur_y + 18, size=4, fill=INK_GOLD)
        draw.text((rx + 38, cur_y + 10), "SYSTEM TACTICAL BRIEFING", font=fonts["small_bold"], fill=INK_GOLD)

        tips = [
            "• Tap /inventory in Bot PM to equip higher-rank weapons & armor",
            "• Purchase health elixirs & stat gear from the Hunter Shop",
            "• Use /claim daily to receive gold and experience allowances",
        ]
        for idx, tip in enumerate(tips):
            draw.text((rx + 24, cur_y + 34 + idx * 20), tip, font=fonts["small"], fill=INK_SECONDARY)

        cur_y += advice_h + 12

    # Bottom System Footer
    footer_text = "[ The System acknowledges those who strive to grow stronger. ]"
    fb = fonts["small"].getbbox(footer_text)
    draw.text(
        (rx + rw // 2 - (fb[2] - fb[0]) // 2, ry + rh - 24),
        footer_text,
        font=fonts["small"],
        fill=INK_SKY,
    )

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = "hunt_result.png"
    return buf
