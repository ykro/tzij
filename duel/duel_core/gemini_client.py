"""Gemini via Vertex AI with the Google Gen AI SDK (Goliath's side of the duel).

Auth is ADC; no API keys. Network failures are raised as `OfflineError` so the duel can show
"Goliath offline" instead of a stack trace.
"""

from __future__ import annotations

import asyncio
import socket
import time

from .types import Completion, Message, OfflineError


def _is_network_error(exc: BaseException) -> bool:
    import httpx  # google-genai uses httpx under the hood

    try:
        from google.auth.exceptions import TransportError
    except ImportError:  # pragma: no cover
        TransportError = ()  # type: ignore[assignment]
    network = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, socket.gaierror, ConnectionError, TransportError)
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, network):
            return True
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__  # type: ignore[assignment]
    return False


class GeminiClient:
    def __init__(
        self,
        project: str,
        location: str = "global",
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        thinking_level: str | None = "low",
        timeout_s: float = 20.0,
    ) -> None:
        from google import genai

        self._client = genai.Client(vertexai=True, project=project, location=location)
        self.temperature, self.max_output_tokens = temperature, max_output_tokens
        self.thinking_level, self.timeout_s = thinking_level, timeout_s

    def _config(self, system: str | None):
        from google.genai import types

        return types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_level=self.thinking_level) if self.thinking_level else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),  # no tools here
        )

    async def complete(self, messages: list[Message], *, model: str) -> Completion:
        from google.genai import types

        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system") or None
        contents = [
            types.Content(role="model" if m["role"] == "assistant" else "user", parts=[types.Part(text=m["content"])])
            for m in messages
            if m["role"] != "system"
        ]
        t0 = time.perf_counter()
        try:
            res = await asyncio.wait_for(
                self._client.aio.models.generate_content(model=model, contents=contents, config=self._config(system)),
                self.timeout_s,
            )
        except asyncio.TimeoutError as exc:
            # Slow is not offline: the round shows an error for Goliath, not "sin conexión".
            raise TimeoutError(f"Gemini did not answer in {self.timeout_s}s") from exc
        except Exception as exc:
            if _is_network_error(exc):
                raise OfflineError(str(exc)) from exc
            raise
        latency_ms = (time.perf_counter() - t0) * 1000
        usage = res.usage_metadata
        # Thinking tokens are billed at the output rate, so they count as output here.
        out_tokens = (getattr(usage, "candidates_token_count", 0) or 0) + (getattr(usage, "thoughts_token_count", 0) or 0)
        return Completion(
            text=res.text or "",
            model=model,
            latency_ms=latency_ms,
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=out_tokens,
        )
