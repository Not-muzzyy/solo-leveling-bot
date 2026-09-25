"""
game/rich_text.py — Telegram Rich Text Formatting Helper (HTML Mode).

telegram-text integration: Bold / Italic / InlineCode / Chain / Quote / PlainText
are re-exported for composing messages. Render with .to_html() — NEVER rely on
str(element) or f-string interpolation without .to_html() (that yields MarkdownV2).

GOLDEN RULE: telegram-text does NOT HTML-escape. Every dynamic/user-controlled
value must pass escape_html() BEFORE being wrapped in an element:
    Bold(escape_html(hunter.hunter_name)).to_html()

Also provides: safe_caption / safe_message (length-safe truncation that closes
open tags) and validate_telegram_html (strict Telegram tag validator).
"""

from __future__ import annotations

import asyncio
from html import escape as _html_escape
from html.parser import HTMLParser
import re
from typing import Any, Optional

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, CopyTextButton

from telegram_text import Bold, Italic, InlineCode, Chain, Quote, PlainText

ALLOWED_TELEGRAM_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "tg-spoiler", "code", "pre", "blockquote", "a", "tg-emoji"
}


def escape_html(text: Any) -> str:
    """Safely escape dynamic text for Telegram HTML parse mode.
    Replaces &, <, >, \", and ' with standard HTML entities.
    """
    if text is None:
        return ""
    return _html_escape(str(text), quote=True)


def safe_caption(text: str, max_len: int = 1024) -> str:
    """
    Ensure a caption does not exceed Telegram's media caption limit (1024 chars),
    safely truncating and closing any open HTML tags if necessary so the entity parsing remains valid.
    """
    if not text or len(text) <= max_len:
        return text

    tokens = [t for t in re.split(r'(<[^>]+>|&[a-zA-Z0-9#]+;)', text) if t]
    open_tags: list[str] = []
    res: list[str] = []
    curr_len = 0
    truncated = False

    for token in tokens:
        if token.startswith('</') and token.endswith('>'):
            tag = token[2:-1].strip().lower()
            if open_tags and open_tags[-1] == tag:
                open_tags.pop()
            elif tag in open_tags:
                open_tags.remove(tag)
            res.append(token)
            curr_len += len(token)
        elif token.startswith('<') and token.endswith('>'):
            raw = token[1:-1].strip()
            tag = raw.split()[0].lower()
            open_tags.append(tag)
            res.append(token)
            curr_len += len(token)
        else:
            closing_len = sum(len(f'</{t}>') for t in reversed(open_tags))
            budget = max_len - curr_len - closing_len - 3
            if budget <= 0:
                truncated = True
                break
            if len(token) > budget:
                res.append(token[:budget])
                curr_len += budget
                truncated = True
                break
            else:
                res.append(token)
                curr_len += len(token)

    if truncated:
        res.append('...')
    for t in reversed(open_tags):
        res.append(f'</{t}>')

    return ''.join(res)


def safe_message(text: str, max_len: int = 4096) -> str:
    """
    Ensure a text message does not exceed Telegram's message text limit (4096 chars),
    safely truncating and closing any open HTML tags if necessary.
    """
    return safe_caption(text, max_len=max_len)


class TelegramHTMLValidator(HTMLParser):
    """Strict parser to validate whether an HTML string complies with Telegram parse rules."""
    def __init__(self):
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        tag_lower = tag.lower()
        if tag_lower not in ALLOWED_TELEGRAM_TAGS:
            self.errors.append(f"Unsupported tag: <{tag}>")
        self.stack.append(tag_lower)

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if not self.stack:
            self.errors.append(f"Unexpected closing tag: </{tag}> (no open tag)")
            return
        expected = self.stack.pop()
        if expected != tag_lower:
            self.errors.append(f"Mismatched closing tag: expected </{expected}>, got </{tag}>")


def validate_telegram_html(html_str: str) -> tuple[bool, str]:
    """
    Validate an HTML string against Telegram's parse mode constraints.
    Returns (is_valid, error_description).
    """
    validator = TelegramHTMLValidator()
    try:
        validator.feed(html_str)
        if validator.stack:
            validator.errors.append(f"Unclosed tags remaining: {validator.stack}")
    except Exception as exc:
        validator.errors.append(f"Parse error: {exc}")

    if validator.errors:
        return False, "; ".join(validator.errors)
    return True, ""


