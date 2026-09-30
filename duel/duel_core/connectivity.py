"""Is there internet? Asked before calling the cloud model.

With Wi-Fi off, waiting for an HTTP timeout would freeze the stage for seconds. A TCP connect
to the API host with a short timeout answers in milliseconds, and the result is cached briefly
so a round doesn't pay for the check twice.
"""

from __future__ import annotations

import asyncio
import time


class Connectivity:
    def __init__(
        self,
        host: str = "aiplatform.googleapis.com",
        port: int = 443,
        timeout_s: float = 0.8,
        ttl_s: float = 3.0,
        force_offline: bool = False,
    ) -> None:
        self.host, self.port, self.timeout_s, self.ttl_s = host, port, timeout_s, ttl_s
        self.force_offline = force_offline  # rehearsals: simulate "Wi-Fi off" without touching the OS
        self._cached: tuple[float, bool] | None = None

    async def is_online(self) -> bool:
        if self.force_offline:
            return False
        now = time.monotonic()
        if self._cached and now - self._cached[0] < self.ttl_s:
            return self._cached[1]
        online = await self._probe()
        self._cached = (now, online)
        return online

    async def _probe(self) -> bool:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), self.timeout_s)
        except (OSError, asyncio.TimeoutError):
            return False
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
        return True
