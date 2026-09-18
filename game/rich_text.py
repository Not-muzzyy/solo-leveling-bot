"""
game/rich_text.py — Telegram Rich Text Formatting Helper (HTML Mode).

Implements Telegram HTML formatting in accordance with telegram_rich_text_formatting.md:
- HTML escaping for all user-controlled/dynamic inputs
- Semantic tags: <b>, <i>, <u>, <s>, <code>, <pre>, <blockquote>, <blockquote expandable>, <tg-spoiler>
- User links (<a href="tg://user?id=...">) and URLs (<a href="...">)
- System card & lore blockquote builders
"""

from __future__ import annotations

from html import escape as _html_escape
from typing import Any, Optional


def escape_html(text: Any) -> str:
    """Safely escape dynamic text for Telegram HTML parse mode."""
    if text is None:
        return ""
    return _html_escape(str(text), quote=True)


def bold(text: Any) -> str:
    """Format text as <b>bold</b>."""
    return f"<b>{escape_html(text)}</b>"


def italic(text: Any) -> str:
    """Format text as <i>italic</i>."""
    return f"<i>{escape_html(text)}</i>"


def underline(text: Any) -> str:
    """Format text as <u>underlined</u>."""
    return f"<u>{escape_html(text)}</u>"


def strike(text: Any) -> str:
    """Format text as <s>strikethrough</s>."""
    return f"<s>{escape_html(text)}</s>"


def spoiler(text: Any) -> str:
    """Format text as <tg-spoiler>hidden spoiler</tg-spoiler>."""
    return f"<tg-spoiler>{escape_html(text)}</tg-spoiler>"


def code(text: Any) -> str:
    """Format text as inline <code>text</code>."""
    return f"<code>{escape_html(text)}</code>"


def pre(text: Any, language: str = "") -> str:
    """Format text as a preformatted <pre> code block with optional language."""
    escaped = escape_html(text)
    if language:
        return f'<pre><code class="language-{escape_html(language)}">\n{escaped}\n</code></pre>'
    return f"<pre>\n{escaped}\n</pre>"


def link(text: Any, url: str) -> str:
    """Format clickable URL: <a href="url">text</a>."""
    return f'<a href="{escape_html(url)}">{escape_html(text)}</a>'


def mention(user_id: int, name: Any) -> str:
    """Format Telegram user profile mention: <a href="tg://user?id=123">Name</a>."""
    return f'<a href="tg://user?id={user_id}">{escape_html(name)}</a>'


def blockquote(text: str, expandable: bool = False) -> str:
    """
    Format text as a Telegram blockquote.
    Note: text inside can already contain HTML tags, so it is not double-escaped.
    """
    tag = "<blockquote expandable>" if expandable else "<blockquote>"
    return f"{tag}\n{text.strip()}\n</blockquote>"


def system_lore(quote_text: str) -> str:
    """Format dramatic System lore quote inside an authentic blockquote."""
    clean = quote_text.strip()
    if not clean.startswith("「"):
        clean = f"「 {clean} 」"
    return blockquote(f"<i>{escape_html(clean)}</i>")


def system_header(title: str, subtitle: Optional[str] = None) -> str:
    """Generate an atmospheric holographic system header box."""
    esc_title = escape_html(title.upper())
    res = f"<b>╔══════════════════════════════╗</b>\n<b>║  ⚡ {esc_title}  ⚡  ║</b>\n<b>╚══════════════════════════════╝</b>"
    if subtitle:
        res += f"\n<i>{escape_html(subtitle)}</i>"
    return res