# ── Inline Button & Keyboard Helpers ──────────────────────────────────────────

def inline_button(
    text: str,
    callback_data: Optional[str] = None,
    url: Optional[str] = None,
    web_app_url: Optional[str] = None,
    switch_inline_query: Optional[str] = None,
    switch_inline_query_current_chat: Optional[str] = None,
    style: Optional[Any] = None,
    copy_text: Optional[Any] = None,
) -> InlineKeyboardButton:
    """
    Build a Pyrogram InlineKeyboardButton with rich convenience options and modern Telegram styling.

    Examples:
        inline_button("⚔️ Hunt", callback_data="hunt", style=enums.ButtonStyle.PRIMARY)
        inline_button("📢 Channel", url="https://t.me/example")
        inline_button("📋 Copy Hunter ID", copy_text="12345678")
    """
    kwargs: dict[str, Any] = {"text": str(text)}
    if style is not None:
        kwargs["style"] = style
    if copy_text is not None:
        if isinstance(copy_text, str):
            kwargs["copy_text"] = CopyTextButton(text=copy_text)
        else:
            kwargs["copy_text"] = copy_text
    elif url:
        kwargs["url"] = url
    elif web_app_url:
        kwargs["web_app"] = WebAppInfo(url=web_app_url)
    elif switch_inline_query is not None:
        kwargs["switch_inline_query"] = switch_inline_query
    elif switch_inline_query_current_chat is not None:
        kwargs["switch_inline_query_current_chat"] = switch_inline_query_current_chat
    else:
        kwargs["callback_data"] = callback_data or "noop"

    return InlineKeyboardButton(**kwargs)


def callback_button(
    text: str,
    callback_data: str,
    style: Optional[Any] = None,
) -> InlineKeyboardButton:
    """Convenience shortcut for an inline callback button with optional modern ButtonStyle."""
    kwargs: dict[str, Any] = {"text": str(text), "callback_data": callback_data}
    if style is not None:
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)


def copy_button(
    text: str,
    copy_value: str,
    style: Optional[Any] = None,
) -> InlineKeyboardButton:
    """Convenience shortcut for a 1-tap CopyTextButton."""
    kwargs: dict[str, Any] = {
        "text": str(text),
        "copy_text": CopyTextButton(text=str(copy_value)),
    }
    if style is not None:
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)


def url_button(text: str, url: str) -> InlineKeyboardButton:
    """Convenience shortcut for an inline URL link button."""
    return InlineKeyboardButton(text=str(text), url=url)


def inline_keyboard(
    *rows: list[InlineKeyboardButton] | InlineKeyboardButton | list[list[InlineKeyboardButton]],
) -> InlineKeyboardMarkup:
    """
    Build a Pyrogram InlineKeyboardMarkup from button rows.

    Supports multiple calling conventions:
        inline_keyboard([btn1, btn2], [btn3])
        inline_keyboard([[btn1, btn2], [btn3]])
        inline_keyboard(btn1, btn2)  # single row of buttons
    """
    if not rows:
        return InlineKeyboardMarkup([])

    # Check if first element is already a list of rows: [[b1, b2], [b3]]
    if len(rows) == 1 and isinstance(rows[0], list):
        first = rows[0]
        if first and isinstance(first[0], list):
            return InlineKeyboardMarkup(first)

    formatted_rows: list[list[InlineKeyboardButton]] = []
    single_row_accum: list[InlineKeyboardButton] = []

    for item in rows:
        if isinstance(item, list):
            if single_row_accum:
                formatted_rows.append(single_row_accum)
                single_row_accum = []
            formatted_rows.append(item)
        elif isinstance(item, InlineKeyboardButton):
            single_row_accum.append(item)

    if single_row_accum:
        formatted_rows.append(single_row_accum)

    return InlineKeyboardMarkup(formatted_rows)


def build_keyboard_grid(
    buttons: list[InlineKeyboardButton],
    columns: int = 2,
) -> InlineKeyboardMarkup:
    """Arrange a flat list of InlineKeyboardButtons into a grid of N columns."""
    if not buttons:
        return InlineKeyboardMarkup([])

    cols = max(1, columns)
    rows = [buttons[i : i + cols] for i in range(0, len(buttons), cols)]
    return InlineKeyboardMarkup(rows)
