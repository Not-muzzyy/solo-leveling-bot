"""
game/forge_image.py — Solo Leveling Blacksmith Forge Image Renderer.

Generates an atmospheric Hallmark-standard RPG Blacksmith Forge Card:
- Deep obsidian canvas with glowing amber/orange atmospheric forge bloom
- High-contrast multi-font cascade (0 tofu boxes)
- Precision vector graphics: Anvil silhouette, diamond accents, HUD brackets
- Visual enhancement gauge with success probability and stat delta previews
"""

from __future__ import annotations

import io
from typing import Optional
from PIL import Image, ImageDraw

from config import RARITIES
from game.font_manager import get_font_cascade
from game.design_tokens import (
    CANVAS_TOP,
    CANVAS_BOTTOM,
    CANVAS_BORDER,
    SURFACE_BASE,
    SURFACE_ELEVATED,
    SURFACE_BORDER,
    SURFACE_BORDER_LIGHT,
    INK_PRIMARY,
    INK_SECONDARY,
    INK_MUTED,
    INK_CYAN,
    INK_SKY,
    INK_GOLD,
    INK_GREEN,
    INK_RED,
    RANK_COLORS,
    RARITY_COLORS,
    draw_atmospheric_canvas,
    draw_hud_corners,
    draw_diamond,
    draw_coin_icon,
)
from models import Hunter, Inventory, Item

WIDTH = 860
HEIGHT = 980

AMBER_GLOW = (245, 158, 11)
FIRE_ORANGE = (234, 88, 12)


