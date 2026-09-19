"""
/* Hallmark · component: duel_resolution_card · genre: atmospheric · theme: Midnight (Abyssal Monarch) */
game/duel_image.py — Solo Leveling Duel Combat Resolution Image Card Renderer.

Generates a stylized, high-resolution 920 × 580 px image card representing
a PvP duel between two hunters.
Features:
- Dual fighter columns (Challenger vs Opponent)
- Real player profile pictures (or rank-colored silhouetted fallbacks)
- Multi-font unicode fallback cascade (Korean, CJK, fancy fonts, emojis)
- Central glowing "VS" clash emblem with vertical energy beam
- Prominent "WON / VICTORY" and "LOST / DEFEATED" outcome banners under each respective fighter
- Damage dealt, crits, equipment summary, and reward breakdowns
- Native vector geometric icons (Crown, Skull, Lightning, Diamond, Shields) to ensure 0 tofu boxes on all platforms.
"""

from __future__ import annotations

import io
import math
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import RANKS
from game.font_manager import get_font_cascade, clean_and_normalize_name, load_font
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
    INK_RED,
    INK_RED_DARK,
    INK_GREEN,
    INK_GREEN_DARK,
    RANK_COLORS,
    draw_atmospheric_canvas,
    draw_hud_corners,
    draw_diamond,
    draw_lightning_icon,
    draw_crown_icon,
    draw_skull_icon,
    draw_swords_icon,
    draw_rounded_gauge,
)
from models import Hunter, Inventory, Item, DuelResult

# Dimensions
WIDTH = 920
HEIGHT = 580

HUD_CYAN = INK_CYAN
HUD_BLUE = (37, 99, 235)
HUD_SKY = INK_SKY
ALERT_RED = INK_RED
ALERT_DARK_RED = INK_RED_DARK
GOLD_COLOR = INK_GOLD
GREEN_COLOR = INK_GREEN
GREEN_DARK = INK_GREEN_DARK
TEXT_WHITE = INK_PRIMARY
TEXT_MUTED = INK_SECONDARY
TEXT_DIM = INK_MUTED
CARD_BG = SURFACE_BASE
CARD_BORDER = SURFACE_BORDER


# ── Vector Icon Helpers (Guaranteed 0 Tofu Boxes) ─────────────────────────────

def _draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 5, fill=HUD_CYAN) -> None:
    """Draw a crisp vector diamond accent."""
    draw.polygon([(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)], fill=fill)


def _draw_lightning(draw: ImageDraw.ImageDraw, cx: int, cy: int, fill=GOLD_COLOR, scale: float = 1.0) -> None:
    """Draw a crisp vector lightning bolt."""
    pts = [
        (cx + int(2 * scale), cy - int(8 * scale)),
        (cx - int(5 * scale), cy - int(1 * scale)),
        (cx - int(1 * scale), cy - int(1 * scale)),
        (cx - int(3 * scale), cy + int(8 * scale)),
        (cx + int(5 * scale), cy + int(1 * scale)),
        (cx + int(1 * scale), cy + int(1 * scale)),
    ]
    draw.polygon(pts, fill=fill)


def _draw_crown(draw: ImageDraw.ImageDraw, cx: int, cy: int, fill=GOLD_COLOR, scale: float = 1.0) -> None:
    """Draw a royal victor crown vector."""
    w = int(14 * scale)
    h = int(10 * scale)
    pts = [
        (cx - w, cy - int(h * 0.6)),
        (cx - int(w * 0.45), cy),
        (cx, cy - h),
        (cx + int(w * 0.45), cy),
        (cx + w, cy - int(h * 0.6)),
        (cx + int(w * 0.75), cy + int(h * 0.7)),
        (cx - int(w * 0.75), cy + int(h * 0.7)),
    ]
    draw.polygon(pts, fill=fill)
    r = max(1, int(2 * scale))
    draw.ellipse([cx - w - r, cy - int(h * 0.6) - r, cx - w + r, cy - int(h * 0.6) + r], fill=fill)
    draw.ellipse([cx - r, cy - h - r, cx + r, cy - h + r], fill=fill)
    draw.ellipse([cx + w - r, cy - int(h * 0.6) - r, cx + w + r, cy - int(h * 0.6) + r], fill=fill)


