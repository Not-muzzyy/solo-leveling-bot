"""
game/font_manager.py — Universal Unicode Font Manager and Fallback Renderer.

Provides robust normalization for fancy Unicode "font" generators (Fraktur, Script,
Small Caps, Enclosed/Circled, Fullwidth, Monospace, Mathematical symbols) and
a multi-font fallback cascade for global languages (Korean Hangul, Japanese Kana/Kanji,
Chinese Hanzi, Cyrillic, Greek, Arabic, and Unicode Emojis/Symbols) to ensure
no user ever sees missing-glyph "tofu" boxes (□ / ?).
"""

from __future__ import annotations

import os
import sys
import unicodedata
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

# Mapping for stylistic phonetic Unicode characters (small caps, superscripts, subscripts)
# that standard NFKC does not normalize by default
STYLE_TRANSLATION_MAP = {
    # Small caps
    'ᴀ': 'A', 'ʙ': 'B', 'ᴄ': 'C', 'ᴅ': 'D', 'ᴇ': 'E', 'ꜰ': 'F', 'ɢ': 'G', 'ʜ': 'H',
    'ɪ': 'I', 'ᴊ': 'J', 'ᴋ': 'K', 'ʟ': 'L', 'ᴍ': 'M', 'ɴ': 'N', 'ᴏ': 'O', 'ᴘ': 'P',
    'ǫ': 'Q', 'ʀ': 'R', 'ꜱ': 'S', 'ᴛ': 'T', 'ᴜ': 'U', 'ᴠ': 'V', 'ᴡ': 'W',
    'ʏ': 'Y', 'ᴢ': 'Z',
    # Superscripts
    'ᵃ': 'a', 'ᵇ': 'b', 'ᶜ': 'c', 'ᵈ': 'd', 'ᵉ': 'e', 'ᶠ': 'f', 'ᵍ': 'g', 'ʰ': 'h',
    'ⁱ': 'i', 'ʲ': 'j', 'ᵏ': 'k', 'ˡ': 'l', 'ᵐ': 'm', 'ⁿ': 'n', 'ᵒ': 'o', 'ᵖ': 'p',
    'ʳ': 'r', 'ˢ': 's', 'ᵗ': 't', 'ᵘ': 'u', 'ᵛ': 'v', 'ʷ': 'w', 'ˣ': 'x', 'ʸ': 'y', 'ᶻ': 'z',
    # Subscripts
    'ₐ': 'a', 'ₑ': 'e', 'ₕ': 'h', 'ᵢ': 'i', 'ⱼ': 'j', 'ₖ': 'k', 'ₗ': 'l', 'ₘ': 'm',
    'ₙ': 'n', 'ₒ': 'o', 'ₚ': 'p', 'ᵣ': 'r', 'ₛ': 's', 'ₜ': 't', 'ᵤ': 'u', 'ᵥ': 'v', 'ₓ': 'x',
}


def clean_and_normalize_name(name: Optional[str]) -> str:
    """
    De-stylizes fancy text generator Unicode characters into clean base characters
    while preserving authentic international languages (Hangul, Hanzi, Kana, Cyrillic, etc.)
    and standard emojis.
    
    Examples:
        "𝕾𝖚𝖓𝖌 𝕵𝖎𝖓𝖜𝖔𝖔" -> "Sung Jinwoo"
        "𝓒𝓱𝓪 𝓗𝓪𝓮-𝓘𝓷" -> "Cha Hae-In"
        "ꜱᴜɴɢ ᴊɪɴᴡᴏᴏ" -> "SUNG JINWOO"
        "Ⓢⓤⓝⓖ"       -> "Sung"
        "성진우"       -> "성진우" (preserved)
        "ソン・ジヌ"   -> "ソン・ジヌ" (preserved)
        "成振宇"       -> "成振宇" (preserved)
    """
    if not name:
        return ""

    # 1. Translate small caps and superscript/subscript variants
    chars = [STYLE_TRANSLATION_MAP.get(c, c) for c in name]
    text = "".join(chars)

    # 2. Unicode NFKC normalization translates Mathematical Alphanumeric Symbols
    # (Fraktur, Script, Double-Struck, Sans-Serif Bold/Italic, Monospace, Circled, etc.)
    normalized = unicodedata.normalize("NFKC", text).strip()

    # 3. Strip any leading @ if user accidentally included it
    if normalized.startswith("@"):
        normalized = normalized[1:].strip()

    return normalized


