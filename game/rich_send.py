"""game/rich_send.py — Rich Message transport with verbatim classic fallback.

Every helper: validate doc -> build InputRichMessage(html, media,
skip_entity_detection=True) -> call kurigram -> on ANY exception run
the caller's fallback() (the original classic call, unchanged).

There is deliberately NO feature flag (spec: user decision). The fallback
is the only safety net; it must never be an empty stub at a call site.
"""
from __future__ import annotations

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

