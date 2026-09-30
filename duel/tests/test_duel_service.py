"""Duel service tests: rounds, blind verdicts, scoreboard, offline Goliath, event latency."""

import asyncio
import json
import time

import httpx
import pytest

from duel_core import Connectivity, GeminiClient, OfflineError, Price
from tzij_duel.main import create_app
from tzij_duel.rounds import VERDICTS
from tzij_duel.variants import Variant, translate


async def _client(service):
    app = create_app(service.settings, service)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _finish(service):
    await asyncio.gather(*list(service.tasks))


async def test_evaluation_round_is_scored_with_chrf(service):
    async with await _client(service) as client:
        res = await client.post("/api/rounds", json={"kind": "evaluacion", "direction": "es-quc"})
        assert res.status_code == 200
        await _finish(service)
        state = (await client.get("/api/state")).json()
    round_ = state["round"]
    assert round_["status"] == "done" and round_["reference"]
    for name in ("david", "goliath"):
        assert round_["results"][name]["status"] == "ok"
        assert round_["results"][name]["chrf"] is not None
    # David answers from its retrieval context (licensed data), Goliath has none.
    assert round_["results"]["david"]["chrf"] > round_["results"]["goliath"]["chrf"]
    assert state["scoreboard"]["david"]["evaluation_rounds"] == 1
    assert round_["results"]["david"]["cost_usd"] == 0.0
    assert round_["results"]["goliath"]["cost_usd"] > 0.0


async def test_mock_david_only_returns_kiche_from_licensed_data(service, retriever):
    result = await translate(service.david, "El perro duerme", "es-quc", retriever=retriever, online=True)
    assert result.text == "Le tz'i' kawar pa le ja."  # the fixture's licensed example, never invented


async def test_live_round_blind_verdicts(service):
    async with await _client(service) as client:
        await client.post("/api/rounds", json={"kind": "en_vivo", "direction": "es-quc", "text": "Mi perro es nuevo"})
        await _finish(service)
        blind = (await client.get("/api/validator")).json()["round"]
        text = json.dumps(blind)
        for secret in ("david", "goliath", "gemma-test", "gemini-test", "latency", "cost", "reference"):
            assert secret not in text.lower()
        assert [t["slot"] for t in blind["translations"]] == [0, 1]
        round_id = blind["id"]
        order = service.store.current.blind_order
        r = await client.post(f"/api/rounds/{round_id}/verdicts", json={"slot": 0, "verdict": "correcta", "voter": "phone-1"})
        assert r.status_code == 200
        # Same voter changes their mind: one verdict per voter and translation.
        await client.post(f"/api/rounds/{round_id}/verdicts", json={"slot": 0, "verdict": "aceptable", "voter": "phone-1"})
        await client.post(f"/api/rounds/{round_id}/verdicts", json={"slot": 1, "verdict": "incorrecta", "voter": "phone-1"})
        state = (await client.get("/api/state")).json()
    tallies = state["round"]["tallies"]
    assert tallies[order[0]] == {"correcta": 0, "aceptable": 1, "incorrecta": 0}
    assert tallies[order[1]] == {"correcta": 0, "aceptable": 0, "incorrecta": 1}
    assert state["scoreboard"][order[0]]["verdicts"]["aceptable"] == 1


async def test_blind_order_varies_between_rounds(service):
    orders = set()
    for i in range(12):
        round_ = service.store.create(kind="en_vivo", direction="es-quc", source_text=f"hola {i}")
        orders.add(tuple(round_.blind_order))
    assert len(orders) == 2


async def test_invalid_requests(service):
    async with await _client(service) as client:
        assert (await client.post("/api/rounds", json={"kind": "en_vivo", "text": "  "})).status_code == 422
        assert (await client.post("/api/rounds", json={"kind": "otro"})).status_code == 422
        await client.post("/api/rounds", json={"kind": "en_vivo", "text": "hola"})
        # A second round while one is translating is refused.
        assert (await client.post("/api/rounds", json={"kind": "en_vivo", "text": "hola"})).status_code in (200, 409)
        await _finish(service)
        rid = service.store.current.id
        bad = await client.post(f"/api/rounds/{rid}/verdicts", json={"slot": 0, "verdict": "genial", "voter": "phone-1"})
        assert bad.status_code == 422
        missing = await client.post("/api/rounds/nope/verdicts", json={"slot": 0, "verdict": "correcta", "voter": "phone-1"})
        assert missing.status_code == 404