def _draw_skull(draw: ImageDraw.ImageDraw, cx: int, cy: int, fill=(254, 202, 202), bg=ALERT_DARK_RED, scale: float = 1.0) -> None:
    """Draw a defeat skull vector."""
    rw = int(9 * scale)
    rh = int(9 * scale)
    draw.ellipse([cx - rw, cy - rh, cx + rw, cy], fill=fill)
    jw = int(5 * scale)
    jh = int(8 * scale)
    draw.rounded_rectangle([cx - jw, cy - int(2 * scale), cx + jw, cy + jh], radius=max(1, int(2 * scale)), fill=fill)
    # Eye sockets
    er = max(1, int(2 * scale))
    draw.ellipse([cx - int(4 * scale) - er, cy - int(3 * scale) - er, cx - int(4 * scale) + er, cy - int(3 * scale) + er], fill=bg)
    draw.ellipse([cx + int(4 * scale) - er, cy - int(3 * scale) - er, cx + int(4 * scale) + er, cy - int(3 * scale) + er], fill=bg)


def _draw_swords(draw: ImageDraw.ImageDraw, cx: int, cy: int, fill=HUD_CYAN) -> None:
    """Draw crossed blades vector."""
    # Blade 1
    draw.line([(cx - 7, cy - 7), (cx + 7, cy + 7)], fill=fill, width=2)
    draw.line([(cx - 6, cy - 2), (cx - 2, cy - 6)], fill=fill, width=2)
    # Blade 2
    draw.line([(cx + 7, cy - 7), (cx - 7, cy + 7)], fill=fill, width=2)
    draw.line([(cx + 6, cy - 2), (cx + 2, cy - 6)], fill=fill, width=2)


def _draw_avatar(
    base: Image.Image,
    pfp_input: Optional[Image.Image | bytes],
    cx: int,
    cy: int,
    size: int = 90,
    rank: str = "E",
) -> None:
    """Draw circular profile avatar with anti-aliased rank-colored ring."""
    x = cx - size // 2
    y = cy - size // 2

    mask_scale = 4
    high_size = size * mask_scale
    mask_high = Image.new("L", (high_size, high_size), 0)
    m_draw = ImageDraw.Draw(mask_high)
    m_draw.ellipse([0, 0, high_size - 1, high_size - 1], fill=255)
    mask = mask_high.resize((size, size), Image.Resampling.LANCZOS)

    pfp_img: Optional[Image.Image] = None
    if isinstance(pfp_input, bytes):
        try:
            pfp_img = Image.open(io.BytesIO(pfp_input)).convert("RGBA")
        except Exception:
            pfp_img = None
    elif isinstance(pfp_input, Image.Image):
        pfp_img = pfp_input.convert("RGBA")

    if pfp_img:
        try:
            w, h = pfp_img.size
            dim = min(w, h)
            left = (w - dim) // 2
            top = (h - dim) // 2
            cropped = pfp_img.crop((left, top, left + dim, top + dim))
            resized = cropped.resize((size, size), Image.Resampling.LANCZOS)

            layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            layer.paste(resized, (0, 0), mask=mask)
            base.alpha_composite(layer, (x, y))
        except Exception:
            pfp_img = None

    if not pfp_img:
        bg = Image.new("RGBA", (size, size), (15, 23, 42, 255))
        d = ImageDraw.Draw(bg)
        c = size // 2
        d.ellipse([c - 16, c - 24, c + 16, c + 8], fill=(56, 189, 248, 220))
        d.chord([c - 30, c + 10, c + 30, c + 50], start=0, end=180, fill=(30, 58, 102, 240))
        layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        layer.paste(bg, (0, 0), mask=mask)
        base.alpha_composite(layer, (x, y))

    ring_color = RANK_COLORS.get(rank, HUD_CYAN)
    draw = ImageDraw.Draw(base)
    draw.ellipse([x - 3, y - 3, x + size + 3, y + size + 3], outline=(ring_color[0], ring_color[1], ring_color[2], 70), width=1)
    draw.ellipse([x - 1, y - 1, x + size + 1, y + size + 1], outline=ring_color, width=2)


