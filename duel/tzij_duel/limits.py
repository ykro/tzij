"""Protection against running up the bill on the public page.

The page is public and both sides cost money: Gemini per call, David per second his GPU is up.
These limits never get in the way of a talk (a few dozen translations, one or two wake-ups) but
stop a script or a forgotten tab from spending all day:

  per IP     translations per minute, and readiness checks per minute (each one may wake David)
  per day    Gemini calls and David wake-ups for the whole page
  per visit  a page left open keeps David awake for at most KEEPALIVE_MAX_MIN after its last
             translation; after that the readiness checks stop reaching David and he can sleep
             (the next translation wakes him again)

Counters live in the page's memory: the page runs as a single instance (infra/21-page.sh,
--max-instances 1), so they are global. A restart resets them, which only happens when nobody uses
the page.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from datetime import date

# Cloud Run turns David's GPU off about 15 minutes after his last request.
DAVID_IDLE_S = 15 * 60


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


class Limits:
    def __init__(self, *, translate_per_min: int | None = None, checks_per_min: int | None = None,
                 gemini_per_day: int | None = None, wakes_per_day: int | None = None,
                 keepalive_max_min: int | None = None, clock=time.monotonic, today=date.today) -> None:
        self.translate_per_min = translate_per_min if translate_per_min is not None else _int("LIMIT_TRANSLATE_PER_MIN", 120)
        self.checks_per_min = checks_per_min if checks_per_min is not None else _int("LIMIT_CHECKS_PER_MIN", 240)
        self.gemini_per_day = gemini_per_day if gemini_per_day is not None else _int("LIMIT_GEMINI_PER_DAY", 2000)
        self.wakes_per_day = wakes_per_day if wakes_per_day is not None else _int("LIMIT_DAVID_WAKES_PER_DAY", 12)
        self.keepalive_s = 60 * (keepalive_max_min if keepalive_max_min is not None else _int("KEEPALIVE_MAX_MIN", 45))
        self.clock, self.today = clock, today
        self._hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self._day = today()
        self.gemini_today = 0
        self.wakes_today = 0
        self._last_translate: dict[str, float] = {}
        self._last_ready: float | None = None
        self._waking = False

    def _new_day(self) -> None:
        if self.today() != self._day:
            self._day, self.gemini_today, self.wakes_today = self.today(), 0, 0

    def allow(self, ip: str, kind: str) -> bool:
        """Sliding one-minute window per IP and kind ("translate" or "check")."""
        limit = self.translate_per_min if kind == "translate" else self.checks_per_min
        window, now = self._hits[(ip, kind)], self.clock()
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            return False
        window.append(now)
        return True

    def translated(self, ip: str) -> None:
        self._last_translate[ip] = self.clock()

    def keep_alive(self, ip: str) -> bool:
        """May this visitor's readiness check reach David? Only within KEEPALIVE_MAX_MIN of its last translation
        (or before its first one: opening the page wakes him)."""
        last = self._last_translate.get(ip)
        return last is None or self.clock() - last <= self.keepalive_s

    def gemini_call(self) -> bool:
        self._new_day()
        if self.gemini_today >= self.gemini_per_day:
            return False
        self.gemini_today += 1
        return True

    def start_check(self) -> bool:
        """Before a readiness check reaches David. If he has been asleep (no "ready" for longer than his idle
        timeout), this check wakes him: one wake-up, counted once until he answers ready. False when the
        day's wake-ups are used up."""
        self._new_day()
        awake = self._last_ready is not None and self.clock() - self._last_ready <= DAVID_IDLE_S
        if awake or self._waking:
            return True
        if self.wakes_today >= self.wakes_per_day:
            return False
        self.wakes_today += 1
        self._waking = True
        return True

    def end_check(self, ready: bool) -> None:
        if ready:
            self._last_ready, self._waking = self.clock(), False
