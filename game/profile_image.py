"""
game/profile_image.py — Solo Leveling System Status Window Image Renderer.

Generates a stylized, high-resolution RPG Status Card image using Pillow,
replicating the glowing blue/purple HUD aesthetic of Solo Leveling.
Supports user profile photo (PFP) and full name (first name + last name).
"""

from __future__ import annotations

import io
import math
import os
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import RANKS
from models import Hunter, Inventory, Item

# Canvas dimensions (High-DPI 860 x 1180)
WIDTH = 860
HEIGHT = 1180

# Color Palette (Solo Leveling Dark HUD)
BG_TOP = (6, 10, 20)           # Deep abyssal navy
BG_BOTTOM = (3, 5, 12)         # Near pitch black
HUD_CYAN = (0, 229, 255)       # Neon cyan
HUD_BLUE = (37, 99, 235)       # Royal blue
HUD_SKY = (56, 189, 248)       # Sky blue
TEXT_WHITE = (248, 250, 252)   # Bright white
TEXT_MUTED = (148, 163, 184)   # Slate gray
TEXT_DIM = (71, 85, 105)       # Dark slate
CARD_BG = (12, 19, 35, 230)    # Glassy dark navy
CARD_BORDER = (30, 58, 102)    # Border blue

# Rank Colors
RANK_COLORS = {
    "E": (148, 163, 184),             # Slate / Bronze
    "D": (34, 197, 94),               # Emerald Green
    "C": (56, 189, 248),              # Sky Blue
    "B": (168, 85, 247),              # Arcane Purple
    "A": (244, 63, 94),               # Crimson Red
    "S": (251, 191, 36),              # Radiant Gold
    "SS": (245, 158, 11),             # Deep Solar Gold
    "SSS": (239, 68, 68),             # Divine Blood Red
    "National Level": (236, 72, 153), # Electric Pink
    "Monarch": (192, 132, 252),       # Shadow Monarch Violet
}

# Rarity Colors
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

    # Try plain font name lookup by OS
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue

    return ImageFont.load_default()


def _get_fonts():
    """Retrieve styled fonts for different text hierarchies."""
    bold_candidates = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    regular_candidates = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]
    mono_candidates = ["consola.ttf", "consolab.ttf", "cour.ttf"]

    return {
        "title": _load_font(bold_candidates, 30),
        "subtitle": _load_font(bold_candidates, 18),
        "header_tag": _load_font(bold_candidates, 13),
        "name": _load_font(bold_candidates, 26),
        "name_small": _load_font(bold_candidates, 21),
        "rank": _load_font(bold_candidates, 18),
        "body_bold": _load_font(bold_candidates, 15),
        "body": _load_font(regular_candidates, 14),
        "stat_val": _load_font(bold_candidates, 16),
        "stat_label": _load_font(bold_candidates, 14),
        "small": _load_font(regular_candidates, 12),
        "small_bold": _load_font(bold_candidates, 12),
        "mono": _load_font(mono_candidates, 13),
        "footer": _load_font(bold_candidates, 14),
    }


