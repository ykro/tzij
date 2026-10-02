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

from . import constraints as dict_guide
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
    retrieval: str = "vector"  # "vector" (EmbeddingGemma only) or "hybrid" (BM25 + vectors + fuzzy glossary)
    k: int = 6  # examples and glossary entries in the context
    mbr: int = 0  # >0: sample this many candidates and keep the consensus one (MBR with chrF++)
    sampler: ModelClient | None = None  # client with sampling temperature, for MBR
    # Dictionary-guided decoding (constraints.py): "" off, "prompt+select" or "select".
    constrained: str = ""
    max_constraints: int = 3


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
    k: int | None = None,
) -> ContenderResult:
    k = k or variant.k
    source_lang = DIRECTIONS[direction][0]
    text = normalize_kiche(text) if source_lang == "quc" else normalize_spanish(text)
    context, retrieval_ms, required = "", 0.0, []
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
        if variant.constrained:
            required = dict_guide.constraints_from(found, variant.max_constraints)
            if "prompt" in variant.constrained and required:
                context = f"{context}\n{dict_guide.prompt_block(required)}"
    messages = translation_messages(text, direction, context)
    if variant.mbr and variant.sampler is not None:
        result = await _mbr(variant, messages, online, direction, required)
    else:
        contender = Contender(variant.name, variant.client, variant.model, variant.price, variant.requires_network)
        result = (await run_duel([contender], messages, online=online))[variant.name]
    if result.status == "ok":
        result.text = normalize_output(result.text, direction)
        result.latency_ms = round((result.latency_ms or 0) + retrieval_ms, 1)
        if reference is not None:
            result.chrf = round(chrf_pp(result.text, reference), 2)
    return result


async def _mbr(variant: Variant, messages, online: bool, direction: str,
               required: list | None = None) -> ContenderResult:
    """Minimum Bayes risk decoding: N samples, keep the one that agrees most with the others.

    Each candidate is scored by its average chrF++ against the other candidates; the winner is
    the "consensus" translation. It costs N generations (run in parallel; Ollama queues what it
    can't batch), so latency is reported for the whole thing.
    """
    t0 = time.perf_counter()
    contenders = [Contender(f"{variant.name}#{i}", variant.sampler, variant.model, variant.price, variant.requires_network)
                  for i in range(variant.mbr)]
    runs = await asyncio.gather(*(run_duel([c], messages, online=online) for c in contenders))
    samples = [r[c.name] for r, c in zip(runs, contenders)]
    ok = [s for s in samples if s.status == "ok" and s.text]
    if not ok:
        failed = samples[0]
        failed.name = variant.name
        return failed
    texts = [normalize_output(s.text, direction) for s in ok]
    def support(i: int) -> float:
        others = [chrf_pp(texts[i], texts[j]) for j in range(len(texts)) if j != i]
        return sum(others) / len(others) if others else 0.0
    pool = list(range(len(texts)))
    if required:  # dictionary-guided: only the candidates that use the most required words compete
        covered = [dict_guide.coverage(t, required, direction) for t in texts]
        if max(covered) > 0:
            pool = [i for i in pool if covered[i] == max(covered)]
    best = max(pool, key=support)
    chosen = ok[best]
    chosen.name = variant.name
    chosen.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    chosen.input_tokens = sum(s.input_tokens for s in ok)
    chosen.output_tokens = sum(s.output_tokens for s in ok)
    return chosen


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


def ollama_client(s: Settings, temperature: float = 0.2) -> OllamaClient:
    client = OllamaClient(s.ollama_url, temperature=temperature)
    client.options["num_ctx"] = s.ollama_num_ctx
    return client


def _env_flag(name: str) -> bool:
    import os

    return os.environ.get(name, "0").strip().lower() in {"1", "true", "yes", "on"}


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
    stage_mbr = s.mbr_samples if _env_flag("MBR_ON_STAGE") and not s.mock_ai else 0
    david = Variant("david", "David", david_client, s.david_model or "mock-gemma", Price.free(), True, False,
                    retrieval=s.rag_mode, k=s.rag_k, mbr=stage_mbr,
                    sampler=ollama_client(s, temperature=0.7) if stage_mbr else None,
                    constrained=s.constrained_mode if _env_flag("CONSTRAINED_ON_STAGE") else "",
                    max_constraints=s.max_constraints)
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
    sampler = ollama if s.mock_ai else ollama_client(s, temperature=0.7)
    for tag in s.base_model_tags + s.finetuned_model_tags:
        variants.append(Variant(tag, f"{tag}", ollama, tag, Price.free(), False, False))
        # Baseline retrieval (vector, k=6, best first) keeps its name so old runs stay comparable.
        variants.append(Variant(f"{tag}+rag", f"{tag} + recuperación", ollama, tag, Price.free(), True, False))
        hybrid = Variant(f"{tag}+hybrid", f"{tag} + recuperación híbrida", ollama, tag, Price.free(), True, False,
                         retrieval="hybrid", k=s.rag_k)
        variants.append(hybrid)
        if s.mbr_samples:
            variants.append(Variant(f"{tag}+hybrid+mbr{s.mbr_samples}", f"{tag} + híbrida + MBR", ollama, tag,
                                    Price.free(), True, False, retrieval="hybrid", k=s.rag_k,
                                    mbr=s.mbr_samples, sampler=sampler))
            if s.constrained_mode:
                suffix = "dict" if s.constrained_mode == "prompt+select" else "dictsel"
                variants.append(Variant(f"{tag}+hybrid+mbr{s.mbr_samples}+{suffix}", f"{tag} + híbrida + MBR + diccionario",
                                        ollama, tag, Price.free(), True, False, retrieval="hybrid", k=s.rag_k,
                                        mbr=s.mbr_samples, sampler=sampler, constrained=s.constrained_mode,
                                        max_constraints=s.max_constraints))
    if s.gemini_model:
        variants.append(Variant(s.gemini_model, s.gemini_model, gemini, s.gemini_model, gemini_price(s), False, True))
        variants.append(Variant(f"{s.gemini_model}+rag", f"{s.gemini_model} + recuperación", gemini,
                                s.gemini_model, gemini_price(s), True, True))
    return variants
