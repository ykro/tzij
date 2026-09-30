"""Cost from per-million-token prices.

Prices live in the app config (env vars), never here: they change over time, and showing
that a frontier model's price moves while the local model's inference stays at zero is
part of the story.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input_per_million: float = 0.0
    output_per_million: float = 0.0

    @classmethod
    def free(cls) -> "Price":
        """Local inference: the laptop is already paid for."""
        return cls(0.0, 0.0)


def cost_usd(price: Price, input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * price.input_per_million + output_tokens * price.output_per_million) / 1_000_000
