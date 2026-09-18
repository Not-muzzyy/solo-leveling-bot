# Telegram Bot Rich Text Formatting — Agent Context

## Purpose

This document defines how an agent should implement rich-text formatting in Telegram bots, especially for messages and media captions.

The preferred format is **Telegram HTML parse mode** because it is generally easier to generate dynamically than MarkdownV2.

---

## 1. Pyrogram Setup

For Pyrogram:

```python
from pyrogram import enums

await message.reply_text(
    caption,
    parse_mode=enums.ParseMode.HTML
)
```

The same approach can be used with media captions:

```python
await message.reply_photo(
    photo="image.jpg",
    caption=caption,
    parse_mode=enums.ParseMode.HTML
)
```

Examples for other media:

```python
await message.reply_video(
    video="video.mp4",
    caption=caption,
    parse_mode=enums.ParseMode.HTML
)

await message.reply_document(
    document="file.zip",
    caption=caption,
    parse_mode=enums.ParseMode.HTML
)

await message.reply_audio(
    audio="song.mp3",
    caption=caption,
    parse_mode=enums.ParseMode.HTML
)
```

---

# 2. Supported HTML Formatting

## Bold

```html
<b>Bold text</b>
```

Alternative:

```html
<strong>Bold text</strong>
```

Example:

```html
<b>Download Complete</b>
```

---

## Italic

```html
<i>Italic text</i>
```

Alternative:

```html
<em>Italic text</em>
```

Example:

```html
<i>Processing your file...</i>
```

---

## Underline

```html
<u>Underlined text</u>
```

Alternative:

```html
<ins>Underlined text</ins>
```

Example:

```html
<u>Important</u>
```

---

## Strikethrough

```html
<s>Strikethrough text</s>
```

Alternative:

```html
<del>Strikethrough text</del>
```

Example:

```html
<s>Old price: ₹999</s>
```

---

## Spoiler

```html
<tg-spoiler>Hidden text</tg-spoiler>
```

Example:

```html
<tg-spoiler>This information is hidden.</tg-spoiler>
```

---

## Inline Code

```html
<code>print("Hello")</code>
```

Example:

```html
Run <code>/start</code> to start the bot.
```

---

## Code Block

```html
<pre>
def hello():
    print("Hello World")
</pre>
```

For a language-specific code block:

```html
<pre><code class="language-python">
def hello():
    print("Hello World")
</code></pre>
```

Example:

```html
<pre><code class="language-javascript">
console.log("Hello World");
</code></pre>
```

---

# 3. Clickable Links

Basic link:

```html
<a href="https://example.com">Open Website</a>
```

Telegram user link:

```html
<a href="tg://user?id=123456789">User</a>
```

Example:

```html
<a href="https://t.me/example">📢 Join Channel</a>
```

Do not put untrusted URLs into links without validating or sanitizing them if the application requires URL safety.

---

# 4. Blockquotes

Normal quote:

```html
<blockquote>
This is a quoted message.
</blockquote>
```

Example:

```html
<blockquote>
<b>Notice</b>

Your download has completed successfully.
</blockquote>
```

Expandable quote:

```html
<blockquote expandable>
This content can be expanded.
</blockquote>
```

Example:

```html
<blockquote expandable>
<b>Additional Information</b>

This section contains additional details that
do not need to be visible immediately.
</blockquote>
```

---

# 5. Custom Emoji

Telegram supports custom emoji using a Telegram custom emoji ID:

```html
<tg-emoji emoji-id="CUSTOM_EMOJI_ID">👍</tg-emoji>
```

Example structure:

```html
<tg-emoji emoji-id="5368324170671202286">👍</tg-emoji>
```

Important:

- The emoji ID must be a valid Telegram custom emoji ID.
- Do not invent random IDs.
- A normal Unicode emoji can be used when a custom emoji is not required.

Normal emoji:

```text
🔥 🎵 📥 ✅ ❌ ⚡ 🚀
```

---

# 6. Combining Formatting

Telegram formatting tags can be combined when the resulting HTML is valid.

Example:

```html
<b><i>Bold and italic</i></b>
```

Another example:

```html
<u><b>Important Information</b></u>
```

Example:

```html
<b>🎵 <i>Download Complete</i></b>
```

Keep nested tags simple and properly closed.

Correct:

```html
<b><i>Hello</i></b>
```

Incorrect:

```html
<b><i>Hello</b></i>
```

---

# 7. New Lines

Use normal newline characters in Python strings.