def load_font(font_names: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Cross-platform font loader. Tries font_names against OS font directories."""
    font_dirs = []
    if sys.platform == "win32":
        font_dirs.append(os.environ.get("WINDIR", "C:\\Windows") + "\\Fonts")
    else:
        for d in ["/usr/share/fonts", "/usr/local/share/fonts",
                  os.path.expanduser("~/.fonts"),
                  "/usr/share/fonts/truetype", "/usr/share/fonts/truetype/dejavu",
                  "/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/noto",
                  "/usr/share/fonts/truetype/ubuntu"]:
            if os.path.isdir(d):
                font_dirs.append(d)

    for name in font_names:
        for d in font_dirs:
            path = os.path.join(d, name)
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


class FontCascade:
    """
    Font hierarchy wrapper that seamlessly falls back across system fonts to render
    any character without missing-glyph tofu boxes (□).
    """

    def __init__(self, size: int, is_bold: bool = True, primary_font_names: Optional[list[str]] = None):
        self.size = size
        self.is_bold = is_bold

        # Cross-platform font directories
        font_dirs = []
        if sys.platform == "win32":
            win_fonts = os.environ.get("WINDIR", "C:\\Windows") + "\\Fonts"
            font_dirs.append(win_fonts)
        else:
            # Linux / macOS
            for d in [
                "/usr/share/fonts",
                "/usr/local/share/fonts",
                os.path.expanduser("~/.fonts"),
                "/usr/share/fonts/truetype",
                "/usr/share/fonts/truetype/dejavu",
                "/usr/share/fonts/truetype/liberation",
                "/usr/share/fonts/truetype/noto",
                "/usr/share/fonts/truetype/ubuntu",
            ]:
                if os.path.isdir(d):
                    font_dirs.append(d)

        if not primary_font_names:
            primary_font_names = (
                ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "NotoSans-Bold.ttf", "Ubuntu-R.ttf"]
                if is_bold
                else ["segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "NotoSans-Regular.ttf", "Ubuntu-R.ttf"]
            )

        # Global fallbacks covering Korean, Chinese, Japanese, Emojis, Symbols, and Cyrillic
        fallback_names = (
            [
                "malgun.ttf", "malgunbd.ttf", "batang.ttc", "gulim.ttc", "msyh.ttc", "meiryo.ttc",
                "seguiemj.ttf", "SegoeIcons.ttf", "arial.ttf",
                "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "NotoSans-Regular.ttf", "NotoSansCJK-Regular.ttc",
            ]
            if not is_bold
            else [
                "malgunbd.ttf", "malgun.ttf", "batang.ttc", "gulim.ttc", "msyhbd.ttc", "meiryo.ttc",
                "seguiemj.ttf", "SegoeIcons.ttf", "arial.ttf",
                "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "NotoSans-Bold.ttf", "NotoSansCJK-Bold.ttc",
            ]
        )

        self.fonts: list[ImageFont.FreeTypeFont | ImageFont.ImageFont] = []

        def _try_load(fname: str) -> Optional[ImageFont.FreeTypeFont]:
            for d in font_dirs:
                path = os.path.join(d, fname)
                if os.path.exists(path):
                    try:
                        return ImageFont.truetype(path, size)
                    except Exception:
                        pass
            return None

        # Load primary font
        for fname in primary_font_names:
            font = _try_load(fname)
            if font:
                self.fonts.append(font)
                break
        if not self.fonts:
            try:
                self.fonts.append(ImageFont.load_default(size=size))
            except TypeError:
                self.fonts.append(ImageFont.load_default())

        # Load fallback fonts
        for fname in fallback_names:
            font = _try_load(fname)
            if font:
                self.fonts.append(font)

        # Cache the .notdef glyph bytes for each font to instantly detect missing glyphs
        self._notdef_bytes: list[bytes] = []
        for f in self.fonts:
            try:
                self._notdef_bytes.append(bytes(f.getmask(chr(0xFFFF))))
            except Exception:
                self._notdef_bytes.append(b"")

        self._char_font_cache: dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

    def get_font_for_char(self, ch: str) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Find the first font in the cascade that contains a valid glyph for `ch`."""
        if ch in self._char_font_cache:
            return self._char_font_cache[ch]
        if ch in (" ", "\t", "\n"):
            return self.fonts[0]

        for i, f in enumerate(self.fonts):
            try:
                mask = f.getmask(ch)
                if mask.size != (0, 0) and bytes(mask) != self._notdef_bytes[i]:
                    self._char_font_cache[ch] = f
                    return f
            except Exception:
                continue

        # Default back to primary font if no font supports it
        default_f = self.fonts[0]
        self._char_font_cache[ch] = default_f
        return default_f

    def _split_runs(self, text: str) -> list[tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, str]]:
        """Split text into contiguous runs sharing the same font."""
        if not text:
            return []
        runs = []
        current_font = None
        current_str = []
        for ch in text:
            f = self.get_font_for_char(ch)
            if f != current_font:
                if current_str:
                    runs.append((current_font, "".join(current_str)))
                    current_str = []
                current_font = f
            current_str.append(ch)
        if current_str:
            runs.append((current_font, "".join(current_str)))
        return runs

    def getbbox(self, text: str, clean: bool = True) -> tuple[int, int, int, int]:
        """Compute the bounding box of `text` across the multi-font cascade."""
        if clean:
            text = clean_and_normalize_name(text)
        if not text:
            return (0, 0, 0, 0)

        total_w = 0
        min_top = 9999
        max_bottom = -9999
        for font, run_text in self._split_runs(text):
            bb = font.getbbox(run_text)
            total_w += (bb[2] - bb[0])
            min_top = min(min_top, bb[1])
            max_bottom = max(max_bottom, bb[3])

        if min_top == 9999:
            min_top = 0
            max_bottom = self.size
        return (0, min_top, total_w, max_bottom)

    def get_width(self, text: str, max_w: Optional[int] = None) -> int:
        """Compute the rendered pixel width of text."""
        bb = self.getbbox(text)
        w = bb[2] - bb[0]
        if max_w is not None and w > max_w:
            return max_w
        return w

    def draw_text(
        self,
        draw: ImageDraw.ImageDraw,
        xy: tuple[int, int],
        text: str,
        fill,
        clean: bool = True,
        max_w: Optional[int] = None,
        anchor: Optional[str] = None,
    ) -> int:
        """
        Draw text on the image with automatic character-level fallback.
        Returns total width drawn in pixels.
        Supports optional max_w truncation and Pillow-style anchor ('mt', 'ra', 'mm', etc.).
        """
        if clean:
            text = clean_and_normalize_name(text)
        if not text:
            return 0

        # Handle max width constraint
        if max_w is not None:
            bb = self.getbbox(text, clean=False)
            w = bb[2] - bb[0]
            if w > max_w:
                while len(text) > 2 and self.getbbox(text + "...", clean=False)[2] > max_w:
                    text = text[:-1]
                text += "..."

        x, y = xy

        # Handle anchor alignment
        if anchor:
            bb = self.getbbox(text, clean=False)
            tw = bb[2] - bb[0]
            th = bb[3] - bb[1]
            if anchor.startswith("m"):  # mt, mm, mb
                x -= tw // 2
            elif anchor.startswith("r"):  # ra, rt, rm, rb
                x -= tw
            if len(anchor) > 1:
                if anchor[1] == "m":
                    y -= th // 2
                elif anchor[1] == "b":
                    y -= th

        cur_x = x
        for font, run_text in self._split_runs(text):
            draw.text((cur_x, y), run_text, font=font, fill=fill)
            bb = font.getbbox(run_text)
            cur_x += (bb[2] - bb[0])

        return cur_x - x


# Global font cascade cache by (size, is_bold)
_CASCADE_CACHE: dict[tuple[int, bool], FontCascade] = {}


def get_font_cascade(size: int, is_bold: bool = True) -> FontCascade:
    """Retrieve or instantiate a cached FontCascade for the given size and weight."""
    key = (size, is_bold)
    if key not in _CASCADE_CACHE:
        _CASCADE_CACHE[key] = FontCascade(size=size, is_bold=is_bold)
    return _CASCADE_CACHE[key]
