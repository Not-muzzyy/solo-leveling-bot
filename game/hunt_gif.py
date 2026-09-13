"""
game/hunt_gif.py — Compact 16:9 Animated Solo Leveling Combat GIF Generator.

Generates a wide, compact 16:9 banner battle sequence animation for the /hunt command.
Optimized for mobile Telegram to occupy ~40% of the screen instead of full screen,
with razor-sharp typography, zero dithering blur, and snappy combat timings.
"""

from __future__ import annotations

import io
import math
import os
import random
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import RANK_EMOJI, RARITY_EMOJI
from models import Hunter, Monster, HuntResult, Item

# Dimensions (Compact 16:9 Banner - Fits mobile screen without full-screen stretching)
WIDTH = 640
HEIGHT = 360

# Color Constants
BG_DARK = (7, 11, 20)
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
    """Hierarchy of crisp fonts for 16:9 compact battle banner."""
    bold_fonts = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    reg_fonts = ["segoeui.ttf", "arial.ttf", "calibri.ttf"]
    return {
        "title": _load_font(bold_fonts, 18),
        "header": _load_font(bold_fonts, 15),
        "sub": _load_font(bold_fonts, 12),
        "body_bold": _load_font(bold_fonts, 13),
        "body": _load_font(reg_fonts, 12),
        "big_damage": _load_font(bold, 30) if "bold" in locals() else _load_font(bold_fonts, 30),
        "impact": _load_font(bold_fonts, 18),
        "small_bold": _load_font(bold_fonts, 11),
        "small": _load_font(reg_fonts, 10),
    }


