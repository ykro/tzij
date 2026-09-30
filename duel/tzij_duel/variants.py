"""The contenders, as variants: a model + whether it reads the retrieval index.

On stage:  David   = LOCAL_MODEL_TAG (Gemma on Ollama) + retrieval
           Goliath = GEMINI_MODEL alone (the frontier model as people use it)
In `make eval` every available combination runs, including Gemini + the same
retrieval: if the context helps Gemini too, the report says so.

Retrieval is a step of David, not of the model: its time counts in David's
latency because the audience waits for it too.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

from data.normalize import normalize_kiche, normalize_spanish
from duel_core import (
    Contender,
    ContenderResult,
    GeminiClient,
    MockClient,
    ModelClient,
    OllamaClient,
    Price,
    chrf_pp,
    run_duel,
)
from rag.retrieve import Retriever

from .prompts import DIRECTIONS, translation_messages
from .settings import Settings


@dataclass
class Variant:
    name: str  # stable id used in reports and the scoreboard
    label: str  # what the audience reads
    client: ModelClient
    model: str
    price: Price
    uses_rag: bool
    requires_network: bool


def normalize_output(text: str, direction: str) -> str:
    """Model output goes through the same normalization as the references."""
    target = DIRECTIONS[direction][1]
    return normalize_kiche(text) if target == "quc" else normalize_spanish(text)


async def translate(
    variant: Variant,
    text: str,
    direction: str,
    *,
    retriever: Retriever | None,
    online: bool,
    reference: str | None = None,
    k: int = 6,
) -> ContenderResult:
    source_lang = DIRECTIONS[direction][0]
    text = normalize_kiche(text) if source_lang == "quc" else normalize_spanish(text)
    context, retrieval_ms = "", 0.0
    if variant.uses_rag:
        if retriever is None:
            return ContenderResult(variant.name, variant.model, "error", error="índice de recuperación no disponible")
        t0 = time.perf_counter()
        try:
            found = await asyncio.to_thread(retriever.retrieve, text, direction, k)
        except Exception as exc:  # Ollama embeddings down: David can't use its data
            return ContenderResult(variant.name, variant.model, "error", error=f"recuperación: {exc}"[:200])
        retrieval_ms = (time.perf_counter() - t0) * 1000
        context = found.as_prompt_context()
    messages = translation_messages(text, direction, context)
    contender = Contender(variant.name, variant.client, variant.model, variant.price, variant.requires_network)
    result = (await run_duel([contender], messages, online=online))[variant.name]
    if result.status == "ok":
        result.text = normalize_output(result.text, direction)
        result.latency_ms = round((result.latency_ms or 0) + retrieval_ms, 1)
        if reference is not None:
            result.chrf = round(chrf_pp(result.text, reference), 2)
    return result


# --- mock mode (MOCK_AI=1): no network, no GPU, and no invented K'iche' -------------------------
# The mock answers are *taken from the retrieval context* (licensed data), never made up: David
# returns the target of its best example, Goliath (who has no context) the Spanish unchanged.

_EXAMPLE_RE = re.compile(r"^- .+? => (.+)$", re.M)
_GLOSSARY_RE = re.compile(r"^- .+? = (.+)$", re.M)


def _mock_david(messages) -> str:
    user = messages[-1]["content"]
    match = _EXAMPLE_RE.search(user) or _GLOSSARY_RE.search(user)
    return match.group(1) if match else "…"


def _mock_goliath(messages) -> str:
    return messages[-1]["content"].rsplit("\n", 1)[-1]


def ollama_client(s: Settings) -> OllamaClient:
    client = OllamaClient(s.ollama_url)
    client.options["num_ctx"] = s.ollama_num_ctx
    return client


def gemini_price(s: Settings) -> Price:
    return Price(s.gemini_input_usd_per_m, s.gemini_output_usd_per_m)


def stage_variants(s: Settings) -> tuple[Variant, Variant]:
    """David and Goliath as the audience sees them."""
    if s.mock_ai:
        david_client: ModelClient = MockClient(_mock_david, latency_ms=420, sleep=True)
        goliath_client: ModelClient = MockClient(_mock_goliath, latency_ms=1500, offline=s.force_offline, sleep=True)
    else:
        david_client = ollama_client(s)
        goliath_client = GeminiClient(s.project, s.location, thinking_level=s.gemini_thinking_level or None)
    david = Variant("david", "David", david_client, s.david_model or "mock-gemma", Price.free(), True, False)
    goliath = Variant("goliath", "Goliath", goliath_client, s.gemini_model or "mock-gemini", gemini_price(s), False, True)
    return david, goliath


def eval_variants(s: Settings) -> list[Variant]:
    """Every combination available now; fine-tuned tags join when FINETUNED_MODEL_TAGS is set."""
    if s.mock_ai:
        ollama: ModelClient = MockClient(_mock_david, latency_ms=400)
        gemini: ModelClient = MockClient(_mock_goliath, latency_ms=1500)
    else:
        ollama = ollama_client(s)
        gemini = GeminiClient(s.project, s.location, thinking_level=s.gemini_thinking_level or None)
    variants: list[Variant] = []
    for tag in s.base_model_tags + s.finetuned_model_tags:
        variants.append(Variant(tag, f"{tag}", ollama, tag, Price.free(), False, False))
        variants.append(Variant(f"{tag}+rag", f"{tag} + recuperación", ollama, tag, Price.free(), True, False))
    if s.gemini_model:
        variants.append(Variant(s.gemini_model, s.gemini_model, gemini, s.gemini_model, gemini_price(s), False, True))
        variants.append(Variant(f"{s.gemini_model}+rag", f"{s.gemini_model} + recuperación", gemini,
                                s.gemini_model, gemini_price(s), True, True))
    return variants
