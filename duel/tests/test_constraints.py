"""Dictionary-guided decoding (constraints from exact glossary hits), llama-server bias, multi-prompt MBR."""

import asyncio

from duel_core import MockClient, Price
from rag.retrieve import Hit, RetrievalResult
from tzij_duel import constraints as C
from tzij_duel.variants import Variant, _mbr


def _found(direction="es-quc"):
    r = RetrievalResult(query="El pollo come maíz.", direction=direction)
    r.glossary = [
        Hit("maíz", "ixim", "lexicon", "gatitos", "dictionary", 1.0, "exact"),
        Hit("pollo", "ak'", "lexicon", "gatitos", "dictionary", 1.0, "exact"),
        Hit("el", "ri", "lexicon", "gatitos", "dictionary", 1.0, "exact"),  # stop word: ignored
        Hit("milpa", "ab'ix", "lexicon", "gatitos", "dictionary", 0.9, "fuzzy"),  # not exact: ignored
    ]
    return r


def test_constraints_only_exact_content_words_in_the_input():
    assert C.constraints_from(_found()) == [("maíz", ["ixim"]), ("pollo", ["ak'"])]
    assert C.constraints_from(_found(), max_constraints=1) == [("maíz", ["ixim"])]


def test_llama_server_client_biases_the_first_token_of_each_form():
    import json

    import httpx

    from duel_core import LlamaServerClient

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path == "/tokenize":
            return httpx.Response(200, json={"tokens": {"ixim": [11, 12], " ixim": [21, 22]}[body["content"]]})
        seen.update(body)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Kutij ixim."}}],
                                         "usage": {"prompt_tokens": 12, "completion_tokens": 4}})

    client = LlamaServerClient("http://llama.test", min_p=0.02, transport=httpx.MockTransport(handler))
    out = asyncio.run(client.with_bias([("ixim", 2.0)]).complete([{"role": "user", "content": "x"}], model="m"))
    assert out.text == "Kutij ixim." and out.output_tokens == 4
    assert sorted(seen["logit_bias"]) == [[11, 2.0], [21, 2.0]] and seen["min_p"] == 0.02
    assert seen["chat_template_kwargs"] == {"enable_thinking": False}
    assert client.logit_bias == []  # the base client stays unbiased


def test_multi_prompt_contexts_keep_the_material_and_vary_the_order():
    r = RetrievalResult(query="q", direction="es-quc")
    r.examples = [Hit(f"es{i}", f"quc{i}", "sentence", "s", "d", 1.0, "hybrid") for i in range(4)]
    r.glossary = _found().glossary
    contexts = r.variants(4)
    assert contexts[0] == r.as_prompt_context() and len(set(contexts)) == 4
    assert contexts[2].count("=>") == 3  # even variants drop one example


def test_mbr_sends_each_sample_its_own_prompt():
    prompts = []

    def answer(messages):
        prompts.append(messages[-1]["content"])
        return "Kutij ixim."

    sampler = MockClient(answer, latency_ms=1)
    v = Variant("d", "d", sampler, "m", Price.free(), True, False, mbr=3, sampler=sampler, multi_prompt=True)
    per_sample = [[{"role": "user", "content": f"p{i}"}] for i in range(3)]
    asyncio.run(_mbr(v, per_sample[0], True, "es-quc", None, per_sample))
    assert sorted(prompts) == ["p0", "p1", "p2"]
