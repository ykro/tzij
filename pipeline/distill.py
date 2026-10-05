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
   reach the MEDIAN chrF++ of the same round trip on real dev pairs (stricter than the 25th
   percentile used for pipeline/synthetic.py, because Gemini reads its own K'iche' back easily).

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
from pipeline.synthetic import Gemini  # noqa: E402
from tzij_duel.prompts import translation_messages  # noqa: E402

OUT_DIR = REPO / "data" / "train" / "distilled"
SPANISH = OUT_DIR / "spanish.jsonl"
PAIRS = OUT_DIR / "pairs.jsonl"
META = OUT_DIR / "meta.json"
ORIGIN = "distilled_gemini"
SEED = 2027
GEN_PROMPT = "tzij-distill-gen-v1"
TR_PROMPT = "tzij-distill-translate-v1"
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


def _meta() -> dict:
    return json.loads(META.read_text()) if META.exists() else {}


def _save_meta(meta: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")


def _dataset() -> Path:
    processed = REPO / "data" / "processed"
    return processed / (processed / "LATEST").read_text().strip()


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
    threshold = json.loads((REPO / "data" / "train" / "synthetic" / "meta.json").read_text())["round_trip"]["median"]

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
    done = {}
    if PAIRS.exists():
        done = {x["es_key"]: x for x in map(json.loads, PAIRS.read_text().splitlines())}
    todo = [x for x in rows if match_key(x["es"]) not in done]

    g = Gemini(concurrency=16)
    stats = {"translated": 0, "alphabet": 0, "length": 0, "round_trip": 0, "kept": 0, "failed": 0}

    async def one(x: dict) -> dict | None:
        context = retriever.retrieve(x["es"], "es-quc", k).as_prompt_context()
        user = translation_messages(x["es"], "es-quc", context)[-1]["content"]
        out = await g.json(TR_SYSTEM, user, temperature=0.2)
        quc = normalize_kiche(str(out.get("quc", ""))) if isinstance(out, dict) else ""
        if not quc:
            stats["failed"] += 1
            return None
        stats["translated"] += 1
        names = {w for w in re.findall(r"\b[A-ZÁÉÍÓÚÑ][\w']+", x["es"])}
        if outside_alphabet(" ".join(w for w in quc.split() if w.strip(".,;:!?¿¡\"()") not in names)):
            stats["alphabet"] += 1
            return None
        ratio = len(quc.split()) / max(len(x["es"].split()), 1)
        if not 0.4 <= ratio <= 2.0:
            stats["length"] += 1
            return None
        rt = await g.round_trip([quc])
        score = chrf_pp(rt[0], x["es"]) if rt else 0.0
        if score < threshold:
            stats["round_trip"] += 1
            return None
        stats["kept"] += 1
        pid = "dst-" + hashlib.sha1(f"{match_key(x['es'])}|{match_key(quc)}".encode()).hexdigest()[:12]
        return {"pair_id": pid, "es": x["es"], "quc": quc, "es_key": match_key(x["es"]), "round_trip_chrf": round(score, 1),
                "domain": x["domain"], "topic": x["topic"], "origin": ORIGIN, "model": g.model,
                "prompt_version": TR_PROMPT, "seed": SEED}

    t0 = time.perf_counter()
    results = []
    for i in range(0, len(todo), 400):  # checkpoint every 400 sentences
        chunk = await asyncio.gather(*(one(x) for x in todo[i:i + 400]))
        with PAIRS.open("a", encoding="utf-8") as fh:
            for rec in chunk:
                if rec:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        results += chunk
        print(f"  {min(i + 400, len(todo))}/{len(todo)} kept so far {stats['kept']} (${g.cost():.2f})", flush=True)
    meta = _meta()
    prev = meta.get("translate", {})
    meta["translate"] = {"model": g.model, "prompt_version": TR_PROMPT, "seed": SEED, "k": k,
                         "round_trip_threshold": threshold, "threshold_rule": "median round-trip chrF++ of real dev pairs",
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
