"""game/rich_message.py — Telegram Rich Message (Bot API 10.1+) block builders.

GOLDEN RULE: block builders do NOT escape. Every dynamic value must pass
escape_html() from game.rich_text BEFORE being wrapped:
    paragraph(f"👤 <b>Hunter:</b> {escape_html(name)}")

Inline wrappers bold/italic/code DO escape (raw text in) — pass raw values.

Block-level newlines must be <br>: all builders route content through _nl().
Validation limits (Telegram): 32768 text chars, 500 blocks, 16 depth,
50 media, 20 table columns.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

from game.rich_text import escape_html

MAX_TEXT = 32768
MAX_BLOCKS = 500
MAX_DEPTH = 16
MAX_MEDIA = 50
MAX_TABLE_COLS = 20

_BLOCK_TAGS = ("p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table",
               "blockquote", "aside", "details", "figure", "footer", "pre", "div")
_BLOCK_RE = re.compile(r"<(?:p|h[1-6]|ul|ol|table|blockquote|aside|details|figure|footer|pre|div)[ >]")
_MEDIA_RE = re.compile(r"<(?:img|video|audio|tg-document)[ >]")


class RichValidationError(Exception):
    """Rich message violates a Telegram limit or is malformed."""


def _nl(text: str) -> str:
    return text.replace("\n", "<br>")


def bold(text: str) -> str:
    return f"<b>{escape_html(text)}</b>"


def italic(text: str) -> str:
    return f"<i>{escape_html(text)}</i>"


def code(text: str) -> str:
    return f"<code>{escape_html(text)}</code>"


def heading(level: int, text: str) -> str:
    if not 1 <= level <= 6:
        raise RichValidationError(f"heading level {level} out of 1..6")
    return f"<h{level}>{_nl(text)}</h{level}>"


def paragraph(content: str) -> str:
    return f"<p>{_nl(content)}</p>"


def divider() -> str:
    return "<hr/>"


def footer(text: str) -> str:
    return f"<footer>{_nl(text)}</footer>"


def bullet_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{_nl(i)}</li>" for i in items) + "</ul>"


def number_list(items: list[str]) -> str:
    return "<ol>" + "".join(f"<li>{_nl(i)}</li>" for i in items) + "</ol>"


def checkbox_list(pairs: list[tuple[str, bool]]) -> str:
    return "<ul>" + "".join(
        f"<li><input type=\"checkbox\"{' checked' if done else ''}>{_nl(text)}</li>"
        for text, done in pairs
    ) + "</ul>"


def table(rows: list[list[str]], header: bool = True,
          caption: str | None = None, aligns: list[str] | None = None) -> str:
    if not rows:
        raise RichValidationError("table needs at least one row")
    cols = max(len(r) for r in rows)
    if cols > MAX_TABLE_COLS:
        raise RichValidationError(f"table has {cols} cols > {MAX_TABLE_COLS}")
    out = ["<table>"]
    if caption:
        out.append(f"<caption>{_nl(caption)}</caption>")
    for r_i, row in enumerate(rows):
        out.append("<tr>")
        cell_tag = "th" if header and r_i == 0 else "td"
        for c_i, cell in enumerate(row):
            align = ""
            if aligns and c_i < len(aligns) and aligns[c_i] in ("left", "center", "right"):
                align = f' align="{aligns[c_i]}"'
            out.append(f"<{cell_tag}{align}>{_nl(cell)}</{cell_tag}>")
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def quote(text: str, expandable: bool = True, cite: str | None = None) -> str:
    attr = " expandable" if expandable else ""
    cite_html = f"<cite>{_nl(cite)}</cite>" if cite else ""
    return f"<blockquote{attr}>{_nl(text)}{cite_html}</blockquote>"


def details(summary: str, body: str, open_: bool = False) -> str:
    attr = " open" if open_ else ""
    return f"<details{attr}><summary>{_nl(summary)}</summary>{body}</details>"


def photo_block(media_id: str, caption: str | None = None) -> str:
    cap = f"<figcaption>{_nl(caption)}</figcaption>" if caption else ""
    return f'<figure><img src="tg://photo?id={media_id}"/>{cap}</figure>'


def link(text: str, url: str) -> str:
    return f'<a href="{url}">{text}</a>'


def anchor(name: str) -> str:
    return f'<a name="{name}"></a>'


def toc(entries: list[tuple[str, str]]) -> str:
    items = "".join(f'<li><a href="#{name}">{label}</a></li>' for label, name in entries)
    return f"<p><b>📑 Contents</b></p><ul>{items}</ul>"


def button_row(buttons: list[dict], align: str | None = None) -> str:
    align_attr = f' align="{align}"' if align in ("left", "center", "right") else ""
    btns = "".join(
        _tg_button(b) for b in buttons
    )
    return f"<tg-button-row{align_attr}>{btns}</tg-button-row>"


def _tg_button(b: dict) -> str:
    btype = b.get("type", "url")
    attrs = "".join(f' {k}="{b[k]}"' for k in ("url", "data", "query", "style") if k in b)
    return f'<tg-button type="{btype}"{attrs}>{escape_html(b["text"])}</tg-button>'


class RichDoc:
    def __init__(self, *blocks: str) -> None:
        self.blocks = blocks

    def to_html(self) -> str:
        return "".join(self.blocks)

    def validate(self) -> str:
        html = self.to_html()
        _check_balance(html)
        depth = _max_depth(html)
        if depth > MAX_DEPTH:
            raise RichValidationError(f"nesting depth {depth} > {MAX_DEPTH}")
        text_len = len(re.sub(r"<[^>]+>", "", html))
        if text_len > MAX_TEXT:
            raise RichValidationError(f"text length {text_len} > {MAX_TEXT}")
        n_blocks = len(_BLOCK_RE.findall(html))
        if n_blocks > MAX_BLOCKS:
            raise RichValidationError(f"block count {n_blocks} > {MAX_BLOCKS}")
        n_media = len(_MEDIA_RE.findall(html))
        if n_media > MAX_MEDIA:
            raise RichValidationError(f"media count {n_media} > {MAX_MEDIA}")
        return html


class RawRichDoc(RichDoc):
    """Pre-built HTML passthrough (validated on send)."""

    def __init__(self, html: str) -> None:
        super().__init__(html)


class _BalanceChecker(HTMLParser):
    _VOID = {"br", "hr", "img", "input", "meta", "link"}
    _SELF = {"img", "input"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []
        self.errors: list[str] = []
        self.depth = 0
        self.max_depth = 0

    def handle_starttag(self, tag: str, attrs):
        if tag in self._SELF:
            return
        self.stack.append(tag)
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag: str):
        if tag in self._SELF:
            return
        if not self.stack:
            self.errors.append(f"stray </{tag}>")
            return
        if self.stack[-1] != tag:
            self.errors.append(f"expected </{self.stack[-1]}>, got </{tag}>")
            return
        self.stack.pop()
        self.depth -= 1


def _parse(html: str) -> _BalanceChecker:
    p = _BalanceChecker()
    p.feed(html)
    p.close()
    return p


def _check_balance(html: str) -> None:
    p = _parse(html)
    if p.errors or p.stack:
        raise RichValidationError(
            f"unbalanced HTML: {p.errors or 'unclosed ' + str(p.stack)}"
        )


def _max_depth(html: str) -> int:
    return _parse(html).max_depth


if __name__ == "__main__":
    from game.rich_message import (
        RichDoc, RichValidationError, heading, paragraph, divider, footer,
        bullet_list, number_list, checkbox_list, table, quote, details,
        photo_block, link, anchor, toc, button_row, bold, italic, code,
    )
    from game.rich_text import escape_html

    # escaping: builders pass content through untouched (golden rule is caller-side)
    assert paragraph("a &amp; b") == "<p>a &amp; b</p>"
    # _nl: raw newlines inside blocks become <br>
    assert paragraph("a\nb") == "<p>a<br>b</p>"
    # wrappers DO escape (raw text in)
    assert bold('x<y>&"z') == "<b>x&lt;y&gt;&amp;&quot;z</b>"
    assert italic("i") == "<i>i</i>"
    assert code("c") == "<code>c</code>"
    # headings
    assert heading(1, "T") == "<h1>T</h1>"
    assert heading(6, "T") == "<h6>T</h6>"
    # lists
    assert bullet_list(["a", "b"]) == "<ul><li>a</li><li>b</li></ul>"
    assert number_list(["a"]) == "<ol><li>a</li></ol>"
    assert checkbox_list([("done", True), ("todo", False)]) == (
        "<ul><li><input type=\"checkbox\" checked>done</li>"
        "<li><input type=\"checkbox\">todo</li></ul>"
    )
    # table: header row + 20-col limit
    t = table([["H1", "H2"], ["a", "b"]])
    assert t == "<table><tr><th>H1</th><th>H2</th></tr><tr><td>a</td><td>b</td></tr></table>"
    assert table([["x"] * 20])  # exactly 20 OK
    try:
        table([["x"] * 21]); raise SystemExit("21-col table accepted - fix limit")
    except RichValidationError:
        pass
    # quote / details
    assert quote("q", expandable=True) == "<blockquote expandable>q</blockquote>"
    assert quote("q", expandable=False) == "<blockquote>q</blockquote>"
    assert quote("q", cite="Sys") == "<blockquote expandable>q<cite>Sys</cite></blockquote>"
    d = details("S", "body")
    assert d == "<details><summary>S</summary>body</details>"
    # photo block: media id MUST match InputRichMessageMedia.id convention
    assert photo_block("card") == '<figure><img src="tg://photo?id=card"/></figure>'
    assert photo_block("card", caption="cap") == (
        '<figure><img src="tg://photo?id=card"/><figcaption>cap</figcaption></figure>'
    )
    # links / anchors / toc
    assert link("go", "https://x.dev") == '<a href="https://x.dev">go</a>'
    assert anchor("sec") == '<a name="sec"></a>'
    assert toc([("Combat", "sec-1")]) == (
        '<p><b>📑 Contents</b></p><ul><li><a href="#sec-1">Combat</a></li></ul>'
    )
    # button row (in-body)
    assert button_row([{"text": "Open", "type": "url", "url": "https://x.dev"}]) == (
        '<tg-button-row><tg-button type="url" url="https://x.dev">Open</tg-button></tg-button-row>'
    )
    # misc blocks
    assert divider() == "<hr/>"
    assert footer("f") == "<footer>f</footer>"
    # RichDoc
    doc = RichDoc(heading(1, "A"), paragraph("b"))
    assert doc.to_html() == "<h1>A</h1><p>b</p>"
    assert doc.validate() == "<h1>A</h1><p>b</p>"
    # limits: 32768 text chars (tags stripped), 500 blocks, 16 depth
    try:
        RichDoc(paragraph("x" * 32769)).validate(); raise SystemExit("32769 accepted")
    except RichValidationError:
        pass
    try:
        RichDoc(*([paragraph("x")] * 501)).validate(); raise SystemExit("501 blocks accepted")
    except RichValidationError:
        pass
    try:
        RichDoc(paragraph("<b>" * 17 + "x" + "</b>" * 17)).validate(); raise SystemExit("depth 17 accepted")
    except RichValidationError:
        pass
    # unbalanced HTML is caught
    try:
        RichDoc("<p>oops").validate(); raise SystemExit("unbalanced accepted")
    except RichValidationError:
        pass
    # adversarial dynamic text passes ONLY when pre-escaped (golden rule)
    evil = '<script>&"\'</script>'
    ok = paragraph(escape_html(evil))
    RichDoc(ok).validate()  # must not raise
    assert "<script>" not in ok
    print("RICH SELF-CHECK OK")
