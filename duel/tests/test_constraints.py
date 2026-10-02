"""Dictionary-guided decoding: constraints from exact glossary hits, coverage, MBR selection."""

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


def test_coverage_allows_kiche_prefixes_and_spanish_inflection():
    cons = C.constraints_from(_found())
    assert C.coverage("Kutij ixim ri ak'.", cons, "es-quc") == 2
    assert C.coverage("Kutij wa ri ak'.", cons, "es-quc") == 1
    assert C.coverage("Comemos maíz.", [("kitij", ["comer"]), ("ixim", ["maíz"])], "quc-es") == 2


def test_mbr_prefers_candidates_that_use_the_dictionary():
    answers = iter(["Kutij wa ri tz'i'.", "Kutij wa ri tz'i'.", "Kutij ixim ri ak'.", "Kutij wa ri tz'i'."])
    sampler = MockClient(lambda messages: next(answers), latency_ms=1)
    v = Variant("d", "d", sampler, "m", Price.free(), True, False, mbr=4, sampler=sampler, constrained="select")
    messages = [{"role": "user", "content": "x"}]
    plain = asyncio.run(_mbr(v, messages, True, "es-quc"))
    assert plain.text == "Kutij wa ri tz'i'."  # consensus alone picks the majority
    answers = iter(["Kutij wa ri tz'i'.", "Kutij wa ri tz'i'.", "Kutij ixim ri ak'.", "Kutij wa ri tz'i'."])
    guided = asyncio.run(_mbr(v, messages, True, "es-quc", C.constraints_from(_found())))
    assert guided.text == "Kutij ixim ri ak'."


def test_prompt_block_lists_required_forms():
    block = C.prompt_block([("maíz", ["ixim"]), ("agua", ["ja'", "joron"])])
    assert "maíz = ixim" in block and "agua = ja' / joron" in block
    assert C.prompt_block([]) == ""
