"""
game/shop_image.py — Solo Leveling Hunter Shop Image Card Renderer.

Generates a stylized, high-resolution RPG Shop Card image using Pillow,
showcasing available equipment, consumables, and materials with custom vector artwork,
rarity auras, stat badges, prices, and affordability indicators.
"""

from __future__ import annotations

import io
import math
import os
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import RANKS, RARITY_EMOJI
from game.font_manager import get_font_cascade, clean_and_normalize_name
from models import Hunter, Item
from game.shop import SHOP_ITEMS, get_shop_items_by_type

# Canvas dimensions (860 x 1060 — matching inventory for visual consistency)
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

CATEGORIES = [
    ("weapon", "WEAPONS"),
    ("armor", "ARMOR"),
    ("accessory", "ACCESSORIES"),
    ("consumable", "CONSUMABLES"),
    ("material", "MATERIALS"),
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
    """Retrieve styled fonts for different text hierarchies."""
    bold = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    regular = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]

    return {
        "title": _load_font(bold, 24),
        "subtitle": _load_font(bold, 15),
        "header_tag": _load_font(bold, 13),
        "name": _load_font(bold, 20),
        "rank": _load_font(bold, 15),
        "item_name": _load_font(bold, 17),
        "body_bold": _load_font(bold, 14),
        "body": _load_font(regular, 13),
        "small_bold": _load_font(bold, 12),
        "small": _load_font(regular, 11),
        "price_large": _load_font(bold, 18),
        "footer": _load_font(bold, 13),
    }