def _draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    current: int,
    maximum: int,
    fill_color: Tuple[int, int, int],
    bg_color: Tuple[int, int, int] = (20, 30, 50),
) -> None:
    """Draw smooth rounded HP bar."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=bg_color)
    if maximum > 0 and current > 0:
        pct = min(1.0, max(0.0, current / maximum))
        fill_w = max(h, int(w * pct))
        draw.rounded_rectangle([x, y, x + fill_w, y + h], radius=h // 2, fill=fill_color)


def render_duel_card(
    result: Any,
    *args,
    challenger_pfp: Optional[Image.Image | bytes] = None,
    opponent_pfp: Optional[Image.Image | bytes] = None,
    challenger_inv: Optional[Inventory] = None,
    opponent_inv: Optional[Inventory] = None,
    **kwargs,
) -> io.BytesIO:
    """
    Render a high-definition 920 × 580 px Duel Combat Resolution Card.
    Returns BytesIO containing PNG bytes.
    """
    if not isinstance(result, DuelResult):
        for a in args:
            if isinstance(a, DuelResult):
                result = a
                break
    # 1. Base Canvas & Atmospheric Radial Bloom
    base = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    draw_atmospheric_canvas(
        base,
        top_color=CANVAS_TOP,
        bottom_color=CANVAS_BOTTOM,
        bloom_cx=WIDTH // 2,
        bloom_cy=HEIGHT // 2,
        bloom_color=(0, 229, 255, 24),
        bloom_radius=280,
    )
    draw = ImageDraw.Draw(base)

    # 2. Top Header Bar
    font_header = load_font(["segoeuib.ttf", "arialbd.ttf"], 13)
    font_sub = load_font(["segoeui.ttf", "arial.ttf"], 11)
    font_bold = load_font(["segoeuib.ttf", "arialbd.ttf"], 13)
    font_stat_val = load_font(["segoeuib.ttf", "arialbd.ttf"], 14)
    font_vs = load_font(["impact.ttf", "segoeuib.ttf", "arialbd.ttf"], 36)
    font_outcome_title = load_font(["segoeuib.ttf", "arialbd.ttf", "impact.ttf"], 22)
    font_outcome_sub = load_font(["segoeuib.ttf", "arialbd.ttf"], 12)

    # Top border line with cyan glow
    draw.line([(30, 45), (WIDTH - 30, 45)], fill=HUD_CYAN, width=2)
    draw.polygon([(25, 45), (32, 41), (32, 49)], fill=HUD_CYAN)
    draw.polygon([(WIDTH - 25, 45), (WIDTH - 32, 41), (WIDTH - 32, 49)], fill=HUD_CYAN)

    header_text = "COMBAT ARENA // 헌터 협회 대련 [PVP RESOLUTION]"
    draw.text((WIDTH // 2, 25), header_text, font=font_header, fill=HUD_CYAN, anchor="mm")
    _draw_swords(draw, WIDTH // 2 - 250, 25, fill=HUD_CYAN)
    _draw_swords(draw, WIDTH // 2 + 250, 25, fill=HUD_CYAN)

    # 3. Fighter Columns Dimensions
    col_w = 380
    col_h = 475
    c_x1 = 30
    c_y1 = 60
    c_x2 = c_x1 + col_w
    c_y2 = c_y1 + col_h

    o_x1 = WIDTH - 30 - col_w
    o_y1 = 60
    o_x2 = o_x1 + col_w
    o_y2 = o_y1 + col_h

    def render_fighter_panel(
        hunter: Hunter,
        inv: Optional[Inventory],
        pfp: Optional[Image.Image | bytes],
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        is_winner: bool,
        damage_dealt: int,
        crits: int,
        hp_left: int,
        max_hp: int,
        xp_gain: int,
        gold_gain: int,
        leveled_up: bool,
        new_level: Optional[int],
    ):
        cx = (x1 + x2) // 2

        # Border & background tint
        border_col = (50, 180, 100) if is_winner else (180, 45, 60)
        panel_outline = (border_col[0], border_col[1], border_col[2], 180)
        panel_fill = (14, 24, 44, 235) if is_winner else (24, 16, 28, 235)

        # Draw panel container
        draw.rounded_rectangle([x1, y1, x2, y2], radius=12, fill=panel_fill, outline=panel_outline, width=2)

        # Top corner accents
        acc_len = 16
        draw.line([(x1 + 4, y1 + 4), (x1 + 4 + acc_len, y1 + 4)], fill=border_col, width=2)
        draw.line([(x1 + 4, y1 + 4), (x1 + 4, y1 + 4 + acc_len)], fill=border_col, width=2)
        draw.line([(x2 - 4, y1 + 4), (x2 - 4 - acc_len, y1 + 4)], fill=border_col, width=2)
        draw.line([(x2 - 4, y1 + 4), (x2 - 4, y1 + 4 + acc_len)], fill=border_col, width=2)

        # Avatar
        avatar_cy = y1 + 55
        _draw_avatar(base, pfp, cx, avatar_cy, size=84, rank=hunter.rank)

        # Hunter Name (Using Universal FontCascade for zero tofu boxes)
        cascade_name = get_font_cascade(size=19, is_bold=True)
        raw_name = hunter.display_full_name
        bb = cascade_name.getbbox(raw_name)
        nw = bb[2] - bb[0]
        name_x = cx - min(nw, 320) // 2
        name_y = y1 + 104
        cascade_name.draw_text(draw, (name_x, name_y), raw_name, fill=TEXT_WHITE, max_w=320)

        # Badges Row: [ RANK X ] • Lv. XX • CP XXX
        rank_col = RANK_COLORS.get(hunter.rank, HUD_CYAN)
        badges_y = y1 + 132

        # Rank Pill
        rank_text = f"RANK {hunter.rank}"
        f_badge = load_font(["segoeuib.ttf", "arialbd.ttf"], 11)
        r_bb = f_badge.getbbox(rank_text)
        r_w = (r_bb[2] - r_bb[0]) + 16
        r_x = cx - 75 - r_w // 2
        draw.rounded_rectangle([r_x, badges_y, r_x + r_w, badges_y + 20], radius=10, fill=(rank_col[0] // 4, rank_col[1] // 4, rank_col[2] // 4), outline=rank_col, width=1)
        draw.text((r_x + r_w // 2, badges_y + 10), rank_text, font=f_badge, fill=rank_col, anchor="mm")

        # Level Pill
        lvl_text = f"Lv. {hunter.level}"
        l_x = cx - 20
        draw.rounded_rectangle([l_x, badges_y, l_x + 60, badges_y + 20], radius=10, fill=(18, 32, 58), outline=HUD_SKY, width=1)
        draw.text((l_x + 30, badges_y + 10), lvl_text, font=f_badge, fill=TEXT_WHITE, anchor="mm")

        # CP Pill (with vector lightning)
        cp_text = f"{hunter.combat_power} CP"
        cp_x = cx + 48
        draw.rounded_rectangle([cp_x, badges_y, cp_x + 85, badges_y + 20], radius=10, fill=(35, 25, 10), outline=GOLD_COLOR, width=1)
        _draw_lightning(draw, cp_x + 12, badges_y + 10, fill=GOLD_COLOR, scale=0.7)
        draw.text((cp_x + 48, badges_y + 10), cp_text, font=f_badge, fill=GOLD_COLOR, anchor="mm")

        # HP Bar
        hp_y = y1 + 164
        hp_bar_w = 330
        hp_bar_x = cx - hp_bar_w // 2
        hp_col = GREEN_COLOR if hp_left > (max_hp * 0.3) else ALERT_RED
        _draw_progress_bar(draw, hp_bar_x, hp_y, hp_bar_w, 10, hp_left, max_hp, fill_color=hp_col, bg_color=(25, 35, 55))

        # HP Text
        hp_label = f"HP: {hp_left} / {max_hp}"
        draw.text((cx, hp_y + 18), hp_label, font=font_sub, fill=TEXT_MUTED, anchor="mm")

        # Equipment Info Row
        eq_y = y1 + 198
        draw.rounded_rectangle([x1 + 16, eq_y, x2 - 16, eq_y + 36], radius=6, fill=(18, 28, 50, 220), outline=CARD_BORDER, width=1)

        weap = inv.get_equipped("weapon") if inv else None
        arm = inv.get_equipped("armor") if inv else None
        weap_name = weap.name if weap else "Standard Dagger"
        arm_name = arm.name if arm else "Hunter Uniform"

        f_eq = load_font(["segoeui.ttf", "arial.ttf"], 11)
        f_eq_bold = load_font(["segoeuib.ttf", "arialbd.ttf"], 10)

        # Weapon line
        draw.rounded_rectangle([x1 + 22, eq_y + 5, x1 + 68, eq_y + 17], radius=3, fill=(28, 44, 75))
        draw.text((x1 + 45, eq_y + 11), "WEAPON", font=f_eq_bold, fill=HUD_SKY, anchor="mm")
        draw.text((x1 + 74, eq_y + 11), weap_name[:20], font=f_eq, fill=TEXT_WHITE, anchor="lm")

        # Armor line
        draw.rounded_rectangle([x1 + 22, eq_y + 19, x1 + 68, eq_y + 31], radius=3, fill=(28, 44, 75))
        draw.text((x1 + 45, eq_y + 25), "ARMOR", font=f_eq_bold, fill=TEXT_MUTED, anchor="mm")
        draw.text((x1 + 74, eq_y + 25), arm_name[:20], font=f_eq, fill=TEXT_MUTED, anchor="lm")

        # Record stat
        draw.text((x2 - 25, eq_y + 18), f"Record: {hunter.duel_wins}W - {hunter.duel_losses}L", font=f_eq, fill=HUD_CYAN, anchor="rm")

        # Combat Performance Box
        perf_y = y1 + 242
        draw.rounded_rectangle([x1 + 16, perf_y, x2 - 16, perf_y + 44], radius=6, fill=(15, 22, 40), outline=(25, 45, 80), width=1)

        # Damage Dealt
        draw.text((x1 + 35, perf_y + 12), "DAMAGE DEALT", font=font_sub, fill=TEXT_MUTED)
        _draw_diamond(draw, x1 + 28, perf_y + 28, size=4, fill=ALERT_RED)
        draw.text((x1 + 38, perf_y + 28), f"{damage_dealt:,} DMG", font=font_stat_val, fill=TEXT_WHITE)

        # Crits Landed
        draw.text((cx + 15, perf_y + 12), "CRITICAL STRIKES", font=font_sub, fill=TEXT_MUTED)
        crit_fill = GOLD_COLOR if crits > 0 else TEXT_MUTED
        _draw_lightning(draw, cx + 8, perf_y + 28, fill=crit_fill, scale=0.7)
        draw.text((cx + 18, perf_y + 28), f"{crits} Hits", font=font_stat_val, fill=crit_fill)

        # ── PROMINENT OUTCOME BANNER (WON / LOST) ──
        out_y1 = y1 + 296
        out_y2 = y2 - 16

        if is_winner:
            # Winner Banner: Glowing Emerald & Gold
            draw.rounded_rectangle([x1 + 16, out_y1, x2 - 16, out_y2], radius=10, fill=GREEN_DARK, outline=GREEN_COLOR, width=2)
            draw.rounded_rectangle([x1 + 18, out_y1 + 2, x2 - 18, out_y2 - 2], radius=8, outline=(74, 222, 128, 90), width=1)

            # Crown icon + Text
            draw.text((cx, out_y1 + 24), "VICTORY  •  WON", font=font_outcome_title, fill=GOLD_COLOR, anchor="mm")
            _draw_crown(draw, cx - 120, out_y1 + 24, fill=GOLD_COLOR, scale=1.0)
            _draw_crown(draw, cx + 120, out_y1 + 24, fill=GOLD_COLOR, scale=1.0)

            draw.text((cx, out_y1 + 50), "SURVIVED THE ARENA CLASH", font=font_outcome_sub, fill=GREEN_COLOR, anchor="mm")

            # Reward spoils
            rew_str = f"SPOILS: +{xp_gain} XP  |  +{gold_gain} Gold"
            draw.text((cx, out_y1 + 75), rew_str, font=font_bold, fill=TEXT_WHITE, anchor="mm")

            if leveled_up and new_level:
                draw.text((cx, out_y1 + 98), f"LEVEL UP! Advanced to Lv. {new_level}!", font=font_bold, fill=HUD_CYAN, anchor="mm")
            else:
                draw.text((cx, out_y1 + 98), f"Total Arena Victories: {hunter.duel_wins}", font=font_sub, fill=TEXT_MUTED, anchor="mm")
        else:
            # Loser Banner: Crimson & Dark Charcoal
            draw.rounded_rectangle([x1 + 16, out_y1, x2 - 16, out_y2], radius=10, fill=ALERT_DARK_RED, outline=ALERT_RED, width=2)
            draw.rounded_rectangle([x1 + 18, out_y1 + 2, x2 - 18, out_y2 - 2], radius=8, outline=(248, 113, 113, 80), width=1)

            # Skull icon + Text
            draw.text((cx, out_y1 + 24), "DEFEATED  •  LOST", font=font_outcome_title, fill=(254, 202, 202), anchor="mm")
            _draw_skull(draw, cx - 125, out_y1 + 24, fill=(254, 202, 202), bg=ALERT_DARK_RED, scale=1.0)
            _draw_skull(draw, cx + 125, out_y1 + 24, fill=(254, 202, 202), bg=ALERT_DARK_RED, scale=1.0)

            draw.text((cx, out_y1 + 50), "KNOCKED DOWN IN COMBAT", font=font_outcome_sub, fill=ALERT_RED, anchor="mm")

            # Consolation XP
            rew_str = f"CONSOLATION: +{xp_gain} XP (Combat Training)"
            draw.text((cx, out_y1 + 75), rew_str, font=font_bold, fill=TEXT_WHITE, anchor="mm")
            draw.text((cx, out_y1 + 98), "Train harder to challenge again!", font=font_sub, fill=TEXT_MUTED, anchor="mm")

    # Render Challenger (Left)
    c_is_winner = result.winner_is_challenger
    render_fighter_panel(
        hunter=result.challenger,
        inv=challenger_inv,
        pfp=challenger_pfp,
        x1=c_x1,
        y1=c_y1,
        x2=c_x2,
        y2=c_y2,
        is_winner=c_is_winner,
        damage_dealt=result.challenger_damage_dealt,
        crits=result.challenger_crits,
        hp_left=result.challenger_hp_left,
        max_hp=result.challenger_max_hp,
        xp_gain=result.winner_xp_gained if c_is_winner else result.loser_xp_gained,
        gold_gain=result.winner_gold_gained if c_is_winner else 0,
        leveled_up=result.winner_leveled_up if c_is_winner else False,
        new_level=result.winner_new_level if c_is_winner else None,
    )

    # Render Opponent (Right)
    o_is_winner = not result.winner_is_challenger
    render_fighter_panel(
        hunter=result.opponent,
        inv=opponent_inv,
        pfp=opponent_pfp,
        x1=o_x1,
        y1=o_y1,
        x2=o_x2,
        y2=o_y2,
        is_winner=o_is_winner,
        damage_dealt=result.opponent_damage_dealt,
        crits=result.opponent_crits,
        hp_left=result.opponent_hp_left,
        max_hp=result.opponent_max_hp,
        xp_gain=result.winner_xp_gained if o_is_winner else result.loser_xp_gained,
        gold_gain=result.winner_gold_gained if o_is_winner else 0,
        leveled_up=result.winner_leveled_up if o_is_winner else False,
        new_level=result.winner_new_level if o_is_winner else None,
    )

    # 4. Central "VS" Clash Emblem
    center_x = WIDTH // 2
    center_y = HEIGHT // 2 - 25

    # Vertical light ray
    draw.line([(center_x, 65), (center_x, HEIGHT - 55)], fill=(0, 229, 255, 60), width=1)
    draw.line([(center_x - 1, 100), (center_x - 1, HEIGHT - 90)], fill=(0, 229, 255, 30), width=3)

    # Radiant circle behind VS
    vs_r = 44
    draw.ellipse([center_x - vs_r - 6, center_y - vs_r - 6, center_x + vs_r + 6, center_y + vs_r + 6], fill=(0, 150, 255, 30))
    draw.ellipse([center_x - vs_r - 2, center_y - vs_r - 2, center_x + vs_r + 2, center_y + vs_r + 2], fill=(10, 18, 38, 255), outline=HUD_CYAN, width=2)
    draw.ellipse([center_x - vs_r + 4, center_y - vs_r + 4, center_x + vs_r - 4, center_y + vs_r - 4], outline=(0, 229, 255, 90), width=1)

    # VS Text
    draw.text((center_x, center_y - 2), "VS", font=font_vs, fill=TEXT_WHITE, anchor="mm")

    # Underneath VS
    draw.rounded_rectangle([center_x - 42, center_y + 55, center_x + 42, center_y + 75], radius=6, fill=(16, 26, 50), outline=CARD_BORDER, width=1)
    draw.text((center_x, center_y + 65), f"ROUND {result.total_rounds}", font=font_sub, fill=HUD_SKY, anchor="mm")

    # 5. Bottom System Footer
    footer_text = "SOLO LEVELING SYSTEM • OFFICIAL PVP DUEL ARENA • SHADOW PROTOCOL ACTIVATED"
    draw.text((WIDTH // 2, HEIGHT - 20), footer_text, font=font_sub, fill=TEXT_DIM, anchor="mm")

    # Output to BytesIO
    buf = io.BytesIO()
    buf.name = "duel_result.png"
    base.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
