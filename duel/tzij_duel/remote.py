"""The page's client for David's GPU service (private Cloud Run): adds a Google identity token.

On Cloud Run the token comes from the metadata server (the page's service account); on a laptop
(`make examples`) from `gcloud auth print-identity-token`.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from typing import Any

import httpx


class DavidUnavailable(RuntimeError):
    pass


class RemoteDavid:
    def __init__(self, url: str, *, timeout_s: float = 120.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.url = url.rstrip("/")
        self._http = httpx.AsyncClient(base_url=self.url, timeout=timeout_s, transport=transport)
        self._token: tuple[str, float] | None = None

    def _fetch_token(self) -> str:
        try:
            import google.auth.transport.requests
            import google.oauth2.id_token

            return google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), self.url)
        except Exception:
            out = subprocess.run(["gcloud", "auth", "print-identity-token"], capture_output=True, text=True, check=True)
            return out.stdout.strip()

    async def _headers(self) -> dict[str, str]:
        if self._token is None or self._token[1] < time.time():
            token = await asyncio.to_thread(self._fetch_token)
            self._token = (token, time.time() + 45 * 60)  # identity tokens last 1 h
        return {"Authorization": f"Bearer {self._token[0]}"}

    async def health(self, timeout_s: float = 4.0) -> bool:
        """True when David answers at full speed. A request also wakes the service if it was asleep."""
        try:
            res = await self._http.get("/health", headers=await self._headers(), timeout=timeout_s)
            return res.status_code == 200 and bool(res.json().get("ready"))
        except (httpx.HTTPError, ValueError):
            return False

    async def translate(self, text: str, direction: str) -> dict[str, Any]:
        try:
            res = await self._http.post("/translate", json={"text": text, "direction": direction},
                                        headers=await self._headers())
        except httpx.HTTPError as exc:
            raise DavidUnavailable(str(exc)) from exc
        if res.status_code != 200:
            raise DavidUnavailable(f"David {res.status_code}: {res.text[:200]}")
        return res.json()
