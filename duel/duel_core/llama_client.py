"""Async client for llama.cpp's `llama-server` (OpenAI-compatible chat endpoint).

Why next to Ollama: Ollama doesn't expose `logit_bias`, and llama-server does. Dictionary-guided
decoding (tzij_duel/constraints.py) needs it to push the dictionary forms up at the token level
instead of only asking for them in the prompt.

    llama-server -m <gguf> --jinja --parallel 8 -c 32768 --port 8089

`--parallel 8` gives 8 slots that decode concurrently (continuous batching), so MBR with 8
samples costs about one generation's wall time instead of eight.

Sampling: llama.cpp has no absolute-epsilon sampler; `min_p` (drop tokens below p_max · min_p) is
the closest truncation and what we call epsilon sampling here.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from .types import Completion, Message


class LlamaServerError(RuntimeError):
    pass


class LlamaServerClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8089",
        *,
        temperature: float = 0.2,
        max_tokens: int = 128,
        min_p: float | None = None,
        seed: int | None = None,
        logit_bias: list[tuple[str, float]] | None = None,
        timeout_s: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.params: dict[str, Any] = {"temperature": temperature, "max_tokens": max_tokens}
        if min_p is not None:
            self.params["min_p"] = min_p
        if seed is not None:
            self.params["seed"] = seed
        self.logit_bias = list(logit_bias or [])
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=timeout_s, transport=transport)

    def with_bias(self, bias: list[tuple[str, float]]) -> "LlamaServerClient":
        """Same connection and sampling, plus a logit bias for this request's strings."""
        clone = object.__new__(LlamaServerClient)
        clone.base_url, clone.params, clone._http = self.base_url, dict(self.params), self._http
        clone.logit_bias = self.logit_bias + list(bias)
        return clone

    async def complete(self, messages: list[Message], *, model: str) -> Completion:
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": False, **self.params}
        if self.logit_bias:
            # llama-server tokenizes string entries itself and biases every token of the string.
            body["logit_bias"] = [[text, bias] for text, bias in self.logit_bias]
        t0 = time.perf_counter()
        res = await self._http.post("/v1/chat/completions", json=body)
        latency_ms = (time.perf_counter() - t0) * 1000
        if res.status_code != 200:
            raise LlamaServerError(f"llama-server {res.status_code}: {res.text[:200]}")
        data = res.json()
        usage = data.get("usage") or {}
        return Completion(
            text=((data.get("choices") or [{}])[0].get("message") or {}).get("content", "") or "",
            model=model,
            latency_ms=latency_ms,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
        )

    async def is_up(self) -> bool:
        try:
            return (await self._http.get("/health", timeout=1.5)).status_code == 200
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        await self._http.aclose()
