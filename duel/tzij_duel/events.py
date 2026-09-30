"""Server-sent events: every screen (presenter, phones) gets state changes pushed.

SSE instead of polling or WebSockets: one-way is all we need, it survives
proxies, reconnects by itself, and a verdict reaches the presenter screen in
milliseconds over the LAN.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator


class Broadcaster:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def publish(self, event: str, data: Any) -> None:
        message = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        for queue in list(self._subscribers):
            if queue.qsize() < 100:  # a stuck client must not grow memory forever
                queue.put_nowait(message)

    async def stream(self, first: str | None = None, keepalive_s: float = 15.0) -> AsyncIterator[str]:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            if first:
                yield first
            while True:
                try:
                    yield await asyncio.wait_for(queue.get(), keepalive_s)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            self._subscribers.discard(queue)

    @property
    def subscribers(self) -> int:
        return len(self._subscribers)