def _create_canvas(color_accent: Tuple[int, int, int] = (0, 140, 255)) -> Image.Image:
    """Create a dark dungeon gradient canvas with HUD corner brackets."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)

    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(BG_DARK[0] * (1 - ratio * 0.4))
        g = int(BG_DARK[1] * (1 - ratio * 0.3))
        b = int(BG_DARK[2] * (1 - ratio * 0.2))
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Tech corner brackets
    m = 10
    b_len = 16
    draw.rectangle([m, m, WIDTH - m, HEIGHT - m], outline=(25, 45, 75))

    cyan = HUD_CYAN
    draw.line([(m, m), (m + b_len, m)], fill=cyan, width=2)
    draw.line([(m, m), (m, m + b_len)], fill=cyan, width=2)
    draw.line([(WIDTH - m - b_len, m), (WIDTH - m, m)], fill=cyan, width=2)
    draw.line([(WIDTH - m, m), (WIDTH - m, m + b_len)], fill=cyan, width=2)
    draw.line([(m, HEIGHT - m - b_len), (m, HEIGHT - m)], fill=cyan, width=2)
    draw.line([(m, HEIGHT - m), (m + b_len, HEIGHT - m)], fill=cyan, width=2)
    draw.line([(WIDTH - m - b_len, HEIGHT - m), (WIDTH - m, HEIGHT - m)], fill=cyan, width=2)
    draw.line([(WIDTH - m, HEIGHT - m - b_len), (WIDTH - m, HEIGHT - m)], fill=cyan, width=2)

    return img


def _draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 4, fill=HUD_CYAN):
    draw.polygon([(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)], fill=fill)


def _draw_left_panel(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    hunter: Hunter,
    monster: Monster,
    hp_pct: float,
    shake_x: int = 0,
):
    """Draw left panel with Monster card and Hunter info."""
    x = 20 + shake_x
    y = 38
    w = 230
    h = 308

    draw.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)

    # Header Tag
    draw.text((x + 14, y + 12), "[ TARGET ]", font=fonts["small_bold"], fill=ALERT_RED)

    # Rank Badge
    r_color = RANK_COLORS.get(monster.rank, HUD_CYAN)
    r_text = f"{monster.rank}-RANK"
    r_bbox = fonts["small_bold"].getbbox(r_text)
    rw = r_bbox[2] - r_bbox[0]
    draw.rounded_rectangle([x + w - rw - 24, y + 10, x + w - 12, y + 28], radius=4, fill=(r_color[0] // 5, r_color[1] // 5, r_color[2] // 5), outline=r_color)
    draw.text((x + w - rw - 18, y + 13), r_text, font=fonts["small_bold"], fill=r_color)

    # Monster Name
    m_name = monster.name
    if len(m_name) > 18:
        m_name = m_name[:16] + "..."
    draw.text((x + 14, y + 36), m_name, font=fonts["title"], fill=TEXT_WHITE)

    # Level & Stats
    draw.text((x + 14, y + 66), f"Lv.{monster.level}", font=fonts["body_bold"], fill=HUD_SKY)
    draw.text((x + 65, y + 68), f"• ATK {monster.attack}  DEF {monster.defense}", font=fonts["small"], fill=TEXT_MUTED)

    # HP Bar
    bar_x = x + 14
    bar_y = y + 115
    bar_w = w - 28
    bar_h = 12

    draw.text((bar_x, bar_y - 18), "MONSTER HP", font=fonts["small_bold"], fill=ALERT_RED)
    cur_hp = max(0, int(monster.hp * hp_pct))
    hp_str = f"{cur_hp}/{monster.hp}"
    hp_bbox = fonts["small_bold"].getbbox(hp_str)
    draw.text((x + w - 14 - (hp_bbox[2] - hp_bbox[0]), bar_y - 18), hp_str, font=fonts["small_bold"], fill=TEXT_WHITE)

    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=6, fill=(25, 15, 20))
    if hp_pct > 0:
        fill_w = max(8, int(bar_w * hp_pct))
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=6, fill=ALERT_RED)

    # Divider
    draw.line([(x + 14, y + 150), (x + w - 14, y + 150)], fill=CARD_BORDER, width=1)

    # Hunter Status Box at bottom of left panel
    draw.text((x + 14, y + 162), "[ HUNTER ]", font=fonts["small_bold"], fill=HUD_CYAN)
    h_name = hunter.hunter_name
    if len(h_name) > 18:
        h_name = h_name[:16] + "..."
    draw.text((x + 14, y + 182), h_name, font=fonts["body_bold"], fill=TEXT_WHITE)
    draw.text((x + 14, y + 208), f"Level: {hunter.level}", font=fonts["small"], fill=HUD_SKY)
    draw.text((x + 14, y + 230), f"Rank: {hunter.rank}-Rank", font=fonts["small"], fill=GOLD_COLOR)
    draw.text((x + 14, y + 252), f"Combat Power: {hunter.power}", font=fonts["small_bold"], fill=TEXT_WHITE)


def render_hunt_gif(hunter: Hunter, result: HuntResult) -> io.BytesIO:
    """
    Generate a compact 16:9 banner animated battle sequence for the /hunt command.
    Optimized for mobile Telegram with crisp fonts, zero blur, and fast snappy pacing.
    Returns in-memory BytesIO buffer of the GIF file.
    """
    fonts = _get_fonts()
    monster = result.monster
    frames: List[Image.Image] = []
    durations: List[int] = []

    rx = 260
    ry = 38
    rw = WIDTH - rx - 20
    rh = 308

    def draw_top(d, text, color=HUD_CYAN):
        t_b = fonts["sub"].getbbox(text)
        tw = t_b[2] - t_b[0]
        cx = WIDTH // 2
        _draw_diamond(d, cx - tw // 2 - 12, 22, size=3, fill=color)
        _draw_diamond(d, cx + tw // 2 + 12, 22, size=3, fill=color)
        d.text((cx - tw // 2, 15), text, font=fonts["sub"], fill=color)

    # ─────────────────────────────────────────────────────────────
    # FRAME 1: GATE ALERT (Snappy 220ms)
    # ─────────────────────────────────────────────────────────────
    f1 = _create_canvas()
    d1 = ImageDraw.Draw(f1)
    draw_top(d1, "SYSTEM COMBAT SEQUENCE", HUD_CYAN)
    _draw_left_panel(d1, fonts, hunter, monster, hp_pct=1.0)

    d1.rounded_rectangle([rx, ry, rx + rw, ry + rh], radius=10, fill=CARD_BG, outline=ALERT_RED, width=2)
    _draw_diamond(d1, rx + 24, ry + 36, size=4, fill=ALERT_RED)
    d1.text((rx + 34, ry + 28), "RED GATE DETECTED", font=fonts["header"], fill=ALERT_RED)
    d1.text((rx + 24, ry + 75), f"Hostile: {monster.name}", font=fonts["body_bold"], fill=TEXT_WHITE)
    d1.text((rx + 24, ry + 105), f"Target Rank: {monster.rank} • Lv.{monster.level}", font=fonts["body"], fill=HUD_SKY)
    d1.text((rx + 24, ry + 145), "Engaging target in combat...", font=fonts["body"], fill=TEXT_MUTED)

    d1.rounded_rectangle([rx + 24, ry + 200, rx + rw - 24, ry + 240], radius=6, fill=(35, 18, 22), outline=ALERT_RED)
    d1.text((rx + rw // 2 - 60, ry + 212), "BATTLE COMMENCED", font=fonts["small_bold"], fill=ALERT_RED)

    frames.append(f1)
    durations.append(220)

    # ─────────────────────────────────────────────────────────────
    # FRAME 2: CHARGE (Snappy 140ms)
    # ─────────────────────────────────────────────────────────────
    f2 = _create_canvas()
    d2 = ImageDraw.Draw(f2)
    draw_top(d2, "SYSTEM COMBAT SEQUENCE", HUD_CYAN)
    _draw_left_panel(d2, fonts, hunter, monster, hp_pct=1.0)

    d2.rounded_rectangle([rx, ry, rx + rw, ry + rh], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)
    d2.text((rx + 24, ry + 35), "CHARGING ATTACK...", font=fonts["header"], fill=HUD_CYAN)
    d2.line([(rx + 30, ry + 120), (rx + rw - 30, ry + 120)], fill=(0, 229, 255, 120), width=3)
    d2.line([(rx + 50, ry + 135), (rx + rw - 50, ry + 135)], fill=(56, 189, 248, 180), width=4)
    d2.text((rx + 24, ry + 180), f"Hunter Power: {hunter.power}", font=fonts["body_bold"], fill=GOLD_COLOR)

    frames.append(f2)
    durations.append(140)

    # ─────────────────────────────────────────────────────────────
    # FRAME 3: SLASH (Snappy 120ms)
    # ─────────────────────────────────────────────────────────────
    f3 = _create_canvas()
    d3 = ImageDraw.Draw(f3)
    draw_top(d3, "STRIKE DELIVERED", HUD_CYAN)
    _draw_left_panel(d3, fonts, hunter, monster, hp_pct=0.6, shake_x=-6)

    d3.rounded_rectangle([rx, ry, rx + rw, ry + rh], radius=10, fill=CARD_BG, outline=HUD_CYAN, width=1)
    d3.line([(rx + 20, ry + rh - 30), (rx + rw - 20, ry + 30)], fill=(0, 180, 255), width=10)
    d3.line([(rx + 30, ry + rh - 40), (rx + rw - 30, ry + 40)], fill=(255, 255, 255), width=4)

    # Sparks
    for sx, sy in [(rx + 120, ry + 140), (rx + 180, ry + 110), (rx + 150, ry + 170)]:
        d3.line([(sx - 6, sy), (sx + 6, sy)], fill=HUD_CYAN, width=2)
        d3.line([(sx, sy - 6), (sx, sy + 6)], fill=HUD_CYAN, width=2)

    frames.append(f3)
    durations.append(120)

    # ─────────────────────────────────────────────────────────────
    # FRAME 4: DAMAGE BURST (Snappy 200ms)
    # ─────────────────────────────────────────────────────────────
    f4 = _create_canvas()
    d4 = ImageDraw.Draw(f4)
    draw_top(d4, "DAMAGE APPLIED", GOLD_COLOR if result.critical_hit else HUD_CYAN)
    _draw_left_panel(d4, fonts, hunter, monster, hp_pct=0.0 if result.victory else 0.35, shake_x=6)

    d4.rounded_rectangle([rx, ry, rx + rw, ry + rh], radius=10, fill=CARD_BG, outline=GOLD_COLOR if result.critical_hit else HUD_CYAN, width=2)
    if result.critical_hit:
        _draw_diamond(d4, rx + 24, ry + 48, size=4, fill=GOLD_COLOR)
        d4.text((rx + 34, ry + 40), "CRITICAL STRIKE!", font=fonts["impact"], fill=GOLD_COLOR)
        d4.text((rx + 30, ry + 85), f"-{result.damage_dealt} DMG", font=fonts["big_damage"], fill=(255, 255, 255))
    else:
        _draw_diamond(d4, rx + 24, ry + 48, size=4, fill=HUD_CYAN)
        d4.text((rx + 34, ry + 40), "DIRECT HIT!", font=fonts["impact"], fill=HUD_CYAN)
        d4.text((rx + 30, ry + 85), f"-{result.damage_dealt} DMG", font=fonts["big_damage"], fill=HUD_CYAN)

    d4.text((rx + 30, ry + 160), f"Counter Taken: -{result.damage_taken} HP", font=fonts["body"], fill=ALERT_RED)

    frames.append(f4)
    durations.append(200)

    # ─────────────────────────────────────────────────────────────
    # FRAME 5: RESOLUTION (Snappy 220ms)
    # ─────────────────────────────────────────────────────────────
    f5 = _create_canvas()
    d5 = ImageDraw.Draw(f5)
    acc = GREEN_COLOR if result.victory else ALERT_RED
    draw_top(d5, "RESOLUTION", acc)
    _draw_left_panel(d5, fonts, hunter, monster, hp_pct=0.0 if result.victory else 0.2)

    d5.rounded_rectangle([rx, ry, rx + rw, ry + rh], radius=10, fill=(15, 30, 22) if result.victory else (32, 15, 18), outline=acc, width=2)
    if result.victory:
        d5.text((rx + 30, ry + 45), "TARGET ANNIHILATED", font=fonts["body_bold"], fill=GREEN_COLOR)
        d5.text((rx + 30, ry + 80), "VICTORY", font=fonts["big_damage"], fill=TEXT_WHITE)
        d5.text((rx + 30, ry + 160), "Claiming Hunter Rewards...", font=fonts["body"], fill=HUD_SKY)
    else:
        d5.text((rx + 30, ry + 45), "DUNGEON FAILED", font=fonts["body_bold"], fill=ALERT_RED)
        d5.text((rx + 30, ry + 80), "DEFEATED", font=fonts["big_damage"], fill=ALERT_RED)
        d5.text((rx + 30, ry + 160), "The beast overwhelmed you.", font=fonts["body"], fill=TEXT_MUTED)

    frames.append(f5)
    durations.append(220)

    # ─────────────────────────────────────────────────────────────
    # FRAME 6: REWARDS RECAP (Freeze for 1800ms)
    # ─────────────────────────────────────────────────────────────
    f6 = _create_canvas(color_accent=acc)
    d6 = ImageDraw.Draw(f6)
    draw_top(d6, "HUNT SUMMARY : VICTORY" if result.victory else "HUNT SUMMARY : DEFEAT", acc)
    _draw_left_panel(d6, fonts, hunter, monster, hp_pct=0.0 if result.victory else 0.2)

    d6.rounded_rectangle([rx, ry, rx + rw, ry + rh], radius=10, fill=CARD_BG, outline=acc, width=1)

    # Combat Result Row
    d6.text((rx + 16, ry + 14), f"Dealt: {result.damage_dealt} DMG", font=fonts["body_bold"], fill=TEXT_WHITE)
    if result.critical_hit:
        d6.text((rx + 140, ry + 14), "(CRIT!)", font=fonts["small_bold"], fill=GOLD_COLOR)
    d6.text((rx + rw - 130, ry + 14), f"Taken: -{result.damage_taken} HP", font=fonts["small"], fill=ALERT_RED)
    d6.line([(rx + 14, ry + 36), (rx + rw - 14, ry + 36)], fill=CARD_BORDER, width=1)

    cur_y = ry + 48
    if result.victory:
        # EXP & Gold boxes
        half_w = (rw - 38) // 2
        d6.rounded_rectangle([rx + 14, cur_y, rx + 14 + half_w, cur_y + 38], radius=6, fill=(18, 28, 48), outline=HUD_SKY)
        d6.text((rx + 24, cur_y + 11), f"EXP: +{result.xp_gained}", font=fonts["body_bold"], fill=HUD_CYAN)

        d6.rounded_rectangle([rx + 24 + half_w, cur_y, rx + 24 + half_w * 2, cur_y + 38], radius=6, fill=(28, 26, 18), outline=GOLD_COLOR)
        d6.text((rx + 34 + half_w, cur_y + 11), f"GOLD: +{result.gold_gained} G", font=fonts["body_bold"], fill=GOLD_COLOR)
        cur_y += 48

        # Loot Drop
        if result.item_drop:
            item = result.item_drop
            rc = RARITY_COLOR_MAP.get(item.rarity, TEXT_WHITE)
            d6.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 44], radius=6, fill=(22, 26, 42), outline=rc, width=1)
            d6.text((rx + 24, cur_y + 7), f"LOOT: {item.name}", font=fonts["body_bold"], fill=TEXT_WHITE)
            d6.text((rx + 24, cur_y + 25), f"• {item.rarity} ({item.stat_summary()})", font=fonts["small_bold"], fill=rc)
            cur_y += 52

        # Level Up / Rank Up
        if result.leveled_up:
            d6.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 34], radius=6, fill=(16, 40, 28), outline=GREEN_COLOR)
            d6.text((rx + 24, cur_y + 9), f"LEVEL UP! → Level {result.new_level}", font=fonts["body_bold"], fill=GREEN_COLOR)
            cur_y += 42
        elif result.ranked_up:
            rk_c = RANK_COLORS.get(result.new_rank or "E", GOLD_COLOR)
            d6.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 34], radius=6, fill=(35, 25, 15), outline=rk_c)
            d6.text((rx + 24, cur_y + 9), f"RANK UP! → {result.new_rank}-Rank", font=fonts["body_bold"], fill=rk_c)
            cur_y += 42

        # Special Event
        if result.special_event:
            ev = result.special_event.encode("ascii", "ignore").decode().strip() or result.special_event
            if len(ev) > 42:
                ev = ev[:39] + "..."
            d6.text((rx + 18, cur_y + 6), ev, font=fonts["small"], fill=HUD_SKY)

    else:
        # Defeat penalties
        d6.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 38], radius=6, fill=(35, 15, 20), outline=ALERT_RED)
        d6.text((rx + 24, cur_y + 11), f"Gold Lost: -{result.gold_lost} G", font=fonts["body_bold"], fill=ALERT_RED)
        cur_y += 48

        d6.rounded_rectangle([rx + 14, cur_y, rx + rw - 14, cur_y + 38], radius=6, fill=(18, 28, 48), outline=CARD_BORDER)
        d6.text((rx + 24, cur_y + 11), f"Consolation EXP: +{result.xp_gained}", font=fonts["body"], fill=TEXT_MUTED)
        cur_y += 48

        d6.text((rx + 18, cur_y + 10), "Rest up and challenge the gate again, Hunter.", font=fonts["small"], fill=TEXT_MUTED)

    # Footer
    f_msg = "[ The System sees all, Hunter. ]"
    fb = fonts["small"].getbbox(f_msg)
    d6.text((rx + rw // 2 - (fb[2] - fb[0]) // 2, ry + rh - 22), f_msg, font=fonts["small"], fill=HUD_SKY)

    frames.append(f6)
    durations.append(1800)

    # Quantize with dither=NONE for crystal-clear razor sharpness
    quantized: List[Image.Image] = []
    for f in frames:
        q = f.convert("P", palette=Image.Palette.ADAPTIVE, colors=256, dither=Image.Dither.NONE)
        quantized.append(q)

    buf = io.BytesIO()
    quantized[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=quantized[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    buf.seek(0)
    buf.name = "hunt.gif"
    return buf
