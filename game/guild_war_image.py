"""
/* Hallmark · component: guild_war_card · genre: atmospheric · theme: Midnight (Abyssal Monarch) */
game/guild_war_image.py — Solo Leveling Guild War Card Renderers.

Generates stylized, high-resolution RPG Guild War Cards adhering to
the Hallmark Atmospheric Design System and locked design tokens:
- Challenge card: Two guilds face off before war begins
- Status card: Live scoreboard during active war
- Result card: Final outcome with rewards/penalties
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
    INK_PRIMARY,
    INK_SECONDARY,
    INK_MUTED,
    INK_CYAN,
    INK_SKY,
    INK_GOLD,
    INK_RED,
    INK_GREEN,
    INK_PURPLE,
    WAR_RED,
    WAR_GOLD,
    RANK_COLORS,
    draw_atmospheric_canvas,
    draw_hud_corners,
    draw_swords_icon,
    draw_shield_icon,
    draw_diamond,
)
from models import Guild, Hunter

# Canvas dimensions
CHALLENGE_W, CHALLENGE_H = 860, 480
STATUS_W, STATUS_H = 860, 700
RESULT_W, RESULT_H = 860, 600


def _get_fonts():
    bold = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    regular = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]
    return {
        "title": load_font(bold, 26),
        "subtitle": load_font(bold, 13),
        "guild_name": load_font(bold, 20),
        "section": load_font(bold, 13),
        "body": load_font(regular, 13),
        "body_bold": load_font(bold, 13),
        "score_large": load_font(bold, 24),
        "score_medium": load_font(bold, 16),
        "small": load_font(regular, 11),
        "small_bold": load_font(bold, 11),
        "footer": load_font(bold, 12),
        "row_name": load_font(bold, 13),
        "row_stat": load_font(regular, 12),
    }


def _get_owner_name(members: list[Hunter], owner_id: int) -> str:
    for h in members:
        if h.user_id == owner_id:
            return h.display_full_name
    return "Unknown"


def _draw_guild_panel(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    guild: Guild,
    members: list[Hunter],
    x: int, y: int,
    w: int, h: int,
    side: str,  # "left" or "right"
    total_power: int,
    score_label: str = "",
    score_value: str = "",
) -> None:
    """Draw a guild panel for challenge/status cards."""
    border_color = WAR_GOLD if side == "left" else WAR_RED
    draw.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=SURFACE_BASE, outline=border_color, width=2)

    # Shield icon
    shield_x = x + 34 if side == "left" else x + w - 34
    draw_shield_icon(draw, shield_x, y + 30, fill=INK_PURPLE, scale=1.4)

    # Guild name
    name_x = x + 60 if side == "left" else x + 10
    cascade = get_font_cascade(19, is_bold=True)
    clean_gname = clean_and_normalize_name(guild.name)
    if side == "left":
        cascade.draw_text(draw, (name_x, y + 16), clean_gname, fill=INK_PRIMARY, max_w=w - 80)
    else:
        name_w = cascade.get_width(clean_gname, max_w=w - 80)
        cascade.draw_text(draw, (x + w - 60 - name_w, y + 16), clean_gname, fill=INK_PRIMARY, max_w=w - 80)

    # Stats row
    stats_y = y + 52
    stats_text = f"{len(guild.members)}/15  •  ⚡{total_power:,}  •  WAR {guild.war_score}"
    if side == "left":
        draw.text((x + 20, stats_y), stats_text, font=fonts["small"], fill=INK_SECONDARY)
    else:
        draw.text((x + w - 20, stats_y), stats_text, font=fonts["small"], fill=INK_SECONDARY, anchor="rt")

    # Score if provided
    if score_label and score_value:
        score_y = y + 72
        draw.text((x + w // 2, score_y), score_value, font=fonts["score_large"], fill=border_color, anchor="mt")
        draw.text((x + w // 2, score_y + 28), score_label, font=fonts["small"], fill=INK_SECONDARY, anchor="mt")

    # Member count preview
    member_y = y + 100 if score_label else y + 78
    owner_str = clean_and_normalize_name(_get_owner_name(members, guild.owner_id))
    preview_text = f"Master: {owner_str} + {max(0, len(members) - 1)} hunters"
    if side == "left":
        draw.text((x + 20, member_y), preview_text, font=fonts["small"], fill=INK_MUTED)
    else:
        draw.text((x + w - 20, member_y), preview_text, font=fonts["small"], fill=INK_MUTED, anchor="rt")


def render_war_challenge_card(
    challenger_guild: Guild,
    challenger_members: list[Hunter],
    defender_guild: Guild,
    defender_members: list[Hunter],
    challenger_power: int,
    defender_power: int,
) -> io.BytesIO:
    """Render the war challenge card showing two guilds face-off."""
    fonts = _get_fonts()
    img = Image.new("RGBA", (CHALLENGE_W, CHALLENGE_H), CANVAS_TOP)
    draw_atmospheric_canvas(
        img,
        top_color=(20, 10, 22),
        bottom_color=CANVAS_BOTTOM,
        bloom_cx=CHALLENGE_W // 2,
        bloom_cy=140,
        bloom_color=(220, 38, 38, 28),
        bloom_radius=260,
    )
    draw = ImageDraw.Draw(img)

    # Perimeter HUD border
    draw.rectangle([16, 16, CHALLENGE_W - 16, CHALLENGE_H - 16], outline=CANVAS_BORDER, width=1)
    draw_hud_corners(draw, (16, 16, CHALLENGE_W - 16, CHALLENGE_H - 16), color=WAR_GOLD, length=24, width=2)

    cx = CHALLENGE_W // 2
    title = "GUILD WAR DECLARATION // 길드 전면전 선포"
    draw_swords_icon(draw, cx - 220, 38, fill=WAR_GOLD)
    draw_swords_icon(draw, cx + 220, 38, fill=WAR_GOLD)
    draw.text((cx, 26), title, font=fonts["title"], fill=WAR_GOLD, anchor="mt")

    sub = "SYSTEM DIRECTIVE // INTER-GUILD TERRITORY CONQUEST AUTHORIZATION"
    draw.text((cx, 58), sub, font=fonts["small"], fill=INK_SECONDARY, anchor="mt")

    # VS clash
    vs_y = 175
    draw.text((cx, vs_y), "VS", font=fonts["title"], fill=WAR_RED, anchor="mt")

    # Guild panels — left (challenger) and right (defender)
    panel_w = 370
    panel_h = 190
    panel_y = 95

    _draw_guild_panel(draw, fonts, challenger_guild, challenger_members,
                      30, panel_y, panel_w, panel_h, "left", challenger_power)
    _draw_guild_panel(draw, fonts, defender_guild, defender_members,
                      CHALLENGE_W - 30 - panel_w, panel_y, panel_w, panel_h, "right", defender_power)

    # Footer
    draw.text(
        (cx, CHALLENGE_H - 36),
        "「 Two syndicates enter the gate. Only one shall claim victory. 」",
        font=fonts["footer"], fill=INK_SKY, anchor="mt",
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def render_war_status_card(
    challenger_guild: Guild,
    defender_guild: Guild,
    challenger_wins: int,
    defender_wins: int,
    matchups: list[tuple[int, int, Optional[int]]],  # (c_uid, d_uid, winner_uid)
    current_match: int,
    total_matches: int,
    challenger_members: list[Hunter],
    defender_members: list[Hunter],
) -> io.BytesIO:
    """Render the live war status/scoreboard card."""
    fonts = _get_fonts()
    img = Image.new("RGBA", (STATUS_W, STATUS_H), CANVAS_TOP)
    draw_atmospheric_canvas(
        img,
        top_color=(20, 10, 22),
        bottom_color=CANVAS_BOTTOM,
        bloom_cx=STATUS_W // 2,
        bloom_cy=140,
        bloom_color=(234, 179, 8, 22),
        bloom_radius=280,
    )
    draw = ImageDraw.Draw(img)

    # Perimeter HUD border
    draw.rectangle([16, 16, STATUS_W - 16, STATUS_H - 16], outline=CANVAS_BORDER, width=1)
    draw_hud_corners(draw, (16, 16, STATUS_W - 16, STATUS_H - 16), color=WAR_GOLD, length=24, width=2)

    cx = STATUS_W // 2

    # Title
    title = "GUILD WAR SCOREBOARD // 길드전 실시간 전황"
    draw.text((cx, 28), title, font=fonts["title"], fill=WAR_GOLD, anchor="mt")

    # Score display
    score_y = 70
    draw.rounded_rectangle([40, score_y, cx - 24, score_y + 80], radius=10, fill=SURFACE_BASE, outline=WAR_GOLD, width=2)
    draw.text((cx - 70, score_y + 8), f"{challenger_wins}", font=fonts["score_large"], fill=WAR_GOLD, anchor="mt")
    draw.text((cx - 70, score_y + 42), clean_and_normalize_name(challenger_guild.name), font=fonts["small_bold"], fill=INK_PRIMARY, anchor="mt")
    draw.text((cx - 70, score_y + 60), f"WAR {challenger_guild.war_score}", font=fonts["small"], fill=INK_SECONDARY, anchor="mt")

    draw.rounded_rectangle([cx + 24, score_y, STATUS_W - 40, score_y + 80], radius=10, fill=SURFACE_BASE, outline=WAR_RED, width=2)
    draw.text((cx + 70, score_y + 8), f"{defender_wins}", font=fonts["score_large"], fill=WAR_RED, anchor="mt")
    draw.text((cx + 70, score_y + 42), clean_and_normalize_name(defender_guild.name), font=fonts["small_bold"], fill=INK_PRIMARY, anchor="mt")
    draw.text((cx + 70, score_y + 60), f"WAR {defender_guild.war_score}", font=fonts["small"], fill=INK_SECONDARY, anchor="mt")

    # VS
    draw.text((cx, score_y + 25), "VS", font=fonts["body_bold"], fill=INK_PRIMARY, anchor="mt")

    # Progress bar
    progress_y = score_y + 92
    draw.text((cx, progress_y), f"MATCH PROGRESS // {current_match} OF {total_matches}", font=fonts["small_bold"], fill=INK_SKY, anchor="mt")
    bar_y = progress_y + 18
    bar_w = STATUS_W - 100
    bar_h = 8
    draw.rounded_rectangle([50, bar_y, 50 + bar_w, bar_y + bar_h], radius=4, fill=(18, 28, 48))
    filled = int(bar_w * (current_match / max(total_matches, 1)))
    if filled > 0:
        draw.rounded_rectangle([50, bar_y, 50 + filled, bar_y + bar_h], radius=4, fill=WAR_GOLD)

    # Match results table
    table_y = bar_y + 26
    draw.rounded_rectangle([40, table_y, STATUS_W - 40, STATUS_H - 42], radius=10, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
    draw.text((60, table_y + 10), "[ COMBAT ENGAGEMENT LOGS ]", font=fonts["small_bold"], fill=INK_CYAN)
    draw.line([(55, table_y + 30), (STATUS_W - 55, table_y + 30)], fill=SURFACE_BORDER, width=1)

    row_y = table_y + 36
    row_h = 34

    if isinstance(challenger_members, dict):
        challenger_members = list(challenger_members.values())
    if isinstance(defender_members, dict):
        defender_members = list(defender_members.values())

    c_lookup = {h.user_id: h for h in challenger_members}
    d_lookup = {h.user_id: h for h in defender_members}

    for i, (c_uid, d_uid, winner_uid) in enumerate(matchups):
        if row_y > STATUS_H - 70:
            break

        ry = row_y + i * row_h
        if i % 2 == 0:
            draw.rounded_rectangle([48, ry, STATUS_W - 48, ry + row_h], radius=4, fill=SURFACE_ELEVATED)

        # Match number
        draw.text((60, ry + 8), f"#{i + 1}", font=fonts["small_bold"], fill=INK_MUTED)

        # Challenger name
        c_hunter = c_lookup.get(c_uid)
        c_name = clean_and_normalize_name(c_hunter.display_full_name if c_hunter else "Unknown")
        c_color = INK_GREEN if winner_uid == c_uid else (INK_RED if winner_uid and winner_uid != c_uid else INK_SECONDARY)
        cascade_c = get_font_cascade(13, is_bold=True)
        cascade_c.draw_text(draw, (90, ry + 6), c_name, fill=c_color, max_w=200)

        # VS
        draw.text((cx, ry + 8), "vs", font=fonts["small"], fill=INK_MUTED, anchor="mt")

        # Defender name
        d_hunter = d_lookup.get(d_uid)
        d_name = clean_and_normalize_name(d_hunter.display_full_name if d_hunter else "Unknown")
        d_color = INK_GREEN if winner_uid == d_uid else (INK_RED if winner_uid and winner_uid != d_uid else INK_SECONDARY)
        cascade_d = get_font_cascade(13, is_bold=True)
        d_w = cascade_d.get_width(d_name, max_w=200)
        cascade_d.draw_text(draw, (STATUS_W - 90 - d_w, ry + 6), d_name, fill=d_color, max_w=200)

        # Result indicator
        if winner_uid == c_uid:
            draw.text((cx, ry + 20), "WIN", font=fonts["small"], fill=INK_GREEN, anchor="mt")
        elif winner_uid == d_uid:
            draw.text((cx, ry + 20), "WIN", font=fonts["small"], fill=INK_GREEN, anchor="mt")
        else:
            draw.text((cx, ry + 20), "PENDING", font=fonts["small"], fill=INK_MUTED, anchor="mt")

    # Footer
    draw.text(
        (cx, STATUS_H - 26),
        "「 The war continues until all battles are decided. 」",
        font=fonts["footer"], fill=INK_SKY, anchor="mt",
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def render_war_result_card(
    challenger_guild: Guild,
    defender_guild: Guild,
    challenger_wins: int,
    defender_wins: int,
    winner_is_challenger: bool,
    challenger_members: list[Hunter],
    defender_members: list[Hunter],
    gold_reward: int,
    xp_reward: int,
    xp_penalty: int,
) -> io.BytesIO:
    """Render the final war result card."""
    fonts = _get_fonts()
    img = Image.new("RGBA", (RESULT_W, RESULT_H), CANVAS_TOP)
    draw_atmospheric_canvas(
        img,
        top_color=(24, 16, 10),
        bottom_color=CANVAS_BOTTOM,
        bloom_cx=RESULT_W // 2,
        bloom_cy=140,
        bloom_color=(250, 204, 21, 26),
        bloom_radius=280,
    )
    draw = ImageDraw.Draw(img)

    # Perimeter HUD border
    draw.rectangle([16, 16, RESULT_W - 16, RESULT_H - 16], outline=CANVAS_BORDER, width=1)
    draw_hud_corners(draw, (16, 16, RESULT_W - 16, RESULT_H - 16), color=WAR_GOLD, length=24, width=2)

    cx = RESULT_W // 2

    if winner_is_challenger:
        winner_guild = challenger_guild
        loser_guild = defender_guild
    else:
        winner_guild = defender_guild
        loser_guild = challenger_guild

    banner_color = WAR_GOLD
    banner_text = "CONQUEST VICTORY // 승리"

    # Banner
    draw.rounded_rectangle([40, 26, RESULT_W - 40, 96], radius=10, fill=(28, 24, 12, 240), outline=banner_color, width=2)
    draw_swords_icon(draw, cx - 180, 48, fill=banner_color)
    draw_swords_icon(draw, cx + 180, 48, fill=banner_color)
    draw.text((cx, 36), banner_text, font=fonts["title"], fill=banner_color, anchor="mt")
    draw.text((cx, 68), f"🏆 {clean_and_normalize_name(winner_guild.name)} claims dominion!", font=fonts["body_bold"], fill=INK_PRIMARY, anchor="mt")

    # Score summary
    score_y = 112
    draw.rounded_rectangle([40, score_y, RESULT_W - 40, score_y + 70], radius=10, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)

    draw.text((cx, score_y + 8), "FINAL WAR SCORE // 최종 점수", font=fonts["small_bold"], fill=INK_CYAN, anchor="mt")
    draw.text((cx - 100, score_y + 30), f"{challenger_wins}", font=fonts["score_large"], fill=WAR_GOLD, anchor="mt")
    draw.text((cx, score_y + 34), "—", font=fonts["body_bold"], fill=INK_PRIMARY, anchor="mt")
    draw.text((cx + 100, score_y + 30), f"{defender_wins}", font=fonts["score_large"], fill=WAR_RED, anchor="mt")
    draw.text((cx - 100, score_y + 54), clean_and_normalize_name(challenger_guild.name), font=fonts["small"], fill=INK_SECONDARY, anchor="mt")
    draw.text((cx + 100, score_y + 54), clean_and_normalize_name(defender_guild.name), font=fonts["small"], fill=INK_SECONDARY, anchor="mt")

    # Rewards section
    rewards_y = score_y + 86
    draw.rounded_rectangle([40, rewards_y, RESULT_W - 40, rewards_y + 160], radius=10, fill=SURFACE_BASE, outline=SURFACE_BORDER, width=1)
    draw.text((60, rewards_y + 10), "[ WAR BOUNTY & REPUTATION CONSEQUENCES ]", font=fonts["small_bold"], fill=INK_CYAN)
    draw.line([(55, rewards_y + 30), (RESULT_W - 55, rewards_y + 30)], fill=SURFACE_BORDER, width=1)

    # Winner rewards
    wy = rewards_y + 40
    draw.rounded_rectangle([60, wy, cx - 10, wy + 50], radius=6, fill=(18, 38, 24, 220), outline=INK_GREEN, width=1)
    draw.text((70, wy + 5), "👑 VICTORIOUS GUILD", font=fonts["small_bold"], fill=INK_GREEN)
    draw.text((70, wy + 22), f"+{gold_reward:,}💰 per hunter  •  +{xp_reward:,} XP", font=fonts["small"], fill=INK_PRIMARY)
    draw.text((70, wy + 36), f"+50 War Rating  •  War Victories +1", font=fonts["small"], fill=INK_MUTED)

    # Loser penalties
    draw.rounded_rectangle([cx + 10, wy, RESULT_W - 60, wy + 50], radius=6, fill=(38, 16, 20, 220), outline=INK_RED, width=1)
    draw.text((cx + 20, wy + 5), "💀 DEFEATED GUILD", font=fonts["small_bold"], fill=INK_RED)
    draw.text((cx + 20, wy + 22), f"-{xp_penalty:,} XP casualty penalty", font=fonts["small"], fill=INK_PRIMARY)
    draw.text((cx + 20, wy + 36), f"-30 War Rating  •  War Defeats +1", font=fonts["small"], fill=INK_MUTED)

    # Top performers
    performers_y = wy + 65
    draw.text((60, performers_y), "🏅 DISTINGUISHED COMBATANTS // 최우수 전투원:", font=fonts["small_bold"], fill=INK_GOLD)
    draw.line([(55, performers_y + 18), (RESULT_W - 55, performers_y + 18)], fill=SURFACE_BORDER, width=1)

    all_fighters = []
    for h in challenger_members:
        all_fighters.append((h, "left"))
    for h in defender_members:
        all_fighters.append((h, "right"))

    py = performers_y + 24
    for h, side in all_fighters[:5]:
        if py > RESULT_H - 60:
            break
        medal = "🥇" if side == ("left" if winner_is_challenger else "right") else "🥈"
        name_str = clean_and_normalize_name(h.display_full_name)
        draw.text((70, py), f"{medal} {name_str}", font=fonts["row_name"], fill=INK_PRIMARY, max_w=300)
        rank_color = RANK_COLORS.get(h.rank, INK_SECONDARY)
        draw.text((RESULT_W - 70, py), f"Lv.{h.level} [{h.rank}]  ⚡{h.power:,}", font=fonts["row_stat"], fill=rank_color, anchor="rt")
        py += 22

    # Footer
    draw.text(
        (cx, RESULT_H - 26),
        "「 Victory belongs to those who fight as one. 」",
        font=fonts["footer"], fill=INK_SKY, anchor="mt",
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
