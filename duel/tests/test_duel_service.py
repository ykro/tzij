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
        # One verdict per translation: a second one (same or another phone) is refused.
        again = await client.post(f"/api/rounds/{round_id}/verdicts", json={"slot": 0, "verdict": "aceptable", "voter": "phone-2"})
        assert again.status_code == 409
        await client.post(f"/api/rounds/{round_id}/verdicts", json={"slot": 1, "verdict": "incorrecta", "voter": "phone-1"})
        state = (await client.get("/api/state")).json()
    tallies = state["round"]["tallies"]
    assert tallies[order[0]] == {"correcta": 1, "aceptable": 0, "incorrecta": 0}
    assert tallies[order[1]] == {"correcta": 0, "aceptable": 0, "incorrecta": 1}
    assert state["scoreboard"][order[0]]["verdicts"]["correcta"] == 1


async def test_votes_only_on_the_current_live_round(service):
    async with await _client(service) as client:
        await client.post("/api/rounds", json={"kind": "en_vivo", "direction": "es-quc", "text": "Hola"})
        await _finish(service)
        old = service.store.current.id
        await client.post("/api/rounds", json={"kind": "evaluacion", "direction": "es-quc"})
        await _finish(service)
        current = service.store.current.id
        stale = await client.post(f"/api/rounds/{old}/verdicts", json={"slot": 0, "verdict": "correcta", "voter": "phone-1"})
        assert stale.status_code == 409
        evaluation = await client.post(f"/api/rounds/{current}/verdicts", json={"slot": 0, "verdict": "correcta", "voter": "phone-1"})
        assert evaluation.status_code == 409


async def _lan_client(service):
    app = create_app(service.settings, service)
    transport = httpx.ASGITransport(app=app, client=("192.168.1.50", 50123))
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_control_endpoints_are_laptop_only(service):
    async with await _lan_client(service) as phone:
        for method, path, body in (
            ("post", "/api/rounds", {"kind": "en_vivo", "text": "hola"}),
            ("post", "/api/reset", {}),
            ("post", "/api/connectivity", {"force_offline": True}),
            ("get", "/api/state", None),
            ("get", "/api/suggestions", None),
            ("get", "/api/events?view=presenter", None),
        ):
            res = await getattr(phone, method)(path, **({"json": body} if body is not None else {}))
            assert res.status_code == 403, path
        assert (await phone.get("/api/validator")).status_code == 200
        assert (await phone.get("/api/health")).status_code == 200


async def test_phone_can_vote_from_the_lan(service):
    async with await _client(service) as laptop:
        await laptop.post("/api/rounds", json={"kind": "en_vivo", "direction": "es-quc", "text": "Hola"})
        await _finish(service)
    async with await _lan_client(service) as phone:
        rid = service.store.current.id
        res = await phone.post(f"/api/rounds/{rid}/verdicts", json={"slot": 1, "verdict": "aceptable", "voter": "phone-1"})
        assert res.status_code == 200


async def test_validator_stream_is_blind(service):
    """Everything the phones receive, over a whole round, carries no names, costs or reference."""
    received: list[str] = []
    stream = service.events.stream("validator")

    async def listen():
        async for message in stream:
            received.append(message)

    listener = asyncio.create_task(listen())
    await asyncio.sleep(0.02)
    from tzij_duel.main import NewRound

    service.start_round(NewRound(kind="evaluacion", direction="es-quc"))
    await _finish(service)
    await asyncio.sleep(0.05)
    listener.cancel()
    blob = "\n".join(received).lower()
    assert received and "event: validator" in blob and "event: state" not in blob
    reference = service.store.current.reference.lower()
    for secret in ("david", "goliath", "gemma-test", "gemini-test", "latency", "cost_usd", "chrf", reference):
        assert secret not in blob


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
    stream = service.events.stream("presenter")
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


def test_model_card_lists_the_training_only_gemini_data_of_the_stage_david(settings):
    from dataclasses import replace

    from tzij_duel.model_card import model_card

    base = model_card(replace(settings, david_model="gemma4:e4b"))
    assert base["finetune_sources"] == [] and base["train_sources"] == []
    stage = model_card(replace(settings, david_model="tzij-2026-10-mix-s7"))
    assert any("Retrotraducción" in s for s in stage["train_sources"])
    assert any("Destilación" in s and "2,409" in s for s in stage["train_sources"])


def test_verdict_options():
    assert VERDICTS == ("correcta", "aceptable", "incorrecta")


