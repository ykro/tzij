"""The demo page's service: David and Goliath side by side, plus the example phrases it offers."""

import json

import httpx

from tzij_duel import examples as ex
from tzij_duel.page import Page, create_app
from tzij_duel.remote import RemoteDavid


async def _client(page):
    app = create_app(page.settings, page)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_translate_shows_both_translations_with_time_and_cost(page):
    async with await _client(page) as client:
        res = await client.post("/api/translate", json={"text": "  El perro duerme bajo la mesa. ", "direction": "es-quc"})
    body = res.json()
    assert res.status_code == 200
    assert body["source_text"] == "El perro duerme bajo la mesa." and body["reference"] is None
    for name, model in (("david", "gemma-test"), ("goliath", "gemini-test")):
        assert body[name]["status"] == "ok" and body[name]["text"] and body[name]["model"] == model
        assert body[name]["latency_ms"] > 0
        assert body[name]["closeness"] is None  # typed text not in the data: nothing to compare against
    # David: the seconds he worked × his GPU instance's price per second (4 vCPU + 16 GiB + L4 by default).
    david = body["david"]["cost"]
    assert david["gpu_seconds"] > 0 and david["usd_per_hour"] == 1.05
    assert abs(david["usd"] - david["gpu_seconds"] * (0.0001867 + 4 * 0.000018 + 16 * 0.000002)) < 1e-6
    # Goliath: his tokens at Gemini's price of the day.
    assert body["goliath"]["cost"]["tokens"] >= 0 and body["goliath"]["cost"]["usd"] >= 0


async def test_a_typed_phrase_that_is_in_the_licensed_data_is_measured(page):
    async with await _client(page) as client:
        body = (await client.post("/api/translate", json={"text": "el perro duerme en la casa", "direction": "es-quc"})).json()
    assert body["reference"]["text"] == "Le tz'i' kawar pa le ja." and body["reference"]["where"] == "memoria"
    assert body["david"]["closeness"] is not None and body["goliath"]["closeness"] is not None


async def test_evidence_shows_the_memory_and_the_shared_words(page):
    async with await _client(page) as client:
        res = await client.post("/api/evidence", json={"text": "El perro duerme bajo la mesa.", "direction": "es-quc",
                                                       "outputs": {"david": "Le tz'i' kawar", "goliath": "Xaq jun"}})
    body = res.json()
    assert res.status_code == 200 and body["memory"]
    assert all({"source_text", "target_text", "source"} <= set(m) for m in body["memory"])
    david = {w["word"]: w["in_memory"] for w in body["words"]["david"]}
    assert david["tz'i'"] is True
    assert not any(w["in_memory"] for w in body["words"]["goliath"])


async def test_each_side_can_be_asked_alone(page):
    async with await _client(page) as client:
        david = (await client.post("/api/translate", json={"text": "El perro duerme en la casa.", "side": "david"})).json()
        goliath = (await client.post("/api/translate", json={"text": "El perro duerme en la casa.", "side": "goliath"})).json()
    assert "david" in david and "goliath" not in david
    assert "goliath" in goliath and "david" not in goliath


async def test_an_example_shows_the_correct_translation_and_closeness(page, monkeypatch):
    example = {"pair_id": "n1", "direction": "es-quc", "text": "El perro duerme en la casa.",
               "reference": "Le tz'i' kawar pa le ja.", "source": "Fixture", "license": "test-only", "url": "https://example.test/"}
    monkeypatch.setattr("tzij_duel.page.load_examples", lambda: [example])
    async with await _client(page) as client:
        picked = (await client.post("/api/translate", json={"text": example["text"], "example": "n1"})).json()
        edited = (await client.post("/api/translate", json={"text": "El perro duerme.", "example": "n1"})).json()
    assert picked["reference"]["text"] == example["reference"] and picked["reference"]["source"] == "Fixture"
    assert picked["david"]["closeness"] is not None and picked["goliath"]["closeness"] is not None
    # The box was edited after picking the example: typed text, no reference.
    assert edited["reference"] is None and edited["david"]["closeness"] is None


async def test_translate_works_both_ways_and_rejects_empty(page):
    async with await _client(page) as client:
        back = await client.post("/api/translate", json={"text": "Le tz'i' kawar pa le ja.", "direction": "quc-es"})
        empty = await client.post("/api/translate", json={"text": "   ", "direction": "es-quc"})
        missing = await client.post("/api/translate", json={"text": "", "direction": "es-quc"})
    assert back.status_code == 200 and back.json()["direction"] == "quc-es"
    assert empty.status_code == 422 and missing.status_code == 422


