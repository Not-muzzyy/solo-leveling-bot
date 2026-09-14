"""
game/hunt_image.py — Solo Leveling Combat Result Image Card Generator.

Generates a static, high-definition 16:9 banner image (PNG) for the /hunt command,
clearly showing VICTORY or DEFEAT with complete battle statistics, rewards, and loot.
Optimized for mobile Telegram with razor-sharp typography, vibrant system colors,
and zero font rendering artifacts.
"""

from __future__ import annotations

import io
import os
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

from config import RANK_EMOJI, RARITY_EMOJI
from game.font_manager import get_font_cascade, clean_and_normalize_name
from models import Hunter, Monster, HuntResult, Item

# Dimensions: 800 x 450 (Crisp 16:9 banner)
WIDTH = 800
HEIGHT = 450

# Color Palette
BG_DARK = (8, 12, 22)
HUD_CYAN = (0, 229, 255)
HUD_BLUE = (37, 99, 235)
HUD_SKY = (56, 189, 248)
ALERT_RED = (239, 68, 68)
GOLD_COLOR = (250, 204, 21)
GREEN_COLOR = (34, 197, 94)
PURPLE_COLOR = (168, 85, 247)
TEXT_WHITE = (248, 250, 252)
TEXT_MUTED = (148, 163, 184)
TEXT_DIM = (71, 85, 105)
CARD_BG = (13, 20, 36)
CARD_BORDER = (30, 58, 102)

RANK_COLORS = {
    "E": (148, 163, 184),
    "D": (34, 197, 94),
    "C": (56, 189, 248),
    "B": (168, 85, 247),
    "A": (244, 63, 94),
    "S": (251, 191, 36),
    "SS": (245, 158, 11),
    "SSS": (239, 68, 68),
    "National Level": (236, 72, 153),
    "Monarch": (192, 132, 252),
}

RARITY_COLOR_MAP = {
    "Common": (148, 163, 184),
    "Uncommon": (34, 197, 94),
    "Rare": (56, 189, 248),
    "Epic": (168, 85, 247),
    "Legendary": (251, 191, 36),
    "Mythic": (239, 68, 68),
}


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
        "title_large": _load_font(bold_fonts, 32),
        "title": _load_font(bold_fonts, 20),
        "header": _load_font(bold_fonts, 16),
        "sub": _load_font(bold_fonts, 13),
        "body_bold": _load_font(bold_fonts, 14),
        "body": _load_font(reg_fonts, 13),
        "small_bold": _load_font(bold_fonts, 12),
        "small": _load_font(reg_fonts, 11),
    }


def _draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 4, fill=HUD_CYAN):
    draw.polygon([(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)], fill=fill)


