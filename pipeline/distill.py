"""Distillation in the test's domains (make distill): Goliath teaches once, David serves offline.

Why: the test (Bloom children's stories and BOUQuET's everyday domains) is outside every licensed
training source, and the 2026-10-04 search found no open K'iche' text for conversation, how-to,
social posts or comments (data/SOURCES.md). Gemini 3.1 Pro and Gemini 3.8 Flash score the same in
K'iche' on dev_domain (40.5 vs 40.6 chrF++), so Flash is the teacher.

Steps, all recorded in data/train/distilled/meta.json:
1. `gen`: Gemini writes everyday Spanish sentences per (domain, topic, register). Domains follow
   BOUQuET's own list plus children's stories; topics are everyday life in Guatemala.
2. Spanish that repeats or overlaps dev/test (any shared 6-gram, BOUQuET included) is dropped.
3. `translate`: Gemini translates each sentence into K'iche' with the same retrieved context David
   gets (examples + glossary from our licensed index), so the K'iche' follows our data's spelling
   and vocabulary.
4. Filters: ALMG alphabet only; length ratio; round trip (Gemini back into Spanish, no context) must
   reach the MEDIAN chrF++ of the same round trip on real dev pairs (the median rather than a lower
   percentile, because Gemini reads its own K'iche' back easily). Computed once, kept in meta.json.

Use: training only, both directions (es->quc: the teacher's K'iche'; quc->es: synthetic source, the
original Spanish as target). Never in the retrieval index, dev, test or the niche. Every record has
origin=distilled_gemini, model, prompt version and seed.

    uv run python -m pipeline.distill gen        # Spanish sentences
    uv run python -m pipeline.distill translate  # K'iche' + filters -> data/train/distilled/pairs.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO), str(REPO / "duel")]

from data.normalize import match_key, normalize_kiche, normalize_spanish, outside_alphabet  # noqa: E402
from duel_core import chrf_pp  # noqa: E402
from pipeline.niche import tokens  # noqa: E402
from tzij_duel.prompts import translation_messages  # noqa: E402
from tzij_duel.settings import get_settings  # noqa: E402

OUT_DIR = REPO / "data" / "train" / "distilled"
SPANISH = OUT_DIR / "spanish.jsonl"
PAIRS = OUT_DIR / "pairs.jsonl"
REJECTED = OUT_DIR / "rejected.jsonl"  # translated and filtered out: a rerun skips them (no paying twice)
META = OUT_DIR / "meta.json"
ORIGIN = "distilled_gemini"
SEED = 2027
GEN_PROMPT = "tzij-distill-gen-v1"
TR_PROMPT = "tzij-distill-translate-v1"
RT_PROMPT = "tzij-roundtrip-v1"
NGRAM = 6

DOMAINS = {
    "conversation": "lines of everyday dialogue between family, neighbours, friends or at the market (questions, answers, greetings, requests)",
    "how-to": "step-by-step instructions and practical advice (cooking, farming, health, household, simple technology)",
    "narration": "first- or third-person narration of everyday events, past and present",
    "social-posts": "short social-media posts about daily life, news in the community, plans and feelings",
    "comments": "short reader comments and reactions to news, videos or posts",
    "reflection": "personal reflections and opinions about family, work, community, nature and change",
    "web-misc": "short informative web text: notices, announcements, descriptions of places and services",
    "other-misc": "signs, short messages, lists, captions and other everyday short texts",
    "story": "sentences of children's stories and fables (animals, grandparents, the village, the forest, the lake)",
}
TOPICS = [
    "el mercado y los precios", "la milpa y la cosecha", "la familia y los abuelos", "la escuela y las tareas",
    "la salud y el centro de salud", "el clima y la lluvia", "el transporte y los caminos", "la fiesta del pueblo",
    "la cocina y las tortillas", "el teléfono y los mensajes", "el trabajo y el dinero", "el agua y el río",
    "los animales de la casa", "el bosque y los árboles", "los vecinos y la comunidad", "los tejidos y la ropa",
    "la iglesia y las costumbres", "el fútbol y los juegos", "los viajes a la ciudad", "la tienda de la esquina",
    "las noticias y la radio", "los niños y el juego", "la lengua materna", "los sueños y los planes",
    "las enfermedades y los remedios", "la noche y las estrellas", "el volcán y la montaña", "las abejas y las flores",
]
REGISTERS = ["sencillo y cotidiano", "con preguntas y respuestas", "con verbos en pasado y futuro"]

GEN_SYSTEM = ("Escribes oraciones en español natural de Guatemala para entrenar un traductor español <-> k'iche'. "
              "Variedad: personas gramaticales, tiempos, preguntas, órdenes, negaciones, números y nombres propios "
              "mayas o comunes. Nada ofensivo ni sensible. Responde solo con JSON: una lista de strings.")
TR_SYSTEM = ("You are an expert K'iche' (Mayan, Guatemala) translator. Modern ALMG orthography: glottal stop as an "
             "ASCII apostrophe ('), no Spanish letters (c, f, d, g, h outside 'ch', ñ, v, z) except in proper names. "
             "Use the reference examples and glossary when they apply. Answer only with JSON: {\"quc\": \"...\"}.")
RT_SYSTEM = ("You translate K'iche' (Mayan, Guatemala) into Spanish. Translate each item faithfully, "
             "one Spanish sentence per item. Answer only with a JSON array of strings, same order and length.")


class Gemini:
    """Async Gemini (Vertex AI) for JSON answers, with token usage and cost."""

    def __init__(self, concurrency: int = 12) -> None:
        from google import genai

        self.s = get_settings()
        self.client = genai.Client(vertexai=True, project=self.s.project, location=self.s.location)
        self.sem = asyncio.Semaphore(concurrency)
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "failed": 0}

    @property
    def model(self) -> str:
        return self.s.gemini_model

    def cost(self) -> float:
        return (self.usage["input_tokens"] * self.s.gemini_input_usd_per_m
                + self.usage["output_tokens"] * self.s.gemini_output_usd_per_m) / 1e6

    async def json(self, system: str, user: str, temperature: float):
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system, temperature=temperature, seed=SEED,
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_level=self.s.gemini_thinking_level)
            if self.s.gemini_thinking_level else None,
        )
        async with self.sem:
            for attempt in range(5):
                try:
                    res = await self.client.aio.models.generate_content(model=self.model, contents=user, config=config)
                    meta = res.usage_metadata
                    self.usage["calls"] += 1
                    self.usage["input_tokens"] += getattr(meta, "prompt_token_count", 0) or 0
                    self.usage["output_tokens"] += ((getattr(meta, "candidates_token_count", 0) or 0)
                                                    + (getattr(meta, "thoughts_token_count", 0) or 0))
                    return json.loads(res.text or "null")
                except json.JSONDecodeError:
                    break
                except Exception:  # transient quota/network
                    await asyncio.sleep(2 * (attempt + 1))
        self.usage["failed"] += 1
        return None

    async def round_trip(self, quc: list[str]) -> list[str] | None:
        items = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(quc))
        out = await self.json(RT_SYSTEM, f"K'iche' items:\n{items}", temperature=0.0)
        if not isinstance(out, list) or len(out) != len(quc):
            return None
        return [normalize_spanish(str(x)) for x in out]


def _meta() -> dict:
    return json.loads(META.read_text()) if META.exists() else {}


def _save_meta(meta: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")


def _dataset() -> Path:
    processed = REPO / "data" / "processed"
    return processed / (processed / "LATEST").read_text().strip()


async def round_trip_threshold(g: Gemini, dataset: Path) -> float:
    """Median round-trip chrF++ of real dev pairs (K'iche' -> Gemini Spanish vs the human Spanish).
    Computed once and kept in meta.json, so every batch is filtered with the same bar."""
    import statistics

    meta = _meta()
    if "round_trip_threshold" in meta.get("translate", {}):
        return meta["translate"]["round_trip_threshold"]
    dev = [json.loads(line) for line in (dataset / "dev.jsonl").read_text(encoding="utf-8").splitlines()]
    dev = [r for r in dev if r["kind"] == "sentence" and r["direction"] == "es-quc"]
    scores = []
    for i in range(0, len(dev), 4):
        batch = dev[i:i + 4]
        rt = await g.round_trip([r["target_text"] for r in batch])
        if rt:
            scores += [chrf_pp(t, r["source_text"]) for t, r in zip(rt, batch)]
    return round(statistics.median(scores), 1)


def held_out(dataset: Path) -> tuple[set[str], set[tuple[str, ...]]]:
    """Exact keys and Spanish 6-grams of every dev/test/niche sentence (BOUQuET and Bloom included)."""
    keys, grams = set(), set()
    for path in [dataset / "dev.jsonl", dataset / "test.jsonl", *dataset.glob("test_*.jsonl")]:
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            keys |= {match_key(r["source_text"]), match_key(r["target_text"])}
            spa = r["source_text"] if r["direction"] == "es-quc" else r["target_text"]
            t = tokens(spa, "spa")
            grams |= {tuple(t[i:i + NGRAM]) for i in range(len(t) - NGRAM + 1)}
    return keys, grams


async def generate(per_call: int = 14) -> dict:
    g = Gemini(concurrency=16)
    jobs = [(d, t, r) for d in DOMAINS for t in TOPICS for r in REGISTERS]
    done = set()
    if SPANISH.exists():
        done = {(x["domain"], x["topic"], x["register"]) for x in map(json.loads, SPANISH.read_text().splitlines())}
    todo = [j for j in jobs if j not in done]

    async def one(domain: str, topic: str, register: str) -> list[dict]:
        user = (f"Escribe {per_call} oraciones distintas (de 5 a 25 palabras) del tipo: {DOMAINS[domain]}. "
                f"Tema: {topic}. Estilo: {register}. Cada oración debe entenderse sola.")
        out = await g.json(GEN_SYSTEM, user, temperature=1.0)
        if not isinstance(out, list):
            return []
        return [{"es": normalize_spanish(str(s)), "domain": domain, "topic": topic, "register": register}
                for s in out if isinstance(s, str) and 5 <= len(s.split()) <= 30]

    t0 = time.perf_counter()
    results = await asyncio.gather(*(one(*j) for j in todo))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with SPANISH.open("a", encoding="utf-8") as fh:
        for rows in results:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    meta = _meta()
    prev = meta.get("gen", {})
    meta["gen"] = {"model": g.model, "prompt_version": GEN_PROMPT, "seed": SEED, "calls": prev.get("calls", 0) + len(todo),
                   "sentences": len(SPANISH.read_text().splitlines()),
                   "cost_usd": round(prev.get("cost_usd", 0) + g.cost(), 4), "seconds": round(time.perf_counter() - t0, 1)}
    _save_meta(meta)
    return meta["gen"]


async def translate(limit: int | None = None) -> dict:
    from pipeline.train_set import raft_retriever

    dataset = _dataset()
    keys, grams = held_out(dataset)
    retriever, k = raft_retriever(dataset.name)

    seen, rows, drop = set(), [], {"duplicate": 0, "held_out": 0}
    for x in map(json.loads, SPANISH.read_text(encoding="utf-8").splitlines()):
        key = match_key(x["es"])
        t = tokens(x["es"], "spa")
        if key in seen:
            drop["duplicate"] += 1
            continue
        if key in keys or any(tuple(t[i:i + NGRAM]) in grams for i in range(len(t) - NGRAM + 1)):
            drop["held_out"] += 1
            continue
        seen.add(key)
        rows.append(x)
    rows = rows[:limit] if limit else rows
    done = set()
    for path in (PAIRS, REJECTED):
        if path.exists():
            done |= {x["es_key"] for x in map(json.loads, path.read_text().splitlines())}
    todo = [x for x in rows if match_key(x["es"]) not in done]

    g = Gemini(concurrency=16)
    threshold = await round_trip_threshold(g, dataset)
    stats = {"translated": 0, "alphabet": 0, "length": 0, "round_trip": 0, "kept": 0, "failed": 0}

    async def one(x: dict) -> dict | None:
        context = retriever.retrieve(x["es"], "es-quc", k).as_prompt_context()
        user = translation_messages(x["es"], "es-quc", context)[-1]["content"]
        out = await g.json(TR_SYSTEM, user, temperature=0.2)
        quc = normalize_kiche(str(out.get("quc", ""))) if isinstance(out, dict) else ""
        if not quc:
            stats["failed"] += 1
            return None  # not recorded: a transient failure is retried on the next run
        stats["translated"] += 1
        names = {w for w in re.findall(r"\b[A-ZÁÉÍÓÚÑ][\w']+", x["es"])}
        reject = lambda why: {"es_key": match_key(x["es"]), "rejected": why}  # noqa: E731
        if outside_alphabet(" ".join(w for w in quc.split() if w.strip(".,;:!?¿¡\"()") not in names)):
            stats["alphabet"] += 1
            return reject("alphabet")
        ratio = len(quc.split()) / max(len(x["es"].split()), 1)
        if not 0.4 <= ratio <= 2.0:
            stats["length"] += 1
            return reject("length")
        rt = await g.round_trip([quc])
        score = chrf_pp(rt[0], x["es"]) if rt else 0.0
        if score < threshold:
            stats["round_trip"] += 1
            return reject("round_trip")
        stats["kept"] += 1
        pid = "dst-" + hashlib.sha1(f"{match_key(x['es'])}|{match_key(quc)}".encode()).hexdigest()[:12]
        return {"pair_id": pid, "es": x["es"], "quc": quc, "es_key": match_key(x["es"]), "round_trip_chrf": round(score, 1),
                "domain": x["domain"], "topic": x["topic"], "origin": ORIGIN, "model": g.model,
                "prompt_version": TR_PROMPT, "seed": SEED}

    t0 = time.perf_counter()
    results = []
    for i in range(0, len(todo), 400):  # checkpoint every 400 sentences
        chunk = await asyncio.gather(*(one(x) for x in todo[i:i + 400]))
        with PAIRS.open("a", encoding="utf-8") as fh, REJECTED.open("a", encoding="utf-8") as rj:
            for rec in chunk:
                if rec:
                    (rj if "rejected" in rec else fh).write(json.dumps(rec, ensure_ascii=False) + "\n")
        results += chunk
        print(f"  {min(i + 400, len(todo))}/{len(todo)} kept so far {stats['kept']} (${g.cost():.2f})", flush=True)
    meta = _meta()
    prev = meta.get("translate", {})
    meta["translate"] = {"model": g.model, "prompt_version": TR_PROMPT, "seed": SEED, "k": k,
                         "round_trip_threshold": threshold, "threshold_rule": "median round-trip chrF++ of real dev pairs",
                         "round_trip_prompt_version": RT_PROMPT,
                         "spanish_candidates": len(rows), **drop, **stats,
                         "pairs_total": len(PAIRS.read_text().splitlines()) if PAIRS.exists() else 0,
                         "cost_usd": round(prev.get("cost_usd", 0) + g.cost(), 4), "seconds": round(time.perf_counter() - t0, 1)}
    _save_meta(meta)
    return meta["translate"]


def records() -> list[dict]:
    """Distilled pairs as train records, both directions (pipeline/train_set.py --distilled)."""
    out = []
    for x in map(json.loads, PAIRS.read_text(encoding="utf-8").splitlines()) if PAIRS.exists() else []:
        base = {"pair_id": x["pair_id"], "kind": "sentence", "split": "train", "status": "clean", "domain": x["domain"],
                "origin": ORIGIN, "source_name": "distilled_gemini", "model": x["model"], "prompt_version": x["prompt_version"]}
        out.append({**base, "id": f"{x['pair_id']}-es-quc", "direction": "es-quc", "source_text": x["es"], "target_text": x["quc"]})
        out.append({**base, "id": f"{x['pair_id']}-quc-es", "direction": "quc-es", "source_text": x["quc"], "target_text": x["es"]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["gen", "translate"])
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    result = asyncio.run(generate() if args.step == "gen" else translate(args.limit))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
