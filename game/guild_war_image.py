"""
game/guild_war_image.py — Solo Leveling Guild War Card Renderers.

Generates stylized, high-resolution RPG Guild War Cards using Pillow:
- Challenge card: Two guilds face off before war begins
- Status card: Live scoreboard during active war
- Result card: Final outcome with rewards/penalties
"""

from __future__ import annotations

import io
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from game.font_manager import get_font_cascade, clean_and_normalize_name, load_font
from models import Guild, Hunter

# Canvas dimensions
CHALLENGE_W, CHALLENGE_H = 860, 480
STATUS_W, STATUS_H = 860, 700
RESULT_W, RESULT_H = 860, 600

# Color Palette
BG_TOP = (7, 11, 24)
BG_BOTTOM = (3, 6, 15)
HUD_CYAN = (0, 229, 255)
GOLD_COLOR = (250, 204, 21)
RED_COLOR = (239, 68, 68)
GREEN_COLOR = (34, 197, 94)
TEXT_WHITE = (248, 250, 252)
TEXT_MUTED = (148, 163, 184)
TEXT_DIM = (71, 85, 105)
CARD_BG = (13, 20, 36, 235)
CARD_BORDER = (30, 58, 102)
GUILD_PURPLE = (168, 85, 247)
WAR_RED = (180, 40, 40)
WAR_GOLD = (220, 180, 40)

RANK_COLORS = {
    "E": (148, 163, 184), "D": (34, 197, 94), "C": (56, 189, 248),
    "B": (168, 85, 247), "A": (244, 63, 94), "S": (251, 191, 36),
    "SS": (245, 158, 11), "SSS": (239, 68, 68), "National Level": (236, 72, 153),
    "Monarch": (192, 132, 252),
}


