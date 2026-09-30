"""Minimal async client for Ollama's REST API (David's side of the duel).

Uses /api/chat with `stream: false`: for short translations the full answer arrives in a few
hundred ms, so streaming adds complexity without changing what the audience sees.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from .types import Completion, Message


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        *,
        temperature: float = 0.2,
        num_predict: int = 128,
        seed: int | None = None,
        keep_alive: str = "30m",  # keep David loaded: a cold load costs seconds on stage
        think: bool = False,  # hybrid-reasoning models think by default; a translation doesn't need it
        timeout_s: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.options: dict[str, Any] = {"temperature": temperature, "num_predict": num_predict}
        if seed is not None:
            self.options["seed"] = seed
        self.keep_alive, self.think = keep_alive, think
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=timeout_s, transport=transport)

    async def complete(self, messages: list[Message], *, model: str) -> Completion:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": self.options,
            "keep_alive": self.keep_alive,
            "think": self.think,
        }
        t0 = time.perf_counter()
        res = await self._http.post("/api/chat", json=body)
        if res.status_code == 400 and "think" in res.text.lower():
            # Models without a thinking mode reject the flag: retry without it.
            body.pop("think")
            res = await self._http.post("/api/chat", json=body)
        latency_ms = (time.perf_counter() - t0) * 1000
        if res.status_code != 200:
            raise OllamaError(f"Ollama {res.status_code}: {res.text[:200]}")
        data = res.json()
        return Completion(
            text=(data.get("message") or {}).get("content", ""),
            model=model,
            latency_ms=latency_ms,
            input_tokens=int(data.get("prompt_eval_count") or 0),
            output_tokens=int(data.get("eval_count") or 0),
        )

    async def is_up(self) -> bool:
        try:
            return (await self._http.get("/api/version", timeout=1.5)).status_code == 200
        except httpx.HTTPError:
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        res = await self._http.get("/api/tags")
        res.raise_for_status()
        return res.json().get("models", [])

    async def has_model(self, model: str) -> bool:
        models = await self.list_models()
        names = {m.get("name") for m in models} | {m.get("model") for m in models}
        return model in names or f"{model}:latest" in names

    async def warm_up(self, model: str) -> None:
        """Load the model into memory before the first round (an empty chat just loads it)."""
        await self._http.post("/api/chat", json={"model": model, "messages": [], "keep_alive": self.keep_alive})

    async def aclose(self) -> None:
        await self._http.aclose()
