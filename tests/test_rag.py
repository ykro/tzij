"""Retrieval index tests with a tiny fixture and a deterministic fake embedder.

The fake embedder (character trigram hashing) lets the tests run without
Ollama; one optional test exercises the real EmbeddingGemma when available.
"""

import hashlib
import json
import math
import os
from pathlib import Path

import httpx
import pytest

from rag.build_index import build
from rag.embedder import CachedEmbedder, OllamaEmbedder
from rag.retrieve import Retriever

FIXTURE = Path(__file__).parent / "fixtures" / "retrieval_train.jsonl"


class TrigramEmbedder:
    name = "fake-trigram"
    calls = 0

    def embed(self, texts):
        TrigramEmbedder.calls += len(texts)
        out = []
        for text in texts:
            vector = [0.0] * 64
            padded = f"  {text.lower()}  "
            for i in range(len(padded) - 2):
                vector[int(hashlib.md5(padded[i:i + 3].encode()).hexdigest(), 16) % 64] += 1
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            out.append([v / norm for v in vector])
        return out


def _records():
    return [json.loads(line) for line in FIXTURE.read_text().splitlines()]


@pytest.fixture
def retriever(tmp_path):
    index = tmp_path / "index.sqlite"
    assert build(_records(), TrigramEmbedder(), index, "fixture") == 10
    return Retriever(index, embedder=TrigramEmbedder())


def test_examples_are_filtered_by_direction(retriever):
    result = retriever.retrieve("El perro duerme", "es-quc", k=2)
    assert result.examples[0].source_text == "El perro duerme en la casa."
    assert result.examples[0].target_text == "Le tz'i' kawar pa le ja."
    assert all(h.kind == "sentence" for h in result.examples)
    back = retriever.retrieve("Le tz'i' kawar", "quc-es", k=2)
    assert back.examples[0].target_text == "El perro duerme en la casa."


def test_glossary_exact_match_comes_first(retriever):
    result = retriever.retrieve("Mi perro es nuevo", "es-quc", k=3)
    exact = [h for h in result.glossary if h.via == "exact"]
    assert {(h.source_text, h.target_text) for h in exact} == {("perro", "tz'i'"), ("nuevo", "k'ak'")}
    assert result.glossary[0].via == "exact" and len(result.glossary) <= 3


def test_query_is_normalized_before_lookup(retriever):
    result = retriever.retrieve("kʼakʼ", "quc-es", k=2)  # typed with U+02BC
    assert result.query == "k'ak'"
    assert result.glossary[0].target_text == "nuevo" and result.glossary[0].via == "exact"


def test_prompt_context(retriever):
    text = retriever.retrieve("¿Cómo estás?", "es-quc", k=1).as_prompt_context()
    assert "Ejemplos:" in text and "La utz awach?" in text


def test_refuses_test_split_records(tmp_path):
    records = _records()
    records[0]["split"] = "test"
    with pytest.raises(ValueError):
        build(records, TrigramEmbedder(), tmp_path / "x.sqlite", "fixture")


def test_embedding_model_mismatch_is_an_error(tmp_path):
    index = tmp_path / "index.sqlite"
    build(_records(), TrigramEmbedder(), index, "fixture")

    class Other(TrigramEmbedder):
        name = "other-model"

    with pytest.raises(RuntimeError, match="make index"):
        Retriever(index, embedder=Other())


def test_bad_direction(retriever):
    with pytest.raises(ValueError):
        retriever.retrieve("hola", "en-quc")


def test_embedding_cache_avoids_recomputation(tmp_path):
    cached = CachedEmbedder(TrigramEmbedder(), tmp_path / "cache.sqlite")
    TrigramEmbedder.calls = 0
    first = cached.embed(["utz", "ja"])
    second = cached.embed(["ja", "utz", "k'ak'"])
    assert TrigramEmbedder.calls == 3
    assert second[0] == pytest.approx(first[1]) and second[1] == pytest.approx(first[0])