def _draw_gradient_background(img: Image.Image) -> None:
    """Draw vertical dark tech gradient background with subtle blue vignetting."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for y in range(h):
        ratio = y / h
        r = int(BG_TOP[0] * (1 - ratio) + BG_BOTTOM[0] * ratio)
        g = int(BG_TOP[1] * (1 - ratio) + BG_BOTTOM[1] * ratio)
        b = int(BG_TOP[2] * (1 - ratio) + BG_BOTTOM[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

    # Add subtle ambient glow layers
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    # Top center ambient cyan glow
    glow_draw.ellipse([w // 2 - 320, -80, w // 2 + 320, 280], fill=(0, 180, 255, 28))
    # Bottom center ambient purple glow
    glow_draw.ellipse([w // 2 - 280, h - 280, w // 2 + 280, h + 120], fill=(139, 92, 246, 22))
    glow = glow.filter(ImageFilter.GaussianBlur(50))
    img.alpha_composite(glow)


def _draw_tech_border(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int) -> None:
    """Draw modern tech HUD corner brackets and outer border."""
    draw.rectangle([x1, y1, x2, y2], outline=(25, 45, 80, 180), width=1)

    bracket_len = 28
    bracket_width = 3
    cyan = HUD_CYAN

    # Top-Left corner
    draw.line([(x1, y1), (x1 + bracket_len, y1)], fill=cyan, width=bracket_width)
    draw.line([(x1, y1), (x1, y1 + bracket_len)], fill=cyan, width=bracket_width)

    # Top-Right corner
    draw.line([(x2 - bracket_len, y1), (x2, y1)], fill=cyan, width=bracket_width)
    draw.line([(x2, y1), (x2, y1 + bracket_len)], fill=cyan, width=bracket_width)

    # Bottom-Left corner
    draw.line([(x1, y2 - bracket_len), (x1, y2)], fill=cyan, width=bracket_width)
    draw.line([(x1, y2), (x1 + bracket_len, y2)], fill=cyan, width=bracket_width)

    # Bottom-Right corner
    draw.line([(x2 - bracket_len, y2), (x2, y2)], fill=cyan, width=bracket_width)
    draw.line([(x2, y2 - bracket_len), (x2, y2)], fill=cyan, width=bracket_width)


def _draw_card(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, radius: int = 10, fill=CARD_BG, outline=CARD_BORDER) -> None:
    """Draw a styled glassmorphic dark container card."""
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=1)


def _draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 5, fill=HUD_CYAN) -> None:
    """Draw a crisp vector diamond accent."""
    draw.polygon([(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)], fill=fill)


def _draw_coin_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int = 7) -> None:
    """Draw a gold coin icon."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(250, 204, 21), outline=(217, 119, 6), width=1)
    draw.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], outline=(254, 240, 138), width=1)


