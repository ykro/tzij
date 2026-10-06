"""Translator page (/traductor/): David alone, plus the example phrases it offers."""

import json

import httpx

from tzij_duel import examples as ex
from tzij_duel.main import create_app


async def _client(service):
    app = create_app(service.settings, service)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_translate_returns_davids_translation_only(service):
    async with await _client(service) as client:
        res = await client.post("/api/translate", json={"text": "  El perro duerme en la casa. ", "direction": "es-quc"})
        state = (await client.get("/api/state")).json()
    body = res.json()
    assert res.status_code == 200
    assert body["status"] == "ok" and body["text"]
    assert body["source_text"] == "El perro duerme en la casa."
    assert body["model"] == service.david.model
    assert "chrf" not in body and "goliath" not in json.dumps(body).lower()
    # Translating is not a round: nothing reaches the duel's scoreboard.
    assert state["round"] is None and state["scoreboard"]["david"]["evaluation_rounds"] == 0


async def test_translate_works_both_ways_and_rejects_empty(service):
    async with await _client(service) as client:
        back = await client.post("/api/translate", json={"text": "Le tz'i' kawar pa le ja.", "direction": "quc-es"})
        empty = await client.post("/api/translate", json={"text": "   ", "direction": "es-quc"})
        missing = await client.post("/api/translate", json={"text": "", "direction": "es-quc"})
    assert back.status_code == 200 and back.json()["direction"] == "quc-es"
    assert empty.status_code == 422 and missing.status_code == 422


async def test_translate_works_with_goliath_offline(service):
    # The page only uses David, who runs on the laptop: no internet needed.
    service.connectivity.force_offline = True
    async with await _client(service) as client:
        res = await client.post("/api/translate", json={"text": "El perro duerme en la casa.", "direction": "es-quc"})
    assert res.json()["status"] == "ok"


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
    assert res.json() == [{"pair_id": "n1", "direction": "es-quc", "text": "Conexión segura",
                           "source": "Mozilla Pontoon (Firefox Focus)", "url": "https://example.test/", "license": "MPL-2.0"}]


def test_passes_requires_every_live_run_above_the_bar():
    assert ex.passes([100.0, 82.5, 50.0])
    assert not ex.passes([100.0, 49.9, 100.0])
    assert not ex.passes([100.0, None, 100.0])
    assert not ex.passes([100.0, 100.0])  # stopped early: not checked enough times


def test_tracked_examples_are_licensed_winning_case_phrases():
    data = json.loads(ex.EXAMPLES.read_text(encoding="utf-8"))
    examples = data["examples"]
    assert len(examples) >= 6
    for e in examples:
        # The use case David wins: the Firefox Focus translation memory, Spanish -> K'iche'.
        assert e["direction"] == "es-quc" and e["product"] == "focus-for-android"
        assert e["license"].startswith("MPL-2.0") and e["url"].startswith("https://")
        assert e["reference"] and e["text"]
        assert ex.passes(e["chrf"], len(e["chrf"]), data["min_chrf"])
    assert len({e["pair_id"] for e in examples}) == len(examples)
