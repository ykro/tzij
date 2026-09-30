"""One duel = the same messages sent to every contender in parallel.

Parallel, not sequential: the audience sees both answers arrive at the same time, and neither
model pays for the other's latency. A contender that fails or has no network doesn't take the
round down; it just reports its status.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any, Literal

from .cost import Price, cost_usd
from .metrics import chrf_pp
from .prompts import clean_translation
from .types import Message, ModelClient, OfflineError

Status = Literal["ok", "offline", "error"]


@dataclass
class Contender:
    name: str  # role in the duel, e.g. "david" / "goliath"
    client: ModelClient
    model: str
    price: Price
    requires_network: bool = False


@dataclass
class ContenderResult:
    name: str
    model: str
    status: Status
    text: str = ""
    latency_ms: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    chrf: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def _run_one(c: Contender, messages: list[Message], online: bool, reference: str | None) -> ContenderResult:
    if c.requires_network and not online:
        return ContenderResult(c.name, c.model, "offline", error="sin conexión")
    try:
        comp = await c.client.complete(messages, model=c.model)
    except OfflineError as exc:
        return ContenderResult(c.name, c.model, "offline", error=str(exc)[:200])
    except Exception as exc:  # a failing contender must not break the round
        return ContenderResult(c.name, c.model, "error", error=f"{type(exc).__name__}: {str(exc)[:200]}")
    text = clean_translation(comp.text)
    return ContenderResult(
        name=c.name,
        model=c.model,
        status="ok",
        text=text,
        latency_ms=round(comp.latency_ms, 1),
        input_tokens=comp.input_tokens,
        output_tokens=comp.output_tokens,
        cost_usd=cost_usd(c.price, comp.input_tokens, comp.output_tokens),
        chrf=round(chrf_pp(text, reference), 2) if reference else None,
    )


async def run_duel(
    contenders: list[Contender],
    messages: list[Message],
    *,
    reference: str | None = None,
    online: bool = True,
) -> dict[str, ContenderResult]:
    results = await asyncio.gather(*(_run_one(c, messages, online, reference) for c in contenders))
    return {r.name: r for r in results}