```python
caption = """
<b>🎬 Video Information</b>

<b>Title:</b> Example Video
<b>Size:</b> 125 MB
<b>Status:</b> <i>Completed</i>
"""
```

You can also construct captions using `\n`:

```python
caption = (
    "<b>🎬 Video Information</b>\n\n"
    "<b>Title:</b> Example Video\n"
    "<b>Size:</b> 125 MB\n"
    "<b>Status:</b> <i>Completed</i>"
)
```

---

# 8. Dynamic Content and HTML Escaping

This is extremely important.

If user-controlled data is inserted into an HTML caption, escape it first.

Use Python's standard library:

```python
from html import escape
```

Example:

```python
title = escape(title)
filename = escape(filename)

caption = f"""
<b>🎬 Title:</b> {title}
<b>📁 File:</b> <code>{filename}</code>
"""
```

Without escaping, content such as:

```text
5 < 10
```

could be interpreted as HTML.

Use:

```python
escape(text)
```

for dynamic content that is not intentionally formatted HTML.

---

# 9. Important Rule for `<code>`

Dynamic code/file names should also be escaped:

```python
from html import escape

filename = escape(filename)

caption = f"<b>File:</b> <code>{filename}</code>"
```

Do not do this with raw user input:

```python
caption = f"<code>{filename}</code>"
```

unless the value is already safely escaped.

---

# 10. Complete Caption Example

```python
from html import escape
from pyrogram import enums

title = escape("Example Video")
filename = escape("example_video.mp4")
size = escape("125 MB")

caption = f"""
<b>╭━━━「 📥 DOWNLOAD 」━━━╮</b>

<b>🎬 Title:</b> {title}
<b>📁 File:</b> <code>{filename}</code>
<b>💾 Size:</b> {size}
<b>⏱ Duration:</b> 03:45

<blockquote>
<b>✅ Download completed successfully!</b>

<i>Your file is ready.</i>
</blockquote>

<b>📌 Commands</b>

<code>/start</code> — Start bot
<code>/help</code> — Help
<code>/settings</code> — Settings

<b>🔗 Links</b>
<a href="https://t.me/example">📢 Channel</a>
<a href="https://example.com">🌐 Website</a>

<tg-spoiler>🔐 Hidden information</tg-spoiler>

<blockquote expandable>
<b>ℹ️ Additional Information</b>

This section contains extra information.
</blockquote>

<b>╰━━━━━━━━━━━━━━━━━━╯</b>
"""

await message.reply_text(
    caption,
    parse_mode=enums.ParseMode.HTML
)
```

---

# 11. Recommended Caption Builder

For a larger bot, avoid manually constructing every caption in every handler.

Create a helper:

```python
from html import escape

def build_caption(title: str, filename: str, size: str) -> str:
    return f"""
<b>📥 Download Complete</b>

<b>🎬 Title:</b> {escape(title)}
<b>📁 File:</b> <code>{escape(filename)}</code>
<b>💾 Size:</b> {escape(size)}

<i>✅ Your file is ready.</i>
"""
```

Then:

```python
caption = build_caption(
    title=title,
    filename=filename,
    size=size
)

await message.reply_text(
    caption,
    parse_mode=enums.ParseMode.HTML
)
```

This keeps formatting consistent across the bot.

---

# 12. Caption Templates

## Download Bot

```python
caption = f"""
<b>╭━━━「 📥 DOWNLOAD 」━━━╮</b>

<b>🎬 Title:</b> {escape(title)}
<b>💾 Size:</b> {escape(size)}
<b>⏱ Duration:</b> {escape(duration)}
<b>📁 Format:</b> {escape(format_name)}

<b>⚡ Status:</b> <i>Completed</i>

<blockquote>
✅ Your file is ready!
</blockquote>

<b>╰━━━━━━━━━━━━━━━━━━╯</b>
"""
```

## Music Bot

```python
caption = f"""
<b>╭━━━「 🎵 MUSIC 」━━━╮</b>

<b>🎵 Title:</b> {escape(title)}
<b>👤 Artist:</b> {escape(artist)}
<b>💿 Album:</b> {escape(album)}
<b>⏱ Duration:</b> {escape(duration)}

<b>🎧 Quality:</b> {escape(quality)}

<i>Enjoy your music! 🎶</i>

<b>╰━━━━━━━━━━━━━━━━━━╯</b>
"""
```

## File Information

