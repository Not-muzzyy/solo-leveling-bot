"""
/* Hallmark · component: guild_leaderboard_card · genre: atmospheric · theme: Midnight (Abyssal Monarch) */
game/guild_leaderboard_image.py — Solo Leveling Visual Guild Leaderboard Card Renderer.

Generates a stylized, high-resolution RPG Guild Leaderboard Card using Pillow,
showcasing the top-ranked guilds by Total Power, Average Level, Total Wealth, or Member Count.
Adheres strictly to Hallmark Atmospheric Design System and locked design tokens.
"""

from __future__ import annotations

import io
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from game.font_manager import get_font_cascade, clean_and_normalize_name, load_font
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
    INK_PURPLE,
    SILVER_COLOR,
    BRONZE_COLOR,
    draw_atmospheric_canvas,
    draw_hud_corners,
    draw_diamond,
    draw_crown_icon,
    draw_coin_icon,
    draw_shield_icon,
)

# Canvas dimensions (860 x 1060)
WIDTH = 860
HEIGHT = 1060

CATEGORIES = [
    ("power", "COMBAT POWER"),
    ("level", "AVG LEVEL"),
    ("wealth", "TOTAL GOLD"),
    ("members", "MEMBERS"),
]


def _get_fonts():
    bold = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    regular = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]
    return {
        "title": load_font(bold, 24),
        "subtitle": load_font(bold, 13),
        "tag": load_font(bold, 12),
        "name_first": load_font(bold, 20),
        "name_podium": load_font(bold, 17),
        "name_row": load_font(bold, 15),
        "score_large": load_font(bold, 20),
        "score_medium": load_font(bold, 16),
        "score_small": load_font(bold, 14),
        "body_bold": load_font(bold, 13),
        "body": load_font(regular, 13),
        "small_bold": load_font(bold, 11),
        "small": load_font(regular, 11),
        "footer": load_font(bold, 12),
    }


def _get_guild_score(guild_data: dict, category: str) -> tuple[str, str]:
    """Return (score_string, unit_label) for a guild aggregate dict."""
    if category == "level":
        return f"{guild_data['avg_level']:.1f}", "AVG LEVEL"
    elif category == "wealth":
        val = guild_data["total_gold"]
        return f"{val:,}", "TOTAL GOLD"
    elif category == "members":
        return f"{guild_data['member_count']}", f"/ 15 MEMBERS"
    else:  # power
        val = guild_data["total_power"]
        return f"{val:,}", "TOTAL POWER"


