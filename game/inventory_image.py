"""
game/inventory_image.py — Solo Leveling Dimensional Inventory Image Renderer.

Generates a stylized, high-resolution RPG Inventory Card image using Pillow,
showcasing the Hunter's active equipment loadout (weapon, armor, accessory)
with custom vector equipment graphics, rarity auras, stat badges,
and storage items for the active category.
"""

from __future__ import annotations

import io
import math
import os
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import RANKS, EQUIPPABLE_TYPES
from models import Hunter, Inventory, Item

# Canvas dimensions (860 x 1060)
WIDTH = 860
HEIGHT = 1060

# Color Palette (Solo Leveling Abyssal Blue HUD)
BG_TOP = (7, 11, 24)
BG_BOTTOM = (3, 6, 15)
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
CARD_BG = (13, 20, 36, 235)
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

RARITY_COLORS = {
    "Common": (148, 163, 184),
    "Uncommon": (34, 197, 94),
    "Rare": (56, 189, 248),
    "Epic": (168, 85, 247),
    "Legendary": (251, 191, 36),
    "Mythic": (239, 68, 68),
}


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
    """Retrieve styled fonts for different text hierarchies."""
    bold = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    regular = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]
    mono = ["consola.ttf", "consolab.ttf", "cour.ttf"]

    return {
        "title": _load_font(bold, 24),
        "subtitle": _load_font(bold, 15),
        "header_tag": _load_font(bold, 13),
        "name": _load_font(bold, 21),
        "rank": _load_font(bold, 15),
        "item_name": _load_font(bold, 18),
        "body_bold": _load_font(bold, 14),
        "body": _load_font(regular, 14),
        "small_bold": _load_font(bold, 12),
        "small": _load_font(regular, 12),
        "mono": _load_font(mono, 12),
        "footer": _load_font(bold, 13),
    }


def _draw_gradient_background(img: Image.Image) -> None:
    """Draw vertical dark tech gradient with subtle cyan & purple vignette."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for y in range(h):
        ratio = y / h
        r = int(BG_TOP[0] * (1 - ratio) + BG_BOTTOM[0] * ratio)
        g = int(BG_TOP[1] * (1 - ratio) + BG_BOTTOM[1] * ratio)
        b = int(BG_TOP[2] * (1 - ratio) + BG_BOTTOM[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    # Top center ambient cyan glow
    glow_draw.ellipse([w // 2 - 300, -60, w // 2 + 300, 240], fill=(0, 180, 255, 30))
    # Bottom ambient purple glow
    glow_draw.ellipse([w // 2 - 250, h - 250, w // 2 + 250, h + 80], fill=(139, 92, 246, 24))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img.alpha_composite(glow)


def _draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 5, fill=(0, 229, 255)) -> None:
    """Draw diamond/rhombus accent vector element."""
    draw.polygon(
        [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)],
        fill=fill,
    )


def _draw_coin_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int = 6) -> None:
    """Draw stylized gold coin icon."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOLD_COLOR, outline=(200, 150, 10), width=1)
    draw.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], outline=(255, 235, 120), width=1)


def _draw_tech_border(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int) -> None:
    """Draw modern tech HUD corner brackets and outer border."""
    draw.rectangle([x1, y1, x2, y2], outline=(25, 45, 80, 180), width=1)
    bracket_len = 26
    bracket_w = 3
    cyan = HUD_CYAN

    # Top-left
    draw.line([(x1, y1), (x1 + bracket_len, y1)], fill=cyan, width=bracket_w)
    draw.line([(x1, y1), (x1, y1 + bracket_len)], fill=cyan, width=bracket_w)
    # Top-right
    draw.line([(x2 - bracket_len, y1), (x2, y1)], fill=cyan, width=bracket_w)
    draw.line([(x2, y1), (x2, y1 + bracket_len)], fill=cyan, width=bracket_w)
    # Bottom-left
    draw.line([(x1, y2), (x1 + bracket_len, y2)], fill=cyan, width=bracket_w)
    draw.line([(x1, y2), (x1, y2 - bracket_len)], fill=cyan, width=bracket_w)
    # Bottom-right
    draw.line([(x2 - bracket_len, y2), (x2, y2)], fill=cyan, width=bracket_w)
    draw.line([(x2, y2), (x2, y2 - bracket_len)], fill=cyan, width=bracket_w)