def _create_canvas(is_victory: bool) -> Image.Image:
    """Create a dark dungeon gradient canvas with HUD corner brackets and ambient glow."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)

    accent = GREEN_COLOR if is_victory else ALERT_RED

    # Subtle ambient background gradient
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        if is_victory:
            r = int(BG_DARK[0] * (1 - ratio * 0.2))
            g = int(BG_DARK[1] + 12 * (1 - ratio))
            b = int(BG_DARK[2] * (1 - ratio * 0.1))
        else:
            r = int(BG_DARK[0] + 18 * (1 - ratio))
            g = int(BG_DARK[1] * (1 - ratio * 0.3))
            b = int(BG_DARK[2] * (1 - ratio * 0.2))
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Outer tech border and corner brackets
    m = 10
    b_len = 20
    draw.rectangle([m, m, WIDTH - m, HEIGHT - m], outline=(25, 45, 75))

    glow_color = HUD_CYAN if is_victory else ALERT_RED
    draw.line([(m, m), (m + b_len, m)], fill=glow_color, width=2)
    draw.line([(m, m), (m, m + b_len)], fill=glow_color, width=2)
    draw.line([(WIDTH - m - b_len, m), (WIDTH - m, m)], fill=glow_color, width=2)
    draw.line([(WIDTH - m, m), (WIDTH - m, m + b_len)], fill=glow_color, width=2)
    draw.line([(m, HEIGHT - m - b_len), (m, HEIGHT - m)], fill=glow_color, width=2)
    draw.line([(m, HEIGHT - m), (m + b_len, HEIGHT - m)], fill=glow_color, width=2)
    draw.line([(WIDTH - m - b_len, HEIGHT - m), (WIDTH - m, HEIGHT - m)], fill=glow_color, width=2)
    draw.line([(WIDTH - m, HEIGHT - m - b_len), (WIDTH - m, HEIGHT - m)], fill=glow_color, width=2)

    return img


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

    draw.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)

    # ── 1. Target Monster Box ──
    draw.text((x + 14, y + 12), "[ GATE TARGET ]", font=fonts["small_bold"], fill=ALERT_RED)

    # Rank Badge
    r_color = RANK_COLORS.get(monster.rank, HUD_CYAN)
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
    draw.text((x + 14, y + 38), m_name, font=fonts["title"], fill=TEXT_WHITE)

    # Level & Stats
    draw.text((x + 14, y + 70), f"Lv.{monster.level}", font=fonts["body_bold"], fill=HUD_SKY)
    draw.text((x + 70, y + 71), f"• ATK {monster.attack}  DEF {monster.defense}", font=fonts["small"], fill=TEXT_MUTED)

    # Monster HP Bar
    bar_x = x + 14
    bar_y = y + 120
    bar_w = w - 28
    bar_h = 12

    draw.text((bar_x, bar_y - 18), "MONSTER HP", font=fonts["small_bold"], fill=ALERT_RED)
    if is_victory:
        hp_str = f"0/{monster.hp} (SLAIN)"
        fill_pct = 0.0
    else:
        rem_hp = max(1, int(monster.hp * 0.25))
        hp_str = f"{rem_hp}/{monster.hp}"
        fill_pct = 0.25

    hp_bbox = fonts["small_bold"].getbbox(hp_str)
    draw.text(
        (x + w - 14 - (hp_bbox[2] - hp_bbox[0]), bar_y - 18),
        hp_str,
        font=fonts["small_bold"],
        fill=TEXT_MUTED if is_victory else ALERT_RED,
    )

    # HP bar background container with crisp outline
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=6, fill=(22, 28, 42), outline=(40, 56, 82), width=1)
    if fill_pct > 0:
        fill_w = max(8, int(bar_w * fill_pct))
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=6, fill=ALERT_RED)

    # Center Divider
    draw.line([(x + 14, y + 160), (x + w - 14, y + 160)], fill=CARD_BORDER, width=1)

    # ── 2. Engaged Hunter Box ──
    draw.text((x + 14, y + 175), "[ ENGAGED HUNTER ]", font=fonts["small_bold"], fill=HUD_CYAN)

    h_rank_color = RANK_COLORS.get(hunter.rank, GOLD_COLOR)
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
    cascade_hunt.draw_text(draw, (x + 14, y + 202), h_name, fill=TEXT_WHITE, max_w=w - 28)

    draw.text((x + 14, y + 236), f"Level: {hunter.level}", font=fonts["body_bold"], fill=HUD_SKY)
    draw.text((x + 14, y + 262), f"Combat Power: {hunter.power:,}", font=fonts["body_bold"], fill=GOLD_COLOR)

    # Hunter HP Status
    h_bar_y = y + 316
    draw.text((bar_x, h_bar_y - 18), "HUNTER HP", font=fonts["small_bold"], fill=HUD_CYAN)
    if is_victory:
        h_hp_str = f"{hunter.hp}/{hunter.max_hp}"
        h_fill_pct = max(0.2, min(1.0, hunter.hp / max(1, hunter.max_hp)))
        bar_fill_color = GREEN_COLOR
    else:
        h_hp_str = f"0/{hunter.max_hp} (EXHAUSTED)"
        h_fill_pct = 0.0
        bar_fill_color = ALERT_RED

    h_hp_bbox = fonts["small_bold"].getbbox(h_hp_str)
    draw.text(
        (x + w - 14 - (h_hp_bbox[2] - h_hp_bbox[0]), h_bar_y - 18),
        h_hp_str,
        font=fonts["small_bold"],
        fill=TEXT_WHITE if is_victory else ALERT_RED,
    )
    draw.rounded_rectangle([bar_x, h_bar_y, bar_x + bar_w, h_bar_y + bar_h], radius=6, fill=(22, 28, 42), outline=(40, 56, 82), width=1)
    if h_fill_pct > 0:
        draw.rounded_rectangle([bar_x, h_bar_y, bar_x + max(8, int(bar_w * h_fill_pct)), h_bar_y + bar_h], radius=6, fill=bar_fill_color)

    # Hunter Gold
    draw.text((x + 14, y + 352), f"Treasury: {hunter.gold:,} G", font=fonts["small"], fill=TEXT_MUTED)


def render_hunt_image(hunter: Hunter, result: HuntResult) -> io.BytesIO:
    """
    Generate a high-definition static 16:9 banner image for the /hunt command.
    Renders crystal-clear VICTORY or DEFEAT status with combat stats, rewards, and loot.
    Returns in-memory BytesIO buffer of the PNG file.
    """
    fonts = _get_fonts()
    monster = result.monster
    is_vic = result.victory

    img = _create_canvas(is_vic)
    draw = ImageDraw.Draw(img)

    # ── Top HUD Header ──
    header_text = "SYSTEM COMBAT RESOLUTION : VICTORY" if is_vic else "SYSTEM COMBAT RESOLUTION : DEFEAT"
    acc_color = GREEN_COLOR if is_vic else ALERT_RED

    tb = fonts["sub"].getbbox(header_text)
    tw = tb[2] - tb[0]
    cx = WIDTH // 2
    _draw_diamond(draw, cx - tw // 2 - 14, 24, size=4, fill=acc_color)
    _draw_diamond(draw, cx + tw // 2 + 14, 24, size=4, fill=acc_color)
    draw.text((cx - tw // 2, 16), header_text, font=fonts["sub"], fill=acc_color)

    # ── Draw Left Panel (Monster & Hunter Cards) ──
    _draw_left_panel(draw, fonts, hunter, monster, is_vic)

    # ── Draw Right Panel (Battle Outcome & Rewards) ──
    rx = 298
    ry = 40
    rw = WIDTH - rx - 22
    rh = 388

    # Outer Outcome Card Container
    draw.rounded_rectangle([rx, ry, rx + rw, ry + rh], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)

    # ── Outcome Banner Header Box ──
    banner_h = 76
    banner_bg = (14, 38, 25) if is_vic else (42, 16, 22)
    banner_outline = GREEN_COLOR if is_vic else ALERT_RED
    draw.rounded_rectangle([rx + 12, ry + 12, rx + rw - 12, ry + 12 + banner_h], radius=8, fill=banner_bg, outline=banner_outline, width=2)

    if is_vic:
        _draw_diamond(draw, rx + 28, ry + 36, size=6, fill=GREEN_COLOR)
        _draw_diamond(draw, rx + 28, ry + 54, size=4, fill=GOLD_COLOR)
        draw.text((rx + 44, ry + 18), "VICTORY", font=fonts["title_large"], fill=TEXT_WHITE)
        draw.text((rx + 46, ry + 56), "GATE CLEARED • TARGET ANNIHILATED", font=fonts["small_bold"], fill=GREEN_COLOR)
    else:
        _draw_diamond(draw, rx + 28, ry + 36, size=6, fill=ALERT_RED)
        _draw_diamond(draw, rx + 28, ry + 54, size=4, fill=ALERT_RED)
        draw.text((rx + 44, ry + 18), "DEFEATED", font=fonts["title_large"], fill=ALERT_RED)
        draw.text((rx + 46, ry + 56), "DUNGEON FAILED • HUNTER OVERWHELMED", font=fonts["small_bold"], fill=TEXT_MUTED)

    # ── Combat Performance Row ──
    perf_y = ry + 98
    draw.text((rx + 16, perf_y), f"Damage Dealt: {result.damage_dealt:,} DMG", font=fonts["body_bold"], fill=TEXT_WHITE)
    if result.critical_hit:
        crit_bbox = fonts["small_bold"].getbbox("CRITICAL HIT!")
        cw = crit_bbox[2] - crit_bbox[0]
        crit_x = rx + 225
        draw.rounded_rectangle([crit_x, perf_y - 2, crit_x + cw + 14, perf_y + 18], radius=4, fill=(40, 32, 10), outline=GOLD_COLOR)
        draw.text((crit_x + 7, perf_y), "CRITICAL HIT!", font=fonts["small_bold"], fill=GOLD_COLOR)

    taken_str = f"Damage Taken: -{result.damage_taken:,} HP"
    t_bbox = fonts["small_bold"].getbbox(taken_str)
    draw.text((rx + rw - 16 - (t_bbox[2] - t_bbox[0]), perf_y), taken_str, font=fonts["small_bold"], fill=ALERT_RED)

    draw.line([(rx + 14, perf_y + 24), (rx + rw - 14, perf_y + 24)], fill=CARD_BORDER, width=1)

    cur_y = perf_y + 36

    if is_vic:
        # ── Rewards: EXP & Gold boxes side-by-side ──
        box_w = (rw - 36) // 2
        # EXP Box
        draw.rounded_rectangle([rx + 14, cur_y, rx + 14 + box_w, cur_y + 44], radius=6, fill=(16, 28, 48), outline=HUD_SKY, width=1)
        _draw_diamond(draw, rx + 26, cur_y + 22, size=3, fill=HUD_CYAN)
        draw.text((rx + 36, cur_y + 7), "EXPERIENCE", font=fonts["small"], fill=TEXT_MUTED)
        draw.text((rx + 36, cur_y + 22), f"+{result.xp_gained:,} EXP", font=fonts["body_bold"], fill=HUD_CYAN)

        # Gold Box
        draw.rounded_rectangle([rx + 22 + box_w, cur_y, rx + 22 + box_w * 2, cur_y + 44], radius=6, fill=(30, 26, 16), outline=GOLD_COLOR, width=1)
        _draw_diamond(draw, rx + 34 + box_w, cur_y + 22, size=3, fill=GOLD_COLOR)
        draw.text((rx + 44 + box_w, cur_y + 7), "GOLD BOUNTY", font=fonts["small"], fill=TEXT_MUTED)
        draw.text((rx + 44 + box_w, cur_y + 22), f"+{result.gold_gained:,} G", font=fonts["body_bold"], fill=GOLD_COLOR)

        cur_y += 56

        # ── Level Up or Rank Up Banner (if triggered) ──
        if result.leveled_up:
            draw.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 38], radius=6, fill=(16, 42, 28), outline=GREEN_COLOR, width=1)
            _draw_diamond(draw, rx + 26, cur_y + 19, size=4, fill=GREEN_COLOR)
            draw.text((rx + 38, cur_y + 10), f"LEVEL UP! Advanced to Level {result.new_level}", font=fonts["body_bold"], fill=GREEN_COLOR)
            cur_y += 48
        elif result.ranked_up:
            rk_c = RANK_COLORS.get(result.new_rank or "E", GOLD_COLOR)
            draw.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 38], radius=6, fill=(38, 28, 14), outline=rk_c, width=1)
            _draw_diamond(draw, rx + 26, cur_y + 19, size=4, fill=rk_c)
            draw.text((rx + 38, cur_y + 10), f"RANK UP! Promoted to {result.new_rank}-Rank Hunter", font=fonts["body_bold"], fill=rk_c)
            cur_y += 48

        # ── Loot Item Drop (if dropped) ──
        if result.item_drop:
            item = result.item_drop
            rc = RARITY_COLOR_MAP.get(item.rarity, TEXT_WHITE)
            draw.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 50], radius=6, fill=(20, 24, 40), outline=rc, width=1)
            _draw_diamond(draw, rx + 26, cur_y + 25, size=4, fill=rc)
            type_label = item.type.capitalize()
            draw.text((rx + 38, cur_y + 9), f"LOOT DROP : {item.name}", font=fonts["body_bold"], fill=TEXT_WHITE)
            draw.text((rx + 38, cur_y + 28), f"[{item.rarity}] {type_label} • {item.stat_summary()}", font=fonts["small_bold"], fill=rc)
            cur_y += 60

        # ── Special Event Notice (if any) ──
        if result.special_event:
            ev = result.special_event.encode("ascii", "ignore").decode().strip() or result.special_event
            if len(ev) > 52:
                ev = ev[:49] + "..."
            draw.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 32], radius=6, fill=(16, 24, 42), outline=HUD_SKY, width=1)
            _draw_diamond(draw, rx + 24, cur_y + 16, size=3, fill=HUD_SKY)
            draw.text((rx + 34, cur_y + 8), ev, font=fonts["small_bold"], fill=HUD_SKY)
            cur_y += 42

    else:
        # ── Defeat: Penalties & Consolation side-by-side ──
        box_w = (rw - 36) // 2
        # Treasury Penalty Box
        draw.rounded_rectangle([rx + 14, cur_y, rx + 14 + box_w, cur_y + 46], radius=6, fill=(38, 16, 22), outline=ALERT_RED, width=1)
        _draw_diamond(draw, rx + 26, cur_y + 23, size=3, fill=ALERT_RED)
        draw.text((rx + 36, cur_y + 8), "TREASURY PENALTY", font=fonts["small"], fill=TEXT_MUTED)
        draw.text((rx + 36, cur_y + 24), f"-{result.gold_lost:,} G Lost", font=fonts["body_bold"], fill=ALERT_RED)

        # Consolation EXP Box
        draw.rounded_rectangle([rx + 22 + box_w, cur_y, rx + 22 + box_w * 2, cur_y + 46], radius=6, fill=(16, 24, 40), outline=HUD_SKY, width=1)
        _draw_diamond(draw, rx + 34 + box_w, cur_y + 23, size=3, fill=HUD_SKY)
        draw.text((rx + 44 + box_w, cur_y + 8), "SURVIVAL EXP", font=fonts["small"], fill=TEXT_MUTED)
        draw.text((rx + 44 + box_w, cur_y + 24), f"+{result.xp_gained:,} EXP", font=fonts["body_bold"], fill=HUD_SKY)

        cur_y += 60

        # System Advice Card (Clean & Helpful)
        advice_h = 100
        draw.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + advice_h], radius=6, fill=(14, 18, 30), outline=(40, 56, 85), width=1)
        _draw_diamond(draw, rx + 26, cur_y + 18, size=4, fill=GOLD_COLOR)
        draw.text((rx + 38, cur_y + 10), "SYSTEM TACTICAL BRIEFING", font=fonts["small_bold"], fill=GOLD_COLOR)

        tips = [
            "• Tap /inventory in Bot PM to equip higher-rank weapons & armor",
            "• Purchase health elixirs & stat gear from the Hunter Shop",
            "• Use /claim daily to receive gold and experience allowances",
        ]
        for idx, tip in enumerate(tips):
            draw.text((rx + 24, cur_y + 34 + idx * 20), tip, font=fonts["small"], fill=TEXT_MUTED)

        cur_y += advice_h + 12

    # ── Bottom System Footer ──
    footer_text = "[ The System acknowledges those who strive to grow stronger. ]"
    fb = fonts["small"].getbbox(footer_text)
    draw.text(
        (rx + rw // 2 - (fb[2] - fb[0]) // 2, ry + rh - 24),
        footer_text,
        font=fonts["small"],
        fill=HUD_SKY,
    )

    # Export as pristine PNG
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = "hunt_result.png"
    return buf
