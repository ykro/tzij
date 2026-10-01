"""Fixtures for the duel service: mock models, a tiny retrieval index, a tiny dataset."""

import json
import shutil
from pathlib import Path

import pytest

from duel_core import MockClient, Price
from rag.build_index import build
from rag.retrieve import Retriever
from tests.test_rag import TrigramEmbedder
from tzij_duel.main import Service
from tzij_duel.settings import Settings
from tzij_duel.variants import Variant, _mock_david, _mock_goliath

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"

TEST_RECORDS = [
    ("t1", "El perro duerme en la casa.", "Le tz'i' kawar pa le ja."),
    ("t2", "¿Cómo estás tú hoy?", "La utz awach kamik?"),
]


@pytest.fixture
def dataset(tmp_path) -> Path:
    processed = tmp_path / "processed"
    version = processed / "v1"
    version.mkdir(parents=True)
    lines = []
    for pid, spa, quc in TEST_RECORDS:
        for direction, src, tgt in (("es-quc", spa, quc), ("quc-es", quc, spa)):
            lines.append(json.dumps({"id": f"{pid}-{direction}", "pair_id": pid, "direction": direction,
                                     "source_text": src, "target_text": tgt, "source_name": "fixture",
                                     "domain": "everyday", "kind": "sentence", "split": "test",
                                     "status": "pending_native_review", "origin": "web", "url": "u",
                                     "license": "CC0", "ref": ""}, ensure_ascii=False))
    (version / "test.jsonl").write_text("\n".join(lines) + "\n")
    manifest = {"version": "v1", "created_at": "2026-09-30T20:58:55+00:00",
                "sources": [{"name": "fixture", "title": "Fixture", "role": "test"}], "pairs_by_source": {"fixture": {"test": 2}},
                "pairs_by_split": {"train": 5, "dev": 0, "test": 2}, "finetune": {"threshold_met": False}}
    (version / "manifest.json").write_text(json.dumps(manifest))
    (processed / "LATEST").write_text("v1\n")
    return processed


@pytest.fixture
def retriever(tmp_path) -> Retriever:
    records = [json.loads(line) for line in (FIXTURES / "retrieval_train.jsonl").read_text().splitlines()]
    index = tmp_path / "index.sqlite"
    build(records, TrigramEmbedder(), index, "fixture")
    return Retriever(index, embedder=TrigramEmbedder())


@pytest.fixture
def settings(tmp_path, dataset) -> Settings:
    return Settings(mock_ai=True, force_offline=False, state_path=tmp_path / "state" / "rounds.json",
                    processed_dir=dataset, web_dir=tmp_path / "no-web", rag_index=tmp_path / "index.sqlite",
                    gemini_model="gemini-test", david_model="gemma-test", public_url="http://192.0.2.10:8787",
                    gemini_input_usd_per_m=0.75, gemini_output_usd_per_m=3.75)


@pytest.fixture
def service(settings, retriever) -> Service:
    david = Variant("david", "David", MockClient(_mock_david, latency_ms=400), "gemma-test", Price.free(), True, False)
    goliath = Variant("goliath", "Goliath", MockClient(_mock_goliath, latency_ms=1500), "gemini-test",
                      Price(0.75, 3.75), False, True)
    from tzij_duel.deck import Deck

    return Service(settings, david=david, goliath=goliath, retriever=retriever, deck=Deck(settings.processed_dir))