def _ollama_has(model):
    try:
        tags = httpx.get("http://localhost:11434/api/tags", timeout=2).json()
        return any(m["name"].split(":")[0] == model.split(":")[0] for m in tags.get("models", []))
    except (httpx.HTTPError, ValueError):
        return False


@pytest.mark.ollama
@pytest.mark.skipif(not os.environ.get("EMBEDDING_MODEL") or not _ollama_has(os.environ.get("EMBEDDING_MODEL", "")),
                    reason="needs Ollama with EMBEDDING_MODEL pulled")
def test_real_embeddinggemma_retrieval(tmp_path):
    index = tmp_path / "index.sqlite"
    build(_records(), OllamaEmbedder(), index, "fixture")
    result = Retriever(index).retrieve("Mi perro está dormido en casa", "es-quc", k=1)
    assert result.examples[0].target_text == "Le tz'i' kawar pa le ja."


def test_exclude_keeps_the_answer_out_of_the_context(retriever):
    plain = retriever.retrieve("El perro duerme en la casa.", "es-quc", k=3)
    assert any(h.target_text == "Le tz'i' kawar pa le ja." for h in plain.examples)
    raft = retriever.retrieve("El perro duerme en la casa.", "es-quc", k=3,
                              exclude={"El perro duerme en la casa.", "Le tz'i' kawar pa le ja."})
    assert "Le tz'i' kawar pa le ja." not in raft.as_prompt_context()
    assert raft.examples  # the rest of the context is still there


def test_hybrid_and_fuzzy(tmp_path):
    index = tmp_path / "index.sqlite"
    build(_records(), TrigramEmbedder(), index, "fixture")
    hybrid = Retriever(index, embedder=TrigramEmbedder(), mode="hybrid", fuzzy=True)
    result = hybrid.retrieve("El perro duerme", "es-quc", k=2)
    assert result.examples[0].target_text == "Le tz'i' kawar pa le ja."
    assert result.examples[0].via == "hybrid"
    # "perros" is one edit away from the headword "perro": fuzzy glossary finds it.
    fuzzy = hybrid.retrieve("Los perros", "es-quc", k=3)
    assert any(h.via == "fuzzy" and h.target_text == "tz'i'" for h in fuzzy.glossary)
    plain = Retriever(index, embedder=TrigramEmbedder())
    assert not any(h.via == "fuzzy" for h in plain.retrieve("Los perros", "es-quc", k=3).glossary)


def test_best_last_order(tmp_path):
    index = tmp_path / "index.sqlite"
    build(_records(), TrigramEmbedder(), index, "fixture")
    first = Retriever(index, embedder=TrigramEmbedder()).retrieve("El perro duerme", "es-quc", k=2).examples
    last = Retriever(index, embedder=TrigramEmbedder(), order="best_last").retrieve("El perro duerme", "es-quc", k=2).examples
    assert [h.source_text for h in last] == [h.source_text for h in reversed(first)]


def test_trigram_finds_roots_inside_words(tmp_path):
    index = tmp_path / "index.sqlite"
    build(_records(), TrigramEmbedder(), index, "fixture")
    tri = Retriever(index, embedder=TrigramEmbedder(), mode="hybrid", trigram=True)
    assert tri._tri_ids("kawar", "quc-es", "sentence", 5)  # substring of a longer K'iche' sentence
    result = tri.retrieve("Le tz'i' kawar", "quc-es", k=2)
    assert result.examples and result.examples[0].via == "hybrid"


def test_coverage_selection_prefers_new_words():
    from rag.retrieve import Hit, coverage_select

    hits = [Hit("el perro come", "a", "sentence", "s", "d", 0.9, "hybrid"),
            Hit("el perro duerme", "b", "sentence", "s", "d", 0.8, "hybrid"),
            Hit("la casa grande", "c", "sentence", "s", "d", 0.1, "hybrid")]
    chosen = coverage_select("el perro duerme en la casa", hits, 2)
    assert [h.target_text for h in chosen] == ["b", "c"]  # "casa" beats a second "perro"