```python
caption = f"""
<b>📁 FILE INFORMATION</b>

<b>Name:</b> <code>{escape(filename)}</code>
<b>Size:</b> {escape(size)}
<b>Type:</b> {escape(file_type)}
<b>Uploaded:</b> {escape(upload_time)}

<blockquote>
<b>✅ Upload completed.</b>
</blockquote>
"""
```

---

# 13. HTML vs MarkdownV2

Telegram bots commonly use:

- HTML
- MarkdownV2

For most dynamically generated bot captions, use HTML unless there is a specific reason to use MarkdownV2.

### HTML

```python
caption = "<b>Hello</b> <i>World</i>"

await message.reply_text(
    caption,
    parse_mode=enums.ParseMode.HTML
)
```

### MarkdownV2

```python
caption = "*Hello* _World_"

await message.reply_text(
    caption,
    parse_mode=enums.ParseMode.MARKDOWN_V2
)
```

MarkdownV2 has many characters that require escaping, so it can be more difficult for generated content.

---

# 14. MarkdownV2 Special Characters

When using MarkdownV2, Telegram requires escaping special characters in appropriate contexts.

Common special characters include:

```text
_ * [ ] ( ) ~ ` > # + - = | { } . !
```

For dynamic MarkdownV2 content, implement a proper escaping helper rather than manually escaping random characters.

Example concept:

```python
from re import escape as regex_escape
```

Do not assume Python's regex escaping is identical to Telegram's MarkdownV2 escaping rules. Use a Telegram-specific MarkdownV2 escape function.

---

# 15. Do Not Use Arbitrary HTML

Telegram does **not** support arbitrary browser HTML.

Do not assume these will work:

```html
<div>
<span>
<p>
<table>
<style>
<img>
<br>
```

Use Telegram-supported formatting tags only.

For line breaks, use:

```python
"\n"
```

rather than:

```html
<br>
```

---

# 16. Formatting Support Checklist

When implementing a rich-text system, support at least:

- [x] Bold
- [x] Italic
- [x] Underline
- [x] Strikethrough
- [x] Spoiler
- [x] Inline code
- [x] Code blocks
- [x] Language-specific code blocks
- [x] Clickable URLs
- [x] Telegram user links
- [x] Blockquotes
- [x] Expandable blockquotes
- [x] Custom emoji
- [x] Unicode emoji
- [x] Nested formatting
- [x] New lines
- [x] Safe escaping of dynamic text

---

# 17. Agent Implementation Rules

When implementing Telegram rich-text captions:

1. Prefer HTML parse mode for generated captions.
2. Use `enums.ParseMode.HTML` in Pyrogram.
3. Escape all dynamic/user-controlled text with `html.escape()`.
4. Never treat user-controlled text as trusted HTML.
5. Properly close every formatting tag.
6. Use only Telegram-supported HTML tags.
7. Use `\n` for line breaks.
8. Validate URLs before inserting them into `<a href="...">`.
9. Use valid custom emoji IDs only.
10. Keep caption templates centralized when the bot has many handlers.
11. Make formatting helpers reusable.
12. Test captions with special characters such as `<`, `>`, `&`, quotes, and apostrophes.
13. Remember that Telegram has caption/message length limits; do not assume unlimited HTML.
14. If a caption becomes too large, shorten it or split the content into a separate message where appropriate.
15. Do not require Telegram Premium for standard rich-text formatting.

---

# 18. Minimal Reference

```html
<b>Bold</b>
<i>Italic</i>
<u>Underline</u>
<s>Strike</s>
<tg-spoiler>Spoiler</tg-spoiler>
<code>Code</code>
<pre>Code block</pre>
<a href="https://example.com">Link</a>
<blockquote>Quote</blockquote>
<blockquote expandable>Expandable quote</blockquote>
<tg-emoji emoji-id="ID">👍</tg-emoji>
```

Pyrogram:

```python
from pyrogram import enums

await message.reply_text(
    text,
    parse_mode=enums.ParseMode.HTML
)
```

For media:

```python
await message.reply_photo(
    photo,
    caption=text,
    parse_mode=enums.ParseMode.HTML
)
```

---

## Final Recommendation

Build a small formatting utility layer around Telegram HTML.

Recommended structure:

```text
bot/
├── utils/
│   ├── formatting.py
│   └── captions.py
├── handlers/
│   ├── start.py
│   ├── download.py
│   └── music.py
└── main.py
```

`formatting.py` should contain escaping and reusable formatting helpers.

`captions.py` should contain reusable caption templates.

Handlers should provide data to those helpers instead of duplicating large HTML strings.

This produces consistent formatting, safer dynamic content, and easier maintenance across the entire bot.