async def test_deck_runs_out(service):
    async with await _client(service) as client:
        for _ in range(2):
            assert (await client.post("/api/rounds", json={"kind": "evaluacion", "direction": "quc-es"})).status_code == 200
            await _finish(service)
        assert (await client.post("/api/rounds", json={"kind": "evaluacion", "direction": "quc-es"})).status_code == 404


async def test_wifi_off_goliath_offline_david_still_translates(service):
    async with await _client(service) as client:
        r = await client.post("/api/connectivity", json={"force_offline": True})
        assert r.json()["online"] is False
        await client.post("/api/rounds", json={"kind": "evaluacion", "direction": "es-quc"})
        await _finish(service)
        state = (await client.get("/api/state")).json()
    assert state["online"] is False
    assert state["round"]["results"]["goliath"]["status"] == "offline"
    assert state["round"]["results"]["david"]["status"] == "ok"
    assert state["scoreboard"]["goliath"]["chrf_mean"] is None


class _NoNetworkModels:
    async def generate_content(self, **kwargs):
        raise httpx.ConnectError("[Errno 8] nodename nor servname provided")


async def test_real_gemini_client_network_failure_is_offline(retriever):
    """Wi-Fi off with the real client: the SDK's connection error becomes OfflineError."""
    client = GeminiClient.__new__(GeminiClient)
    client.temperature, client.max_output_tokens, client.thinking_level, client.timeout_s = 0.2, None, None, 2.0
    client._client = type("C", (), {"aio": type("A", (), {"models": _NoNetworkModels()})()})()
    with pytest.raises(OfflineError):
        await client.complete([{"role": "user", "content": "hola"}], model="gemini-test")
    goliath = Variant("goliath", "Goliath", client, "gemini-test", Price(0.75, 3.75), False, True)
    # Even if the connectivity probe said "online", the round reports offline, not a crash.
    result = await translate(goliath, "Hola", "es-quc", retriever=None, online=True)
    assert result.status == "offline"


async def test_connectivity_probe_detects_no_route():
    probe = Connectivity(host="127.0.0.1", port=1, timeout_s=0.3)
    started = time.perf_counter()
    assert await probe.is_online() is False
    assert time.perf_counter() - started < 1.0  # never freezes the stage


async def test_verdict_reaches_presenter_stream_under_a_second(service):
    round_ = service.store.create(kind="en_vivo", direction="es-quc", source_text="hola")
    service.store.set_results(round_.id, {"david": {"status": "ok", "text": "x"}, "goliath": {"status": "ok", "text": "y"}})
    stream = service.events.stream()
    received = asyncio.Queue()

    async def listen():
        async for message in stream:
            if message.startswith("event: state") and '"correcta": 1' in message:
                await received.put(time.perf_counter())
                return

    listener = asyncio.create_task(listen())
    await asyncio.sleep(0.05)
    from tzij_duel.main import Verdict

    sent = time.perf_counter()
    service.vote(round_.id, Verdict(slot=0, verdict="correcta", voter="phone-1"))
    arrived = await asyncio.wait_for(received.get(), 1.0)
    listener.cancel()
    assert arrived - sent < 1.0


async def test_reset_clears_rounds_and_state_file(service):
    service.store.create(kind="en_vivo", direction="es-quc", source_text="hola")
    assert service.settings.state_path.exists()
    started = time.perf_counter()
    service.reset()
    assert service.store.rounds == [] and not service.settings.state_path.exists()
    assert time.perf_counter() - started < 10


async def test_model_card_and_validator_url(service):
    state = service.state()
    card = state["model_card"]
    assert card["sources"] == 1 and card["pairs"] == 7 and card["data_date"] == "septiembre 2026"
    assert state["validator_url"] == "http://192.0.2.10:8787/validar/"


def test_verdict_options():
    assert VERDICTS == ("correcta", "aceptable", "incorrecta")
