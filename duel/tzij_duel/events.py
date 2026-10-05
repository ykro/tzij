"""Server-sent events: every screen (presenter, phones) gets state changes pushed.

SSE instead of polling or WebSockets: one-way is all we need, it survives
proxies, reconnects by itself, and a verdict reaches the presenter screen in
milliseconds over the LAN.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Callable


PRESENTER, VALIDATOR = "presenter", "validator"


class Broadcaster:
    """One subscriber set per audience. The validator's phones never receive the presenter's
    state (model names, latency, cost, reference): blindness is enforced here, not in the UI."""

    def __init__(self, on_change: Callable[[str], None] | None = None) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = {PRESENTER: set(), VALIDATOR: set()}
        # Called with the channel when a subscriber joins or leaves (the presenter shows whether a
        # validator phone is connected).
        self.on_change = on_change

    def _changed(self, channel: str) -> None:
        if self.on_change:
            self.on_change(channel)

    def publish(self, channel: str, event: str, data: Any) -> None:
        message = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        for queue in list(self._subscribers[channel]):
            if queue.qsize() < 100:  # a stuck client must not grow memory forever
                queue.put_nowait(message)

    async def stream(self, channel: str, first: str | None = None, keepalive_s: float = 15.0) -> AsyncIterator[str]:
        queue: asyncio.Queue = asyncio.Queue()
        subscribers = self._subscribers[channel]
        subscribers.add(queue)
        self._changed(channel)
        try:
            if first:
                yield first
            while True:
                try:
                    yield await asyncio.wait_for(queue.get(), keepalive_s)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            subscribers.discard(queue)
            self._changed(channel)

    def count(self, channel: str) -> int:
        return len(self._subscribers[channel])
