"""Deterministic stand-in for any model client (`MOCK_AI=1`).

Tests and rehearsals must run without network or GPUs. The mock answers from a responder
function (default: echo the last user message), with a fixed fake latency and token counts
derived from word counts, so cost and latency code paths are exercised too.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from .types import Completion, Message, OfflineError


def _last_user(messages: list[Message]) -> str:
    return next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")


class MockClient:
    def __init__(
        self,
        responder: Callable[[list[Message]], str] | None = None,
        *,
        latency_ms: float = 120.0,
        offline: bool = False,
        sleep: bool = False,
    ) -> None:
        self.responder = responder or _last_user
        self.latency_ms, self.offline, self.sleep = latency_ms, offline, sleep
        self.calls: list[tuple[str, list[Message]]] = []

    async def complete(self, messages: list[Message], *, model: str) -> Completion:
        self.calls.append((model, messages))
        if self.offline:
            raise OfflineError("mock offline")
        if self.sleep:
            await asyncio.sleep(self.latency_ms / 1000)
        text = self.responder(messages)
        prompt_words = sum(len(m["content"].split()) for m in messages)
        return Completion(
            text=text,
            model=model,
            latency_ms=self.latency_ms,
            input_tokens=int(prompt_words * 1.4),
            output_tokens=int(len(text.split()) * 1.4) + 1,
        )