def _draw_anvil_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 24, fill=AMBER_GLOW) -> None:
    """Draw vector blacksmith anvil silhouette."""
    # Top horn & face
    draw.polygon([
        (cx - size, cy - size // 3),
        (cx + size, cy - size // 3),
        (cx + size - 6, cy + size // 6),
        (cx - size + 8, cy + size // 6),
    ], fill=fill)
    # Waist & base
    draw.rectangle([cx - size // 4, cy + size // 6, cx + size // 4, cy + size // 2], fill=fill)
    draw.polygon([
        (cx - size + 4, cy + size),
        (cx + size - 4, cy + size),
        (cx + size // 3, cy + size // 2),
        (cx - size // 3, cy + size // 2),
    ], fill=fill)


def render_forge_image(
    hunter: Hunter,
    inventory: Inventory,
    selected_item: Optional[Item] = None,
    notice: Optional[str] = None,
) -> io.BytesIO:
    """Render a high-resolution, Hallmark-compliant Blacksmith Forge Card."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), CANVAS_TOP)

    # 1. Atmospheric Forge Canvas with warm orange/amber forge bloom
    draw_atmospheric_canvas(
        img,
        top_color=(16, 12, 18),
        bottom_color=(8, 6, 10),
        bloom_cx=WIDTH // 2,
        bloom_cy=160,
        bloom_color=(245, 158, 11, 40),
        bloom_radius=320,
        grid_spacing=60,
    )

    draw = ImageDraw.Draw(img)

    # Outer border & cybernetic HUD corners
    draw.rectangle([10, 10, WIDTH - 10, HEIGHT - 10], outline=CANVAS_BORDER, width=1)
    draw_hud_corners(draw, (10, 10, WIDTH - 10, HEIGHT - 10), color=AMBER_GLOW, length=24, width=2)

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
    draw_diamond(draw, 34, header_y + 8, size=4, fill=AMBER_GLOW)
    font_eyebrow.draw_text(
        draw, (46, header_y + 2),
        "SYSTEM WORKSHOP // DIMENSIONAL BLACKSMITH // ANVIL V3.0",
        fill=AMBER_GLOW,
    )

    # Status Pill
    status_text = "ANVIL // ACTIVE"
    draw.rounded_rectangle([WIDTH - 170, header_y, WIDTH - 30, header_y + 22], radius=4, fill=SURFACE_ELEVATED, outline=AMBER_GLOW, width=1)
    draw_diamond(draw, WIDTH - 156, header_y + 11, size=3, fill=FIRE_ORANGE)
    font_badge.draw_text(draw, (WIDTH - 142, header_y + 5), status_text, fill=INK_PRIMARY)

    # Title & Subtitle
    font_title.draw_text(draw, (34, header_y + 26), "BLACKSMITH'S FORGE & SYNTHESIS", fill=INK_PRIMARY)
    font_subtitle.draw_text(
        draw, (34, header_y + 64),
        "Temper weapons & armor with dungeon materials to unlock transcendent power.",
        fill=INK_SECONDARY,
    )

    draw.line([(34, header_y + 92), (WIDTH - 34, header_y + 92)], fill=SURFACE_BORDER, width=1)
    draw.line([(34, header_y + 92), (200, header_y + 92)], fill=AMBER_GLOW, width=2)

    # ── Hunter Treasury & Material Stock ─────────────────────
    info_y = 132
    info_h = 60
    draw.rounded_rectangle([34, info_y, WIDTH - 34, info_y + info_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)

    materials = inventory.get_by_type("material")
    h_name = hunter.display_full_name if hasattr(hunter, "display_full_name") and hunter.display_full_name else hunter.hunter_name
    font_body_bold.draw_text(draw, (50, info_y + 12), f"HUNTER: {h_name} [Rank {hunter.rank}]", fill=INK_PRIMARY)
    font_body.draw_text(draw, (50, info_y + 34), f"Treasury: {hunter.gold:,} Gold ┊ Crafting Materials: {len(materials)} stored", fill=INK_SECONDARY)

    draw_coin_icon(draw, WIDTH - 150, info_y + 30, r=8)
    font_body_bold.draw_text(draw, (WIDTH - 134, info_y + 22), f"{hunter.gold:,} G", fill=INK_GOLD)

    # ── Notice Banner (if enhancement occurred) ──────────────
    curr_y = info_y + info_h + 14
    if notice:
        n_col = INK_GREEN if "SUCCESS" in notice or "COMPLETE" in notice else INK_RED
        draw.rounded_rectangle([34, curr_y, WIDTH - 34, curr_y + 40], radius=6, fill=SURFACE_ELEVATED, outline=n_col, width=1)
        draw_diamond(draw, 50, curr_y + 20, size=4, fill=n_col)
        clean_notice = notice.replace("✨", "").replace("🔮", "").replace("💥", "").replace("❌", "").strip()
        font_body_bold.draw_text(draw, (64, curr_y + 12), clean_notice, fill=n_col, max_w=WIDTH - 120)
        curr_y += 54

    # ── Anvil Enhancement Chamber ────────────────────────────
    chamber_y = curr_y
    chamber_h = 360
    draw.rounded_rectangle([34, chamber_y, WIDTH - 34, chamber_y + chamber_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
    draw_hud_corners(draw, (34, chamber_y, WIDTH - 34, chamber_y + chamber_h), color=AMBER_GLOW, length=16, width=1)

    _draw_anvil_icon(draw, 54, chamber_y + 24, size=14, fill=AMBER_GLOW)
    font_section.draw_text(draw, (78, chamber_y + 16), "PRIMARY ENHANCEMENT ANVIL (+1 TO +10)", fill=INK_PRIMARY)
    draw.line([(50, chamber_y + 44), (WIDTH - 50, chamber_y + 44)], fill=SURFACE_BORDER, width=1)

    if selected_item:
        # Display selected equipment
        r_col = RARITY_COLORS.get(selected_item.rarity, INK_PRIMARY)
        item_box_y = chamber_y + 60
        draw.rounded_rectangle([50, item_box_y, WIDTH - 50, item_box_y + 90], radius=6, fill=SURFACE_ELEVATED, outline=r_col, width=1)

        font_title.draw_text(draw, (70, item_box_y + 14), selected_item.display_name, fill=INK_PRIMARY)
        font_body_bold.draw_text(draw, (70, item_box_y + 54), f"[{selected_item.rarity.upper()}] • {selected_item.type.upper()}", fill=r_col)
        font_body_bold.draw_text(draw, (WIDTH - 300, item_box_y + 54), f"CURRENT STATS: {selected_item.stat_summary()}", fill=INK_GREEN)

        # Upgrade Progression Details
        next_lvl = selected_item.upgrade_level + 1
        prog_y = item_box_y + 110

        from game.crafting import UPGRADE_SUCCESS_RATES, get_upgrade_cost
        gold_cost, mat_name = get_upgrade_cost(selected_item)
        rate = UPGRADE_SUCCESS_RATES.get(next_lvl, 0.20)
        pct_str = f"{int(rate * 100)}%"

        font_body_bold.draw_text(draw, (70, prog_y), f"TARGET TIER: +{next_lvl} (Boost: +15% Stats)", fill=AMBER_GLOW)
        font_body_bold.draw_text(draw, (WIDTH - 250, prog_y), f"SUCCESS RATE: {pct_str}", fill=INK_CYAN)

        # Rate gauge bar
        bar_w = WIDTH - 140
        bar_h = 16
        draw.rounded_rectangle([70, prog_y + 26, 70 + bar_w, prog_y + 26 + bar_h], radius=4, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER)
        fill_w = int(bar_w * rate)
        if fill_w > 0:
            fill_col = INK_GREEN if rate >= 0.70 else (AMBER_GLOW if rate >= 0.40 else INK_RED)
            draw.rounded_rectangle([70, prog_y + 26, 70 + fill_w, prog_y + 26 + bar_h], radius=4, fill=fill_col)

        # Resource Requirements Box
        req_y = prog_y + 60
        font_body.draw_text(draw, (70, req_y), "REQUIRED REAGENTS:", fill=INK_SECONDARY)

        # Cost pills
        draw.rounded_rectangle([70, req_y + 24, 250, req_y + 54], radius=4, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER)
        draw_coin_icon(draw, 88, req_y + 39, r=6)
        font_body_bold.draw_text(draw, (104, req_y + 30), f"{gold_cost:,} Gold", fill=INK_GOLD)

        draw.rounded_rectangle([266, req_y + 24, 520, req_y + 54], radius=4, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER)
        draw_diamond(draw, 282, req_y + 39, size=4, fill=AMBER_GLOW)
        font_body_bold.draw_text(draw, (298, req_y + 30), "1 Crafting Catalyst", fill=INK_PRIMARY)
    else:
        # Default prompt when no item selected yet
        prompt_y = chamber_y + 90
        draw.rounded_rectangle([70, prompt_y, WIDTH - 70, prompt_y + 140], radius=8, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER)
        _draw_anvil_icon(draw, WIDTH // 2, prompt_y + 45, size=24, fill=SURFACE_BORDER_LIGHT)
        msg1 = "「 Place weapon, armor, or accessory upon the anvil 」"
        font_body_bold.draw_text(draw, (WIDTH // 2 - 180, prompt_y + 75), msg1, fill=INK_SECONDARY)
        msg2 = "Use /forge upgrade <item_id> or tap equipment buttons below to temper your gear."
        font_body.draw_text(draw, (WIDTH // 2 - 240, prompt_y + 102), msg2, fill=INK_MUTED)

    # ── Rarity Transmutation Crucible ────────────────────────
    trans_y = chamber_y + chamber_h + 16
    trans_h = 240
    draw.rounded_rectangle([34, trans_y, WIDTH - 34, trans_y + trans_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
    draw_hud_corners(draw, (34, trans_y, WIDTH - 34, trans_y + trans_h), color=INK_CYAN, length=16, width=1)

    draw_diamond(draw, 54, trans_y + 24, size=4, fill=INK_CYAN)
    font_section.draw_text(draw, (78, trans_y + 16), "TRANSMUTATION CRUCIBLE (RARITY FUSION)", fill=INK_PRIMARY)
    draw.line([(50, trans_y + 44), (WIDTH - 50, trans_y + 44)], fill=SURFACE_BORDER, width=1)

    fuse_tiers = [
        ("COMMON FUSION", "3 Common Gear + 1 Catalyst -> 1 UNCOMMON Item", RARITY_COLORS["Common"], RARITY_COLORS["Uncommon"]),
        ("UNCOMMON FUSION", "3 Uncommon Gear + 1 Catalyst -> 1 RARE Item", RARITY_COLORS["Uncommon"], RARITY_COLORS["Rare"]),
        ("RARE FUSION", "3 Rare Gear + 1 Catalyst -> 1 EPIC Item", RARITY_COLORS["Rare"], RARITY_COLORS["Epic"]),
    ]

    fy = trans_y + 56
    for title, desc, c_from, c_to in fuse_tiers:
        draw.rounded_rectangle([50, fy, WIDTH - 50, fy + 48], radius=6, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER, width=1)
        draw_diamond(draw, 68, fy + 24, size=4, fill=c_from)
        draw_diamond(draw, 78, fy + 24, size=4, fill=c_to)
        font_body_bold.draw_text(draw, (94, fy + 8), title, fill=c_to)
        font_body.draw_text(draw, (94, fy + 26), desc, fill=INK_SECONDARY)
        fy += 56

    # ── Footer Quote ─────────────────────────────────────────
    footer_y = HEIGHT - 46
    draw.line([(34, footer_y), (WIDTH - 34, footer_y)], fill=SURFACE_BORDER, width=1)
    quote = "「 THE BLACKSMITH'S HAMMER TURNS SLAG INTO RELICS OF POWER 」"
    font_footer.draw_text(draw, (WIDTH // 2 - 210, footer_y + 12), quote, fill=AMBER_GLOW)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
