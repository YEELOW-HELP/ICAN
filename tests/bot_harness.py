"""Drives the bot's real, registered aiogram handlers through fake raw
Telegram updates, with only the network boundary faked (via a custom
`BaseSession`). This is the closest thing to a true end-to-end regression
test for the bot: real router, real filters, real FSM transitions -- nothing
about `app/bot/handlers.py` itself is mocked, only the Telegram API and the
AI agent (passed in by the caller) are.
"""

from __future__ import annotations

import itertools
import time
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, Router
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, SendMessage, TelegramMethod
from aiogram.types import Chat, Message

from app.bot.handlers import register_handlers

_id_counter = itertools.count(1)


def _next_id() -> int:
    return next(_id_counter)


class FakeSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod] = []

    async def close(self) -> None:
        pass

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=_next_id(),
                date=datetime.now(timezone.utc),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        if isinstance(method, AnswerCallbackQuery):
            return True
        if isinstance(method, EditMessageReplyMarkup):
            return True
        raise NotImplementedError(f"FakeSession: unsupported Telegram method {type(method).__name__}")

    async def stream_content(self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True):
        yield b""


class BotHarness:
    def __init__(self, session_factory, agent) -> None:
        self.session = FakeSession()
        self.bot = Bot(token="123456:TEST-TOKEN-NOT-REAL", session=self.session)
        self.dp = Dispatcher()
        router = Router()
        register_handlers(router, session_factory, agent)
        self.dp.include_router(router)

    @property
    def sent_messages(self) -> list[SendMessage]:
        return [c for c in self.session.calls if isinstance(c, SendMessage)]

    def last_sent_text(self) -> str | None:
        sent = self.sent_messages
        return sent[-1].text if sent else None

    def texts_since(self, index: int) -> list[str]:
        return [m.text for m in self.sent_messages[index:]]

    async def send_text(self, telegram_id: int, text: str, chat_id: int | None = None) -> None:
        chat_id = chat_id if chat_id is not None else telegram_id
        update = {
            "update_id": _next_id(),
            "message": {
                "message_id": _next_id(),
                "date": int(time.time()),
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": telegram_id, "is_bot": False, "first_name": "Test"},
                "text": text,
            },
        }
        await self.dp.feed_raw_update(self.bot, update)

    async def send_document(self, telegram_id: int, filename: str, chat_id: int | None = None) -> None:
        chat_id = chat_id if chat_id is not None else telegram_id
        update = {
            "update_id": _next_id(),
            "message": {
                "message_id": _next_id(),
                "date": int(time.time()),
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": telegram_id, "is_bot": False, "first_name": "Test"},
                "document": {"file_id": "fake_file", "file_unique_id": "fake_unique", "file_name": filename},
            },
        }
        await self.dp.feed_raw_update(self.bot, update)

    async def click(
        self, telegram_id: int, callback_data: str, chat_id: int | None = None, message_id: int | None = None
    ) -> None:
        chat_id = chat_id if chat_id is not None else telegram_id
        message_id = message_id if message_id is not None else _next_id()
        update = {
            "update_id": _next_id(),
            "callback_query": {
                "id": f"cbq{_next_id()}",
                "from": {"id": telegram_id, "is_bot": False, "first_name": "Test"},
                "message": {
                    "message_id": message_id,
                    "date": int(time.time()),
                    "chat": {"id": chat_id, "type": "private"},
                    "from": {"id": 999999, "is_bot": True, "first_name": "Bot"},
                    "text": "prompt",
                },
                "chat_instance": "instance1",
                "data": callback_data,
            },
        }
        await self.dp.feed_raw_update(self.bot, update)