def _get_fonts():
    bold = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahoma.ttf"]
    regular = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]
    return {
        "title": load_font(bold, 28),
        "subtitle": load_font(bold, 14),
        "guild_name": load_font(bold, 22),
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


def _draw_gradient_bg(img: Image.Image) -> None:
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for y in range(h):
        ratio = y / h
        r = int(BG_TOP[0] * (1 - ratio) + BG_BOTTOM[0] * ratio)
        g = int(BG_TOP[1] * (1 - ratio) + BG_BOTTOM[1] * ratio)
        b = int(BG_TOP[2] * (1 - ratio) + BG_BOTTOM[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([w // 2 - 250, -50, w // 2 + 250, 180], fill=(180, 40, 40, 20))
    gd.ellipse([w // 2 - 200, h - 150, w // 2 + 200, h + 50], fill=(220, 180, 40, 15))
    glow = glow.filter(ImageFilter.GaussianBlur(35))
    img.alpha_composite(glow)


def _draw_tech_border(draw: ImageDraw.ImageDraw, x1, y1, x2, y2) -> None:
    draw.rectangle([x1, y1, x2, y2], outline=(25, 45, 80, 180), width=1)
    blen, bw = 24, 3
    for corners in [
        ((x1, y1), (x1 + blen, y1), (x1, y1 + blen)),
        ((x2 - blen, y1), (x2, y1), (x2, y1 + blen)),
        ((x1, y2), (x1 + blen, y2), (x1, y2 - blen)),
        ((x2 - blen, y2), (x2, y2), (x2, y2 - blen)),
    ]:
        draw.line([corners[0], corners[1]], fill=WAR_GOLD, width=bw)
        draw.line([corners[0], corners[2]], fill=WAR_GOLD, width=bw)


def _draw_shield(draw: ImageDraw.ImageDraw, cx, cy, size=16, fill=GUILD_PURPLE) -> None:
    pts = [
        (cx, cy - size),
        (cx + int(size * 0.8), cy - int(size * 0.5)),
        (cx + int(size * 0.7), cy + int(size * 0.3)),
        (cx, cy + size),
        (cx - int(size * 0.7), cy + int(size * 0.3)),
        (cx - int(size * 0.8), cy - int(size * 0.5)),
    ]
    draw.polygon(pts, fill=fill, outline=(200, 130, 255), width=1)


def _draw_swords_icon(draw: ImageDraw.ImageDraw, cx, cy, size=14) -> None:
    """Draw crossed swords icon."""
    draw.line([(cx - size, cy - size), (cx + size, cy + size)], fill=WAR_GOLD, width=3)
    draw.line([(cx + size, cy - size), (cx - size, cy + size)], fill=WAR_GOLD, width=3)
    draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=WAR_GOLD)


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
    # Panel background
    border_color = WAR_GOLD if side == "left" else WAR_RED
    draw.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=(18, 24, 40, 220), outline=border_color, width=2)

    # Shield icon
    shield_x = x + 40 if side == "left" else x + w - 40
    _draw_shield(draw, shield_x, y + 30, size=18, fill=GUILD_PURPLE)

    # Guild name
    name_x = x + 65 if side == "left" else x + 10
    name_align = "lt" if side == "left" else "rt"
    cascade = get_font_cascade(20, is_bold=True)
    if side == "left":
        cascade.draw_text(draw, (name_x, y + 14), guild.name, fill=TEXT_WHITE, max_w=w - 80)
    else:
        name_w = cascade.get_width(guild.name, max_w=w - 80)
        cascade.draw_text(draw, (x + w - 65 - name_w, y + 14), guild.name, fill=TEXT_WHITE, max_w=w - 80)

    # Stats row
    stats_y = y + 50
    stats_text = f"{len(guild.members)}/15  •  ⚡{total_power:,}  •  WAR {guild.war_score}"
    if side == "left":
        draw.text((x + 20, stats_y), stats_text, font=fonts["small"], fill=TEXT_MUTED)
    else:
        draw.text((x + w - 20, stats_y), stats_text, font=fonts["small"], fill=TEXT_MUTED, anchor="rt")

    # Score if provided
    if score_label and score_value:
        score_y = y + 70
        draw.text((x + w // 2, score_y), score_value, font=fonts["score_large"], fill=border_color, anchor="mt")
        draw.text((x + w // 2, score_y + 28), score_label, font=fonts["small"], fill=TEXT_MUTED, anchor="mt")

    # Member count preview
    member_y = y + 100 if score_label else y + 75
    preview_text = f"👑 {clean_and_normalize_name(_get_owner_name(members, guild.owner_id))} + {max(0, len(members) - 1)} hunters"
    if side == "left":
        draw.text((x + 20, member_y), preview_text, font=fonts["small"], fill=TEXT_DIM)
    else:
        draw.text((x + w - 20, member_y), preview_text, font=fonts["small"], fill=TEXT_DIM, anchor="rt")


def _get_owner_name(members: list[Hunter], owner_id: int) -> str:
    for h in members:
        if h.user_id == owner_id:
            return h.display_full_name
    return "Unknown"


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
    img = Image.new("RGBA", (CHALLENGE_W, CHALLENGE_H), (0, 0, 0, 255))
    _draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)
    _draw_tech_border(draw, 18, 18, CHALLENGE_W - 18, CHALLENGE_H - 18)

    # Title
    cx = CHALLENGE_W // 2
    title = "GUILD WAR DECLARATION"
    tb = fonts["title"].getbbox(title)
    tw = tb[2] - tb[0]
    _draw_swords_icon(draw, cx - tw // 2 - 30, 44, size=12)
    _draw_swords_icon(draw, cx + tw // 2 + 30, 44, size=12)
    draw.text((cx, 30), title, font=fonts["title"], fill=WAR_GOLD, anchor="mt")

    sub = "SYSTEM PROTOCOL — INTER-GUILD COMBAT AUTHORIZATION"
    draw.text((cx, 64), sub, font=fonts["small"], fill=TEXT_MUTED, anchor="mt")

    # VS text
    vs_y = 160
    draw.text((cx, vs_y), "VS", font=fonts["title"], fill=WAR_RED, anchor="mt")

    # Guild panels — left (challenger) and right (defender)
    panel_w = 380
    panel_h = 200
    panel_y = 100
    gap = 20

    _draw_guild_panel(draw, fonts, challenger_guild, challenger_members,
                      30, panel_y, panel_w, panel_h, "left", challenger_power)
    _draw_guild_panel(draw, fonts, defender_guild, defender_members,
                      CHALLENGE_W - 30 - panel_w, panel_y, panel_w, panel_h, "right", defender_power)

    # Footer
    draw.text(
        (cx, CHALLENGE_H - 40),
        "「 Two guilds enter. Only one shall claim victory. 」",
        font=fonts["footer"], fill=TEXT_DIM, anchor="mt",
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
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
    img = Image.new("RGBA", (STATUS_W, STATUS_H), (0, 0, 0, 255))
    _draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)
    _draw_tech_border(draw, 18, 18, STATUS_W - 18, STATUS_H - 18)

    cx = STATUS_W // 2

    # Title
    title = "GUILD WAR — LIVE SCOREBOARD"
    draw.text((cx, 30), title, font=fonts["title"], fill=WAR_GOLD, anchor="mt")

    # Score display
    score_y = 75
    # Left score (challenger)
    draw.rounded_rectangle([40, score_y, cx - 30, score_y + 80], radius=10, fill=(18, 24, 40, 220), outline=WAR_GOLD, width=2)
    draw.text((cx - 70, score_y + 10), f"{challenger_wins}", font=fonts["score_large"], fill=WAR_GOLD, anchor="mt")
    draw.text((cx - 70, score_y + 42), clean_and_normalize_name(challenger_guild.name), font=fonts["small_bold"], fill=TEXT_WHITE, anchor="mt")
    draw.text((cx - 70, score_y + 60), f"WAR {challenger_guild.war_score}", font=fonts["small"], fill=TEXT_MUTED, anchor="mt")

    # Right score (defender)
    draw.rounded_rectangle([cx + 30, score_y, STATUS_W - 40, score_y + 80], radius=10, fill=(18, 24, 40, 220), outline=WAR_RED, width=2)
    draw.text((cx + 70, score_y + 10), f"{defender_wins}", font=fonts["score_large"], fill=WAR_RED, anchor="mt")
    draw.text((cx + 70, score_y + 42), clean_and_normalize_name(defender_guild.name), font=fonts["small_bold"], fill=TEXT_WHITE, anchor="mt")
    draw.text((cx + 70, score_y + 60), f"WAR {defender_guild.war_score}", font=fonts["small"], fill=TEXT_MUTED, anchor="mt")

    # VS
    draw.text((cx, score_y + 25), "VS", font=fonts["body_bold"], fill=TEXT_WHITE, anchor="mt")

    # Progress bar
    progress_y = score_y + 95
    draw.text((cx, progress_y), f"MATCH {current_match} / {total_matches}", font=fonts["small"], fill=TEXT_MUTED, anchor="mt")
    bar_y = progress_y + 18
    bar_w = STATUS_W - 100
    bar_h = 8
    draw.rounded_rectangle([50, bar_y, 50 + bar_w, bar_y + bar_h], radius=4, fill=(20, 30, 50))
    filled = int(bar_w * (current_match / max(total_matches, 1)))
    if filled > 0:
        draw.rounded_rectangle([50, bar_y, 50 + filled, bar_y + bar_h], radius=4, fill=WAR_GOLD)

    # Match results table
    table_y = bar_y + 30
    draw.rounded_rectangle([40, table_y, STATUS_W - 40, STATUS_H - 40], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)
    draw.text((60, table_y + 10), "[ BATTLE RECORD ]", font=fonts["small_bold"], fill=HUD_CYAN)
    draw.line([(55, table_y + 30), (STATUS_W - 55, table_y + 30)], fill=CARD_BORDER, width=1)

    row_y = table_y + 38
    row_h = 34

    # Build lookup dicts
    c_lookup = {h.user_id: h for h in challenger_members}
    d_lookup = {h.user_id: h for h in defender_members}

    for i, (c_uid, d_uid, winner_uid) in enumerate(matchups):
        if row_y > STATUS_H - 60:
            break

        ry = row_y + i * row_h
        if i % 2 == 0:
            draw.rounded_rectangle([48, ry, STATUS_W - 48, ry + row_h], radius=4, fill=(16, 24, 40, 150))

        # Match number
        draw.text((60, ry + 8), f"#{i + 1}", font=fonts["small_bold"], fill=TEXT_DIM)

        # Challenger name
        c_hunter = c_lookup.get(c_uid)
        c_name = c_hunter.display_full_name if c_hunter else "???"
        c_color = GREEN_COLOR if winner_uid == c_uid else (RED_COLOR if winner_uid and winner_uid != c_uid else TEXT_MUTED)
        draw.text((90, ry + 4), c_name, font=fonts["row_name"], fill=c_color, max_w=200)

        # VS
        draw.text((cx, ry + 8), "vs", font=fonts["small"], fill=TEXT_DIM, anchor="mt")

        # Defender name
        d_hunter = d_lookup.get(d_uid)
        d_name = d_hunter.display_full_name if d_hunter else "???"
        d_color = GREEN_COLOR if winner_uid == d_uid else (RED_COLOR if winner_uid and winner_uid != d_uid else TEXT_MUTED)
        d_name_w = fonts["row_name"].getbbox(d_name)[2] - fonts["row_name"].getbbox(d_name)[0]
        draw.text((STATUS_W - 90 - min(d_name_w, 200), ry + 4), d_name, font=fonts["row_name"], fill=d_color, max_w=200)

        # Result
        if winner_uid == c_uid:
            draw.text((cx, ry + 22), "← WIN", font=fonts["small"], fill=GREEN_COLOR, anchor="mt")
        elif winner_uid == d_uid:
            draw.text((cx, ry + 22), "WIN →", font=fonts["small"], fill=GREEN_COLOR, anchor="mt")
        else:
            draw.text((cx, ry + 22), "PENDING", font=fonts["small"], fill=TEXT_DIM, anchor="mt")

    # Footer
    draw.text(
        (cx, STATUS_H - 28),
        "「 The war continues until all battles are decided. 」",
        font=fonts["footer"], fill=TEXT_DIM, anchor="mt",
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
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
    img = Image.new("RGBA", (RESULT_W, RESULT_H), (0, 0, 0, 255))
    _draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)
    _draw_tech_border(draw, 18, 18, RESULT_W - 18, RESULT_H - 18)

    cx = RESULT_W // 2

    # Title — winner banner
    if winner_is_challenger:
        winner_guild = challenger_guild
        loser_guild = defender_guild
        banner_color = WAR_GOLD
        banner_text = "VICTORY"
    else:
        winner_guild = defender_guild
        loser_guild = challenger_guild
        banner_color = WAR_GOLD
        banner_text = "VICTORY"

    # Banner
    draw.rounded_rectangle([40, 25, RESULT_W - 40, 95], radius=10, fill=(28, 24, 12, 240), outline=banner_color, width=2)
    draw.text((cx, 38), f"⚔️ {banner_text} ⚔️", font=fonts["title"], fill=banner_color, anchor="mt")
    draw.text((cx, 72), f"🏆 {clean_and_normalize_name(winner_guild.name)} wins the war!", font=fonts["body_bold"], fill=TEXT_WHITE, anchor="mt")

    # Score summary
    score_y = 115
    draw.rounded_rectangle([40, score_y, RESULT_W - 40, score_y + 70], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)

    draw.text((cx, score_y + 10), "FINAL SCORE", font=fonts["small_bold"], fill=HUD_CYAN, anchor="mt")
    draw.text((cx - 100, score_y + 35), f"{challenger_wins}", font=fonts["score_large"], fill=WAR_GOLD, anchor="mt")
    draw.text((cx, score_y + 40), "—", font=fonts["body_bold"], fill=TEXT_WHITE, anchor="mt")
    draw.text((cx + 100, score_y + 35), f"{defender_wins}", font=fonts["score_large"], fill=WAR_RED, anchor="mt")
    draw.text((cx - 100, score_y + 58), clean_and_normalize_name(challenger_guild.name), font=fonts["small"], fill=TEXT_MUTED, anchor="mt")
    draw.text((cx + 100, score_y + 58), clean_and_normalize_name(defender_guild.name), font=fonts["small"], fill=TEXT_MUTED, anchor="mt")

    # Rewards section
    rewards_y = score_y + 90
    draw.rounded_rectangle([40, rewards_y, RESULT_W - 40, rewards_y + 160], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)
    draw.text((60, rewards_y + 10), "[ WAR REWARDS & CONSEQUENCES ]", font=fonts["small_bold"], fill=HUD_CYAN)
    draw.line([(55, rewards_y + 30), (RESULT_W - 55, rewards_y + 30)], fill=CARD_BORDER, width=1)

    # Winner rewards
    wy = rewards_y + 40
    draw.rounded_rectangle([60, wy, cx - 10, wy + 50], radius=6, fill=(28, 38, 20, 200), outline=GREEN_COLOR, width=1)
    draw.text((70, wy + 5), "👑 WINNER", font=fonts["small_bold"], fill=GREEN_COLOR)
    draw.text((70, wy + 22), f"+{gold_reward}💰 per member  •  +{xp_reward} XP per fighter", font=fonts["small"], fill=TEXT_WHITE)
    draw.text((70, wy + 36), f"+{50} war_score  •  war_wins +1", font=fonts["small"], fill=TEXT_DIM)

    # Loser penalties
    draw.rounded_rectangle([cx + 10, wy, RESULT_W - 60, wy + 50], radius=6, fill=(38, 18, 18, 200), outline=RED_COLOR, width=1)
    draw.text((cx + 20, wy + 5), "💀 DEFEATED", font=fonts["small_bold"], fill=RED_COLOR)
    draw.text((cx + 20, wy + 22), f"-{xp_penalty} XP per member", font=fonts["small"], fill=TEXT_WHITE)
    draw.text((cx + 20, wy + 36), f"-{30} war_score  •  war_losses +1", font=fonts["small"], fill=TEXT_DIM)

    # Top performers
    performers_y = wy + 65
    draw.text((60, performers_y), "🏅 TOP FIGHTERS:", font=fonts["small_bold"], fill=GOLD_COLOR)
    draw.line([(55, performers_y + 18), (RESULT_W - 55, performers_y + 18)], fill=CARD_BORDER, width=1)

    # Collect all fighters from both sides
    all_fighters = []
    for h in challenger_members:
        all_fighters.append((h, "left"))
    for h in defender_members:
        all_fighters.append((h, "right"))

    py = performers_y + 24
    for h, side in all_fighters[:6]:  # show top 6
        if py > RESULT_W - 60:
            break
        medal = "🥇" if side == ("left" if winner_is_challenger else "right") else "🥈"
        draw.text((70, py), f"{medal} {h.display_full_name}", font=fonts["row_name"], fill=TEXT_WHITE, max_w=300)
        rank_color = RANK_COLORS.get(h.rank, TEXT_MUTED)
        draw.text((RESULT_W - 70, py), f"Lv.{h.level} [{h.rank}]  ⚡{h.power:,}", font=fonts["row_stat"], fill=rank_color, anchor="rt")
        py += 22

    # Footer
    draw.text(
        (cx, RESULT_H - 28),
        "「 Victory belongs to those who fight as one. 」",
        font=fonts["footer"], fill=TEXT_DIM, anchor="mt",
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    buf.seek(0)
    return buf