def render_guild_leaderboard_image(
    guilds_data: list[dict],
    category: str = "power",
    viewer_guild_id: Optional[int] = None,
) -> io.BytesIO:
    """
    Generate a high-definition static Guild Leaderboard Card.

    guilds_data: list of dicts, each with keys:
        name, owner_name, member_count, total_power, avg_level, total_gold, guild_id
    Already sorted descending by caller.
    """
    fonts = _get_fonts()
    img = Image.new("RGBA", (WIDTH, HEIGHT), CANVAS_TOP)
    draw_atmospheric_canvas(
        img,
        top_color=CANVAS_TOP,
        bottom_color=CANVAS_BOTTOM,
        bloom_cx=WIDTH // 2,
        bloom_cy=140,
        bloom_color=(250, 204, 21, 22),
        bloom_radius=280,
    )
    draw = ImageDraw.Draw(img)

    # Perimeter HUD border
    draw.rectangle([18, 18, WIDTH - 18, HEIGHT - 18], outline=CANVAS_BORDER, width=1)
    draw_hud_corners(draw, (18, 18, WIDTH - 18, HEIGHT - 18), color=INK_GOLD, length=24, width=2)

    # ── Header ──
    cx = WIDTH // 2
    sub_title = "SYSTEM DIRECTIVE // SYNDICATE STRIKE FORCE REGISTRY"
    tb_sub = fonts["subtitle"].getbbox(sub_title)
    sub_w = tb_sub[2] - tb_sub[0]
    draw_diamond(draw, cx - sub_w // 2 - 14, 34, size=4, fill=INK_GOLD)
    draw_diamond(draw, cx + sub_w // 2 + 14, 34, size=4, fill=INK_GOLD)
    draw.text((cx - sub_w // 2, 26), sub_title, font=fonts["subtitle"], fill=INK_GOLD)

    main_title = "GUILD RANKINGS // 세계 길드 순위"
    tb = fonts["title"].getbbox(main_title)
    tw = tb[2] - tb[0]
    draw.text((WIDTH // 2 - tw // 2, 48), main_title, font=fonts["title"], fill=INK_PRIMARY)

    tag_text = "National Hunter Association — Official Guild Registry"
    tb_tag = fonts["small"].getbbox(tag_text)
    draw.text((WIDTH // 2 - (tb_tag[2] - tb_tag[0]) // 2, 80), tag_text, font=fonts["small"], fill=INK_SKY)

    # ── Category Tabs ──
    tab_y = 104
    tab_h = 36
    num_tabs = len(CATEGORIES)
    total_tabs_w = WIDTH - 64
    spacing = 8
    tab_w = (total_tabs_w - (num_tabs - 1) * spacing) // num_tabs

    for idx, (cat_key, cat_label) in enumerate(CATEGORIES):
        tx1 = 32 + idx * (tab_w + spacing)
        tx2 = tx1 + tab_w
        is_active = (cat_key == category)

        if is_active:
            tab_fill = SURFACE_ACCENT
            tab_border = INK_CYAN
            tab_text_color = INK_CYAN
            border_w = 2
        else:
            tab_fill = SURFACE_BASE
            tab_border = SURFACE_BORDER
            tab_text_color = INK_SECONDARY
            border_w = 1

        draw.rounded_rectangle([tx1, tab_y, tx2, tab_y + tab_h], radius=6, fill=tab_fill, outline=tab_border, width=border_w)
        tb_c = fonts["small_bold"].getbbox(cat_label)
        cw = tb_c[2] - tb_c[0]
        draw.text((tx1 + (tab_w - cw) // 2, tab_y + 10), cat_label, font=fonts["small_bold"], fill=tab_text_color)

    # ── Podium #1 ──
    y_p1 = 152
    h_p1 = 96
    g1 = guilds_data[0] if len(guilds_data) > 0 else None

    draw.rounded_rectangle([32, y_p1, WIDTH - 32, y_p1 + h_p1], radius=10, fill=(28, 24, 12, 240), outline=INK_GOLD, width=2)
    draw.rounded_rectangle([46, y_p1 + 14, 114, y_p1 + h_p1 - 14], radius=8, fill=(48, 38, 14), outline=INK_GOLD, width=1)
    draw_crown_icon(draw, 80, y_p1 + 34, fill=INK_GOLD, scale=1.0)
    draw.text((64, y_p1 + 48), "1ST", font=fonts["subtitle"], fill=INK_GOLD)

    if g1:
        cascade_1 = get_font_cascade(20, is_bold=True)
        cascade_1.draw_text(draw, (130, y_p1 + 18), clean_and_normalize_name(g1["name"]), fill=INK_PRIMARY, max_w=400)

        draw.text((130, y_p1 + 48), f"Master: {clean_and_normalize_name(g1['owner_name'])}", font=fonts["body"], fill=INK_SECONDARY)
        draw.text((130, y_p1 + 66), f"{g1['member_count']}/15 Members", font=fonts["small"], fill=INK_MUTED)

        score_val, score_unit = _get_guild_score(g1, category)
        tb_s1 = fonts["score_large"].getbbox(score_val)
        sw_1 = tb_s1[2] - tb_s1[0]
        draw.text((WIDTH - 50 - sw_1, y_p1 + 22), score_val, font=fonts["score_large"], fill=INK_GOLD)
        tb_u1 = fonts["small_bold"].getbbox(score_unit)
        uw_1 = tb_u1[2] - tb_u1[0]
        draw.text((WIDTH - 50 - uw_1, y_p1 + 50), score_unit, font=fonts["small_bold"], fill=INK_SKY)
    else:
        draw.text((130, y_p1 + 36), "No Guilds Yet", font=fonts["name_first"], fill=INK_SECONDARY)

    # ── Podium #2 ──
    y_p2 = y_p1 + h_p1 + 10
    h_p2 = 78
    g2 = guilds_data[1] if len(guilds_data) > 1 else None

    draw.rounded_rectangle([32, y_p2, WIDTH - 32, y_p2 + h_p2], radius=8, fill=SURFACE_ELEVATED, outline=SILVER_COLOR, width=1)
    draw.rounded_rectangle([46, y_p2 + 12, 114, y_p2 + h_p2 - 12], radius=6, fill=SURFACE_ACCENT, outline=SILVER_COLOR, width=1)
    draw_diamond(draw, 80, y_p2 + 25, size=4, fill=SILVER_COLOR)
    draw.text((64, y_p2 + 36), "2ND", font=fonts["body_bold"], fill=SILVER_COLOR)

    if g2:
        cascade_2 = get_font_cascade(17, is_bold=True)
        cascade_2.draw_text(draw, (130, y_p2 + 14), clean_and_normalize_name(g2["name"]), fill=INK_PRIMARY, max_w=400)
        draw.text((130, y_p2 + 42), f"{g2['member_count']}/15 Members ┊ Master: {clean_and_normalize_name(g2['owner_name'])}", font=fonts["small"], fill=INK_SECONDARY)

        score_val, score_unit = _get_guild_score(g2, category)
        tb_s2 = fonts["score_medium"].getbbox(score_val)
        sw_2 = tb_s2[2] - tb_s2[0]
        draw.text((WIDTH - 50 - sw_2, y_p2 + 16), score_val, font=fonts["score_medium"], fill=SILVER_COLOR)
        tb_u2 = fonts["small_bold"].getbbox(score_unit)
        uw_2 = tb_u2[2] - tb_u2[0]
        draw.text((WIDTH - 50 - uw_2, y_p2 + 40), score_unit, font=fonts["small_bold"], fill=INK_SKY)
    else:
        draw.text((130, y_p2 + 28), "Vacant", font=fonts["body_bold"], fill=INK_SECONDARY)

    # ── Podium #3 ──
    y_p3 = y_p2 + h_p2 + 10
    h_p3 = 78
    g3 = guilds_data[2] if len(guilds_data) > 2 else None

    draw.rounded_rectangle([32, y_p3, WIDTH - 32, y_p3 + h_p3], radius=8, fill=SURFACE_ELEVATED, outline=BRONZE_COLOR, width=1)
    draw.rounded_rectangle([46, y_p3 + 12, 114, y_p3 + h_p3 - 12], radius=6, fill=SURFACE_ACCENT, outline=BRONZE_COLOR, width=1)
    draw_diamond(draw, 80, y_p3 + 25, size=4, fill=BRONZE_COLOR)
    draw.text((64, y_p3 + 36), "3RD", font=fonts["body_bold"], fill=BRONZE_COLOR)

    if g3:
        cascade_3 = get_font_cascade(17, is_bold=True)
        cascade_3.draw_text(draw, (130, y_p3 + 14), clean_and_normalize_name(g3["name"]), fill=INK_PRIMARY, max_w=400)
        draw.text((130, y_p3 + 42), f"{g3['member_count']}/15 Members ┊ Master: {clean_and_normalize_name(g3['owner_name'])}", font=fonts["small"], fill=INK_SECONDARY)

        score_val, score_unit = _get_guild_score(g3, category)
        tb_s3 = fonts["score_medium"].getbbox(score_val)
        sw_3 = tb_s3[2] - tb_s3[0]
        draw.text((WIDTH - 50 - sw_3, y_p3 + 16), score_val, font=fonts["score_medium"], fill=BRONZE_COLOR)
        tb_u3 = fonts["small_bold"].getbbox(score_unit)
        uw_3 = tb_u3[2] - tb_u3[0]
        draw.text((WIDTH - 50 - uw_3, y_p3 + 40), score_unit, font=fonts["small_bold"], fill=INK_SKY)
    else:
        draw.text((130, y_p3 + 28), "Vacant", font=fonts["body_bold"], fill=INK_SECONDARY)

    # ── Rows #4–#10 ──
    list_y = y_p3 + h_p3 + 14
    list_h = 490
    draw.rounded_rectangle([32, list_y, WIDTH - 32, list_y + list_h], radius=10, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)

    draw.text((50, list_y + 14), "[ ELITE GUILDS #4 - #10 ]", font=fonts["tag"], fill=INK_CYAN)
    draw.line([(48, list_y + 36), (WIDTH - 48, list_y + 36)], fill=SURFACE_BORDER, width=1)

    row_start_y = list_y + 42
    row_h = 58
    for idx in range(3, 10):
        pos = idx + 1
        ry = row_start_y + (idx - 3) * row_h
        g_entry = guilds_data[idx] if idx < len(guilds_data) else None

        if idx % 2 == 0:
            draw.rounded_rectangle([44, ry + 2, WIDTH - 44, ry + row_h - 2], radius=6, fill=SURFACE_ELEVATED)

        # Position badge
        draw.rounded_rectangle([52, ry + 12, 92, ry + row_h - 12], radius=4, fill=SURFACE_BASE, outline=SURFACE_BORDER)
        draw.text((60, ry + 17), f"#{pos}", font=fonts["small_bold"], fill=INK_SKY)

        if g_entry:
            cascade_row = get_font_cascade(15, is_bold=True)
            cascade_row.draw_text(draw, (108, ry + 11), clean_and_normalize_name(g_entry["name"]), fill=INK_PRIMARY, max_w=380)

            draw.text((108, ry + 33), f"{g_entry['member_count']}/15  •  Master: {clean_and_normalize_name(g_entry['owner_name'])}", font=fonts["small"], fill=INK_SECONDARY)

            s_val, s_unit = _get_guild_score(g_entry, category)
            full_score = f"{s_val} {s_unit}"
            tb_fs = fonts["score_small"].getbbox(full_score)
            fsw = tb_fs[2] - tb_fs[0]
            draw.text((WIDTH - 56 - fsw, ry + 18), full_score, font=fonts["score_small"], fill=INK_CYAN)
        else:
            draw.text((108, ry + 20), "— Vacant Position —", font=fonts["body"], fill=INK_MUTED)

    # ── Viewer's Guild Standing ──
    user_y = list_y + list_h + 14
    user_h = 60
    draw.rounded_rectangle([32, user_y, WIDTH - 32, user_y + user_h], radius=8, fill=SURFACE_ELEVATED, outline=INK_CYAN, width=2)

    draw_diamond(draw, 50, user_y + 20, size=4, fill=INK_CYAN)
    draw.text((62, user_y + 10), "[ YOUR GUILD'S STANDING ]", font=fonts["small_bold"], fill=INK_CYAN)

    if viewer_guild_id is not None:
        try:
            my_idx = next(i for i, g in enumerate(guilds_data) if g["guild_id"] == viewer_guild_id)
            my_guild = guilds_data[my_idx]
            my_rank_str = f"#{my_idx + 1}"
            draw.text((50, user_y + 32), f"{my_rank_str}  •  {clean_and_normalize_name(my_guild['name'])}", font=fonts["body_bold"], fill=INK_PRIMARY)
            s_val, s_unit = _get_guild_score(my_guild, category)
            tb_my = fonts["score_medium"].getbbox(f"{s_val} {s_unit}")
            mw = tb_my[2] - tb_my[0]
            draw.text((WIDTH - 50 - mw, user_y + 22), f"{s_val} {s_unit}", font=fonts["score_medium"], fill=INK_GOLD)
        except StopIteration:
            draw.text((50, user_y + 28), "Your guild is not yet ranked. Grow stronger together!", font=fonts["body"], fill=INK_SECONDARY)
    else:
        draw.text((50, user_y + 22), "Join a guild with /guild join to see your standing here.", font=fonts["body"], fill=INK_SECONDARY)

    # ── Footer ──
    footer_text = "[ A guild's strength is measured by the bonds of its hunters. ]"
    tb_f = fonts["footer"].getbbox(footer_text)
    fw = tb_f[2] - tb_f[0]
    draw.text((WIDTH // 2 - fw // 2, HEIGHT - 34), footer_text, font=fonts["footer"], fill=INK_SKY)

    # Export
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = f"guild_leaderboard_{category}.png"
    return buf
