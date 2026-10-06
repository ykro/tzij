"""Fixtures for the page and David's service: mock models, a tiny retrieval index."""

import json
from pathlib import Path

import pytest

from duel_core import MockClient, Price
from rag.build_index import build
from rag.retrieve import Retriever
from tests.test_rag import TrigramEmbedder
from tzij_duel.david_app import David
from tzij_duel.page import InProcessDavid, Page
from tzij_duel.settings import Settings
from tzij_duel.variants import Variant, _mock_david, _mock_goliath

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"


@pytest.fixture
def retriever(tmp_path) -> Retriever:
    records = [json.loads(line) for line in (FIXTURES / "retrieval_train.jsonl").read_text().splitlines()]
    index = tmp_path / "index.sqlite"
    build(records, TrigramEmbedder(), index, "fixture")
    return Retriever(index, embedder=TrigramEmbedder())


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(mock_ai=True, web_dir=tmp_path / "no-web", rag_index=tmp_path / "index.sqlite",
                    gemini_model="gemini-test", david_model="gemma-test", david_url="",
                    gemini_input_usd_per_m=0.75, gemini_output_usd_per_m=3.75)


@pytest.fixture
def david(settings, retriever) -> David:
    variant = Variant("david", "David", MockClient(_mock_david, latency_ms=400), "gemma-test", Price.free(), True, False)
    return David(settings, variant=variant, retriever=retriever)


@pytest.fixture
def page(settings, david) -> Page:
    local = InProcessDavid.__new__(InProcessDavid)
    local.david = david
    goliath = Variant("goliath", "Goliath", MockClient(_mock_goliath, latency_ms=1500), "gemini-test",
                      Price(0.75, 3.75), False, True)
    return Page(settings, david=local, goliath=goliath)
