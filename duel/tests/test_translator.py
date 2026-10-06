"""Translator page (/traductor/): David and Goliath side by side, plus the example phrases it offers."""

import json

import httpx

from tzij_duel import examples as ex
from tzij_duel.main import create_app


async def _client(service):
    app = create_app(service.settings, service)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_translate_compares_david_and_goliath_without_a_round(service):
    async with await _client(service) as client:
        res = await client.post("/api/translate", json={"text": "  El perro duerme en la casa. ", "direction": "es-quc"})
        state = (await client.get("/api/state")).json()
    body = res.json()
    assert res.status_code == 200
    assert body["source_text"] == "El perro duerme en la casa." and body["reference"] is None
    for name, model in (("david", service.david.model), ("goliath", service.goliath.model)):
        assert body[name]["status"] == "ok" and body[name]["text"] and body[name]["model"] == model
        assert body[name]["closeness"] is None  # typed text: nothing to compare against
    assert body["david"]["cost_usd"] == 0.0 and body["goliath"]["cost_usd"] > 0.0
    # Translating is not a round: nothing reaches the duel's scoreboard.
    assert state["round"] is None and state["scoreboard"]["david"]["evaluation_rounds"] == 0


async def test_each_side_can_be_asked_alone(service):
    async with await _client(service) as client:
        david = (await client.post("/api/translate", json={"text": "El perro duerme en la casa.", "side": "david"})).json()
        goliath = (await client.post("/api/translate", json={"text": "El perro duerme en la casa.", "side": "goliath"})).json()
    assert "david" in david and "goliath" not in david
    assert "goliath" in goliath and "david" not in goliath


async def test_an_example_shows_the_correct_translation_and_closeness(service, monkeypatch):
    example = {"pair_id": "n1", "direction": "es-quc", "text": "El perro duerme en la casa.",
               "reference": "Le tz'i' kawar pa le ja.", "source": "Fixture", "license": "test-only", "url": "https://example.test/"}
    monkeypatch.setattr("tzij_duel.main.load_examples", lambda: [example])
    async with await _client(service) as client:
        picked = (await client.post("/api/translate", json={"text": example["text"], "example": "n1"})).json()
        edited = (await client.post("/api/translate", json={"text": "El perro duerme.", "example": "n1"})).json()
    assert picked["reference"]["text"] == example["reference"] and picked["reference"]["source"] == "Fixture"
    assert picked["david"]["closeness"] is not None and picked["goliath"]["closeness"] is not None
    # The box was edited after picking the example: typed text, no reference.
    assert edited["reference"] is None and edited["david"]["closeness"] is None


async def test_translate_works_both_ways_and_rejects_empty(service):
    async with await _client(service) as client:
        back = await client.post("/api/translate", json={"text": "Le tz'i' kawar pa le ja.", "direction": "quc-es"})
        empty = await client.post("/api/translate", json={"text": "   ", "direction": "es-quc"})
        missing = await client.post("/api/translate", json={"text": "", "direction": "es-quc"})
    assert back.status_code == 200 and back.json()["direction"] == "quc-es"
    assert empty.status_code == 422 and missing.status_code == 422


async def test_offline_goliath_says_so_and_david_still_translates(service):
    service.connectivity.force_offline = True
    async with await _client(service) as client:
        res = await client.post("/api/translate", json={"text": "El perro duerme en la casa.", "direction": "es-quc"})
    body = res.json()
    assert body["online"] is False
    assert body["david"]["status"] == "ok" and body["goliath"]["status"] == "offline"


async def test_examples_endpoint_serves_the_tracked_examples(service, tmp_path, monkeypatch):
    path = tmp_path / "examples.json"
    path.write_text(json.dumps({"examples": [{
        "pair_id": "n1", "direction": "es-quc", "text": "Conexión segura", "reference": "Chajital t'iqonem",
        "source": "Mozilla Pontoon (Firefox Focus)", "url": "https://example.test/", "license": "MPL-2.0",
        "chrf": [100.0, 100.0, 100.0]}]}))
    monkeypatch.setattr(ex, "EXAMPLES", path)
    monkeypatch.setattr("tzij_duel.main.load_examples", lambda: ex.load_examples(path))
    async with await _client(service) as client:
        res = await client.get("/api/examples")
    assert res.json() == [{"pair_id": "n1", "direction": "es-quc", "text": "Conexión segura", "reference": "Chajital t'iqonem",
                           "source": "Mozilla Pontoon (Firefox Focus)", "url": "https://example.test/", "license": "MPL-2.0"}]


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
        # The use case David wins: the Firefox Focus translation memory, Spanish -> K'iche'.
        assert e["direction"] == "es-quc" and e["product"] == "focus-for-android"
        assert e["license"].startswith("MPL-2.0") and e["url"].startswith("https://")
        assert e["reference"] and e["text"]
        runs = list(zip(e["david_chrf"], e["goliath_chrf"]))
        assert ex.passes(runs, len(runs), data["min_chrf"], data["min_margin"]) and len(runs) >= 3
    assert len({e["pair_id"] for e in examples}) == len(examples)