async def test_info_and_david_readiness(page):
    async with await _client(page) as client:
        info = (await client.get("/api/info")).json()
        ready = (await client.get("/api/david")).json()
    assert info["david"] == "gemma-test" and info["goliath"] == "gemini-test"
    assert info["david_usd_per_hour"] == 1.05 and info["gemini_usd_per_m"] == {"input": 0.75, "output": 3.75}
    assert ready == {"ready": True}


def _remote(handler) -> RemoteDavid:
    remote = RemoteDavid("https://david.test", transport=httpx.MockTransport(handler))
    remote._fetch_token = lambda: "token"  # no metadata server in tests
    return remote


async def test_remote_david_sends_an_identity_token_and_reads_readiness():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen[request.url.path] = request.headers.get("authorization")
        if request.url.path == "/health":
            return httpx.Response(200, json={"ready": False})
        return httpx.Response(200, json={"status": "ok", "text": "Chajital t'iqonem", "model": "m", "error": None})

    remote = _remote(handler)
    assert await remote.health() is False
    assert (await remote.translate("Conexión segura", "es-quc"))["text"] == "Chajital t'iqonem"
    assert seen == {"/health": "Bearer token", "/translate": "Bearer token"}


async def test_david_down_is_an_error_on_his_side_only(settings, page):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    broken = Page(settings, david=_remote(handler), goliath=page.goliath)
    async with await _client(broken) as client:
        body = (await client.post("/api/translate", json={"text": "El perro duerme en la casa."})).json()
        ready = (await client.get("/api/david")).json()
    assert body["david"]["status"] == "error" and body["david"]["text"] == ""
    assert body["goliath"]["status"] == "ok"
    assert ready == {"ready": False}


async def test_examples_endpoint_serves_the_tracked_examples(page, tmp_path, monkeypatch):
    path = tmp_path / "examples.json"
    path.write_text(json.dumps({"examples": [{
        "pair_id": "n1", "direction": "es-quc", "text": "Conexión segura", "reference": "Chajital t'iqonem",
        "source": "Mozilla Pontoon (Firefox Focus)", "url": "https://example.test/", "license": "MPL-2.0",
        "chrf": [100.0, 100.0, 100.0]}]}))
    monkeypatch.setattr("tzij_duel.page.load_examples", lambda: ex.load_examples(path))
    async with await _client(page) as client:
        res = await client.get("/api/examples")
    assert res.json() == [{"pair_id": "n1", "direction": "es-quc", "text": "Conexión segura", "reference": "Chajital t'iqonem",
                           "source": "Mozilla Pontoon (Firefox Focus)", "url": "https://example.test/", "license": "MPL-2.0",
                           "product": "Firefox Focus"}]


def test_passes_requires_david_close_and_clearly_ahead_every_time():
    assert ex.passes([(100.0, 20.0), (82.5, 30.0), (50.0, 35.0)])
    assert not ex.passes([(100.0, 20.0), (49.9, 10.0), (100.0, 20.0)])  # David not close enough once
    assert not ex.passes([(100.0, 20.0), (60.0, 50.0), (100.0, 20.0)])  # Goliath too close once
    assert not ex.passes([(100.0, 20.0), (100.0, None), (100.0, 20.0)])  # a failed call is a fail
    assert not ex.passes([(100.0, 20.0), (100.0, 20.0)])  # stopped early: not checked enough times


def test_tracked_examples_are_licensed_winning_case_phrases():
    data = json.loads(ex.EXAMPLES.read_text(encoding="utf-8"))
    examples = data["examples"]
    assert len(examples) >= 6
    for e in examples:
        # The use case David wins: a translation memory (Mozilla Pontoon products), Spanish -> K'iche'.
        assert e["direction"] == "es-quc" and e["product"] in ex.PRODUCT_NAME
        assert e["license"].startswith("MPL-2.0") and e["url"].startswith("https://")
        assert e["reference"] and e["text"]
        runs = list(zip(e["david_chrf"], e["goliath_chrf"]))
        assert ex.passes(runs, len(runs), data["min_chrf"], data["min_margin"]) and len(runs) >= 3
    assert len({e["pair_id"] for e in examples}) == len(examples)


def test_gemini_price_changes_on_the_announced_day(settings):
    from datetime import date

    from tzij_duel.settings import gemini_price_on

    settings.gemini_next_price = "2027-01-01:1.50/7.50"
    assert gemini_price_on(settings, date(2026, 12, 31)) == (0.75, 3.75)
    assert gemini_price_on(settings, date(2027, 1, 1)) == (1.5, 7.5)
