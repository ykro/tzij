"""Cost protection on the public page: per-IP rates, daily caps and the keep-alive limit."""

from datetime import date

import httpx

from tzij_duel.limits import Limits
from tzij_duel.page import DAVID_CAP_TEXT, GEMINI_CAP_TEXT, create_app


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_per_ip_window_resets_after_a_minute():
    clock = Clock()
    lim = Limits(translate_per_min=2, clock=clock)
    assert lim.allow("a", "translate") and lim.allow("a", "translate")
    assert not lim.allow("a", "translate")
    assert lim.allow("b", "translate")  # another visitor is not affected
    clock.t = 61
    assert lim.allow("a", "translate")


def test_gemini_daily_cap_resets_the_next_day():
    day = [date(2026, 10, 7)]
    lim = Limits(gemini_per_day=2, today=lambda: day[0])
    assert lim.gemini_call() and lim.gemini_call() and not lim.gemini_call()
    day[0] = date(2026, 10, 8)
    assert lim.gemini_call()


def test_a_wake_up_is_counted_once_until_david_is_ready():
    clock = Clock()
    lim = Limits(wakes_per_day=1, clock=clock)
    assert lim.start_check() and lim.start_check()  # the same wake-up, asked every 3 s
    lim.end_check(True)
    clock.t = 10 * 60
    assert lim.start_check()  # still awake: no new wake-up
    lim.end_check(True)
    clock.t += 16 * 60  # asleep again
    assert not lim.start_check()  # the day's only wake-up is used


def test_a_page_left_open_stops_keeping_david_awake():
    clock = Clock()
    lim = Limits(keepalive_max_min=45, clock=clock)
    assert lim.keep_alive("a")  # opening the page wakes him
    lim.translated("a")
    clock.t = 44 * 60
    assert lim.keep_alive("a")
    clock.t = 46 * 60
    assert not lim.keep_alive("a")
    lim.translated("a")
    assert lim.keep_alive("a")


def _client(page):
    app = create_app(page.settings, page)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_the_page_answers_the_limits_in_plain_spanish(page):
    page.limits = Limits(translate_per_min=1, gemini_per_day=0, wakes_per_day=0)
    async with _client(page) as client:
        first = (await client.post("/api/translate", json={"text": "El perro duerme bajo la mesa."})).json()
        second = await client.post("/api/translate", json={"text": "El perro duerme bajo la mesa."})
        david = (await client.get("/api/david")).json()
    assert first["goliath"]["error"] == GEMINI_CAP_TEXT and first["david"]["error"] == DAVID_CAP_TEXT
    assert second.status_code == 429 and "espera" in second.json()["detail"]
    assert david == {"ready": False, "capped": True}


def test_talk_day_usage_is_far_below_the_default_caps():
    lim = Limits()
    assert lim.translate_per_min >= 20 and lim.gemini_per_day >= 1000 and lim.wakes_per_day >= 5
    assert lim.keepalive_s >= 30 * 60