async def test_mock_mode_needs_no_ollama_and_shows_only_licensed_kiche(tmp_path, monkeypatch):
    """MOCK_AI=1 builds its own tiny index (hashing embeddings) and deck from duel/mock_data."""
    import json as _json

    import httpx as _httpx

    from tzij_duel.main import MOCK_DATA, Service
    from tzij_duel.settings import Settings

    def no_ollama(*args, **kwargs):
        raise AssertionError("mock mode must not call Ollama")

    monkeypatch.setattr(_httpx.Client, "post", no_ollama)
    settings = Settings(mock_ai=True, state_path=tmp_path / "state" / "rounds.json", processed_dir=tmp_path / "none",
                        rag_index=tmp_path / "missing.sqlite", web_dir=tmp_path / "no-web")
    service = Service(settings)
    licensed = {r["target_text"] for r in map(_json.loads, (MOCK_DATA / "index_pairs.jsonl").read_text().splitlines())}
    service.start_round(type("B", (), {"kind": "evaluacion", "direction": "es-quc", "text": None})())
    await asyncio.gather(*list(service.tasks))
    result = service.store.current.results["david"]
    assert result["status"] == "ok" and result["text"] in licensed | {"…"}
    assert service.store.current.reference_meta["source_name"] == "bloom_kiche"


def test_no_winner_without_a_rival(service):
    round_ = service.store.create(kind="evaluacion", direction="es-quc", source_text="x", reference="y")
    service.store.set_results(round_.id, {"david": {"status": "ok", "chrf": 12.0},
                                          "goliath": {"status": "offline", "chrf": None}})
    assert service.store.scoreboard()["evaluation_wins"] == {"david": 0, "goliath": 0, "empate": 0}


async def test_reset_during_an_in_flight_round(service):
    from tzij_duel.main import NewRound

    service.start_round(NewRound(kind="evaluacion", direction="es-quc"))
    service.reset()  # the round task is still translating
    await _finish(service)
    assert service.store.rounds == []


def test_index_dataset_mismatch_is_reported(service, settings):
    from tzij_duel.main import index_mismatch

    assert service.retriever.dataset_version == "fixture"
    warning = index_mismatch(service.retriever, settings.processed_dir)
    assert warning and "make index" in warning


async def test_specialty_round_draws_only_from_the_niche(service, tmp_path):
    import json

    from tzij_duel.deck import Deck

    niche = tmp_path / "test_niche.jsonl"
    niche.write_text(json.dumps({"id": "n1-es-quc", "pair_id": "n1", "direction": "es-quc",
                                 "source_text": "Agregar otro motor de búsqueda", "target_text": "Chaya' jun chik ch'ich'",
                                 "source_name": "pontoon_mozilla", "domain": "software", "kind": "sentence",
                                 "status": "auto_validated", "url": "u", "license": "MPL-2.0"}) + "\n")
    service.deck = Deck(service.settings.processed_dir, niche_file=niche)
    async with await _client(service) as client:
        state = (await client.get("/api/state")).json()
        assert state["niche_deck_size"] == 1
        # Specialty rounds are always Spanish -> K'iche' (what the niche measures).
        res = await client.post("/api/rounds", json={"kind": "evaluacion", "direction": "quc-es", "specialty": True})
        assert res.status_code == 200
        await _finish(service)
        round_ = (await client.get("/api/state")).json()["round"]
        assert round_["reference_meta"]["pair_id"] == "n1" and round_["reference_meta"]["specialty"] is True
        assert round_["direction"] == "es-quc"
        again = await client.post("/api/rounds", json={"kind": "evaluacion", "direction": "es-quc", "specialty": True})
        assert again.status_code == 404 and "especialidad" in again.json()["detail"]
        # Normal evaluation rounds never draw from the niche.
        normal = await client.post("/api/rounds", json={"kind": "evaluacion", "direction": "es-quc"})
        assert normal.status_code == 200
        await _finish(service)
        assert (await client.get("/api/state")).json()["round"]["reference_meta"]["pair_id"] != "n1"


async def test_presenter_state_counts_connected_validators(service):
    # The validator is optional: the presenter only says it's waiting for a verdict when a phone is
    # connected, so the state carries the count and is republished when a phone joins or leaves.
    seen = []
    service.events.on_change = lambda ch: seen.append((ch, service.state()["validators"]))
    assert service.state()["validators"] == 0
    stream = service.events.stream("validator", first="hello")
    assert await stream.__anext__() == "hello"
    assert service.state()["validators"] == 1
    await stream.aclose()
    assert service.state()["validators"] == 0
    assert seen == [("validator", 1), ("validator", 0)]
