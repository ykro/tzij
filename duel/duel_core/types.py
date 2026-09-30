"""Shared types: every model client (local, cloud, mock) returns the same `Completion`,
so the duel, the eval and the scoreboard never care who answered."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class Completion:
    text: str
    model: str
    latency_ms: float  # wall clock, measured by the caller side: what the audience actually waits
    input_tokens: int = 0
    output_tokens: int = 0  # includes "thinking" tokens when the provider bills them as output


class OfflineError(RuntimeError):
    """The model cannot be reached because there is no network (not a model failure)."""


class ModelClient(Protocol):
    async def complete(self, messages: list[Message], *, model: str) -> Completion: ...
