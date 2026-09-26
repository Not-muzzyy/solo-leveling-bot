"""Telegram Mini App launch links and command handoff UI."""

from __future__ import annotations

from urllib.parse import quote

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import MINIAPP_API_ENABLED, MINIAPP_BOT_USERNAME
from game.rich_message import RichDoc, heading, paragraph
from game.rich_send import reply_rich


def miniapp_launch_keyboard(section: str, label: str) -> InlineKeyboardMarkup | None:
    """Build a Main Mini App deep link when the API and BotFather app are configured."""
    if not MINIAPP_API_ENABLED or not MINIAPP_BOT_USERNAME:
        return None

    url = f"https://t.me/{MINIAPP_BOT_USERNAME}?startapp={quote(section, safe='')}"
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, url=url)]])


async def send_miniapp_entry(
    message: Message,
    *,
    section: str,
    title: str,
    description: str,
    button_label: str,
) -> bool:
    """Send a section-specific app launch button; return false when not configured."""
    keyboard = miniapp_launch_keyboard(section, button_label)
    if keyboard is None:
        return False

    await reply_rich(
        message,
        RichDoc(heading(1, title), paragraph(description)),
        reply_markup=keyboard,
        fallback=lambda: message.reply_text(f"{title}\n\n{description}", reply_markup=keyboard),
    )
    return True
