"""`make warmup` retries transient failures, so a cold first call doesn't fail the talk-day check."""

from __future__ import annotations

import asyncio

from duel_core.duel import ContenderResult
from tzij_duel.warmup import with_retries


def _call(statuses: list[str]):
    calls = {"n": 0}

    async def call():
        status = statuses[min(calls["n"], len(statuses) - 1)]
        calls["n"] += 1
        return ContenderResult("goliath", "gemini", status, text="ok" if status == "ok" else "",
                               error=None if status == "ok" else "ReadTimeout: 20 s")

    return call, calls


async def _no_sleep(_):
    return None


def test_a_timeout_then_success_passes():
    call, calls = _call(["error", "ok"])
    r = asyncio.run(with_retries(call, "Goliath", sleep=_no_sleep))
    assert r.status == "ok" and calls["n"] == 2


def test_retries_are_bounded():
    call, calls = _call(["error"])
    r = asyncio.run(with_retries(call, "Goliath", attempts=3, sleep=_no_sleep))
    assert r.status == "error" and calls["n"] == 3


def test_offline_is_not_retried():
    call, calls = _call(["offline"])
    r = asyncio.run(with_retries(call, "Goliath", sleep=_no_sleep))
    assert r.status == "offline" and calls["n"] == 1
