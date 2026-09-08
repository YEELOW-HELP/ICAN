from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class Debouncer:
    """Coalesces rapid-fire messages from the same key (e.g. a Telegram user
    splitting one answer across several messages) into a single flush call,
    fired `delay_seconds` after the last push. Keeps the AI screening agent
    from being called once per message when it should be called once per
    "turn" — directly bounds wasted API spend."""

    def __init__(self, delay_seconds: float, flush: Callable[[int, list[str]], Awaitable[None]]) -> None:
        self._delay = delay_seconds
        self._flush = flush
        self._buffers: dict[int, list[str]] = {}
        self._tasks: dict[int, asyncio.Task] = {}

    def push(self, key: int, text: str) -> None:
        self._buffers.setdefault(key, []).append(text)

        existing_task = self._tasks.get(key)
        if existing_task is not None and not existing_task.done():
            existing_task.cancel()

        self._tasks[key] = asyncio.create_task(self._wait_and_flush(key))

    async def _wait_and_flush(self, key: int) -> None:
        try:
            await asyncio.sleep(self._delay)
        except asyncio.CancelledError:
            return  # superseded by a newer message; that task will flush instead

        texts = self._buffers.pop(key, None)
        self._tasks.pop(key, None)
        if not texts:
            return

        try:
            await self._flush(key, texts)
        except Exception:
            # Last-resort net: the flush callback is expected to handle its
            # own errors (e.g. by messaging the user), but a bug there must
            # never surface as a silently swallowed task exception that
            # leaves the user with no reply at all.
            logger.exception("Debouncer flush failed for key=%s", key)