def _draw_avatar(
    base: Image.Image,
    pfp_image: Optional[Image.Image],
    x: int,
    y: int,
    size: int = 96,
    rank: str = "E",
) -> None:
    """
    Draw a circular profile avatar with anti-aliasing and a rank-colored glowing ring.
    Falls back to a stylized Hunter silhouette if no PFP is provided.
    """
    # 4x supersampled circular mask for anti-aliasing
    mask_scale = 4
    high_size = size * mask_scale
    mask_high = Image.new("L", (high_size, high_size), 0)
    mask_draw = ImageDraw.Draw(mask_high)
    mask_draw.ellipse([0, 0, high_size - 1, high_size - 1], fill=255)
    mask = mask_high.resize((size, size), Image.Resampling.LANCZOS)

    if pfp_image:
        try:
            # Crop to square center
            w, h = pfp_image.size
            dim = min(w, h)
            left = (w - dim) // 2
            top = (h - dim) // 2
            cropped = pfp_image.crop((left, top, left + dim, top + dim))
            avatar_resized = cropped.resize((size, size), Image.Resampling.LANCZOS).convert("RGBA")

            avatar_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            avatar_layer.paste(avatar_resized, (0, 0), mask=mask)
            base.alpha_composite(avatar_layer, (x, y))
        except Exception:
            pfp_image = None

    if not pfp_image:
        # Render sleek Hunter silhouette fallback
        avatar_bg = Image.new("RGBA", (size, size), (15, 23, 42, 255))
        avatar_draw = ImageDraw.Draw(avatar_bg)
        center = size // 2
        # Head
        avatar_draw.ellipse([center - 16, center - 26, center + 16, center + 6], fill=(56, 189, 248, 220))
        # Shoulders
        avatar_draw.chord([center - 32, center + 10, center + 32, center + 50], start=0, end=180, fill=(30, 58, 102, 240))
        avatar_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        avatar_layer.paste(avatar_bg, (0, 0), mask=mask)
        base.alpha_composite(avatar_layer, (x, y))

    # Glowing outer border ring matching rank color
    ring_color = RANK_COLORS.get(rank, HUD_CYAN)
    draw = ImageDraw.Draw(base)
    # Faint outer ring
    draw.ellipse([x - 3, y - 3, x + size + 3, y + size + 3], outline=(ring_color[0], ring_color[1], ring_color[2], 90), width=1)
    # Sharp inner ring
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
    """Draw a smooth rounded progress bar."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=bg_color)
    if maximum > 0 and current > 0:
        fill_pct = min(1.0, max(0.0, current / maximum))
        fill_w = max(h, int(w * fill_pct))
        draw.rounded_rectangle([x, y, x + fill_w, y + h], radius=h // 2, fill=fill_color)


def _draw_stat_row(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    x: int,
    y: int,
    w: int,
    name: str,
    full_name: str,
    val: int,
    max_val: int = 40,
) -> None:
    """Render a single stat line with label, value, and segmented HUD gauge."""
    # Stat Code (e.g. STR)
    draw.text((x, y), name, font=fonts["stat_label"], fill=HUD_SKY)
    # Stat Full Name
    draw.text((x + 45, y + 2), full_name, font=fonts["small"], fill=TEXT_MUTED)

    # Value
    val_str = str(val)
    val_bbox = fonts["stat_val"].getbbox(val_str)
    val_w = val_bbox[2] - val_bbox[0]
    draw.text((x + 160 - val_w, y), val_str, font=fonts["stat_val"], fill=TEXT_WHITE)

    # Bar gauge
    bar_x = x + 175
    bar_w = w - 175
    bar_h = 10
    bar_y = y + 5

    # Gauge track
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=4, fill=(18, 28, 48))

    # Fill
    pct = min(1.0, max(0.05, val / max(max_val, val)))
    fill_len = int(bar_w * pct)
    if fill_len > 4:
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_len, bar_y + bar_h], radius=4, fill=HUD_CYAN)


def render_profile_image(
    hunter: Hunter,
    inventory: Inventory,
    pfp_image: Optional[Image.Image] = None,
    full_name: Optional[str] = None,
) -> io.BytesIO:
    """
    Render a Solo Leveling Status Window image for the given hunter, inventory,
    optional profile photo, and full name (first + last name).
    Returns a BytesIO buffer containing the encoded PNG image.
    """
    # 1. Initialize image with alpha
    base = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    _draw_gradient_background(base)

    draw = ImageDraw.Draw(base)
    fonts = _get_fonts()

    # 2. Outer Tech HUD boundary
    margin = 32
    _draw_tech_border(draw, margin, margin, WIDTH - margin, HEIGHT - margin)

    # 3. Top System Header
    header_y = 52
    tag_text = "S Y S T E M   S T A T U S   W I N D O W"
    tag_bbox = fonts["header_tag"].getbbox(tag_text)
    tag_w = tag_bbox[2] - tag_bbox[0]
    center_x = WIDTH // 2

    # Vector diamonds flanking title
    _draw_diamond(draw, center_x - tag_w // 2 - 20, header_y + 8, size=5, fill=HUD_CYAN)
    _draw_diamond(draw, center_x + tag_w // 2 + 20, header_y + 8, size=5, fill=HUD_CYAN)

    # Decorative header lines
    draw.line([(center_x - 260, header_y + 8), (center_x - tag_w // 2 - 35, header_y + 8)], fill=(0, 180, 255, 120), width=1)
    draw.line([(center_x + tag_w // 2 + 35, header_y + 8), (center_x + 260, header_y + 8)], fill=(0, 180, 255, 120), width=1)
    draw.text((center_x - tag_w // 2, header_y), tag_text, font=fonts["header_tag"], fill=HUD_CYAN)

    # Sub-header notice
    sub_notice = "HUNTER REGISTRY DATABASE"
    sub_bbox = fonts["small"].getbbox(sub_notice)
    sub_w = sub_bbox[2] - sub_bbox[0]
    draw.text((center_x - sub_w // 2, header_y + 22), sub_notice, font=fonts["small"], fill=TEXT_MUTED)

    # 4. Identity Card (Avatar PFP, Name, Rank, Title)
    card1_y = 96
    card1_h = 140
    card_w = WIDTH - (margin + 20) * 2
    card_x = margin + 20
    _draw_card(draw, card_x, card1_y, card_x + card_w, card1_y + card1_h, radius=12)

    # Draw User Avatar (PFP or fallback)
    avatar_size = 96
    avatar_x = card_x + 22
    avatar_y = card1_y + (card1_h - avatar_size) // 2
    _draw_avatar(base, pfp_image, avatar_x, avatar_y, size=avatar_size, rank=hunter.rank)

    # Rank Badge (Right-aligned inside Card 1)
    rank_color = RANK_COLORS.get(hunter.rank, HUD_CYAN)
    rank_badge_text = f"{hunter.rank}-RANK"
    rank_bbox = fonts["rank"].getbbox(rank_badge_text)
    badge_text_w = rank_bbox[2] - rank_bbox[0]
    badge_w = max(130, badge_text_w + 36)
    badge_h = 44
    badge_x = card_x + card_w - badge_w - 24
    badge_y = card1_y + 28

    # Draw Rank Badge container
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
        radius=8,
        fill=(rank_color[0] // 5, rank_color[1] // 5, rank_color[2] // 5, 200),
        outline=rank_color,
        width=2,
    )
    draw.text((badge_x + (badge_w - badge_text_w) // 2, badge_y + 11), rank_badge_text, font=fonts["rank"], fill=rank_color)

    # Rank category caption under badge
    rank_cap = "HUNTER CLASS"
    cap_bbox = fonts["small_bold"].getbbox(rank_cap)
    cap_w = cap_bbox[2] - cap_bbox[0]
    draw.text((badge_x + (badge_w - cap_w) // 2, badge_y + 54), rank_cap, font=fonts["small_bold"], fill=TEXT_MUTED)

    # Text Block (Next to Avatar, before Rank Badge)
    text_x = avatar_x + avatar_size + 20
    max_text_w = badge_x - text_x - 16

    # Determine display name (User's First + Last name if available, else hunter_name)
    primary_name = full_name.strip() if full_name and full_name.strip() else hunter.hunter_name

    # Check if primary name fits, otherwise use smaller font or truncate
    name_font = fonts["name"]
    name_bbox = name_font.getbbox(primary_name)
    if (name_bbox[2] - name_bbox[0]) > max_text_w:
        name_font = fonts["name_small"]
        name_bbox = name_font.getbbox(primary_name)
        if (name_bbox[2] - name_bbox[0]) > max_text_w:
            while len(primary_name) > 3 and (name_font.getbbox(primary_name + "...")[2] - name_font.getbbox(primary_name + "...")[0]) > max_text_w:
                primary_name = primary_name[:-1]
            primary_name += "..."

    draw.text((text_x, card1_y + 22), primary_name, font=name_font, fill=TEXT_WHITE)

    # Sub-header line: Hunter Codename & Title
    if full_name and full_name.strip().lower() != hunter.hunter_name.strip().lower():
        title_text = f"Hunter: {hunter.hunter_name} • {hunter.title}"
    else:
        title_text = f"Title: {hunter.title}"

    # Truncate title if too long
    t_bbox = fonts["body_bold"].getbbox(title_text)
    if (t_bbox[2] - t_bbox[0]) > max_text_w:
        while len(title_text) > 5 and (fonts["body_bold"].getbbox(title_text + "...")[2] - fonts["body_bold"].getbbox(title_text + "...")[0]) > max_text_w:
            title_text = title_text[:-1]
        title_text += "..."

    draw.text((text_x, card1_y + 60), title_text, font=fonts["body_bold"], fill=HUD_SKY)

    # Username or User ID tag
    user_tag = f"@{hunter.username}" if hunter.username else f"ID: {hunter.user_id}"
    draw.text((text_x, card1_y + 88), user_tag, font=fonts["small"], fill=TEXT_MUTED)

    # 5. Vitals & Progression (Level, Power, HP, XP)
    card2_y = card1_y + card1_h + 16
    card2_h = 175
    _draw_card(draw, card_x, card2_y, card_x + card_w, card2_y + card2_h, radius=12)

    # Calculate equipment power bonus
    weapon = inventory.get_equipped("weapon")
    armor = inventory.get_equipped("armor")
    accessory = inventory.get_equipped("accessory")
    equip_power = sum(
        (i.atk_bonus + i.def_bonus + i.hp_bonus + i.spd_bonus)
        for i in [weapon, armor, accessory]
        if i
    )

    # Left Column: Level
    draw.text((card_x + 24, card2_y + 18), "CURRENT LEVEL", font=fonts["small_bold"], fill=TEXT_MUTED)
    draw.text((card_x + 24, card2_y + 36), f"Lv. {hunter.level}", font=fonts["title"], fill=HUD_CYAN)

    # Right Column: Power
    draw.text((card_x + card_w // 2, card2_y + 18), "COMBAT POWER", font=fonts["small_bold"], fill=TEXT_MUTED)
    power_str = f"{hunter.power}"
    draw.text((card_x + card_w // 2, card2_y + 36), power_str, font=fonts["title"], fill=(251, 191, 36))
    if equip_power > 0:
        p_bbox = fonts["title"].getbbox(power_str)
        p_w = p_bbox[2] - p_bbox[0]
        draw.text((card_x + card_w // 2 + p_w + 10, card2_y + 46), f"(+{equip_power})", font=fonts["body_bold"], fill=(34, 197, 94))

    # Divider line
    draw.line([(card_x + 24, card2_y + 82), (card_x + card_w - 24, card2_y + 82)], fill=(25, 45, 80), width=1)

    # HP Progress Bar
    bar_width = card_w - 48
    hp_y = card2_y + 94
    draw.text((card_x + 24, hp_y), "HP", font=fonts["body_bold"], fill=(239, 68, 68))
    hp_text = f"{hunter.hp} / {hunter.max_hp}"
    hp_bbox = fonts["body_bold"].getbbox(hp_text)
    hp_tw = hp_bbox[2] - hp_bbox[0]
    draw.text((card_x + card_w - 24 - hp_tw, hp_y), hp_text, font=fonts["body_bold"], fill=TEXT_WHITE)
    _draw_progress_bar(draw, card_x + 24, hp_y + 20, bar_width, 10, hunter.hp, hunter.max_hp, fill_color=(239, 68, 68))

    # XP Progress Bar
    xp_y = hp_y + 38
    draw.text((card_x + 24, xp_y), "EXP", font=fonts["body_bold"], fill=HUD_SKY)
    xp_pct = int((hunter.xp / hunter.xp_needed) * 100) if hunter.xp_needed > 0 else 0
    xp_text = f"{hunter.xp} / {hunter.xp_needed}  ({xp_pct}%)"
    xp_bbox = fonts["body_bold"].getbbox(xp_text)
    xp_tw = xp_bbox[2] - xp_bbox[0]
    draw.text((card_x + card_w - 24 - xp_tw, xp_y), xp_text, font=fonts["body_bold"], fill=TEXT_WHITE)
    _draw_progress_bar(draw, card_x + 24, xp_y + 20, bar_width, 10, hunter.xp, hunter.xp_needed, fill_color=HUD_CYAN)

    # 6. Attributes / Stats Matrix
    card3_y = card2_y + card2_h + 16
    card3_h = 210
    _draw_card(draw, card_x, card3_y, card_x + card_w, card3_y + card3_h, radius=12)

    _draw_diamond(draw, card_x + 30, card3_y + 26, size=4, fill=HUD_SKY)
    draw.text((card_x + 42, card3_y + 16), "ABILITY MATRIX", font=fonts["subtitle"], fill=HUD_SKY)

    stats_list = [
        ("STR", "Strength", hunter.str_stat),
        ("AGI", "Agility", hunter.agi),
        ("VIT", "Vitality", hunter.vit),
        ("INT", "Intelligence", hunter.int_stat),
        ("PER", "Perception", hunter.per),
    ]
    max_stat = max(max(s[2] for s in stats_list), 30)

    stat_row_y = card3_y + 48
    stat_spacing = 31
    for i, (code, full, val) in enumerate(stats_list):
        _draw_stat_row(draw, fonts, card_x + 24, stat_row_y + i * stat_spacing, card_w - 48, code, full, val, max_val=max_stat)

    # 7. Equipped Gear Slots
    card4_y = card3_y + card3_h + 16
    card4_h = 195
    _draw_card(draw, card_x, card4_y, card_x + card_w, card4_y + card4_h, radius=12)

    _draw_diamond(draw, card_x + 30, card4_y + 26, size=4, fill=HUD_SKY)
    draw.text((card_x + 42, card4_y + 16), "EQUIPMENT SLOTS", font=fonts["subtitle"], fill=HUD_SKY)

    def draw_equip_slot(slot_name: str, item: Optional[Item], sy: int):
        slot_bg_w = card_w - 48
        draw.rounded_rectangle([card_x + 24, sy, card_x + 24 + slot_bg_w, sy + 38], radius=6, fill=(15, 24, 42), outline=(28, 48, 80))

        # Slot Type Tag
        draw.text((card_x + 36, sy + 11), f"[{slot_name}]", font=fonts["small_bold"], fill=HUD_SKY)

        if item:
            r_color = RARITY_COLORS.get(item.rarity, TEXT_WHITE)
            draw.text((card_x + 140, sy + 10), item.name, font=fonts["body_bold"], fill=TEXT_WHITE)

            # Rarity tag
            draw.text((card_x + 370, sy + 11), f"[{item.rarity}]", font=fonts["small_bold"], fill=r_color)

            # Stats summary
            summary = item.stat_summary() or "No Bonus"
            sum_bbox = fonts["small"].getbbox(summary)
            sum_w = sum_bbox[2] - sum_bbox[0]
            draw.text((card_x + 24 + slot_bg_w - sum_w - 14, sy + 11), summary, font=fonts["small"], fill=(34, 197, 94))
        else:
            draw.text((card_x + 140, sy + 11), "-- Empty Slot --", font=fonts["small"], fill=TEXT_DIM)

    gear_y = card4_y + 48
    draw_equip_slot("WEAPON", weapon, gear_y)
    draw_equip_slot("ARMOR", armor, gear_y + 46)
    draw_equip_slot("ACCESSORY", accessory, gear_y + 92)

    # 8. Records / Summary Badges
    card5_y = card4_y + card4_h + 16
    card5_h = 120
    _draw_card(draw, card_x, card5_y, card_x + card_w, card5_y + card5_h, radius=12)

    col_w = (card_w - 30) // 4
    win_rate = "—"
    if hunter.total_hunts > 0:
        wr = (hunter.victories / hunter.total_hunts) * 100
        win_rate = f"{wr:.0f}%"

    gold_str = f"{hunter.gold:,} G"
    metrics = [
        ("GOLD", gold_str, (250, 204, 21)),
        ("INVENTORY", f"{len(inventory.items)} Items", TEXT_WHITE),
        ("TOTAL HUNTS", f"{hunter.total_hunts}", HUD_SKY),
        ("WIN RATE", f"{win_rate}", (34, 197, 94)),
    ]

    for idx, (label, val_str, val_color) in enumerate(metrics):
        cx = card_x + 15 + idx * col_w
        cy = card5_y + 20

        draw.text((cx + 12, cy), label, font=fonts["small_bold"], fill=TEXT_MUTED)
        draw.text((cx + 12, cy + 22), val_str, font=fonts["body_bold"], fill=val_color)

        # Draw gold coin icon for Gold column
        if idx == 0:
            val_bbox = fonts["body_bold"].getbbox(val_str)
            vw = val_bbox[2] - val_bbox[0]
            _draw_coin_icon(draw, cx + 12 + vw + 12, cy + 30, r=6)

        if idx == 3 and hunter.total_hunts > 0:
            draw.text((cx + 12, cy + 46), f"W:{hunter.victories}  L:{hunter.defeats}", font=fonts["small"], fill=TEXT_MUTED)
        elif idx == 0:
            draw.text((cx + 12, cy + 46), "Available funds", font=fonts["small"], fill=TEXT_DIM)
        elif idx == 1:
            equipped_count = sum(1 for i in inventory.items if i.is_equipped)
            draw.text((cx + 12, cy + 46), f"{equipped_count} Equipped", font=fonts["small"], fill=TEXT_DIM)
        elif idx == 2:
            draw.text((cx + 12, cy + 46), "Dungeon clears", font=fonts["small"], fill=TEXT_DIM)

        # Subtle vertical separator between columns
        if idx < 3:
            sep_x = cx + col_w - 4
            draw.line([(sep_x, cy + 4), (sep_x, cy + 64)], fill=(25, 45, 80), width=1)

    # 9. System Footer
    footer_text = "[ The System sees all, Hunter. ]"
    f_bbox = fonts["footer"].getbbox(footer_text)
    f_w = f_bbox[2] - f_bbox[0]
    draw.text((center_x - f_w // 2, HEIGHT - margin - 36), footer_text, font=fonts["footer"], fill=HUD_SKY)

    watermark = "SOLO LEVELING HUNTER SYSTEM"
    wm_bbox = fonts["small"].getbbox(watermark)
    wm_w = wm_bbox[2] - wm_bbox[0]
    draw.text((center_x - wm_w // 2, HEIGHT - margin - 18), watermark, font=fonts["small"], fill=TEXT_DIM)

    # 10. Save to in-memory BytesIO
    buf = io.BytesIO()
    base.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
