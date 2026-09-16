"""
game/help_image.py — Solo Leveling System Operational Manual Image Renderer.

Generates an atmospheric, high-resolution RPG System Manual Card adhering to
Hallmark anti-slop design principles:
- Locked design tokens and elevated surface hierarchy (SURFACE_BASE, SURFACE_ELEVATED)
- Atmospheric radial bloom centered behind the manual header
- High-contrast typography via multi-font cascade (0 tofu boxes)
- Precision vector icons (HUD brackets, Diamonds, Swords, Crown, Coins, Ranks)
- Bento grid layout organizing commands, syndicate protocols, and rank hierarchies.
"""

from __future__ import annotations

import io
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import RANKS, RARITIES
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
    INK_GREEN,
    INK_PURPLE,
    INK_RED,
    RANK_COLORS,
    RARITY_COLORS,
    draw_atmospheric_canvas,
    draw_hud_corners,
    draw_diamond,
    draw_coin_icon,
    draw_swords_icon,
    draw_crown_icon,
)

# Canvas dimensions (860 x 1220 — matches Profile & Shop cards)
WIDTH = 860
HEIGHT = 1220


def generate_help_image() -> io.BytesIO:
    """
    Render a high-resolution, Hallmark-compliant Operational Manual Card.
    Returns in-memory PNG bytes ready for Telegram transmission.
    """
    img = Image.new("RGBA", (WIDTH, HEIGHT), CANVAS_TOP)

    # 1. Atmospheric Canvas with glowing cyan/blue bloom near the top
    draw_atmospheric_canvas(
        img,
        top_color=CANVAS_TOP,
        bottom_color=CANVAS_BOTTOM,
        bloom_cx=WIDTH // 2,
        bloom_cy=140,
        bloom_color=(0, 200, 255, 36),
        bloom_radius=280,
        grid_spacing=60,
    )

    draw = ImageDraw.Draw(img)

    # Outer border & cybernetic HUD corners
    draw.rectangle([10, 10, WIDTH - 10, HEIGHT - 10], outline=CANVAS_BORDER, width=1)
    draw_hud_corners(draw, (10, 10, WIDTH - 10, HEIGHT - 10), color=INK_CYAN, length=24, width=2)

    # Fonts
    font_eyebrow = get_font_cascade(11, is_bold=True)
    font_title = get_font_cascade(28, is_bold=True)
    font_subtitle = get_font_cascade(13, is_bold=False)
    font_section = get_font_cascade(14, is_bold=True)
    font_cmd = get_font_cascade(13, is_bold=True)
    font_desc = get_font_cascade(12, is_bold=False)
    font_badge = get_font_cascade(10, is_bold=True)
    font_footer = get_font_cascade(11, is_bold=True)

    # ── HEADER SECTION ────────────────────────────────────────────────────────
    header_y = 28

    # System Monospace Eyebrow
    draw_diamond(draw, 34, header_y + 8, size=4, fill=INK_CYAN)
    font_eyebrow.draw_text(
        draw,
        (46, header_y + 2),
        "SYSTEM INTERFACE // OPERATIONAL DIRECTIVE // ARCHIVES V2.4",
        fill=INK_CYAN,
    )

    # Status Pill (Right top)
    status_text = "ACCESS // AUTHORIZED"
    st_bb = font_badge.getbbox(status_text)
    st_w = st_bb[2] - st_bb[0] + 24
    draw.rounded_rectangle([WIDTH - 30 - st_w, header_y, WIDTH - 30, header_y + 22], radius=4, fill=SURFACE_ELEVATED, outline=INK_CYAN, width=1)
    draw_diamond(draw, WIDTH - 30 - st_w + 10, header_y + 11, size=3, fill=INK_CYAN)
    font_badge.draw_text(draw, (WIDTH - 30 - st_w + 18, header_y + 5), status_text, fill=INK_PRIMARY)

    # Main Title
    font_title.draw_text(
        draw,
        (34, header_y + 26),
        "HUNTER OPERATIONAL MANUAL",
        fill=INK_PRIMARY,
    )

    # Subtitle
    font_subtitle.draw_text(
        draw,
        (34, header_y + 64),
        "Complete command protocols, dimensional gates, syndicate operations & ascension tiers.",
        fill=INK_SECONDARY,
    )

    # Divider bar
    draw.line([(34, header_y + 92), (WIDTH - 34, header_y + 92)], fill=SURFACE_BORDER, width=1)
    draw.line([(34, header_y + 92), (180, header_y + 92)], fill=INK_CYAN, width=2)

    # ── BENTO CARDS ───────────────────────────────────────────────────────────
    # We organize the guide into 4 high-contrast panels:
    # Top Left: Core Combat & Exploration (W: 386)
    # Top Right: Vault & Dimensional Commerce (W: 386)
    # Mid: Guild Syndicate & Mutual Aid (W: 792)
    # Bottom: Ascension Hierarchy (Ranks & Rarities) (W: 792)

    card_left_x = 34
    card_right_x = 440
    card_w = 386
    card_h = 320
    top_y = 136

    # ── PANEL 1: HUNTER COMBAT & PROGRESSION ─────────────────────────────────
    draw.rounded_rectangle([card_left_x, top_y, card_left_x + card_w, top_y + card_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
    draw_hud_corners(draw, (card_left_x, top_y, card_left_x + card_w, top_y + card_h), color=INK_CYAN, length=12, width=1)

    # Section Header
    draw_diamond(draw, card_left_x + 16, top_y + 18, size=4, fill=INK_CYAN)
    font_section.draw_text(draw, (card_left_x + 28, top_y + 11), "COMBAT & FIELD EXPEDITIONS", fill=INK_PRIMARY)
    draw.line([(card_left_x + 16, top_y + 36), (card_left_x + card_w - 16, top_y + 36)], fill=SURFACE_BORDER, width=1)

    core_cmds = [
        ("/start", "Awaken license & claim starter blade", INK_CYAN),
        ("/hunt", "Slay gate monsters for XP & loot drops (15m CD)", INK_GOLD),
        ("/profile", "Inspect System Status Window, attributes & gear", INK_SKY),
        ("/duel", "Challenge a rival Hunter (reply in group)", INK_RED),
        ("/claim", "Daily Hunter allowance — Gold & XP (24h CD)", INK_GREEN),
    ]

    item_y = top_y + 48
    for cmd, desc, col in core_cmds:
        # Command pill
        c_bb = font_cmd.getbbox(cmd)
        c_w = c_bb[2] - c_bb[0] + 14
        draw.rounded_rectangle([card_left_x + 16, item_y, card_left_x + 16 + c_w, item_y + 20], radius=4, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER_LIGHT, width=1)
        font_cmd.draw_text(draw, (card_left_x + 23, item_y + 3), cmd, fill=col)
        # Description
        font_desc.draw_text(draw, (card_left_x + 16, item_y + 26), desc, fill=INK_SECONDARY, max_w=card_w - 32)
        item_y += 52

    # ── PANEL 2: DIMENSIONAL VAULT & COMMERCE ────────────────────────────────
    draw.rounded_rectangle([card_right_x, top_y, card_right_x + card_w, top_y + card_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
    draw_hud_corners(draw, (card_right_x, top_y, card_right_x + card_w, top_y + card_h), color=INK_CYAN, length=12, width=1)

    draw_diamond(draw, card_right_x + 16, top_y + 18, size=4, fill=INK_GOLD)
    font_section.draw_text(draw, (card_right_x + 28, top_y + 11), "VAULT & EXCHANGE DEPOT", fill=INK_PRIMARY)
    draw.line([(card_right_x + 16, top_y + 36), (card_right_x + card_w - 16, top_y + 36)], fill=SURFACE_BORDER, width=1)

    vault_cmds = [
        ("/inventory", "Interactive storage with 1-tap equip actions", INK_CYAN),
        ("/equip", "Direct alias to inspect and swap loadout", INK_SKY),
        ("/shop", "Acquire weapons, armor, rings & elixirs", INK_GOLD),
        ("/leaderboard", "Global Hall of Fame: Power, Wealth & Kills", INK_PURPLE),
        ("/help", "Transmit this visual operational manual", INK_PRIMARY),
    ]

    item_y = top_y + 48
    for cmd, desc, col in vault_cmds:
        c_bb = font_cmd.getbbox(cmd)
        c_w = c_bb[2] - c_bb[0] + 14
        draw.rounded_rectangle([card_right_x + 16, item_y, card_right_x + 16 + c_w, item_y + 20], radius=4, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER_LIGHT, width=1)
        font_cmd.draw_text(draw, (card_right_x + 23, item_y + 3), cmd, fill=col)
        font_desc.draw_text(draw, (card_right_x + 16, item_y + 26), desc, fill=INK_SECONDARY, max_w=card_w - 32)
        item_y += 52

    # ── PANEL 3: GUILD SYNDICATE & MUTUAL AID ────────────────────────────────
    mid_y = top_y + card_h + 16
    mid_w = WIDTH - 68
    mid_h = 290
    draw.rounded_rectangle([34, mid_y, 34 + mid_w, mid_y + mid_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
    draw_hud_corners(draw, (34, mid_y, 34 + mid_w, mid_y + mid_h), color=INK_CYAN, length=12, width=1)

    # Syndicate header
    draw_crown_icon(draw, 50, mid_y + 18, fill=INK_GOLD, scale=0.9)
    font_section.draw_text(draw, (64, mid_y + 11), "GUILD SYNDICATE OPERATIONS & MUTUAL AID", fill=INK_PRIMARY)

    # Syndicate passive bonus badge
    bonus_text = "PASSIVE: +10% HUNT XP TO ALL GUILD MEMBERS"
    b_bb = font_badge.getbbox(bonus_text)
    b_w = b_bb[2] - b_bb[0] + 20
    draw.rounded_rectangle([34 + mid_w - 16 - b_w, mid_y + 10, 34 + mid_w - 16, mid_y + 28], radius=4, fill=SURFACE_ELEVATED, outline=INK_GREEN, width=1)
    font_badge.draw_text(draw, (34 + mid_w - 16 - b_w + 10, mid_y + 13), bonus_text, fill=INK_GREEN)

    draw.line([(50, mid_y + 36), (34 + mid_w - 16, mid_y + 36)], fill=SURFACE_BORDER, width=1)

    # 2 columns of guild commands inside panel 3
    col1_x = 50
    col2_x = 440
    guild_cmds_col1 = [
        ("/guild create <name>", "Establish your guild (Cost: 500 Gold, max 15 members)", INK_GOLD),
        ("/guild join <name>", "Join an established syndicate for combat buffs", INK_CYAN),
        ("/guild info", "Display syndicate card, roster & war score", INK_SKY),
        ("/guild top", "Inspect top syndicates on the Guild Leaderboard", INK_PURPLE),
    ]

    guild_cmds_col2 = [
        ("/guild war <name>", "Challenge an opposing guild to an all-out war", INK_RED),
        ("/guild leave", "Depart your current syndicate (resets guild XP buff)", INK_SECONDARY),
        ("/gift item <id>", "Transfer an item to a guild comrade (reply in chat)", INK_GREEN),
        ("/gift gold <amount>", "Transfer gold funds to aid your guild comrade", INK_GOLD),
    ]

    gy = mid_y + 48
    for cmd, desc, col in guild_cmds_col1:
        c_bb = font_cmd.getbbox(cmd)
        c_w = c_bb[2] - c_bb[0] + 12
        draw.rounded_rectangle([col1_x, gy, col1_x + c_w, gy + 19], radius=3, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER_LIGHT, width=1)
        font_cmd.draw_text(draw, (col1_x + 6, gy + 3), cmd, fill=col)
        font_desc.draw_text(draw, (col1_x, gy + 24), desc, fill=INK_SECONDARY, max_w=370)
        gy += 56

    gy = mid_y + 48
    for cmd, desc, col in guild_cmds_col2:
        c_bb = font_cmd.getbbox(cmd)
        c_w = c_bb[2] - c_bb[0] + 12
        draw.rounded_rectangle([col2_x, gy, col2_x + c_w, gy + 19], radius=3, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER_LIGHT, width=1)
        font_cmd.draw_text(draw, (col2_x + 6, gy + 3), cmd, fill=col)
        font_desc.draw_text(draw, (col2_x, gy + 24), desc, fill=INK_SECONDARY, max_w=370)
        gy += 56

    # ── PANEL 4: ASCENSION HIERARCHY & ITEM TIERS ─────────────────────────────
    bot_y = mid_y + mid_h + 16
    bot_w = WIDTH - 68
    bot_h = 340
    draw.rounded_rectangle([34, bot_y, 34 + bot_w, bot_y + bot_h], radius=8, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
    draw_hud_corners(draw, (34, bot_y, 34 + bot_w, bot_y + bot_h), color=INK_CYAN, length=12, width=1)

    draw_diamond(draw, 50, bot_y + 18, size=4, fill=INK_CYAN)
    font_section.draw_text(draw, (64, bot_y + 11), "SYSTEM ASCENSION HIERARCHY & ASSET TIERS", fill=INK_PRIMARY)
    draw.line([(50, bot_y + 36), (34 + bot_w - 16, bot_y + 36)], fill=SURFACE_BORDER, width=1)

    # Sub-header: Hunter Ranks
    font_badge.draw_text(draw, (50, bot_y + 46), "HUNTER RANKS (ASCENDING LEVEL MILESTONES)", fill=INK_CYAN)

    rank_ladder = [
        ("E", "Lv 1", RANK_COLORS["E"]),
        ("D", "Lv 10", RANK_COLORS["D"]),
        ("C", "Lv 20", RANK_COLORS["C"]),
        ("B", "Lv 35", RANK_COLORS["B"]),
        ("A", "Lv 50", RANK_COLORS["A"]),
        ("S", "Lv 70", RANK_COLORS["S"]),
        ("SS", "Lv 85", RANK_COLORS["SS"]),
        ("SSS", "Lv 95", RANK_COLORS["SSS"]),
        ("NAT", "Lv 100", RANK_COLORS["National Level"]),
        ("MONARCH", "Lv 120", RANK_COLORS["Monarch"]),
    ]

    rx = 50
    pill_w = 69
    pill_h = 44
    for r_name, req, r_col in rank_ladder:
        draw.rounded_rectangle([rx, bot_y + 64, rx + pill_w, bot_y + 64 + pill_h], radius=4, fill=SURFACE_ELEVATED, outline=r_col, width=1)
        r_bb = font_cmd.getbbox(r_name)
        rw = r_bb[2] - r_bb[0]
        font_cmd.draw_text(draw, (rx + (pill_w - rw) // 2, bot_y + 70), r_name, fill=r_col)
        req_bb = font_badge.getbbox(req)
        reqw = req_bb[2] - req_bb[0]
        font_badge.draw_text(draw, (rx + (pill_w - reqw) // 2, bot_y + 90), req, fill=INK_SECONDARY)
        rx += pill_w + 10

    # Sub-header: Item Rarities & Drop Probabilities
    font_badge.draw_text(draw, (50, bot_y + 128), "ITEM RARITY SPECTRUM & GATE DROP RATES", fill=INK_GOLD)

    rarity_data = [
        ("COMMON", "50%", RARITY_COLORS["Common"]),
        ("UNCOMMON", "25%", RARITY_COLORS["Uncommon"]),
        ("RARE", "15%", RARITY_COLORS["Rare"]),
        ("EPIC", "7%", RARITY_COLORS["Epic"]),
        ("LEGENDARY", "2.5%", RARITY_COLORS["Legendary"]),
        ("MYTHIC", "0.5%", RARITY_COLORS["Mythic"]),
    ]

    rx = 50
    rpill_w = 118
    rpill_h = 44
    for rar_name, rate, rar_col in rarity_data:
        draw.rounded_rectangle([rx, bot_y + 146, rx + rpill_w, bot_y + 146 + rpill_h], radius=4, fill=SURFACE_ELEVATED, outline=rar_col, width=1)
        draw_diamond(draw, rx + 14, bot_y + 168, size=4, fill=rar_col)
        font_cmd.draw_text(draw, (rx + 24, bot_y + 152), rar_name, fill=rar_col)
        font_badge.draw_text(draw, (rx + 24, bot_y + 172), f"DROP: {rate}", fill=INK_SECONDARY)
        rx += rpill_w + 12

    # Core Gameplay Rule Callout Box
    callout_y = bot_y + 208
    callout_w = bot_w - 32
    draw.rounded_rectangle([50, callout_y, 50 + callout_w, callout_y + 112], radius=6, fill=SURFACE_ELEVATED, outline=SURFACE_BORDER, width=1)
    draw_diamond(draw, 66, callout_y + 20, size=3, fill=INK_CYAN)
    font_cmd.draw_text(draw, (78, callout_y + 12), "OPERATIONAL SYSTEM PROTOCOLS & PRIVACY", fill=INK_CYAN)

    tips = [
        "- In group chats, /inventory, /shop & /help open in PM to prevent chat clutter.",
        "- Duels (/duel) are group-exclusive and must be initiated by replying to a target hunter.",
        "- Hunting has a 15-minute gate seal; claims refresh every 24 hours.",
        "- Superadmins can manage hunter attributes, coins, and system balances.",
    ]
    ty = callout_y + 36
    for tip in tips:
        font_desc.draw_text(draw, (66, ty), tip, fill=INK_SECONDARY, max_w=callout_w - 32)
        ty += 18

    # ── FOOTER ────────────────────────────────────────────────────────────────
    footer_y = HEIGHT - 46
    draw.line([(34, footer_y), (WIDTH - 34, footer_y)], fill=SURFACE_BORDER, width=1)

    quote = "「 THE SYSTEM ACKNOWLEDGES THOSE WHO STRIVE TO GROW STRONGER 」"
    q_bb = font_footer.getbbox(quote)
    qw = q_bb[2] - q_bb[0]
    font_footer.draw_text(draw, ((WIDTH - qw) // 2, footer_y + 12), quote, fill=INK_CYAN)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