def _draw_card(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, radius: int = 10, fill=CARD_BG, outline=CARD_BORDER, width: int = 1) -> None:
    """Draw rounded rectangle container with customizable border."""
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=width)


# ── Equipment Vector Icon Renderers ────────────────────────

def _draw_sword_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: Tuple[int, int, int]) -> None:
    """Draw an illuminated hunter blade / sword."""
    x1, y1 = cx - int(size * 0.42), cy + int(size * 0.42)
    x2, y2 = cx + int(size * 0.62), cy - int(size * 0.62)
    hx, hy = cx - int(size * 0.68), cy + int(size * 0.68)
    gx1, gy1 = x1 - int(size * 0.28), y1 - int(size * 0.28)
    gx2, gy2 = x1 + int(size * 0.28), y1 + int(size * 0.28)

    # Aura glow behind blade
    draw.line([(x1, y1), (x2, y2)], fill=(color[0], color[1], color[2], 120), width=7)
    draw.line([(x1, y1), (x2, y2)], fill=color, width=4)
    draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 240), width=2)
    # Crossguard
    draw.line([(gx1, gy1), (gx2, gy2)], fill=color, width=3)
    # Grip & Pommel
    draw.line([(hx, hy), (x1, y1)], fill=(130, 145, 170), width=3)
    draw.ellipse([hx - 3, hy - 3, hx + 3, hy + 3], fill=color)


def _draw_dagger_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: Tuple[int, int, int]) -> None:
    """Draw dual curved hunter daggers (Solo Leveling assassin style)."""
    _draw_sword_icon(draw, cx - 6, cy + 3, int(size * 0.85), color)
    x1, y1 = cx + 8 - int(size * 0.4), cy + 3 - int(size * 0.4)
    x2, y2 = cx + 8 + int(size * 0.5), cy + 3 + int(size * 0.5)
    draw.line([(x1, y1), (x2, y2)], fill=color, width=3)
    draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255), width=1)


