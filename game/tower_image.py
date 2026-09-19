"""
/* Hallmark · component: demon_castle_tower · genre: atmospheric · theme: Midnight (Abyssal Monarch) */
game/tower_image.py — Solo Leveling Demon Castle Tower Image Renderer.

Generates a Hallmark-standard 860x1000 visual Demon Castle Spire Card:
- Deep obsidian/crimson atmospheric canvas with purple demonic bloom
- Spire floor ascension gauge & progress indicator
- Floor Guardian battle card with boss tags and reward previews
- Zero missing glyphs / 0 tofu boxes
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
    INK_GOLD,
    INK_GREEN,
    INK_PURPLE,
    INK_RED,
    draw_atmospheric_canvas,
    draw_hud_corners,
    draw_diamond,
    draw_coin_icon,
)
from game.tower import TowerGuardian, MILESTONE_BOSSES
from models import Hunter

WIDTH = 860
HEIGHT = 1000

BLOOD_RED = (220, 38, 38)
DEMON_PURPLE = (168, 85, 247)


def render_tower_image(
    hunter: Hunter,
    guardian: Any,
    notice: Optional[str] = None,
    **kwargs,
) -> io.BytesIO:
    """Render a high-resolution Hallmark Demon Castle Spire Card."""
    if isinstance(guardian, dict):
        guardian = TowerGuardian(
            floor=guardian.get("floor", getattr(hunter, "tower_floor", 1)),
            name=guardian.get("boss", guardian.get("name", "Floor Guardian")),
            hp=guardian.get("hp", 1200),
            atk=guardian.get("atk", 140),
            defense=guardian.get("defense", 80),
            is_boss=guardian.get("is_boss", True),
            reward_gold=guardian.get("gold", guardian.get("reward_gold", 500)),
            reward_xp=guardian.get("xp", guardian.get("reward_xp", 250)),
        )

    img = Image.new("RGBA", (WIDTH, HEIGHT), CANVAS_TOP)

    # 1. Atmospheric Demonic Canvas with deep purple/crimson bloom
    draw_atmospheric_canvas(
        img,
        top_color=(20, 10, 22),
        bottom_color=(8, 5, 12),
        bloom_cx=WIDTH // 2,
        bloom_cy=150,
        bloom_color=(168, 85, 247, 36),
        bloom_radius=320,
        grid_spacing=60,
    )

    draw = ImageDraw.Draw(img)

    # Outer border & cybernetic HUD corners
    draw.rectangle([10, 10, WIDTH - 10, HEIGHT - 10], outline=CANVAS_BORDER, width=1)
    draw_hud_corners(draw, (10, 10, WIDTH - 10, HEIGHT - 10), color=DEMON_PURPLE, length=24, width=2)

    # Fonts
    font_eyebrow = get_font_cascade(11, is_bold=True)
    font_title = get_font_cascade(26, is_bold=True)
    font_subtitle = get_font_cascade(13, is_bold=False)
    font_section = get_font_cascade(14, is_bold=True)
    font_body_bold = get_font_cascade(14, is_bold=True)
    font_body = get_font_cascade(13, is_bold=False)
    font_badge = get_font_cascade(11, is_bold=True)
    font_large_num = get_font_cascade(36, is_bold=True)
    font_footer = get_font_cascade(11, is_bold=True)

    # ── Header ───────────────────────────────────────────────
    header_y = 28
    draw_diamond(draw, 34, header_y + 8, size=4, fill=DEMON_PURPLE)
    font_eyebrow.draw_text(
        draw, (46, header_y + 2),
        "SYSTEM INSTANT DUNGEON // DEMON CASTLE SPIRE // 100 FLOORS",
        fill=DEMON_PURPLE,
    )

    # Status Pill
    status_text = "GATE // UNSEALED"
    draw.rounded_rectangle([WIDTH - 170, header_y, WIDTH - 30, header_y + 22], radius=4, fill=SURFACE_ELEVATED, outline=BLOOD_RED, width=1)
    draw_diamond(draw, WIDTH - 156, header_y + 11, size=3, fill=BLOOD_RED)
    font_badge.draw_text(draw, (WIDTH - 142, header_y + 5), status_text, fill=INK_PRIMARY)

    font_title.draw_text(draw, (34, header_y + 26), "DEMON CASTLE // 악마성 100층 시험", fill=INK_PRIMARY)
    font_subtitle.draw_text(
        draw, (34, header_y + 64),
        "Conquer each floor guardian to climb the tower and challenge Demon King Baran.",
        fill=INK_SECONDARY,
    )

    draw.line([(34, header_y + 92), (WIDTH - 34, header_y + 92)], fill=SURFACE_BORDER, width=1)
    draw.line([(34, header_y + 92), (220, header_y + 92)], fill=DEMON_PURPLE, width=2)

    # ── Hunter Spire Overview & Keys ──────────────────────────
    info_y = 132
    info_h = 74
    draw.rounded_rectangle([34, info_y, WIDTH - 34, info_y + info_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)

    h_name = hunter.display_full_name if hasattr(hunter, "display_full_name") and hunter.display_full_name else hunter.hunter_name
    font_body_bold.draw_text(draw, (50, info_y + 14), f"CHALLENGER: {h_name} [Rank {hunter.rank}]", fill=INK_PRIMARY)
    font_body.draw_text(draw, (50, info_y + 40), f"Combat Power: {hunter.power} ┊ Highest Cleared: Floor {hunter.tower_highest_floor}", fill=INK_SECONDARY)

    # Keys Badge (Right side)
    key_badge_x = WIDTH - 200
    draw.rounded_rectangle([key_badge_x, info_y + 16, WIDTH - 50, info_y + 56], radius=6, fill=SURFACE_ELEVATED, outline=INK_GOLD, width=1)
    draw_diamond(draw, key_badge_x + 14, info_y + 36, size=4, fill=INK_GOLD)
    font_body_bold.draw_text(draw, (key_badge_x + 28, info_y + 26), f"KEYS: {hunter.tower_keys} / 3", fill=INK_GOLD)

    # ── Notice Banner ─────────────────────────────────────────
    curr_y = info_y + info_h + 14
    if notice:
        n_col = INK_GREEN if "CONQUERED" in notice or "VICTORY" in notice or "UNLOCKED" in notice else BLOOD_RED
        draw.rounded_rectangle([34, curr_y, WIDTH - 34, curr_y + 40], radius=6, fill=SURFACE_ELEVATED, outline=n_col, width=1)
        draw_diamond(draw, 50, curr_y + 20, size=4, fill=n_col)
        clean_notice = notice.replace("⚔️", "").replace("✨", "").replace("☠️", "").replace("🎉", "").strip()
        font_body_bold.draw_text(draw, (64, curr_y + 12), clean_notice, fill=n_col, max_w=WIDTH - 120)
        curr_y += 54

    # ── Floor Ascension Progress Panel ────────────────────────
    prog_y = curr_y
    prog_h = 130
    draw.rounded_rectangle([34, prog_y, WIDTH - 34, prog_y + prog_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)

    draw_diamond(draw, 50, prog_y + 18, size=4, fill=DEMON_PURPLE)
    font_section.draw_text(draw, (64, prog_y + 11), "CURRENT ASCENSION MILESTONE", fill=INK_PRIMARY)
    draw.line([(50, prog_y + 36), (WIDTH - 50, prog_y + 36)], fill=SURFACE_BORDER, width=1)

    # Floor Number Display
    font_large_num.draw_text(draw, (50, prog_y + 50), f"FLOOR {guardian.floor}", fill=DEMON_PURPLE)
    font_body_bold.draw_text(draw, (230, prog_y + 60), "/ 100 FLOORS CONQUERED", fill=INK_SECONDARY)

    # Progress bar
    bar_w = WIDTH - 100
    bar_h = 16
    draw.rounded_rectangle([50, prog_y + 96, 50 + bar_w, prog_y + 96 + bar_h], radius=4, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER)
    fill_ratio = min(1.0, max(0.01, guardian.floor / 100.0))
    fill_w = int(bar_w * fill_ratio)
    draw.rounded_rectangle([50, prog_y + 96, 50 + fill_w, prog_y + 96 + bar_h], radius=4, fill=DEMON_PURPLE)

    # ── Active Floor Guardian Chamber ─────────────────────────
    guard_y = prog_y + prog_h + 16
    guard_h = 290
    draw.rounded_rectangle([34, guard_y, WIDTH - 34, guard_y + guard_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
    draw_hud_corners(draw, (34, guard_y, WIDTH - 34, guard_y + guard_h), color=BLOOD_RED if guardian.is_boss else DEMON_PURPLE, length=16, width=1)

    tag_col = BLOOD_RED if guardian.is_boss else DEMON_PURPLE
    tag_label = "🔥 DEMON MONARCH BOSS" if guardian.is_boss else "👹 FLOOR GUARDIAN"
    draw_diamond(draw, 50, guard_y + 18, size=4, fill=tag_col)
    font_section.draw_text(draw, (64, guard_y + 11), f"CHAMBER GUARDIAN: {tag_label}", fill=tag_col)
    draw.line([(50, guard_y + 36), (WIDTH - 50, guard_y + 36)], fill=SURFACE_BORDER, width=1)

    # Guardian Details Box
    g_box_y = guard_y + 50
    draw.rounded_rectangle([50, g_box_y, WIDTH - 50, g_box_y + 120], radius=6, fill=SURFACE_ELEVATED, outline=tag_col, width=1)

    font_title.draw_text(draw, (70, g_box_y + 14), guardian.name, fill=INK_PRIMARY)
    font_body.draw_text(draw, (70, g_box_y + 52), f"Health: {guardian.hp} HP ┊ Attack: {guardian.atk} ATK ┊ Defense: {guardian.defense} DEF", fill=INK_SECONDARY)

    # Health Bar for guardian
    gh_bar_w = WIDTH - 140
    draw.rounded_rectangle([70, g_box_y + 80, 70 + gh_bar_w, g_box_y + 94], radius=3, fill=SURFACE_BASE, outline=SURFACE_BORDER)
    draw.rounded_rectangle([70, g_box_y + 80, 70 + gh_bar_w, g_box_y + 94], radius=3, fill=BLOOD_RED)

    # Floor Rewards Pill Box
    rew_y = g_box_y + 138
    font_body_bold.draw_text(draw, (50, rew_y), "CLEAR REWARDS:", fill=INK_GOLD)

    draw.rounded_rectangle([190, rew_y - 4, 340, rew_y + 26], radius=4, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER)
    draw_coin_icon(draw, 206, rew_y + 11, r=6)
    font_body_bold.draw_text(draw, (222, rew_y + 2), f"{guardian.reward_gold:,} Gold", fill=INK_GOLD)

    draw.rounded_rectangle([354, rew_y - 4, 490, rew_y + 26], radius=4, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER)
    draw_diamond(draw, 370, rew_y + 11, size=4, fill=INK_CYAN)
    font_body_bold.draw_text(draw, (386, rew_y + 2), f"{guardian.reward_xp:,} XP", fill=INK_CYAN)

    if guardian.is_boss:
        draw.rounded_rectangle([504, rew_y - 4, 760, rew_y + 26], radius=4, fill=SURFACE_ELEVATED, outline=BLOOD_RED)
        draw_diamond(draw, 520, rew_y + 11, size=4, fill=BLOOD_RED)
        font_body_bold.draw_text(draw, (536, rew_y + 2), "★ EXCLUSIVE TITLE & GEAR", fill=BLOOD_RED)

    # ── Milestone Boss Road Map ───────────────────────────────
    map_y = guard_y + guard_h + 14
    map_h = 160
    draw.rounded_rectangle([34, map_y, WIDTH - 34, map_y + map_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)

    draw_diamond(draw, 50, map_y + 18, size=4, fill=INK_GOLD)
    font_section.draw_text(draw, (64, map_y + 11), "DEMON CASTLE MILESTONE PINNACLES", fill=INK_PRIMARY)
    draw.line([(50, map_y + 36), (WIDTH - 50, map_y + 36)], fill=SURFACE_BORDER, width=1)

    milestones = [
        ("FL 10", "Cerberus", "Title: Hellhound Vanquisher"),
        ("FL 25", "Knight Cmdr", "Rare Artifact + 4,000 G"),
        ("FL 50", "Volcan", "Title: Flame Conqueror"),
        ("FL 75", "Metus", "Legendary Soul + 30,000 G"),
        ("FL 100", "King Baran", "Mythic Baran Blade"),
    ]

    mx = 50
    m_box_w = (WIDTH - 100 - (len(milestones) - 1) * 10) // len(milestones)
    for fl_tag, boss, loot in milestones:
        is_cleared = hunter.tower_highest_floor >= int(fl_tag.replace("FL ", ""))
        m_border = INK_GREEN if is_cleared else SURFACE_BORDER
        draw.rounded_rectangle([mx, map_y + 48, mx + m_box_w, map_y + 140], radius=4, fill=SURFACE_ELEVATED, outline=m_border, width=1)
        font_body_bold.draw_text(draw, (mx + 10, map_y + 56), fl_tag, fill=INK_GOLD if not is_cleared else INK_GREEN)
        font_body_bold.draw_text(draw, (mx + 10, map_y + 78), boss, fill=INK_PRIMARY)
        font_badge.draw_text(draw, (mx + 10, map_y + 102), loot, fill=INK_SECONDARY, max_w=m_box_w - 20)
        mx += m_box_w + 10

    # ── Footer ────────────────────────────────────────────────
    footer_y = HEIGHT - 46
    draw.line([(34, footer_y), (WIDTH - 34, footer_y)], fill=SURFACE_BORDER, width=1)
    quote = "「 ONLY THOSE WHO CONQUER THE DEMON CASTLE MAY CLAIM THE THRONE 」"
    font_footer.draw_text(draw, (WIDTH // 2 - 225, footer_y + 12), quote, fill=DEMON_PURPLE)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
