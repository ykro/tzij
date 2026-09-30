"""Generic tests for duel_core (shipped with the package so every repo that vendors it runs them)."""

import asyncio
import json

import httpx
import pytest

from duel_core import (
    Connectivity,
    Contender,
    MockClient,
    OllamaClient,
    Price,
    PromptTemplate,
    chrf_pp,
    clean_translation,
    corpus_chrf_pp,
    cost_usd,
    percentile,
    run_duel,
    summarize,
)


def test_prompt_template_renders_system_examples_and_user():
    t = PromptTemplate(
        version="v1",
        system="Translate from {src} to {tgt}.",
        user="Text: {text}",
        examples=(({"text": "hola"}, "hello"),),
    )
    msgs = t.render(src="es", tgt="en", text="adiós")
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[0]["content"] == "Translate from es to en."
    assert msgs[1]["content"] == "Text: hola"
    assert msgs[-1]["content"] == "Text: adiós"


def test_prompt_template_missing_field_fails_loudly():
    with pytest.raises(KeyError):
        PromptTemplate("v1", "{a}", "{b}").render(a="x")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('"Estuvo regular."', "Estuvo regular."),
        ("Traducción: estuvo regular\n\n(nota: mid = regular)", "estuvo regular"),
        ("  «qué pena»  ", "qué pena"),
        ("", ""),
    ],
)
def test_clean_translation(raw, expected):
    assert clean_translation(raw) == expected


def test_cost_per_million_tokens():
    assert cost_usd(Price(1.5, 7.5), 1_000_000, 0) == pytest.approx(1.5)
    assert cost_usd(Price(1.5, 7.5), 200, 100) == pytest.approx((200 * 1.5 + 100 * 7.5) / 1e6)
    assert cost_usd(Price.free(), 10_000, 10_000) == 0


def test_chrf_pp_identity_and_partial_credit():
    assert chrf_pp("estuvo regular", "estuvo regular") == pytest.approx(100.0)
    partial = chrf_pp("estuvo regularcito", "estuvo regular")
    assert 0 < partial < 100
    assert chrf_pp("", "estuvo regular") == 0
    assert corpus_chrf_pp(["a b c"], ["a b c"]) == pytest.approx(100.0)
    assert corpus_chrf_pp([], []) == 0


def test_percentile_and_summary():
    xs = [100, 200, 300, 400, 500]
    assert percentile(xs, 50) == 300
    assert percentile(xs, 95) == pytest.approx(480)
    assert percentile([], 50) is None
    s = summarize([10, 20])
    assert s["n"] == 2 and s["p50"] == 15 and s["mean"] == 15


def _contenders(goliath_offline=False):
    return [
        Contender("david", MockClient(lambda m: "estuvo regular", latency_ms=300), "local", Price.free()),
        Contender(
            "goliath",
            MockClient(lambda m: '"estuvo más o menos"', latency_ms=900, offline=goliath_offline),
            "cloud",
            Price(1.0, 10.0),
            requires_network=True,
        ),
    ]


def test_duel_runs_both_and_scores_against_reference():
    res = asyncio.run(run_duel(_contenders(), [{"role": "user", "content": "estuvo mid"}], reference="estuvo regular"))
    assert res["david"].status == "ok" and res["david"].chrf == pytest.approx(100.0)
    assert res["david"].cost_usd == 0
    assert res["goliath"].text == "estuvo más o menos"  # quotes cleaned
    assert res["goliath"].cost_usd > 0
    assert res["goliath"].chrf < res["david"].chrf


def test_duel_offline_skips_network_contender_without_calling_it():
    cs = _contenders()
    res = asyncio.run(run_duel(cs, [{"role": "user", "content": "x"}], online=False))
    assert res["goliath"].status == "offline"
    assert cs[1].client.calls == []
    assert res["david"].status == "ok"


def test_duel_offline_error_from_client_is_reported_as_offline():
    res = asyncio.run(run_duel(_contenders(goliath_offline=True), [{"role": "user", "content": "x"}]))
    assert res["goliath"].status == "offline"


def test_duel_error_in_one_contender_does_not_break_round():
    class Boom:
        async def complete(self, messages, *, model):
            raise ValueError("kaput")

    cs = [_contenders()[0], Contender("goliath", Boom(), "cloud", Price())]
    res = asyncio.run(run_duel(cs, [{"role": "user", "content": "x"}]))
    assert res["goliath"].status == "error" and "kaput" in res["goliath"].error
    assert res["david"].status == "ok"


def test_ollama_client_parses_response_and_retries_without_think():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if "think" in body:
            return httpx.Response(400, text='{"error":"model does not support thinking"}')
        return httpx.Response(200, json={"message": {"content": "hola"}, "prompt_eval_count": 12, "eval_count": 3})

    client = OllamaClient(transport=httpx.MockTransport(handler))
    comp = asyncio.run(client.complete([{"role": "user", "content": "hi"}], model="m"))
    assert comp.text == "hola" and comp.input_tokens == 12 and comp.output_tokens == 3
    assert len(seen) == 2 and "think" not in seen[1]


def test_connectivity_forced_offline_and_unreachable_host():
    assert asyncio.run(Connectivity(force_offline=True).is_online()) is False
    # Port 9 on localhost (discard) is closed on dev machines: must answer False fast, not hang.
    assert asyncio.run(Connectivity(host="127.0.0.1", port=9, timeout_s=0.3).is_online()) is False