def _draw_shield_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: Tuple[int, int, int]) -> None:
    """Draw protective heater shield / armor plate."""
    w, h = int(size * 0.8), size
    pts = [
        (cx - w, cy - h + 5),
        (cx + w, cy - h + 5),
        (cx + w, cy + 2),
        (cx, cy + h),
        (cx - w, cy + 2),
    ]
    draw.polygon(pts, fill=(color[0] // 5, color[1] // 5, color[2] // 5, 220), outline=color, width=2)
    # Inner energy cross emblem
    draw.line([(cx, cy - h + 10), (cx, cy + h - 8)], fill=color, width=2)
    draw.line([(cx - w + 6, cy - 2), (cx + w - 6, cy - 2)], fill=color, width=2)
    draw.ellipse([cx - 3, cy - 5, cx + 3, cy + 1], fill=(255, 255, 255))


def _draw_ring_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: Tuple[int, int, int]) -> None:
    """Draw dimensional ring with radiating diamond gemstone."""
    r = int(size * 0.75)
    draw.ellipse([cx - r, cy - r + 5, cx + r, cy + r + 5], outline=color, width=3)
    gem_y = cy - r - 2
    gem_pts = [
        (cx, gem_y - 6),
        (cx + 6, gem_y),
        (cx, gem_y + 6),
        (cx - 6, gem_y),
    ]
    draw.polygon(gem_pts, fill=(255, 255, 255), outline=color, width=2)
    draw.line([(cx - 9, gem_y), (cx + 9, gem_y)], fill=(color[0], color[1], color[2], 180), width=1)


def _draw_potion_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: Tuple[int, int, int]) -> None:
    """Draw alchemy potion flask with glowing liquid."""
    r = int(size * 0.65)
    draw.rectangle([cx - 4, cy - size + 2, cx + 4, cy - r + 3], fill=(80, 100, 130), outline=color)
    draw.rectangle([cx - 6, cy - size, cx + 6, cy - size + 3], fill=(160, 140, 100))
    draw.ellipse([cx - r, cy - r + 4, cx + r, cy + r + 4], fill=(color[0] // 6, color[1] // 6, color[2] // 6), outline=color, width=2)
    draw.chord([cx - r + 2, cy - r + 6, cx + r - 2, cy + r + 2], 0, 180, fill=color)
    draw.point((cx - 3, cy), fill=(255, 255, 255))
    draw.point((cx + 4, cy + 4), fill=(255, 255, 255))


def _draw_crystal_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: Tuple[int, int, int]) -> None:
    """Draw mana core / crafting crystal."""
    w, h = int(size * 0.7), size
    pts = [
        (cx, cy - h + 2),
        (cx + w, cy),
        (cx, cy + h - 2),
        (cx - w, cy),
    ]
    draw.polygon(pts, fill=(color[0] // 5, color[1] // 5, color[2] // 5), outline=color, width=2)
    draw.line([(cx, cy - h + 2), (cx, cy + h - 2)], fill=color, width=1)
    draw.line([(cx - w, cy), (cx + w, cy)], fill=color, width=1)
    draw.point((cx - 2, cy - 4), fill=(255, 255, 255))


def _draw_equipment_icon(
    draw: ImageDraw.ImageDraw,
    item_type: str,
    item_name: str,
    rarity: str,
    cx: int,
    cy: int,
    box_size: int = 56,
    is_equipped: bool = False,
) -> None:
    """Draw a framed item icon box with background and vector artwork."""
    half = box_size // 2
    r_color = RARITY_COLORS.get(rarity, TEXT_WHITE)

    box_fill = (16, 26, 46, 240) if is_equipped else (11, 18, 32, 240)
    border_color = r_color if is_equipped else (
        int(r_color[0] * 0.7), int(r_color[1] * 0.7), int(r_color[2] * 0.7)
    )
    draw.rounded_rectangle(
        [cx - half, cy - half, cx + half, cy + half],
        radius=8,
        fill=box_fill,
        outline=border_color,
        width=2 if is_equipped else 1,
    )

    if rarity in ["Epic", "Legendary", "Mythic"] or is_equipped:
        glow_r = half - 6
        draw.ellipse(
            [cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r],
            fill=(r_color[0] // 6, r_color[1] // 6, r_color[2] // 6, 120),
        )

    name_lower = item_name.lower()
    icon_size = int(box_size * 0.42)

    if item_type == "weapon":
        if any(k in name_lower for k in ["dagger", "fang", "claw", "short sword"]):
            _draw_dagger_icon(draw, cx, cy, icon_size, r_color)
        else:
            _draw_sword_icon(draw, cx, cy, icon_size, r_color)
    elif item_type == "armor":
        _draw_shield_icon(draw, cx, cy, icon_size, r_color)
    elif item_type == "accessory":
        _draw_ring_icon(draw, cx, cy, icon_size, r_color)
    elif item_type == "consumable":
        _draw_potion_icon(draw, cx, cy, icon_size, r_color)
    elif item_type == "material":
        _draw_crystal_icon(draw, cx, cy, icon_size, r_color)
    else:
        _draw_sword_icon(draw, cx, cy, icon_size, r_color)


# ── Main Inventory Image Renderer ─────────────────────────

def render_inventory_image(
    hunter: Hunter,
    inventory: Inventory,
    active_cat: str = "weapon",
    notice: Optional[str] = None,
) -> io.BytesIO:
    """
    Render a high-resolution Solo Leveling Dimensional Storage window image.
    Showcases active equipment loadout and category storage grid with equipment artwork.
    """
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    _draw_gradient_background(img)
    draw = ImageDraw.Draw(img)
    fonts = _get_fonts()

    # Outer border and tech HUD brackets
    _draw_tech_border(draw, 20, 20, WIDTH - 20, HEIGHT - 20)

    # 1. Header Banner with vector diamond accents
    title_text = "SYSTEM NOTIFICATION • DIMENSIONAL STORAGE"
    t_bbox = fonts["title"].getbbox(title_text)
    t_w = t_bbox[2] - t_bbox[0]
    draw.text(((WIDTH - t_w) // 2, 34), title_text, font=fonts["title"], fill=HUD_CYAN)
    _draw_diamond(draw, (WIDTH - t_w) // 2 - 18, 48, size=5, fill=HUD_CYAN)
    _draw_diamond(draw, (WIDTH + t_w) // 2 + 18, 48, size=5, fill=HUD_CYAN)

    sub_text = "Hunter Inventory & Equipment Matrix"
    s_bbox = fonts["small_bold"].getbbox(sub_text)
    s_w = s_bbox[2] - s_bbox[0]
    draw.text(((WIDTH - s_w) // 2, 68), sub_text, font=fonts["small_bold"], fill=TEXT_MUTED)

    # 2. Hunter Info Strip Card
    info_y = 96
    info_h = 58
    _draw_card(draw, 36, info_y, WIDTH - 36, info_y + info_h, radius=8)

    # Hunter Name & Rank
    rank_color = RANK_COLORS.get(hunter.rank, HUD_CYAN)
    draw.text((54, info_y + 11), f"HUNTER: {hunter.hunter_name}", font=fonts["name"], fill=TEXT_WHITE)
    draw.text((54, info_y + 36), f"Rank {hunter.rank} • {hunter.title}", font=fonts["small_bold"], fill=rank_color)

    # Right side metrics: Gold, Capacity, Power
    gold_str = f"{hunter.gold:,} GOLD"
    cap_str = f"{len(inventory.items)} ITEMS"
    pwr_str = f"POWER {hunter.power}"

    rx = WIDTH - 54
    for metric, color in [(pwr_str, (251, 191, 36)), (cap_str, TEXT_WHITE), (gold_str, GOLD_COLOR)]:
        m_bbox = fonts["body_bold"].getbbox(metric)
        m_w = m_bbox[2] - m_bbox[0]
        draw.text((rx - m_w, info_y + 19), metric, font=fonts["body_bold"], fill=color)
        rx -= m_w + 24

    # 3. Notice Banner (if item just equipped)
    curr_y = info_y + info_h + 14
    if notice:
        notice_h = 38
        _draw_card(
            draw, 36, curr_y, WIDTH - 36, curr_y + notice_h,
            radius=6, fill=(18, 38, 70, 240), outline=HUD_CYAN, width=1
        )
        _draw_diamond(draw, 52, curr_y + 19, size=4, fill=HUD_CYAN)
        display_notice = notice.replace("⚡", "").replace("📊", "").replace("💪", "").strip()
        if len(display_notice) > 75:
            display_notice = display_notice[:72] + "..."
        draw.text((64, curr_y + 11), display_notice, font=fonts["small_bold"], fill=HUD_CYAN)
        curr_y += notice_h + 14

    # 4. Active Equipment Loadout (Weapon, Armor, Accessory)
    loadout_y = curr_y
    loadout_h = 138
    _draw_card(draw, 36, loadout_y, WIDTH - 36, loadout_y + loadout_h, radius=10)

    _draw_diamond(draw, 52, loadout_y + 20, size=4, fill=HUD_SKY)
    draw.text((64, loadout_y + 12), "CURRENT ACTIVE LOADOUT", font=fonts["subtitle"], fill=HUD_SKY)
    draw.text((WIDTH - 210, loadout_y + 14), "[EQUIPPED GEAR SLOTS]", font=fonts["small_bold"], fill=TEXT_MUTED)

    slots_y = loadout_y + 40
    slot_w = (WIDTH - 72 - 32) // 3
    slots_data = [
        ("WEAPON", inventory.get_equipped("weapon")),
        ("ARMOR", inventory.get_equipped("armor")),
        ("ACCESSORY", inventory.get_equipped("accessory")),
    ]

    for idx, (slot_name, equipped_item) in enumerate(slots_data):
        sx = 52 + idx * (slot_w + 16)
        sy = slots_y
        sh = 82

        if equipped_item:
            r_color = RARITY_COLORS.get(equipped_item.rarity, TEXT_WHITE)
            _draw_card(draw, sx, sy, sx + slot_w, sy + sh, radius=8, fill=(18, 28, 50, 220), outline=r_color, width=1)
            _draw_equipment_icon(draw, equipped_item.type, equipped_item.name, equipped_item.rarity, sx + 34, sy + sh // 2, box_size=50, is_equipped=True)

            tx = sx + 68
            item_name = equipped_item.name
            if len(item_name) > 13:
                item_name = item_name[:12] + ".."
            draw.text((tx, sy + 10), item_name, font=fonts["body_bold"], fill=TEXT_WHITE)
            draw.text((tx, sy + 32), f"[{equipped_item.rarity.upper()}] • {slot_name}", font=fonts["small_bold"], fill=r_color)

            stats = equipped_item.stat_summary()
            if len(stats) > 16:
                stats = stats[:15] + ".."
            draw.text((tx, sy + 54), stats, font=fonts["small"], fill=GREEN_COLOR)
        else:
            _draw_card(draw, sx, sy, sx + slot_w, sy + sh, radius=8, fill=(12, 17, 30, 200), outline=(28, 44, 72), width=1)
            draw.rounded_rectangle([sx + 10, sy + (sh - 48) // 2, sx + 58, sy + (sh + 48) // 2], radius=6, outline=(36, 56, 90))
            draw.text((sx + 30, sy + 30), "—", font=fonts["body_bold"], fill=TEXT_DIM)
            draw.text((tx := sx + 68, sy + 20), f"-- EMPTY --", font=fonts["body_bold"], fill=TEXT_DIM)
            draw.text((tx, sy + 44), f"No {slot_name.title()}", font=fonts["small"], fill=TEXT_MUTED)

    # 5. Storage Compartment Matrix (Active Category)
    matrix_y = loadout_y + loadout_h + 16
    cat_names = {
        "weapon": "WEAPONS",
        "armor": "ARMOR",
        "accessory": "ACCESSORIES",
        "consumable": "CONSUMABLES",
        "material": "MATERIALS",
    }
    cat_title = cat_names.get(active_cat, active_cat.upper())
    cat_items = inventory.get_by_type(active_cat)

    matrix_h = HEIGHT - matrix_y - 65
    _draw_card(draw, 36, matrix_y, WIDTH - 36, matrix_y + matrix_h, radius=10)

    # Category Matrix Header
    _draw_diamond(draw, 52, matrix_y + 22, size=4, fill=HUD_SKY)
    draw.text((64, matrix_y + 14), f"STORAGE COMPARTMENT: {cat_title} ({len(cat_items)} ITEMS)", font=fonts["subtitle"], fill=HUD_SKY)
    draw.text((WIDTH - 190, matrix_y + 16), "[SYSTEM MATRIX]", font=fonts["small_bold"], fill=TEXT_MUTED)

    items_start_y = matrix_y + 44
    card_h = 100
    spacing = 10
    max_display = min(len(cat_items), 5)

    if not cat_items:
        empty_box_y = matrix_y + 120
        _draw_card(draw, 80, empty_box_y, WIDTH - 80, empty_box_y + 160, radius=8, fill=(11, 16, 28, 200), outline=(26, 42, 70))
        draw.ellipse([WIDTH // 2 - 28, empty_box_y + 24, WIDTH // 2 + 28, empty_box_y + 80], outline=(36, 60, 100), width=2)
        draw.text((WIDTH // 2 - 6, empty_box_y + 40), "—", font=fonts["title"], fill=TEXT_DIM)

        msg1 = "「 This dimensional pocket is currently empty. 」"
        m1_bbox = fonts["body_bold"].getbbox(msg1)
        draw.text(((WIDTH - (m1_bbox[2] - m1_bbox[0])) // 2, empty_box_y + 94), msg1, font=fonts["body_bold"], fill=TEXT_MUTED)

        msg2 = "Defeat dungeon monsters via /hunt or purchase gear at the Hunter Shop!"
        m2_bbox = fonts["small"].getbbox(msg2)
        draw.text(((WIDTH - (m2_bbox[2] - m2_bbox[0])) // 2, empty_box_y + 122), msg2, font=fonts["small"], fill=TEXT_DIM)
    else:
        for i in range(max_display):
            item = cat_items[i]
            iy = items_start_y + i * (card_h + spacing)
            r_color = RARITY_COLORS.get(item.rarity, TEXT_WHITE)

            card_fill = (16, 26, 48, 240) if item.is_equipped else (12, 18, 34, 230)
            card_outline = r_color if item.is_equipped else (
                int(r_color[0] * 0.6), int(r_color[1] * 0.6), int(r_color[2] * 0.6)
            )
            _draw_card(draw, 52, iy, WIDTH - 52, iy + card_h, radius=8, fill=card_fill, outline=card_outline, width=2 if item.is_equipped else 1)

            # Equipment Icon (Left, 64x64)
            icon_cx = 52 + 48
            icon_cy = iy + card_h // 2
            _draw_equipment_icon(draw, item.type, item.name, item.rarity, icon_cx, icon_cy, box_size=64, is_equipped=item.is_equipped)

            # Details Text Block
            tx = 52 + 96
            draw.text((tx, iy + 14), item.name, font=fonts["item_name"], fill=TEXT_WHITE)

            # Line 2: Rarity badge & Category
            rarity_str = f"[{item.rarity.upper()}]"
            draw.text((tx, iy + 42), rarity_str, font=fonts["small_bold"], fill=r_color)
            r_bbox = fonts["small_bold"].getbbox(rarity_str)
            rw = r_bbox[2] - r_bbox[0]
            draw.text((tx + rw + 10, iy + 42), f"• {item.type.upper()}", font=fonts["small"], fill=TEXT_MUTED)

            # Line 3: Stat pills
            stats_str = item.stat_summary()
            draw.text((tx, iy + 66), f"STATS: {stats_str}", font=fonts["small_bold"], fill=GREEN_COLOR)

            # Right Side: Status Tag Badge
            badge_w = 140
            badge_h = 36
            badge_x = WIDTH - 52 - badge_w - 18
            badge_y = iy + (card_h - badge_h) // 2

            if item.is_equipped:
                # Glowing Equipped Badge
                draw.rounded_rectangle(
                    [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
                    radius=6,
                    fill=(10, 32, 58, 245),
                    outline=HUD_CYAN,
                    width=2,
                )
                eq_text = "• EQUIPPED •"
                eq_bbox = fonts["small_bold"].getbbox(eq_text)
                eq_tw = eq_bbox[2] - eq_bbox[0]
                draw.text((badge_x + (badge_w - eq_tw) // 2, badge_y + 10), eq_text, font=fonts["small_bold"], fill=HUD_CYAN)
            else:
                # In Storage Badge
                draw.rounded_rectangle(
                    [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
                    radius=6,
                    fill=(18, 26, 44, 200),
                    outline=(40, 60, 95),
                    width=1,
                )
                st_text = "IN STORAGE"
                st_bbox = fonts["small"].getbbox(st_text)
                st_tw = st_bbox[2] - st_bbox[0]
                draw.text((badge_x + (badge_w - st_tw) // 2, badge_y + 11), st_text, font=fonts["small"], fill=TEXT_MUTED)

    # 6. Bottom System Status Bar
    footer_text = "SYSTEM MATRIX ONLINE • USE BUTTONS BELOW TO SWITCH TABS OR EQUIP GEAR"
    f_bbox = fonts["footer"].getbbox(footer_text)
    f_w = f_bbox[2] - f_bbox[0]
    draw.text(((WIDTH - f_w) // 2, HEIGHT - 46), footer_text, font=fonts["footer"], fill=TEXT_MUTED)

    # Convert to RGB & Save in memory buffer
    rgb_img = img.convert("RGB")
    buf = io.BytesIO()
    rgb_img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = "inventory.png"
    return buf
