# Rich Messages Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all 330 bot send/edit sites from classic `parse_mode=HTML` messages to Telegram Rich Messages (`sendRichMessage`, Bot API 10.1–10.3) with headings, tables, expandable blocks, TOC anchors, pagination keyboards, and embedded card photos.

**Architecture:** New composition module `game/rich_message.py` (block builders → `RichDoc.to_html()`) plus transport helpers `game/rich_send.py` (`reply_rich`/`send_rich`/`edit_rich`, each wrapping `try/except → classic fallback`). Handlers convert site-by-site; the classic call moves **verbatim** into a `fallback=` lambda so a rich-path failure degrades to today's exact behavior. Photo cards stay Pillow-rendered and embed via `tg://photo?id=` + `InputRichMessageMedia`.

**Tech Stack:** Python 3.14, kurigram 2.2.26 (`pyrogram` namespace — `Client.send_rich_message`, `Message.reply_rich`, `edit_message_text(rich_message=...)` all verified present), existing `game/rich_text.py` (`escape_html`), Pillow (unchanged), no new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-26-rich-messages-design.md` (approved, commit `67f39fa`). The plan argues from the spec; executors read both.

## Global Constraints
- **Golden rule:** every dynamic value passes `escape_html()` (from `game.rich_text`) BEFORE entering a builder; static literal HTML is exempt.
- **No feature flag.** Every rich send/edit site carries a `fallback=` lambda whose body is the **current call, moved verbatim** (same args, same `parse_mode` or lack of it).
- `InputRichMessage(html=..., media=..., skip_entity_detection=True)` — `skip_entity_detection=True` always (we control links explicitly).
- Rich limits enforced pre-send: ≤32768 UTF-8 text chars, ≤500 blocks, ≤16 depth, ≤50 media, ≤20 table columns. Classic `safe_caption` 1024 clamp applies ONLY to fallback strings, never to rich docs.
- Exclusions (never converted): 3 non-UI channel-DB writes (`guild_war.py:99,107`, `arise.py:634`), 86 `query.answer()` toasts, all `game/*_image.py` renderers, callback `data` strings, command logic.
- Never modify: `channel_db.py`, `shadows_db.py`, `.env`, live data channels.
- Inline keyboards: 107 existing keyboards attach unchanged via `reply_markup=` — callback routing untouched.
- Rich HTML named entities only: `&lt; &gt; &amp; &quot; &apos; &nbsp; &hellip; &mdash; &ndash; &lsquo; &rsquo; &ldquo; &rdquo;` (+ all numeric). `html.escape(quote=True)` output complies.
- Verification per task: import smoke + assert-based self-check scripts (house pattern — no pytest in this repo).
- Commits: conventional style on `main`, one per task (batches within a task may share).

## Review Focus
1. **Rich send rejected server-side (oversized/bad HTML) mid-command** → command must still answer with the classic message. Every conversion site's `fallback=` is the verbatim old call; Task 2 forces an exception with a stub client and asserts the fallback ran and returned. Import smoke + bot boot in every conversion task.
2. **Dynamic text reaches a builder unescaped** (hunter names like `<b>&"`) → raw markup injection / broken HTML. Golden rule is global; Task 1's self-check renders an adversarial string through every block builder and asserts escaping; each conversion task re-runs the adversarial snippet on its first converted builder.
3. **Embedded photo never renders** (`tg://photo?id=X` ≠ `InputRichMessageMedia.id`) → silent blank. Task 1 asserts `photo_block("x")` emits exactly `tg://photo?id=x`; Task 3 probe proves real rendering end-to-end with a live send.
4. **Wrong branch on in-place edit** (calling `edit_rich` on a classic photo message, or classic edit on a rich message → RPC error) → every converted callback checks `query.message.photo` FIRST (classic branch stays), then `query.message.rich_message`/default → rich. Each conversion task's Step "branch audit" runs the given `rg` pattern asserting photo-first ordering at every edited site.
5. **Raw `\n` inside rich blocks collapses** (rich HTML needs `<br>`) → every builder routes block-level newlines through `_nl()` (`\n` → `<br>`); Task 1 asserts `paragraph("a\nb") == "<p>a<br>b</p>"`.

---

### Task 1: `game/rich_message.py` — builders, RichDoc, self-check

**Files:**
- Create: `game/rich_message.py`
- Test: `python -m game.rich_message` (assert-based `__main__` self-check, house pattern)

**Interfaces:**
- Consumes: `game.rich_text.escape_html` (str → escaped str).
- Produces (all return HTML `str` unless noted): `heading(level: int, text: str)`, `paragraph(content: str)`, `divider() -> str`, `footer(text: str)`, `bullet_list(items: list[str])`, `number_list(items: list[str])`, `checkbox_list(pairs: list[tuple[str, bool]])`, `table(rows: list[list[str]], header: bool = True, caption: str | None = None, aligns: list[str] | None = None)`, `quote(text: str, expandable: bool = True, cite: str | None = None)`, `details(summary: str, body: str, open_: bool = False)`, `photo_block(media_id: str, caption: str | None = None)`, `link(text: str, url: str)`, `anchor(name: str)`, `toc(entries: list[tuple[str, str]])`, `button_row(buttons: list[dict], align: str | None = None)`, `RichDoc(*blocks: str)` with `.to_html() -> str` and `.validate() -> str`, `RichValidationError(Exception)`. Also re-export `bold/italic/code` thin wrappers (`f"<b>{escape_html(t)}</b>"` etc. — these DO escape, unlike telegram-text, because they take raw text; `b_html()/i_html()/code_html()` naming NOT used — keep `bold/italic/code`).

- [ ] **Step 1: Write the failing self-check** — create `game/rich_message.py` containing ONLY the module docstring and a `__main__` block; running it must fail on ImportError/AttributeError:

```python
"""game/rich_message.py — Telegram Rich Message (Bot API 10.1+) block builders.

GOLDEN RULE: builders do NOT escape. Every dynamic value must pass
escape_html() from game.rich_text BEFORE being wrapped:
    paragraph(f"👤 <b>Hunter:</b> {escape_html(name)}")

Block-level newlines must be <br>: all builders route content through _nl().
Validation limits (Telegram): 32768 text chars, 500 blocks, 16 depth,
50 media, 20 table columns.
"""
from __future__ import annotations

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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m game.rich_message`
Expected: `ModuleNotFoundError` / `ImportError` (module has no builders yet).

- [ ] **Step 3: Implement the module** — add to `game/rich_message.py` above the `__main__` block:

```python
import re
from html.parser import HTMLParser

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
    return f"<b>{text}</b>"


def italic(text: str) -> str:
    return f"<i>{text}</i>"


def code(text: str) -> str:
    return f"<code>{text}</code>"


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
```

Add `from game.rich_text import escape_html` to the imports at top (after `from __future__`). Note `bold/italic/code` intentionally do NOT escape despite the golden rule — they receive content already escaped by the caller or literal text; the docstring states the rule.

- [ ] **Step 4: Run self-check to verify it passes**

Run: `python -m game.rich_message`
Expected: `RICH SELF-CHECK OK`. Fix until green (common failures: `_BLOCK_RE` counting `paragraph` openers only once; `details` body passed raw so `RichDoc(details(...))` balance check requires caller-built body be balanced).

- [ ] **Step 5: Commit**

```bash
git add game/rich_message.py
git commit -m "feat: rich message block builders with limit validation"
```

---

### Task 2: `game/rich_send.py` — transport helpers with verbatim fallback

**Files:**
- Create: `game/rich_send.py`
- Test: `python -m game.rich_send` (self-check with stub client)

**Interfaces:**
- Consumes: `RichDoc.validate()`, `game.rich_text.escape_html`.
- Produces (exact signatures every later task calls):
  - `async reply_rich(message: Message, doc: RichDoc, *, reply_markup=None, media: list[InputRichMessageMedia] | None = None, fallback: Callable[[], Awaitable[T]]) -> T`
  - `async send_rich(client: Client, chat_id: int, doc: RichDoc, *, reply_markup=None, media=None, reply_to_message_id: int | None = None, fallback: Callable[[], Awaitable[T]]) -> T`
  - `async edit_rich(client: Client, chat_id: int, message_id: int, doc: RichDoc, *, reply_markup=None, media=None, fallback: Callable[[], Awaitable[T]]) -> T`
  - `photo_media(media_id: str, image: "bytes | BinaryIO") -> InputRichMessageMedia` (wraps `InputMediaPhoto(media=BytesIO(image) if bytes else image)`, id = `media_id` — MUST be the same id used in `photo_block(media_id)`).

- [ ] **Step 1: Write the failing self-check** — create `game/rich_send.py` with only docstring + `__main__` that imports the four names (fails now):

```python
"""game/rich_send.py — Rich Message transport with verbatim classic fallback.

Every helper: validate doc -> build InputRichMessage(html, media,
skip_entity_detection=True) -> call kurigram -> on ANY exception run
the caller's fallback() (the original classic call, unchanged).

There is deliberately NO feature flag (spec: user decision). The fallback
is the only safety net; it must never be an empty stub at a call site.
"""
from __future__ import annotations

if __name__ == "__main__":
    from game.rich_send import reply_rich, send_rich, edit_rich, photo_media
    print("RICH SEND IMPORT OK")
```

- [ ] **Step 2: Run to verify it fails** — Run: `python -m game.rich_send` → Expected: `ImportError`.

- [ ] **Step 3: Implement helpers:**

```python
import asyncio
import io
import logging
from typing import Awaitable, BinaryIO, Callable, TypeVar

from pyrogram import Client, types
from pyrogram.types import InputMediaPhoto, InputRichMessage, InputRichMessageMedia, Message

from game.rich_message import RichDoc

log = logging.getLogger(__name__)
T = TypeVar("T")


def photo_media(media_id: str, image: bytes | BinaryIO) -> InputRichMessageMedia:
    buf = io.BytesIO(image) if isinstance(image, bytes) else image
    return InputRichMessageMedia(id=media_id, media=InputMediaPhoto(media=buf))


def _irm(doc: RichDoc, media: list[InputRichMessageMedia] | None) -> InputRichMessage:
    return InputRichMessage(
        html=doc.validate(), media=media, skip_entity_detection=True,
    )


async def reply_rich(message: Message, doc: RichDoc, *, reply_markup=None,
                     media=None, fallback: Callable[[], Awaitable[T]]) -> T:
    try:
        return await message.reply_rich(
            rich_message=_irm(doc, media), reply_markup=reply_markup,
        )
    except Exception as e:  # noqa: BLE001 - any failure must degrade, not crash
        log.warning("reply_rich failed (%s); running classic fallback", e)
        return await fallback()


async def send_rich(client: Client, chat_id: int, doc: RichDoc, *,
                    reply_markup=None, media=None,
                    reply_to_message_id: int | None = None,
                    fallback: Callable[[], Awaitable[T]]) -> T:
    try:
        reply_parameters = None
        if reply_to_message_id is not None:
            reply_parameters = types.ReplyParameters(message_id=reply_to_message_id)
        return await client.send_rich_message(
            chat_id=chat_id, rich_message=_irm(doc, media),
            reply_markup=reply_markup, reply_parameters=reply_parameters,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("send_rich failed (%s); running classic fallback", e)
        return await fallback()


async def edit_rich(client: Client, chat_id: int, message_id: int, doc: RichDoc, *,
                    reply_markup=None, media=None,
                    fallback: Callable[[], Awaitable[T]]) -> T:
    try:
        return await client.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            rich_message=_irm(doc, media), reply_markup=reply_markup,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("edit_rich failed (%s); running classic fallback", e)
        return await fallback()
```

Add `__main__` block (replacing the placeholder from Step 1) with the forced-failure test — this is Review Focus #1:

```python
if __name__ == "__main__":
    import asyncio
    from game.rich_message import paragraph, RichDoc, RichValidationError
    from game.rich_send import reply_rich, send_rich, edit_rich, photo_media

    class _BoomClient:
        async def send_rich_message(self, **kw):
            raise RuntimeError("server rejected rich message")

        async def edit_message_text(self, **kw):
            raise RuntimeError("server rejected edit")

    class _BoomMessage:
        async def reply_rich(self, **kw):
            raise RuntimeError("server rejected reply")

        async def reply_text(self, text, **kw):
            return f"CLASSIC:{text}"

    async def main():
        doc = RichDoc(paragraph("hi"))
        # 1. forced failure -> fallback runs, returns classic result
        out = await reply_rich(
            _BoomMessage(), doc,
            fallback=lambda: _BoomMessage().reply_text("hi"),
        )
        assert out == "CLASSIC:hi", out
        out = await send_rich(
            _BoomClient(), 1, doc,
            fallback=lambda: asyncio.sleep(0, "CLASSIC-SEND"),
        )
        assert out == "CLASSIC-SEND", out
        out = await edit_rich(
            _BoomClient(), 1, 2, doc,
            fallback=lambda: asyncio.sleep(0, "CLASSIC-EDIT"),
        )
        assert out == "CLASSIC-EDIT", out
        # 2. validation failure BEFORE send also falls back (oversized)
        big = RichDoc(paragraph("x" * 40000))
        out = await send_rich(
            _BoomClient(), 1, big,
            fallback=lambda: asyncio.sleep(0, "FALLBACK-ON-VALIDATION"),
        )
        assert out == "FALLBACK-ON-VALIDATION", out
        # 3. photo_media id plumbing
        pm = photo_media("card", b"\x89PNG fake")
        assert pm.id == "card"
        print("RICH SEND SELF-CHECK OK")

    asyncio.run(main())
```

- [ ] **Step 4: Run self-check** — Run: `python -m game.rich_send` → Expected: `RICH SEND SELF-CHECK OK`.

- [ ] **Step 5: Import smoke across handlers (must be clean before/after)**

Run: `python -c "import handlers.help, handlers.profile, handlers.hunt, handlers.inventory, handlers.guild, handlers.arise, handlers.admin; print('IMPORT SMOKE OK')"`
Expected: `IMPORT SMOKE OK`.

- [ ] **Step 6: Commit**

```bash
git add game/rich_send.py
git commit -m "feat: rich message transport helpers with classic fallback"
```

---

### Task 3: Phase 0 live probe — media, buttons, in-place edit (HARD GATE)

**Files:**
- Create (temp, NOT committed): `C:\Users\saman\AppData\Local\Temp\opencode\probe_rich.py`
- Ledger: create `.superpowers/sdd/2026-09-26-rich-messages/progress.md` with the probe result line

**Interfaces:**
- Consumes: `game.rich_message.*`, `game.rich_send.photo_media`, `.env` (`BOT_TOKEN`, `SUPERADMIN_IDS`), kurigram `Client` (same `name=` session path as `main.py` — read it from `main.py` first).
- Produces: recorded probe verdict that Task 7 branches on: **edit-swaps-photo = YES/NO**.

- [ ] **Step 1: Stop the bot** (it holds the session file)

```powershell
Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
  Where-Object { $_.CommandLine -like '*main.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

- [ ] **Step 2: Read `main.py`** for the exact `Client(...)` construction (session `name=`, `bot_token=`, `api_id`/`api_hash` source) — the probe must reuse it verbatim so it opens the same session.

- [ ] **Step 3: Write the probe:**

```python
"""Probe: rich message media + buttons + in-place edit. Throwaway - do not commit."""
import asyncio, io, os, sys
sys.path.insert(0, r"W:\solo-leveling-bot")
from dotenv import load_dotenv
load_dotenv(r"W:\solo-leveling-bot\.env")
# from main import app  # ONLY if main.py constructs the client at import; else replicate Client(...) verbatim
from pyrogram import Client, types
from game.rich_message import RichDoc, heading, paragraph, table, details, quote, photo_block, anchor, toc, divider, footer
from game.rich_send import photo_media

CHAT_ID = int(os.environ["SUPERADMIN_IDS"].split(",")[0].strip())

# 1x1 red PNG
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415408d763f8cfc000000301010018dd8db00000000049454e44ae426082"
)

async def main():
    # Replicate main.py's Client(...) exactly (read main.py first!)
    app = Client(r"W:\solo-leveling-bot\bot")  # <- adjust name= to match main.py
    await app.start()
    try:
        # 1) rich text + keyboard (buttons must attach)
        doc = RichDoc(
            heading(1, "PROBE // Rich Messages"),
            divider(),
            toc([("Section", "sec")]),
            table([["Metric", "Value"], ["Cells", "2"]]),
            details("Expand me", paragraph("hidden body")),
            quote("expandable quote", expandable=True),
            anchor("sec"),
            footer("probe v1"),
        )
        kb = types.InlineKeyboardMarkup(
            [[types.InlineKeyboardButton("I am a button", callback_data="probe")]]
        )
        m1 = await app.send_rich_message(
            chat_id=CHAT_ID, rich_message=types.InputRichMessage(
                html=doc.validate(), skip_entity_detection=True),
            reply_markup=kb,
        )
        assert m1.rich_message is not None, "send OK but message.rich_message is None"
        print("PROBE 1 (text+buttons): SENT, rich_message present, reply_markup:",
              m1.reply_markup is not None)

        # 2) rich WITH embedded photo
        doc2 = RichDoc(photo_block("probe"), paragraph("photo above this line"))
        m2 = await app.send_rich_message(
            chat_id=CHAT_ID, rich_message=types.InputRichMessage(
                html=doc2.validate(),
                media=[photo_media("probe", PNG)],
                skip_entity_detection=True),
        )
        assert m2.rich_message is not None, "photo-rich send failed"
        print("PROBE 2 (embedded photo): SENT")

        # 3) in-place edit of the PHOTO-rich message with a DIFFERENT photo
        doc3 = RichDoc(photo_block("probe2"), paragraph("EDITED - different photo"))
        try:
            await app.edit_message_text(
                chat_id=CHAT_ID, message_id=m2.id,
                rich_message=types.InputRichMessage(
                    html=doc3.validate(),
                    media=[photo_media("probe2", PNG)],
                    skip_entity_detection=True),
            )
            print("PROBE 3 (edit swaps embedded photo): SUCCESS")
        except Exception as e:
            print(f"PROBE 3 (edit swaps embedded photo): FAILED -> {e!r}")

        # 4) edit TEXT-only rich message (help nav path)
        try:
            await app.edit_message_text(
                chat_id=CHAT_ID, message_id=m1.id,
                rich_message=types.InputRichMessage(
                    html=paragraph("EDITED text").validate(),
                    skip_entity_detection=True),
            )
            print("PROBE 4 (edit rich text): SUCCESS")
        except Exception as e:
            print(f"PROBE 4 (edit rich text): FAILED -> {e!r}")

        # cleanup probe messages
        for m in (m1, m2):
            try:
                await m.delete()
            except Exception:
                pass
        print("PROBE DONE")
    finally:
        await app.stop()

asyncio.run(main())
```

(If `main.py` exports an initialized `app` at import time, importing it is simpler — decide from the file; never start two clients concurrently on the same session.)

- [ ] **Step 4: Run the probe** — Run (workdir `W:\solo-leveling-bot`, `PYTHONIOENCODING=utf-8`): `python C:\Users\saman\AppData\Local\Temp\opencode\probe_rich.py`
Expected: all four PROBE lines print; PROBE 1/2/4 SUCCESS. **PROBE 3 verdict recorded either way.**

- [ ] **Step 5: Human visual confirmation** — ask the user: did the probe message show (a) heading + table + contents links, (b) expandable details/quote toggles, (c) a red photo, (d) a working button? Wait for their confirmation before proceeding. If photo did not render, revisit `photo_block`/`photo_media` id match (Review Focus #3) before ANY conversion work.

- [ ] **Step 6: Record verdict in ledger** — create `.superpowers/sdd/2026-09-26-rich-messages/progress.md`:

```markdown
# SDD ledger — plan: docs/superpowers/plans/2026-09-26-rich-messages-migration.md

Task 3: probe result: text+buttons=<SENT/…>, embedded_photo=<RENDERED/BLANK>, edit_swaps_photo=<SUCCESS/FAILED>, edit_text=<SUCCESS/FAILED>. Human visual confirm: <yes/no>.
Task 3: Ruling: Task 7 photo-edit strategy = <edit_rich | send-new-delete-old> (based on edit_swaps_photo).
```

- [ ] **Step 7: Restart the bot** (same restart command pattern as Task 7's verification — `Start-Process python main.py ...; Start-Sleep 12; Get-Content bot_err.log -Tail 25`) → Expected: `Bot initialized and ready!`, no Traceback.

- [ ] **Step 8: No commit** (probe is temp; ledger is gitignored like the previous project's `.superpowers/`).

---

### Task 4: `handlers/help.py` — full rich conversion (13 sites, TOC + details)

**Files:**
- Modify: `handlers/help.py` (sites per inventory: 13 send/edit + group redirect)
- Modify: `game/captions.py` — add `build_help_rich()` (new; classic `build_help_caption` stays for fallback)

**Interfaces:**
- Consumes: Task 1 builders, Task 2 `reply_rich`/`send_rich`/`edit_rich`/`photo_media`, existing `HELP_CAPTION`, `TOPIC_TEXTS`, `_topic_keyboard`, `_help_pm_keyboard`, `generate_help_image`.
- Produces: `TOPIC_RICH` extended from 1 entry (tiers) to all 7 topics; `build_help_rich() -> RichDoc` for the main manual. Later tasks copy this pattern (TOC + details + photo embed).

**Conversion rules (restated — every task carries its own):**
1. `fallback=` = the current call moved verbatim (args unchanged, including missing `parse_mode`).
2. Every dynamic value → `escape_html()` before entering a builder.
3. Branch order in callbacks: `query.message.photo` (classic) → `query.message.rich_message` (rich) → default (send fresh rich). Classic branches stay byte-identical.
4. Photo sites: `photo_media("<surface>", photo_buf)` + `photo_block("<surface>")` in the doc; `show_caption_above_media=True` → text blocks BEFORE the photo block; default → photo block first.
5. Newlines in block content: builders already apply `_nl()`; do not pre-insert `<br>` in Python string literals.
6. Rich docs are NOT `safe_caption`-truncated; fallback strings keep their existing `safe_caption`/`safe_message` wrapping untouched.

**Worked example — group redirect (rule application, actual code):**

```python
# BEFORE (handlers/help.py, group branch)
await message.reply_text(gc_text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)

# AFTER
_doc = RichDoc(
    heading(1, "[ SYSTEM DIRECTIVE // OPERATIONAL MANUAL ]"),
    paragraph("시스템 안내 // 매뉴얼 전송"),
    paragraph(f"👤 <b>Hunter:</b> <b>{escape_html(user.first_name)}</b>"),
    quote(
        "<b>Notice: Group Chat Optimization Protocol</b><br>"
        "• To keep group communications clear and uncluttered, the high-definition<br>"
        "  operational manual archives are opened directly in private chat.",
        expandable=True,
    ),
    paragraph("<i>Tap below to review directives and mechanics in private chat:</i>"),
)
await reply_rich(
    message, _doc, reply_markup=keyboard,
    fallback=lambda: message.reply_text(
        gc_text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML),
)
```

- [ ] **Step 1: Build `TOPIC_RICH` for all 7 topics** — convert each `TOPIC_TEXTS[...]` entry: first line `<b>[ TITLE ]</b>` → `heading(1, TITLE)`, split sections on their `<b>…</b>` sub-headers into `heading(2, …)` + `bullet_list([...])`, keep the lore `<blockquote expandable>` via `quote(..., expandable=True)`, append `footer("Solo Leveling Hunter System // Archives V2.5")`. Store as pre-rendered HTML strings in a module-level dict built from a helper:

```python
def _rich_topic(title: str, sections: list[tuple[str, list[str]]],
                lore: str | None = None) -> str:
    blocks = [heading(1, f"[ SYSTEM DIRECTIVE // {title} )".replace(")", "]"))]
    blocks.append(divider())
    for sec_title, items in sections:
        blocks.append(heading(2, sec_title))
        blocks.append(bullet_list(items))
    if lore:
        blocks.append(quote(lore, expandable=True))
    blocks.append(footer("Solo Leveling Hunter System // Archives V2.5"))
    return RichDoc(*blocks).validate()
```

(Adjust title formatting to match each existing title exactly — the existing `[ SYSTEM DIRECTIVE // COMBAT & SPIRE ]` text is the source of truth; copy strings from `TOPIC_TEXTS`, do not invent new copy. Items keep their existing `<code>/hunt</code>` etc. inline tags — all valid rich HTML.)

Populate `TOPIC_RICH` for `combat, forge, quests, guild, tiers, shadows, admin` — keep the existing hand-written `tiers` entry (already live since the proof) as-is or regenerate it through `_rich_topic` (must still equal a valid doc; re-run self-check below either way).

- [ ] **Step 2: Convert the 5 plain-text send sites** (line refs from inventory: group redirect; `/help <topic>` reply at ~406 already rich — verify it still uses `reply_rich`-style fallback; `HELP_FALLBACK_TEXT` site; two `reply_text` fallbacks) — apply rules 1–2 with `reply_rich`. The `/help <topic>` path: replace the inline `try: send_rich_message` with `reply_rich(message, RichDoc(*blocks) or RichDoc.from_html(TOPIC_RICH[key]), ...)`; since `TOPIC_RICH` values are pre-validated HTML strings, add to Task 1's module:

```python
class RawRichDoc(RichDoc):  # pre-built HTML passthrough (validated on send)
    def __init__(self, html: str) -> None:
        super().__init__(html)
```

  and use `RawRichDoc(TOPIC_RICH[topic])`. (If Task 1 already shipped `RichDoc` accepting raw html via a `raw=` classmethod, use that instead — implementer picks ONE, documented in the commit message.)

- [ ] **Step 3: Convert the main manual card (photo + caption)** — add to `game/captions.py`:

```python
def build_help_rich() -> RichDoc:
    """Structured main manual: photo card + TOC + collapsible per-topic summaries."""
    from game.rich_message import (RichDoc, photo_block, heading, toc, details,
                                   paragraph, divider, quote, footer, bullet_list)
    sections = [
        ("⚔️ Combat & Spire", "sec-combat", ["<code>/hunt</code> gates &amp; beasts",
         "<code>/explore</code> world map", "<code>/tower</code> 100-floor spire",
         "<code>/duel</code> PvP arena"]),
        ("⚒️ Vault, Forge &amp; Conditioning", "sec-forge", [
         "<code>/forge</code> enhance +1..+10", "<code>/daily</code> conditioning",
         "<code>/stats</code> attribute matrix", "<code>/shop</code> exchange depot"]),
        ("👑 Shadow Monarch Army", "sec-shadow", [
         "<code>/arise &lt;name&gt;</code> extract shadows", "<code>/shadows</code> army roster"]),
    ]
    return RichDoc(
        photo_block("help"),                       # rule 4: caption-below → photo first
        heading(1, "[ SYSTEM DIRECTIVE // OPERATIONAL MANUAL ]"),
        toc([(label, name) for label, name, _ in sections]),
        divider(),
        *(details(label, bullet_list(items)) for label, name, items in sections),
        quote("「 The System acknowledges those who strive to grow stronger. 」",
              expandable=False),
        footer("Solo Leveling Hunter System // Archives V2.5"),
    )
```

  (Content is a condensed index — the full text lives in the image and in topic pages; verify lengths and re-use existing copy lines rather than inventing gameplay facts: the `/hunt` 1m CD / 20-day numbers above must be copied from `HELP_FALLBACK_TEXT`.)

- [ ] **Step 4: Convert `handle()` main PM send** — `reply_photo(...)` → `reply_rich(message, build_help_rich(), reply_markup=_help_pm_keyboard(), media=[photo_media("help", photo_buf)], fallback=lambda: <verbatim reply_photo block>)` (keep `photo_buf = await asyncio.to_thread(generate_help_image)` before the call). Same for `send_help_card_to_chat` (uses `send_rich` with `chat_id=chat_id`).

- [ ] **Step 5: Convert `callback()`** — `help_main` branch: `query.message.photo` → classic `edit_message_media` stays; else → `edit_rich(client, query.message.chat.id, query.message.id, build_help_rich(), media=[photo_media("help", photo_buf)], reply_markup=_help_pm_keyboard(), fallback=<verbatim classic edit/reply>)`. Topic branch: photo → classic reply_text (stays); rich/text → `edit_rich(RawRichDoc(TOPIC_RICH[topic]), ..., fallback=<verbatim classic edit>)`, with final `except → reply_text` preserved inside the fallback.

- [ ] **Step 6: Branch audit** (Review Focus #4):

Run: `rg -n "edit_rich|edit_message_media|edit_message_text" handlers/help.py`
Expected: every converted callback shows `query.message.photo` check BEFORE any rich edit. Manually confirm ordering at each site.

- [ ] **Step 7: Import smoke + self-checks**

Run: `python -m game.rich_message; python -m game.rich_send; python -c "import handlers.help; from game.captions import build_help_rich; d=build_help_rich(); d.validate(); print('HELP RICH OK')"`
Expected: three OK lines.

- [ ] **Step 8: Adversarial spot-check** (Review Focus #2):

Run: `python -c "import handlers.help as h; from game.rich_message import RichDoc, paragraph; from game.rich_text import escape_html; p=paragraph(escape_html('<b>&\"q')); RichDoc(p).validate(); print('ADV OK')"` → `ADV OK`.

- [ ] **Step 9: Restart bot + live check** — restart (Task 3 Step 7 pattern), confirm clean boot, then ask the user to run `/help` in PM and confirm: photo card with TOC links, collapsible sections, topic pages with headings/tables; buttons navigate. Wait for their answer.

- [ ] **Step 10: Commit**

```bash
git add handlers/help.py game/captions.py game/rich_message.py
git commit -m "feat: convert /help to rich messages with TOC and collapsible sections"
```

---

### Task 5: Phase 2a — profile, claim, shop, start (text + photo)

**Files:**
- Modify: `game/formatting.py` (add `format_not_registered_rich()`, `format_cooldown_rich()`)
- Modify: `game/captions.py` (add `build_profile_rich`, `build_claim_rich`, `build_shop_rich`)
- Modify: `handlers/profile.py` (3 sites), `handlers/claim.py` (3), `handlers/shop.py` (6), `handlers/start.py` (10)

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: `format_not_registered_rich() -> RichDoc` and `format_cooldown_rich(remaining_seconds: int) -> RichDoc` — **Tasks 6–9 import these; signatures are fixed.** `build_profile_rich(hunter, inventory, full_name) -> RichDoc`, `build_claim_rich(...)`, `build_shop_rich(...)` mirroring their classic siblings' parameters.

**Conversion rules (restated):** as Task 4 rules 1–6, plus:
7. Notice/cooldown one-liners become `RichDoc(heading(1, …), paragraph(…), quote(...))` — same copy, structured layout.
8. Sites that only say "success" one-liners: `RichDoc(paragraph(<same text>))` — rich transport, no invented structure.

**Worked example — `format_cooldown_rich` (rule 7):**

```python
# game/formatting.py — classic format_cooldown stays untouched (fallback)
def format_cooldown_rich(remaining_seconds: int) -> "RichDoc":
    from game.rich_message import RichDoc, heading, paragraph, quote, code, escape_html as _  # noqa
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60
    return RichDoc(
        heading(1, "[ RECOVERY IN PROGRESS // 피로도 회복 중 ]"),
        paragraph("<i>You are still catching your breath from your previous hunt.</i>"),
        quote(
            f"⏱️ <b>Ready In:</b> {code(escape_html(f'{minutes}m {seconds:02d}s'))}<br>"
            "• Mana fatigue is dissipating. Please stand by before entering another gate.",
            expandable=True,
        ),
    )
```

**Worked example — handler site (claim.py:76):**

```python
# BEFORE
await message.reply_text(_format_cooldown(remaining), parse_mode=enums.ParseMode.HTML)
# AFTER
await reply_rich(
    message, _format_cooldown_rich(remaining),
    fallback=lambda: message.reply_text(
        _format_cooldown(remaining), parse_mode=enums.ParseMode.HTML),
)
```

**Worked example — photo site (shop.py reply_photo):**

```python
# BEFORE
await message.reply_photo(photo=photo_buf, caption=caption,
                          reply_markup=_shop_keyboard(...),
                          parse_mode=enums.ParseMode.HTML)
# AFTER  (caption-below → photo block first)
await reply_rich(
    message, build_shop_rich(shop_data, ...),
    reply_markup=_shop_keyboard(...),
    media=[photo_media("shop", photo_buf)],
    fallback=lambda: message.reply_photo(
        photo=photo_buf, caption=caption, reply_markup=_shop_keyboard(...),
        parse_mode=enums.ParseMode.HTML),
)
```

- [ ] **Step 1: Add the shared rich formatters** — `format_not_registered_rich()` + `format_cooldown_rich()` in `game/formatting.py` per rule 7 (copy the exact text from the classic versions — same `「 」` lore, same `/start` instruction).

- [ ] **Step 2: Convert `handlers/profile.py`** (3 sites: `format_not_registered` at :34, `format_profile` fallback at :75, photo at :66). Photo → `build_profile_rich(...)` + `photo_media("profile", photo_buf)`; text sites → `reply_rich(..., fallback=<verbatim>)`. `format_profile_rich` may be added in `game/formatting.py` OR `build_profile_rich` in `captions.py` — pick captions.py for photo-bearing, formatting.py for text-only, and keep the classic twins untouched.

- [ ] **Step 3: Convert `handlers/claim.py`** (3 text sites :70, :76, :107) — `format_not_registered_rich()`, `format_cooldown_rich()`, `build_claim_rich(...)`.

- [ ] **Step 4: Convert `handlers/shop.py`** (6 sites: guards :54/:91 text, photo :63/:103, fallbacks :96/:111).

- [ ] **Step 5: Convert `handlers/start.py`** (10 sites — all carry keyboards; photos :93/:112/:175/:196 with `build_shop_rich`/`build_inventory_rich`). **Note:** `build_inventory_rich` is used here but inventory's own file converts in Task 7 — add `build_inventory_rich` NOW in `captions.py` (needed by start.py), parameter-identical to `build_inventory_caption`.

- [ ] **Step 6: Adversarial spot-check on first builder of the batch:**

Run: `python -c "from game.captions import build_profile_rich; from models import Hunter, Inventory; h=Hunter(user_id=1, hunter_name='<b>&\"evil', level=1); ..."` — construct minimal valid Hunter/Inventory (read `models.py` dataclass required fields first), call builder, `RichDoc.validate()`, assert `"<b>&quot;evil" in html` style escaping present. Print `ADV OK`.

- [ ] **Step 7: Import smoke + self-checks**

Run: `python -m game.rich_message; python -m game.rich_send; python -c "import handlers.profile, handlers.claim, handlers.shop, handlers.start; print('IMPORT SMOKE OK')"` → OKs.

- [ ] **Step 8: Branch audit** — Run: `rg -n "reply_rich|send_rich|edit_rich" handlers/profile.py handlers/claim.py handlers/shop.py handlers/start.py | measure` and confirm count == 3+3+6+10 = 22 converted sites; each has a `fallback=` (rg `fallback=` count same).

- [ ] **Step 9: Restart + live spot-check with user** (`/profile`, `/claim`, `/shop`) — wait for confirmation.

- [ ] **Step 10: Commit** — `feat: convert profile, claim, shop, start to rich messages`

---

### Task 6: Phase 2b — hunt, duel, explore, redeem

**Files:**
- Modify: `game/formatting.py` (`format_hunt_result_rich`, `format_hunt_victory_rich`/`defeat` if separate), `game/captions.py` (`build_hunt_rich`, `build_duel_challenge_rich`, `build_duel_result_rich`, `build_explore_rich`)
- Modify: `handlers/hunt.py` (5), `handlers/duel.py` (12), `handlers/explore.py` (5), `handlers/redeem.py` (9)

**Interfaces:**
- Consumes: Tasks 1–2, `format_not_registered_rich()` (Task 5), `format_cooldown_rich` (Task 5; hunt uses `format_cooldown` at :90).
- Produces: `build_hunt_rich(hunter, result) -> RichDoc`, `build_duel_result_rich(...)`, `build_explore_rich(...)` — guild/war tasks may reuse `build_duel_result_rich`'s table pattern for scoreboards.

**Conversion rules:** as Task 4 rules 1–8. Duel accept/decline edits (:165, :176) are text-message edits → `edit_rich` with classic `edit_message_text` as fallback; duel result photo (:220) → `reply_rich` + `photo_media("duel", ...)`.

**Worked example — hunt result (rule application):** classic `format_hunt_result` builds `<b>VICTORY</b>`-style lines; rich version:

```python
def format_hunt_result_rich(hunter, result) -> "RichDoc":
    from game.rich_message import (RichDoc, heading, paragraph, table, quote,
                                   divider, code, bold, escape_html)
    won = result.victory
    blocks = [
        heading(1, "⚔️ GATE CLEAR // VICTORY" if won else "💀 GATE RUN // DEFEAT"),
        paragraph(f"{bold('Hunter:')} {escape_html(hunter.hunter_name)} "
                  f"┊ {bold('Monster:')} {escape_html(result.monster_name)}"),
        table(
            [["Metric", "Value"],
             ["Damage dealt", code(escape_html(f"{result.damage_dealt:,}"))],
             ["XP gained", code(escape_html(f"{result.xp_gained:,}"))],
             ["Gold gained", code(escape_html(f"{result.gold_gained:,}"))]],
            aligns=["left", "right"],
        ),
    ]
    if result.loot_lines:
        blocks.append(heading(2, "Spoils"))
        blocks.append(bullet_list([escape_html(x) for x in result.loot_lines]))
    # copy the exact notice/lore line from format_hunt_result (read it; do not invent)
    blocks.append(paragraph("<i>« exact classic notice line »</i>"))
    return RichDoc(*blocks)
```

(Implementer: read `format_hunt_result` first and carry over EVERY field it shows — numbers, titles, notice text — into the rich layout; the comment marks where, it is not content to ship.)

- [ ] **Step 1: Add rich builders** to `formatting.py`/`captions.py` per above (read classic sources; identical data coverage).
- [ ] **Step 2: Convert `handlers/hunt.py`** (5 sites; photo :144).
- [ ] **Step 3: Convert `handlers/duel.py`** (12 sites; edits :165/:176 → `edit_rich`; photo :220 + text fallback :228).
- [ ] **Step 4: Convert `handlers/explore.py`** (5 sites; photo :232 has keyboard, text :254 uses `build_explore_caption` → `build_explore_rich`).
- [ ] **Step 5: Convert `handlers/redeem.py`** (9 text sites; group redirect :64 keeps its URL keyboard).
- [ ] **Step 6: Adversarial spot-check** on `format_hunt_result_rich` with monster name `<img src=x onerror=...>` → validate passes, no raw `<img` in output except none (escaped).
- [ ] **Step 7: Import smoke** — `python -c "import handlers.hunt, handlers.duel, handlers.explore, handlers.redeem; print('IMPORT SMOKE OK')"`.
- [ ] **Step 8: Site-count audit** — `rg -c "fallback=" handlers/hunt.py handlers/duel.py handlers/explore.py handlers/redeem.py` sum == 31 (5+12+5+9).
- [ ] **Step 9: Restart + live check with user** (`/hunt`, `/duel` in group, `/explore`, `/redeem <code>`).
- [ ] **Step 10: Commit** — `feat: convert hunt, duel, explore, redeem to rich messages`

---

### Task 7: Phase 3 — inventory, leaderboard, tower, forge, quest (edit-heavy photo)

**Files:**
- Modify: `game/captions.py` (`build_inventory_rich` may already exist from Task 5 — extend; `build_leaderboard_rich`, `build_tower_rich`, `build_forge_rich`, `build_quest_rich`)
- Modify: `handlers/inventory.py` (43 sites — the 7× triple-branch), `handlers/leaderboard.py` (5), `handlers/tower.py` (12), `handlers/forge.py` (10), `handlers/quest.py` (13)

**Interfaces:**
- Consumes: Tasks 1–2, `format_not_registered_rich` (Task 5), `build_inventory_rich` (Task 5), **Task 3 ledger verdict**.
- Produces: nothing new globally — per-surface `build_*_rich` in `captions.py`.

**STRATEGY BRANCH — read Task 3's ledger line `edit_swaps_photo=` first:**
- If **SUCCESS** → photo-swap sites use `edit_rich(..., media=[photo_media(...)], fallback=<verbatim edit_message_media>)`.
- If **FAILED** → photo-swap sites use send-new/delete-old:

```python
# send-new/delete-old variant (only if probe says edit cannot swap photo)
async def _replace_rich(query, doc, media, reply_markup, fallback):
    try:
        new_msg = await query.message._client.send_rich_message(
            chat_id=query.message.chat.id,
            rich_message=types.InputRichMessage(html=doc.validate(),
                                                media=media,
                                                skip_entity_detection=True),
            reply_markup=reply_markup,
        )
        try:
            await query.message.delete()
        except Exception:
            pass
        return new_msg
    except Exception as e:
        log.warning("replace_rich failed (%s); classic fallback", e)
        return await fallback()
```

  (Place `_replace_rich` in `game/rich_send.py` in that branch — it is dead code if the probe succeeded; only add it when needed.)

**Conversion rules:** Task 4 rules 1–6 +:
9. inventory's triple-branch becomes: `if query.message.photo:` → classic `edit_message_media` (byte-identical) / `elif` text-only classic message → `edit_rich` with classic edit as fallback / fresh sends → `reply_rich`. Never call `edit_rich` while `.photo` is truthy (Review Focus #4).

**Worked example — leaderboard tab switch (leaderboard.py:184-194):**

```python
# BEFORE
if query.message and query.message.photo:
    await query.edit_message_media(
        media=InputMediaPhoto(media=photo_buf, caption=caption,
                              parse_mode=enums.ParseMode.HTML),
        reply_markup=_leaderboard_keyboard(category))
elif query.message:
    await query.message.reply_photo(photo=photo_buf, caption=caption, ...)

# AFTER (probe SUCCESS branch)
if query.message and query.message.photo:
    await edit_rich(
        client, query.message.chat.id, query.message.id,
        build_leaderboard_rich(category),
        reply_markup=_leaderboard_keyboard(category),
        media=[photo_media("leaderboard", photo_buf)],
        fallback=lambda: query.edit_message_media(
            media=InputMediaPhoto(media=photo_buf, caption=caption,
                                  parse_mode=enums.ParseMode.HTML),
            reply_markup=_leaderboard_keyboard(category)),
    )
elif query.message:
    await reply_rich(
        query.message, build_leaderboard_rich(category),
        reply_markup=_leaderboard_keyboard(category),
        media=[photo_media("leaderboard", photo_buf)],
        fallback=lambda: query.message.reply_photo(
            photo=photo_buf, caption=caption,
            reply_markup=_leaderboard_keyboard(category),
            parse_mode=enums.ParseMode.HTML),
    )
```

- [ ] **Step 0: Read ledger strategy line** and pick the branch; state the choice in the commit message.
- [ ] **Step 1: Convert `handlers/leaderboard.py`** (5 sites — smallest edit-heavy file; use it as the pattern).
- [ ] **Step 2: Convert `handlers/quest.py`** (13 sites; edit :328 stats in-place → `edit_rich` text; photo edit :281 → strategy branch).
- [ ] **Step 3: Convert `handlers/tower.py`** (12 sites; photo edits :185/:239 → strategy branch; photo sends :90/:195/:203/:248).
- [ ] **Step 4: Convert `handlers/forge.py`** (10 sites; 4 photo edits :176/:202/:225/:245 → strategy branch; caption edits :173-ish via `build_forge_rich`).
- [ ] **Step 5: Convert `handlers/inventory.py`** (43 sites) — apply rule 9 to the 7 triple-branches (pairs 375/377, 406/408, 432/434, 460/464, 567/569, 638/642, 716/718) plus 6 `edit_message_media` (:389,:416,:443,:552,:623,:701), 8 fresh photo sends, 16 text sites, command-entry guards. Also `build_inventory_rich` must cover every field `build_inventory_caption` renders (read it; same item rows, stats, prices).
- [ ] **Step 6: Adversarial spot-check** on `build_inventory_rich` with item name `Evil <Sword> & "Glory"`.
- [ ] **Step 7: Import smoke** — `python -c "import handlers.inventory, handlers.leaderboard, handlers.tower, handlers.forge, handlers.quest; print('IMPORT SMOKE OK')"`.
- [ ] **Step 8: Branch audit** (Review Focus #4):

Run: `rg -n -U "query\.message\.photo[\s\S]{0,400}edit_rich" handlers/inventory.py handlers/leaderboard.py handlers/tower.py handlers/forge.py handlers/quest.py | rg -c "photo"` — then manually open each hit and confirm the `.photo` check precedes `edit_rich` (rg -U gives context; every converted in-place site must appear with its photo guard above).

- [ ] **Step 9: Site-count audit** — `rg -c "fallback=" <5 files>` sums to 83 (43+5+12+10+13).
- [ ] **Step 10: Restart + live click-through with user**: `/inventory` (tab through weapons/armor/potions — in-place swaps must work), `/leaderboard` (switch all 4 category tabs), `/tower` (open + climb), `/forge` (open + enhance), `/quest` + `/daily`. Wait for confirmation on each.
- [ ] **Step 11: Commit** — `feat: convert inventory, leaderboard, tower, forge, quest to rich messages (strategy: <edit_rich|replace>)`

---

### Task 8: Phase 4a — guild + guild_war

**Files:**
- Modify: `game/captions.py` (`build_guild_rich`, `build_war_challenge_rich`, `build_war_status_rich`)
- Modify: `handlers/guild.py` (67 of 69 — exclude :99/:107? no: those are `guild_war.py`'s; guild.py excludes nothing non-UI), `handlers/guild_war.py` (20 of 22 — exclude :99, :107)

**Interfaces:**
- Consumes: Tasks 1–2, `format_not_registered_rich` (Task 5), Task 7 strategy branch (war photo edits :469/:620 use same branch logic).
- Produces: `build_guild_rich(guild, ...) -> RichDoc` — guild leaderboard tables reused by `guild_leaderboard` tab edits.

**Conversion rules:** Task 4 rules + Task 7 rule 9 + strategy branch. **Guild leaderboard tabs (:910,:1005,:1062,:1111 `edit_message_media`) are the same pattern as leaderboard.py — copy Task 7 Step 1's worked example.** War scoreboard content → `table(...)` (trophies/K-D columns — natural tabular data, spec §3.5).

- [ ] **Step 1: Convert `handlers/guild.py`** — photo sites :175/:846/:915; `edit_message_media` :910/:1005/:1062/:1111 (strategy branch); 62 text sites (many `format_not_registered` → `format_not_registered_rich`, rest `RichDoc(heading/paragraph/quote)` per rule 8 with EXACT existing copy).
- [ ] **Step 2: Convert `handlers/guild_war.py`** — SKIP :99/:107 (non-UI, add `# non-UI: stays classic` comment? NO — do not touch excluded lines at all). Photo :361/:677, edits :400/:415/:431/:475 (text edits → `edit_rich`), photo edits :469/:620 (strategy branch), text :633 + guard texts.
- [ ] **Step 3: Adversarial spot-check** on `build_guild_rich` with guild name `A<B> & "C"`.
- [ ] **Step 4: Import smoke** — `python -c "import handlers.guild, handlers.guild_war; print('IMPORT SMOKE OK')"`.
- [ ] **Step 5: Exclusion audit** — `rg -n "send_message|edit_message_text" handlers/guild_war.py` shows :99/:107 still classic WITHOUT `fallback=` (they are DB writes — unchanged), all other sites converted (`rg -c "fallback=" handlers/guild_war.py` == 20).
- [ ] **Step 6: Branch audit** — same `rg -U` photo-before-edit_rich check on both files.
- [ ] **Step 7: Site-count audit** — `rg -c "fallback=" handlers/guild.py handlers/guild_war.py` sums to 87 (67+20).
- [ ] **Step 8: Restart + live check with user** (`/guild create/info/top`, `/guild war <name>` full challenge→accept flow, guild leaderboard tab switching).
- [ ] **Step 9: Commit** — `feat: convert guild and guild war to rich messages`

---

### Task 9: Phase 4b — arise, admin, main.py

**Files:**
- Modify: `handlers/arise.py` (35 of 36 — exclude :634), `handlers/admin.py` (53), `main.py` (:112 restart notice)

**Interfaces:**
- Consumes: Tasks 1–2, Task 5 shared formatters.
- Produces: none (end state).

**Conversion rules:** Task 4 rules; admin sites are static f-strings → `RichDoc(heading(1, title), paragraph(...), quote(...))` preserving EXACT copy (including `escape_html` interpolations already present). Arise: spawn photo :188 + text :196; shadows caption pagination edit :552 (strategy branch, caption from `_build_shadows_caption` → `build_shadows_rich` in `captions.py`); group spawn text sites keep their group-chat guard structure. `main.py:112` restart notice → `edit_rich` with verbatim classic edit as fallback.

**Worked example — admin one-liner (rule 8):**

```python
# BEFORE (admin.py, grant success)
await message.reply_text(
    f"✅ <b>Gold granted:</b> <code>{escape_html(str(amount))}</code> → <code>{escape_html(target)}</code>",
    parse_mode=enums.ParseMode.HTML)
# AFTER
await reply_rich(
    message,
    RichDoc(paragraph(
        f"✅ <b>Gold granted:</b> <code>{escape_html(str(amount))}</code> → "
        f"<code>{escape_html(target)}</code>")),
    fallback=lambda: message.reply_text(
        f"✅ <b>Gold granted:</b> <code>{escape_html(str(amount))}</code> → "
        f"<code>{escape_html(target)}</code>",
        parse_mode=enums.ParseMode.HTML),
)
```

(To avoid duplicating the string, assign it to a local `text = f"..."` first, then `RichDoc(paragraph(text))` and `fallback=lambda: message.reply_text(text, parse_mode=...)`. Use the local-variable pattern for ALL admin sites — it keeps fallback verbatim without copy drift.)

- [ ] **Step 1: Convert `handlers/admin.py`** (53 sites — use the local-variable pattern; 4 in-place `edit_text` sites → `edit_rich`; :1016 has a keyboard → pass `reply_markup` through).
- [ ] **Step 2: Convert `handlers/arise.py`** (35 sites — spawn photo :188 with `photo_media("shadow", photo_buf)`, shadows pagination :552 strategy branch, `build_shadows_rich` added to `captions.py`; :634 untouched).
- [ ] **Step 3: Convert `main.py:112`** — `edit_rich(client, ..., fallback=<verbatim>)`.
- [ ] **Step 4: Adversarial spot-check** on an admin builder path with amount string containing `<`.
- [ ] **Step 5: Import smoke** — `python -c "import handlers.arise, handlers.admin, main; print('IMPORT SMOKE OK')"` (importing main must NOT start polling — if it does, use `import ast` check instead: `python -c "import ast; ast.parse(open('main.py').read()); print('MAIN PARSE OK')"`).
- [ ] **Step 6: Exclusion audit** — `rg -n "send_message|edit_message_text" handlers/arise.py` shows :634 unchanged (no `fallback=`), everything else converted; `rg -c "fallback=" handlers/arise.py handlers/admin.py` sums to 88 (35+53).
- [ ] **Step 7: Restart + live check with user** (`/addgold` success path, `/arise` flow if a spawn occurs, restart notice message).
- [ ] **Step 8: Commit** — `feat: convert arise, admin, and restart notice to rich messages`

---

### Task 10: Final sweep, verification, closeout

**Files:**
- Modify: only if sweep finds missed sites (fix them in this task)

**Interfaces:**
- Consumes: all prior tasks.

- [ ] **Step 1: Full inventory re-run** — reuse the AST scan approach (or `rg` proxy):

Run: `rg -n "reply_text\(|send_message\(|reply_photo\(|send_photo\(|edit_message_text\(|edit_message_media\(|edit_message_caption\(" handlers main.py -g "*.py" | rg -v "fallback=|def |#" | Measure-Object -Line`
Expected: line count == excluded set only — toasts are `query.answer(` (different pattern), non-UI 3 sites (`guild_war.py:99,107`, `arise.py:634`), and fallback-lambda bodies (indented — the `rg -v "fallback="` may still catch multi-line lambda bodies; audit leftovers manually and classify every remaining hit as: **fallback body / excluded / missed**. Missed sites → convert now (same rules), re-run.

- [ ] **Step 2: Fallback completeness audit** — every `reply_rich|send_rich|edit_rich` call has `fallback=`:

Run: `rg -U -c "reply_rich\([\s\S]{0,300}?fallback=|send_rich\([\s\S]{0,300}?fallback=|edit_rich\([\s\S]{0,300}?fallback=" handlers main.py` vs `rg -c "reply_rich\(|send_rich\(|edit_rich\(" handlers main.py` — counts must match. Investigate any mismatch.

- [ ] **Step 3: Golden-rule audit** — builders never receive raw f-string with unescaped `{user_input}`: spot-check by `rg -n "paragraph\(f?\"" handlers | rg -v "escape_html"` and manually confirm every hit is static-only text (no user vars).

- [ ] **Step 4: Full self-check battery**

Run: `python -m game.rich_message; python -m game.rich_send; python -c "import game.captions, game.formatting, handlers.help, handlers.profile, handlers.hunt, handlers.inventory, handlers.shop, handlers.tower, handlers.forge, handlers.quest, handlers.duel, handlers.explore, handlers.claim, handlers.start, handlers.guild, handlers.guild_war, handlers.leaderboard, handlers.arise, handlers.admin, handlers.redeem; print('FULL IMPORT SMOKE OK')"`
Expected: two self-check OKs + `FULL IMPORT SMOKE OK`.

- [ ] **Step 5: Restart bot + clean-log check**

```powershell
Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
  Where-Object { $_.CommandLine -like '*main.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep 2; Remove-Item bot_err.log,bot_out.log -ErrorAction SilentlyContinue
Start-Process python -ArgumentList main.py -WorkingDirectory W:\solo-leveling-bot `
  -RedirectStandardError W:\solo-leveling-bot\bot_err.log `
  -RedirectStandardOutput W:\solo-leveling-bot\bot_out.log
Start-Sleep 12; Get-Content bot_err.log -Tail 25
```
Expected: `ChannelDB initialized...` + `Bot initialized and ready!`, **zero Traceback**, zero `rich ... failed` warnings at boot.

- [ ] **Step 6: Live acceptance pass with user** — ask them to exercise: `/help` (TOC jump + details expand + topic nav buttons), `/profile`, `/hunt`, `/inventory` (tab paging), `/leaderboard` (tab switch), `/shop`, `/guild info`, `/tower`, `/duel`, `/claim`, `/shadows` (if a shadow exists). Collect failures → fix in this task (same conversion rules), re-run Step 4–5.

- [ ] **Step 7: Closeout** — append final ledger line to `.superpowers/sdd/2026-09-26-rich-messages/progress.md`:

```markdown
Task 10: complete. Sites converted: <fallback= count>; excluded: 3 non-UI + 86 toasts. Self-checks green; full import smoke green; bot boot clean. Live acceptance: <user confirmation date>.
```

- [ ] **Step 8: Final commit** (if any sweep fixes were made; otherwise the working tree is already clean)

```bash
git add -A
git commit -m "chore: rich messages migration sweep fixes" --allow-empty
```

---

## Self-Review (plan vs spec)

1. **Spec coverage:** §3.1 → Task 1; §3.2 → Task 2; §3.3 → Tasks 4–9 (per-file); §3.4 four features → Task 4 (TOC/details/expandable), Task 4/5 (buttons via reply_markup), Task 1 (`RichDoc.validate` 32768 → Show-more); §3.5 → per-task `build_*_rich` twins; §4 error handling → Task 2 forced-failure self-check; §5 verification → Tasks 1/2 self-checks, Task 3 probe, per-task smoke+audits, Task 10 sweep; §6 phasing + contingency → Task 3 ledger + Task 7 Step 0 branch; §7 non-goals → Global Constraints exclusions. **No gaps.**
2. **Placeholder scan:** Task 6's `« exact classic notice line »` comment is a *pointer to read the source*, not shipped content — reworded as such; all other steps carry literal code/commands/expected output. Fixed `_rich_topic` title munging (`replace(")", "]")` is odd — implementer must copy exact titles from `TOPIC_TEXTS`, stated inline.
3. **Type consistency:** `RichDoc(*blocks) -> .validate() -> str` consistent across all tasks; `build_*_rich() -> RichDoc` consistent; `reply_rich(message, doc, *, reply_markup, media, fallback)` signature matches Tasks 4–9 call sites; `photo_media(id, image)` id matches `photo_block(id)` everywhere (`"help"`, `"profile"`, `"shop"`, `"inventory"`, `"duel"`, `"leaderboard"`, `"tower"`, `"forge"`, `"quest"`, `"guild"`, `"war"`, `"shadow"`).
4. **Review Focus:** (1) Task 2 forced-failure + every site's verbatim fallback; (2) Task 1 adversarial assert + per-task ADV steps; (3) Task 1 id assert + Task 3 visual probe; (4) Task 4/7/8/9 branch-audit steps with `rg -U`; (5) Task 1 `_nl` assert + builders route newlines. All five pinned.