def _draw_gradient_background(img: Image.Image) -> None:
    """Draw vertical dark tech gradient with subtle gold and cyan vignette."""
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
    # Top center ambient gold & cyan glow
    glow_draw.ellipse([w // 2 - 320, -80, w // 2 + 320, 240], fill=(250, 204, 21, 24))
    glow_draw.ellipse([w // 2 - 200, -40, w // 2 + 200, 180], fill=(0, 229, 255, 20))
    # Bottom ambient cyan glow
    glow_draw.ellipse([w // 2 - 250, h - 220, w // 2 + 250, h + 80], fill=(37, 99, 235, 22))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img.alpha_composite(glow)


def _draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 5, fill=HUD_CYAN) -> None:
    """Draw diamond vector element."""
    draw.polygon([(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)], fill=fill)


def _draw_coin_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int = 7) -> None:
    """Draw a clean stylized gold coin icon."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOLD_COLOR, outline=(210, 160, 15), width=1)
    draw.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], outline=(255, 240, 140), width=1)
    # Coin center line
    draw.line([(cx, cy - r + 3), (cx, cy + r - 3)], fill=(190, 140, 10), width=1)


def _draw_tech_border(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int) -> None:
    """Draw modern tech HUD corner brackets and outer border."""
    draw.rectangle([x1, y1, x2, y2], outline=(25, 45, 80, 180), width=1)
    bracket_len = 26
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


# ── Equipment Vector Icons ────────────────────────────────

def _draw_sword_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: Tuple[int, int, int]) -> None:
    x1, y1 = cx - int(size * 0.42), cy + int(size * 0.42)
    x2, y2 = cx + int(size * 0.62), cy - int(size * 0.62)
    hx, hy = cx - int(size * 0.68), cy + int(size * 0.68)
    gx1, gy1 = x1 - int(size * 0.28), y1 - int(size * 0.28)
    gx2, gy2 = x1 + int(size * 0.28), y1 + int(size * 0.28)

    draw.line([(x1, y1), (x2, y2)], fill=(color[0], color[1], color[2], 120), width=7)
    draw.line([(x1, y1), (x2, y2)], fill=color, width=4)
    draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 240), width=2)
    draw.line([(gx1, gy1), (gx2, gy2)], fill=color, width=3)
    draw.line([(hx, hy), (x1, y1)], fill=(130, 145, 170), width=3)
    draw.ellipse([hx - 3, hy - 3, hx + 3, hy + 3], fill=color)


def _draw_dagger_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: Tuple[int, int, int]) -> None:
    _draw_sword_icon(draw, cx - 6, cy + 3, int(size * 0.85), color)
    x1, y1 = cx + 8 - int(size * 0.4), cy + 3 - int(size * 0.4)
    x2, y2 = cx + 8 + int(size * 0.5), cy + 3 + int(size * 0.5)
    draw.line([(x1, y1), (x2, y2)], fill=color, width=3)
    draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255), width=1)


def _draw_shield_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: Tuple[int, int, int]) -> None:
    w, h = int(size * 0.8), size
    pts = [
        (cx - w, cy - h + 5),
        (cx + w, cy - h + 5),
        (cx + w, cy + 2),
        (cx, cy + h),
        (cx - w, cy + 2),
    ]
    draw.polygon(pts, fill=(color[0] // 5, color[1] // 5, color[2] // 5, 220), outline=color, width=2)
    draw.line([(cx, cy - h + 10), (cx, cy + h - 8)], fill=color, width=2)
    draw.line([(cx - w + 6, cy - 2), (cx + w - 6, cy - 2)], fill=color, width=2)
    draw.ellipse([cx - 3, cy - 5, cx + 3, cy + 1], fill=(255, 255, 255))


def _draw_ring_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: Tuple[int, int, int]) -> None:
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
    r = int(size * 0.65)
    draw.rectangle([cx - 4, cy - size + 2, cx + 4, cy - r + 3], fill=(80, 100, 130), outline=color)
    draw.rectangle([cx - 6, cy - size, cx + 6, cy - size + 3], fill=(160, 140, 100))
    draw.ellipse([cx - r, cy - r + 4, cx + r, cy + r + 4], fill=(color[0] // 6, color[1] // 6, color[2] // 6), outline=color, width=2)
    draw.chord([cx - r + 2, cy - r + 6, cx + r - 2, cy + r + 2], 0, 180, fill=color)
    draw.point((cx - 3, cy), fill=(255, 255, 255))
    draw.point((cx + 4, cy + 4), fill=(255, 255, 255))


def _draw_crystal_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: Tuple[int, int, int]) -> None:
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
    box_size: int = 64,
) -> None:
    """Draw a framed item icon box with background and vector artwork."""
    half = box_size // 2
    r_color = RARITY_COLORS.get(rarity, TEXT_WHITE)

    box_fill = (14, 22, 38, 240)
    border_color = (int(r_color[0] * 0.8), int(r_color[1] * 0.8), int(r_color[2] * 0.8))
    draw.rounded_rectangle(
        [cx - half, cy - half, cx + half, cy + half],
        radius=8,
        fill=box_fill,
        outline=border_color,
        width=2,
    )

    if rarity in ["Epic", "Legendary", "Mythic"]:
        glow_r = half - 6
        draw.ellipse(
            [cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r],
            fill=(r_color[0] // 6, r_color[1] // 6, r_color[2] // 6, 120),
        )

    name_lower = item_name.lower()
    icon_size = int(box_size * 0.42)

    if item_type == "weapon":
        if any(k in name_lower for k in ["dagger", "fang", "blade"]):
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


def render_shop_image(
    hunter: Hunter,
    active_cat: str = "weapon",
    notice: Optional[str] = None,
) -> io.BytesIO:
    """
    Generate a high-definition static RPG Shop Card for the Hunter Shop.
    Supports individual categories ('weapon', 'armor', 'accessory', 'consumable', 'material')
    or the full departmental overview hub ('menu').
    Returns in-memory BytesIO buffer of the PNG file.
    """
    fonts = _get_fonts()
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    _draw_gradient_background(img)
    draw = ImageDraw.Draw(img)

    # Outer tech border
    _draw_tech_border(draw, 18, 18, WIDTH - 18, HEIGHT - 18)

    # ── 1. Top HUD Header ──
    sub_title = "SYSTEM EXCHANGE DEPOT"
    _draw_diamond(draw, WIDTH // 2 - 130, 36, size=4, fill=GOLD_COLOR)
    _draw_diamond(draw, WIDTH // 2 + 130, 36, size=4, fill=GOLD_COLOR)
    draw.text((WIDTH // 2 - 110, 28), sub_title, font=fonts["subtitle"], fill=GOLD_COLOR)

    main_title = "HUNTER SHOP"
    tb = fonts["title"].getbbox(main_title)
    tw = tb[2] - tb[0]
    draw.text((WIDTH // 2 - tw // 2, 54), main_title, font=fonts["title"], fill=TEXT_WHITE)

    tag_text = "Authorized Equipment & Material Exchange Protocol"
    tb_tag = fonts["small"].getbbox(tag_text)
    draw.text((WIDTH // 2 - (tb_tag[2] - tb_tag[0]) // 2, 86), tag_text, font=fonts["small"], fill=HUD_SKY)

    # ── 2. Hunter Status & Treasury Vault ──
    h_y1 = 112
    h_y2 = 192
    draw.rounded_rectangle([32, h_y1, WIDTH - 32, h_y2], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)

    # Hunter Info Left
    _draw_diamond(draw, 50, h_y1 + 24, size=4, fill=HUD_CYAN)
    draw.text((62, h_y1 + 14), "[ LICENSED HUNTER ]", font=fonts["small_bold"], fill=HUD_CYAN)

    h_name = hunter.display_full_name if hasattr(hunter, "display_full_name") and hunter.display_full_name else hunter.hunter_name
    cascade_shop = get_font_cascade(20, is_bold=True)
    cascade_shop.draw_text(draw, (50, h_y1 + 36), h_name, fill=TEXT_WHITE, max_w=vault_x - 70)

    r_col = RANK_COLORS.get(hunter.rank, GOLD_COLOR)
    draw.text((50, h_y1 + 64), f"Rank: {hunter.rank}-Rank  •  Level {hunter.level}  •  Combat Power: {hunter.power:,}", font=fonts["small_bold"], fill=r_col)

    # Treasury Vault Card on Right
    vault_w = 260
    vault_x = WIDTH - 32 - vault_w - 14
    draw.rounded_rectangle([vault_x, h_y1 + 10, vault_x + vault_w, h_y2 - 10], radius=8, fill=(28, 24, 14, 240), outline=GOLD_COLOR, width=1)
    _draw_diamond(draw, vault_x + 18, h_y1 + 26, size=4, fill=GOLD_COLOR)
    draw.text((vault_x + 28, h_y1 + 18), "AVAILABLE TREASURY", font=fonts["small_bold"], fill=GOLD_COLOR)

    _draw_coin_icon(draw, vault_x + 28, h_y1 + 52, r=9)
    gold_str = f"{hunter.gold:,} GOLD"
    draw.text((vault_x + 46, h_y1 + 42), gold_str, font=fonts["price_large"], fill=TEXT_WHITE)

    # ── 3. Category Tabs Indicator ──
    tab_y = 206
    tab_h = 38
    num_tabs = len(CATEGORIES)
    total_tabs_w = WIDTH - 64
    spacing = 8
    tab_w = (total_tabs_w - (num_tabs - 1) * spacing) // num_tabs

    for idx, (cat_key, cat_label) in enumerate(CATEGORIES):
        tx1 = 32 + idx * (tab_w + spacing)
        tx2 = tx1 + tab_w
        is_active = (cat_key == active_cat)

        if is_active:
            tab_fill = (20, 36, 60, 240)
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
        draw.text((tx1 + (tab_w - cw) // 2, tab_y + 11), cat_label, font=fonts["small_bold"], fill=tab_text_color)

    # ── 4. Notice Banner (Optional) ──
    cur_y = tab_y + tab_h + 14
    if notice:
        draw.rounded_rectangle([32, cur_y, WIDTH - 32, cur_y + 36], radius=6, fill=(16, 42, 28, 240), outline=GREEN_COLOR, width=1)
        _draw_diamond(draw, 50, cur_y + 18, size=4, fill=GREEN_COLOR)
        draw.text((62, cur_y + 9), notice, font=fonts["body_bold"], fill=GREEN_COLOR)
        cur_y += 46

    # ── 5. Items Catalogue Matrix ──
    if active_cat == "menu":
        # Overview of all 5 departments
        draw.rounded_rectangle([32, cur_y, WIDTH - 32, 988], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)
        draw.text((50, cur_y + 18), "[ DEPARTMENT CATALOGUE ]", font=fonts["small_bold"], fill=GOLD_COLOR)
        draw.text((50, cur_y + 40), "Select a category below to browse items and purchase equipment:", font=fonts["body"], fill=TEXT_WHITE)

        dept_items = [
            ("WEAPONS DEPOT", "Longswords, battle axes, mithril katanas, shadow blades, dragon daggers", "+ATK & +SPD", "weapon"),
            ("ARMOR DEPARTMENT", "Leather vests, chainmail, knight's plate, shadow robes, monarch aegis", "+DEF & +HP", "armor"),
            ("ACCESSORIES & RELICS", "Copper rings, silver amulets, mana crystal pendants, monarch earrings", "Multi-stat buffs", "accessory"),
            ("ALCHEMICAL SUPPLIES", "Health recovery potions, strength elixirs, protection scrolls, swift draughts", "Consumables", "consumable"),
            ("CRAFTING MATERIALS", "Refined iron ore, magic crystals, shadow essences, dragon scales", "Forge & Synthesis", "material"),
        ]

        row_y = cur_y + 74
        for dept_title, dept_desc, dept_tag, dept_type in dept_items:
            draw.rounded_rectangle([48, row_y, WIDTH - 48, row_y + 86], radius=8, fill=(16, 24, 42, 220), outline=CARD_BORDER, width=1)
            # Framed vector icon on left
            _draw_equipment_icon(draw, item_type=dept_type, item_name=dept_title, rarity="Rare", cx=84, cy=row_y + 43, box_size=56)
            draw.text((126, row_y + 16), dept_title, font=fonts["item_name"], fill=TEXT_WHITE)
            draw.text((126, row_y + 44), dept_desc, font=fonts["body"], fill=TEXT_MUTED)

            # Tag pill right
            tb_t = fonts["small_bold"].getbbox(dept_tag)
            tw_t = tb_t[2] - tb_t[0]
            draw.rounded_rectangle([WIDTH - 70 - tw_t - 16, row_y + 16, WIDTH - 70, row_y + 40], radius=4, fill=(18, 32, 54), outline=HUD_SKY)
            draw.text((WIDTH - 70 - tw_t - 8, row_y + 22), dept_tag, font=fonts["small_bold"], fill=HUD_SKY)
            row_y += 98

    else:
        # Category specific item cards
        items = get_shop_items_by_type(active_cat)
        draw.rounded_rectangle([32, cur_y, WIDTH - 32, 988], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)

        cat_title = active_cat.upper()
        draw.text((50, cur_y + 16), f"[ {cat_title} SHOWCASE ]", font=fonts["small_bold"], fill=HUD_CYAN)
        draw.text((50, cur_y + 36), f"Available items in the {active_cat.title()} category:", font=fonts["body"], fill=TEXT_MUTED)

        card_start_y = cur_y + 64
        card_h = 104
        spacing_y = 10

        for idx, entry in enumerate(items):
            cy_box = card_start_y + idx * (card_h + spacing_y)
            if cy_box + card_h > 980:
                break

            r_color = RARITY_COLORS.get(entry["rarity"], TEXT_WHITE)
            can_afford = (hunter.gold >= entry["price"])

            # Outer row box
            draw.rounded_rectangle(
                [48, cy_box, WIDTH - 48, cy_box + card_h],
                radius=8,
                fill=(16, 24, 42, 220),
                outline=r_color if can_afford else CARD_BORDER,
                width=1,
            )

            # Vector item icon left
            _draw_equipment_icon(
                draw,
                item_type=entry["type"],
                item_name=entry["name"],
                rarity=entry["rarity"],
                cx=92,
                cy=cy_box + card_h // 2,
                box_size=68,
            )

            # Item details middle
            item_text_x = 144
            draw.text((item_text_x, cy_box + 16), entry["name"], font=fonts["item_name"], fill=TEXT_WHITE)

            # Rarity tag pill
            r_str = f"[{entry['rarity'].upper()}]"
            draw.text((item_text_x, cy_box + 44), r_str, font=fonts["small_bold"], fill=r_color)

            # Stats summary
            stats_parts = []
            if entry["atk"]:
                stats_parts.append(f"+{entry['atk']} ATK")
            if entry["def"]:
                stats_parts.append(f"+{entry['def']} DEF")
            if entry["hp"]:
                stats_parts.append(f"+{entry['hp']} HP")
            if entry["spd"]:
                stats_parts.append(f"+{entry['spd']} SPD")
            stats_desc = " • ".join(stats_parts) if stats_parts else "Crafting & Synthesis Material"

            draw.text((item_text_x + 95, cy_box + 44), f"•  {stats_desc}", font=fonts["small"], fill=HUD_SKY if stats_parts else TEXT_MUTED)

            # Price & Affordability right
            price_box_w = 210
            px1 = WIDTH - 48 - price_box_w - 14
            px2 = WIDTH - 48 - 14

            # Price row with coin icon
            _draw_coin_icon(draw, px1 + 20, cy_box + 30, r=8)
            p_text = f"{entry['price']:,} GOLD"
            draw.text((px1 + 36, cy_box + 20), p_text, font=fonts["price_large"], fill=GOLD_COLOR)

            # Affordability badge
            badge_y = cy_box + 52
            if can_afford:
                draw.rounded_rectangle([px1 + 8, badge_y, px2 - 8, badge_y + 32], radius=4, fill=(16, 42, 28), outline=GREEN_COLOR, width=1)
                draw.text((px1 + 22, badge_y + 8), "READY TO PURCHASE", font=fonts["small_bold"], fill=GREEN_COLOR)
            else:
                diff = entry["price"] - hunter.gold
                draw.rounded_rectangle([px1 + 8, badge_y, px2 - 8, badge_y + 32], radius=4, fill=(38, 16, 22), outline=ALERT_RED, width=1)
                draw.text((px1 + 18, badge_y + 8), f"NEED {diff:,} G MORE", font=fonts["small_bold"], fill=ALERT_RED)

    # ── 6. Bottom System Footer ──
    footer_text = "[ Authorized by the Hunter Association & System Protocol ]"
    tb_f = fonts["footer"].getbbox(footer_text)
    fw = tb_f[2] - tb_f[0]
    draw.text((WIDTH // 2 - fw // 2, HEIGHT - 46), footer_text, font=fonts["footer"], fill=HUD_SKY)

    # Export as pristine PNG
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = f"shop_{active_cat}.png"
    return buf
