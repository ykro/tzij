"""Synthetic training pairs grounded in our licensed data (make synthetic).

Synthetic data became allowed for Tzij after David lost the pre-registered niche
(evals/niche_results.md). The guardrails:

- Training only. Synthetic pairs never enter test, dev, the niche slice or the retrieval
  index, and any pair whose Spanish or K'iche' repeats a dev/test sentence is dropped.
- Grounded generation, two methods:
  * `dict`: dictionary-anchored. For every short entry of our training lexicon (K'iche'
    headword + Spanish gloss + an attested train sentence that uses it, when there is one),
    Gemini writes 3 short phrases and 1 short sentence that use that exact headword. Phrases
    are weighted because short phrases are David's closest slice.
  * `slots`: template/slot filling on UD K'iche' train sentences. A noun or verb is swapped
    for another form attested in UD with the same POS and the same features (person, number,
    possessor, aspect, transitivity), whose lemma is in our dictionary. The K'iche' is
    therefore built from attested words and frames. Gemini only writes the Spanish side.
- Rejections, all recorded in data/train/synthetic/meta.json:
  * the K'iche' side lacks the headword (normalized);
  * it uses letters outside the ALMG alphabet;
  * it repeats dev/test or another synthetic pair;
  * it fails the round-trip check. Gemini translates the K'iche' back into Spanish, and chrF++
    against the Spanish must reach a threshold set on dev: the 25th percentile of the same
    round trip on real dev pairs.
- Tagging: origin=synthetic, with method, model, prompt version and seed on every record.
  The share of training is capped (pipeline/train_set.py --syn CAP; cap chosen on dev).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO), str(REPO / "duel")]

from data.normalize import match_key, normalize_kiche, normalize_spanish, outside_alphabet  # noqa: E402
from duel_core import chrf_pp  # noqa: E402
from pipeline.niche import tokens  # noqa: E402
from tzij_duel.settings import get_settings  # noqa: E402

OUT_DIR = REPO / "data" / "train" / "synthetic"
META = OUT_DIR / "meta.json"
UD_CONLLU = REPO / "data" / "raw" / "ud_kiche_iu" / "quc_iu-ud-test.conllu"
SEED = 2027
ORIGIN = "synthetic"
RT_PROMPT = "tzij-roundtrip-v1"
DICT_PROMPT = "tzij-dict-anchored-v1"
SLOT_PROMPT = "tzij-ud-slots-v1"
ORTHOGRAPHY = ("Modern ALMG K'iche' orthography: glottal stop written as an ASCII apostrophe ('), "
               "no Spanish letters (c, f, d, g, h outside 'ch', ñ, v, z).")

RT_SYSTEM = ("You translate K'iche' (Mayan, Guatemala) into Spanish. Translate each item faithfully, "
             "one Spanish sentence per item. Answer only with a JSON array of strings, same order and length.")
DICT_SYSTEM = ("You write training examples for a Spanish <-> K'iche' translator. " + ORTHOGRAPHY +
               " Use simple, natural, everyday language. Answer only with JSON.")
SLOT_SYSTEM = ("You translate K'iche' (Mayan, Guatemala) into Spanish. You get an original K'iche' sentence "
               "with its human Spanish translation, and a variant where exactly one word was replaced. Translate "
               "the variant, keeping the original Spanish wording except where the replaced word requires a change "
               "(including agreement). Answer only with JSON: {\"es\": \"...\"}.")


# ---------------------------------------------------------------- Gemini

class Gemini:
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


# ---------------------------------------------------------------- shared data

def _dataset() -> Path:
    processed = REPO / "data" / "processed"
    return processed / (processed / "LATEST").read_text().strip()


def _records(dataset: Path, split: str) -> list[dict]:
    return [json.loads(l) for l in (dataset / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()]


def held_out_keys(dataset: Path) -> set[str]:
    """Keys of every dev/test sentence: a synthetic pair repeating one is a leak."""
    keys = set()
    for split in ("dev", "test"):
        for r in _records(dataset, split):
            keys.add(match_key(r["source_text"]))
            keys.add(match_key(r["target_text"]))
    return keys


def _has_phrase(text_tokens: list[str], phrase: list[str]) -> bool:
    n = len(phrase)
    return any(text_tokens[i:i + n] == phrase for i in range(len(text_tokens) - n + 1))


def _meta() -> dict:
    return json.loads(META.read_text()) if META.exists() else {}


def _save_meta(meta: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")


def _pair_record(es: str, quc: str, method: str, prompt: str, model: str, extra: dict) -> dict:
    pid = "syn-" + hashlib.sha1(f"{method}|{match_key(quc)}|{match_key(es)}".encode()).hexdigest()[:12]
    return {"pair_id": pid, "es": es, "quc": quc, "origin": ORIGIN, "method": method, "model": model,
            "prompt_version": prompt, "seed": SEED, "words_quc": len(quc.split()), **extra}


# ---------------------------------------------------------------- round-trip threshold (dev)

async def threshold(g: Gemini, dataset: Path) -> dict:
    dev = [r for r in _records(dataset, "dev") if r["kind"] == "sentence" and r["direction"] == "es-quc"]
    scores = []
    for i in range(0, len(dev), 4):
        batch = dev[i:i + 4]
        rt = await g.round_trip([r["target_text"] for r in batch])
        if rt:
            scores += [chrf_pp(t, r["source_text"]) for t, r in zip(rt, batch)]
    p = np.percentile(scores, [10, 25, 50, 75])
    result = {"dev_pairs": len(scores), "p10": round(p[0], 1), "p25": round(p[1], 1), "median": round(p[2], 1),
              "p75": round(p[3], 1), "threshold": round(float(p[1]), 1),
              "rule": "25th percentile of the round-trip chrF++ of real dev pairs"}
    meta = _meta()
    meta["round_trip"] = {**result, "prompt_version": RT_PROMPT, "model": g.model}
    _save_meta(meta)
    return result


# ---------------------------------------------------------------- dictionary-anchored

def dictionary_entries(dataset: Path) -> list[dict]:
    train = _records(dataset, "train")
    entries: dict[str, dict] = {}
    for r in train:
        if r["kind"] != "lexicon" or r["direction"] != "es-quc":
            continue
        quc = normalize_kiche(r["target_text"])
        if any(ch in quc + r["source_text"] for ch in "()/=[]"):
            continue  # course notation like "Ch'uki'(k)": not a form to copy literally
        q, e = tokens(quc, "quc"), tokens(r["source_text"], "spa")
        if 1 <= len(q) <= 3 and 1 <= len(e) <= 4 and not outside_alphabet(quc):
            entries.setdefault(" ".join(q), {"headword": quc.strip(" .,;"), "gloss": r["source_text"].strip(),
                                             "entry_id": r["id"], "source_name": r["source_name"], "tokens": q})
    examples = [r for r in train if r["kind"] == "sentence" and r["direction"] == "es-quc"
                and r["source_name"] in ("ud_kiche_iu", "coerll_kiche")]
    index: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(examples, key=lambda r: r["id"]):
        for t in set(tokens(r["target_text"], "quc")):
            index[t].append(r)
    for e in entries.values():
        for r in index.get(e["tokens"][0], []):
            if _has_phrase(tokens(r["target_text"], "quc"), e["tokens"]):
                e["example"] = {"quc": r["target_text"], "es": r["source_text"], "id": r["id"]}
                break
    return sorted(entries.values(), key=lambda e: e["entry_id"])


def dict_prompt(e: dict) -> str:
    lines = [f"Dictionary entry: K'iche' \"{e['headword']}\" = Spanish \"{e['gloss']}\"."]
    if "example" in e:
        lines.append(f"Attested example: K'iche' \"{e['example']['quc']}\" = Spanish \"{e['example']['es']}\".")
    lines.append(
        f"Write 4 Spanish-K'iche' pairs that use the K'iche' form \"{e['headword']}\" exactly as written "
        "(same spelling, no added prefixes or suffixes on it): 3 short phrases of 1-4 words and 1 short "
        "sentence of 5-8 words. Everyday situations. "
        'JSON: [{"es": "...", "quc": "..."}, ...]')
    return "\n".join(lines)


async def generate_dict(g: Gemini, dataset: Path, limit: int | None = None) -> dict:
    thr = _meta()["round_trip"]["threshold"]
    held = held_out_keys(dataset)
    entries = dictionary_entries(dataset)[:limit] if limit else dictionary_entries(dataset)
    out_path = OUT_DIR / "dictionary_anchored.jsonl"
    done = {json.loads(l)["entry_id"] for l in out_path.read_text().splitlines()} if out_path.exists() else set()
    rejected = defaultdict(int)
    seen: set[str] = set()
    kept = []

    async def one(e: dict) -> list[dict]:
        raw = await g.json(DICT_SYSTEM, dict_prompt(e), temperature=0.7)
        if not isinstance(raw, list):
            rejected["no_json"] += 1
            return []
        cands = []
        for item in raw[:6]:
            if not isinstance(item, dict) or not item.get("es") or not item.get("quc"):
                rejected["malformed"] += 1
                continue
            es, quc = normalize_spanish(str(item["es"])), normalize_kiche(str(item["quc"]))
            if not _has_phrase(tokens(quc, "quc"), e["tokens"]):
                rejected["no_headword"] += 1
            elif outside_alphabet(quc):
                rejected["alphabet"] += 1
            elif match_key(quc) in held or match_key(es) in held:
                rejected["dev_test_overlap"] += 1
            elif match_key(quc) in seen:
                rejected["duplicate"] += 1
            else:
                seen.add(match_key(quc))
                cands.append((es, quc))
        if not cands:
            return []
        rt = await g.round_trip([q for _, q in cands])
        if rt is None:
            rejected["round_trip_failed"] += len(cands)
            return []
        out = []
        for (es, quc), back in zip(cands, rt):
            score = chrf_pp(back, es)
            if score < thr:
                rejected["round_trip_low"] += 1
                continue
            out.append(_pair_record(es, quc, "dictionary_anchored", DICT_PROMPT, g.model, {
                "entry_id": e["entry_id"], "headword": e["headword"], "gloss": e["gloss"],
                "entry_source": e["source_name"], "attested_example": e.get("example", {}).get("id"),
                "round_trip_es": back, "round_trip_chrf": round(score, 1)}))
        return out

    todo = [e for e in entries if e["entry_id"] not in done]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    for i in range(0, len(todo), 200):  # checkpoint every 200 entries
        results = await asyncio.gather(*(one(e) for e in todo[i:i + 200]))
        with out_path.open("a", encoding="utf-8") as fh:
            for recs in results:
                for rec in recs:
                    kept.append(rec)
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  dict {min(i + 200, len(todo))}/{len(todo)} entries, kept {len(kept)}, ${g.cost():.2f}", flush=True)
    return {"entries": len(entries), "entries_with_attested_example": sum("example" in e for e in entries),
            "kept_this_run": len(kept), "rejected_this_run": dict(rejected), "seconds": round(time.perf_counter() - t0)}


# ---------------------------------------------------------------- UD slot filling

def parse_conllu(path: Path) -> list[dict]:
    sents = []
    for block in path.read_text(encoding="utf-8").split("\n\n"):
        meta, toks = {}, []
        for line in block.splitlines():
            if line.startswith("# ") and " = " in line:
                k, v = line[2:].split(" = ", 1)
                meta[k] = v
            elif line and not line.startswith("#"):
                c = line.split("\t")
                if len(c) == 10 and c[0].isdigit():
                    toks.append({"form": c[1], "lemma": c[2], "upos": c[3], "feats": c[5],
                                 "space": "SpaceAfter=No" not in c[9]})
        if toks and meta.get("text[spa]"):
            sents.append({"id": meta.get("sent_id", ""), "quc": meta.get("text", ""), "es": meta["text[spa]"],
                          "tokens": toks})
    return sents


def _render(toks: list[dict]) -> str:
    return "".join(t["form"] + (" " if t["space"] else "") for t in toks).strip()


def slot_candidates(dataset: Path, per_sentence: int = 2) -> list[dict]:
    train_keys = {match_key(normalize_kiche(r["target_text"])) for r in _records(dataset, "train")
                  if r["source_name"] == "ud_kiche_iu" and r["direction"] == "es-quc"}
    held = held_out_keys(dataset)
    lexicon: dict[str, str] = {}
    for r in _records(dataset, "train"):
        if r["kind"] == "lexicon" and r["direction"] == "quc-es":
            t = tokens(r["source_text"], "quc")
            if len(t) == 1:
                lexicon.setdefault(t[0], r["target_text"])
    sents = []
    for s in parse_conllu(UD_CONLLU):
        key = match_key(normalize_kiche(s["quc"]))
        if key in train_keys and key not in held and match_key(s["es"]) not in held:
            sents.append(s)
    pool: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)  # (upos, feats) -> lemma -> token
    for s in sents:
        for t in s["tokens"]:
            lemma = tokens(normalize_kiche(t["lemma"]), "quc")
            if t["upos"] in ("NOUN", "VERB") and lemma and lemma[0] in lexicon:
                pool[(t["upos"], t["feats"])].setdefault(lemma[0], {**t, "gloss": lexicon[lemma[0]]})
    rng = random.Random(SEED)
    out = []
    for s in sents:
        slots = [i for i, t in enumerate(s["tokens"]) if t["upos"] in ("NOUN", "VERB")
                 and len(pool.get((t["upos"], t["feats"]), {})) >= 2]
        rng.shuffle(slots)
        for i in slots[:per_sentence]:
            old = s["tokens"][i]
            old_lemma = (tokens(normalize_kiche(old["lemma"]), "quc") or [""])[0]
            options = sorted(l for l in pool[(old["upos"], old["feats"])] if l != old_lemma)
            if not options:
                continue
            new = pool[(old["upos"], old["feats"])][rng.choice(options)]
            toks = list(s["tokens"])
            toks[i] = {**old, "form": new["form"]}
            out.append({"ud_id": s["id"], "orig_quc": normalize_kiche(s["quc"]), "orig_es": normalize_spanish(s["es"]),
                        "quc": normalize_kiche(_render(toks)), "old": old["form"], "new": new["form"],
                        "new_lemma": new["lemma"], "gloss": new["gloss"], "upos": old["upos"], "feats": old["feats"]})
    return out


async def generate_slots(g: Gemini, dataset: Path) -> dict:
    thr = _meta()["round_trip"]["threshold"]
    held = held_out_keys(dataset)
    cands = slot_candidates(dataset)
    out_path = OUT_DIR / "ud_slots.jsonl"
    done = {json.loads(l)["quc"] for l in out_path.read_text().splitlines()} if out_path.exists() else set()
    rejected = defaultdict(int)
    kept = []

    async def one(c: dict) -> dict | None:
        if outside_alphabet(c["quc"]):
            rejected["alphabet"] += 1
            return None
        if match_key(c["quc"]) in held:
            rejected["dev_test_overlap"] += 1
            return None
        user = (f"Original K'iche': {c['orig_quc']}\nOriginal Spanish: {c['orig_es']}\n"
                f"Variant K'iche': {c['quc']}\nReplaced word: \"{c['old']}\" -> \"{c['new']}\" "
                f"(dictionary: \"{c['new_lemma']}\" = \"{c['gloss']}\")")
        res = await g.json(SLOT_SYSTEM, user, temperature=0.2)
        es = normalize_spanish(str(res.get("es", ""))) if isinstance(res, dict) else ""
        if not es:
            rejected["no_json"] += 1
            return None
        if match_key(es) in held:
            rejected["dev_test_overlap"] += 1
            return None
        rt = await g.round_trip([c["quc"]])
        if not rt:
            rejected["round_trip_failed"] += 1
            return None
        score = chrf_pp(rt[0], es)
        if score < thr:
            rejected["round_trip_low"] += 1
            return None
        return _pair_record(es, c["quc"], "ud_slots", SLOT_PROMPT, g.model, {
            "ud_id": c["ud_id"], "swap": f"{c['old']} -> {c['new']}", "upos": c["upos"], "feats": c["feats"],
            "round_trip_es": rt[0], "round_trip_chrf": round(score, 1)})

    todo = [c for c in cands if c["quc"] not in done]
    seen: set[str] = set()
    todo = [c for c in todo if not (match_key(c["quc"]) in seen or seen.add(match_key(c["quc"])))]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    for i in range(0, len(todo), 300):
        results = await asyncio.gather(*(one(c) for c in todo[i:i + 300]))
        with out_path.open("a", encoding="utf-8") as fh:
            for rec in results:
                if rec:
                    kept.append(rec)
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  slots {min(i + 300, len(todo))}/{len(todo)}, kept {len(kept)}, ${g.cost():.2f}", flush=True)
    return {"candidates": len(cands), "kept_this_run": len(kept), "rejected_this_run": dict(rejected),
            "seconds": round(time.perf_counter() - t0)}


# ---------------------------------------------------------------- CLI

async def main_async(args) -> None:
    g = Gemini()
    dataset = _dataset()
    meta = _meta()
    if args.command in ("threshold", "all") and ("round_trip" not in meta or args.command == "threshold"):
        print("threshold", await threshold(g, dataset))
    steps = {"dict": generate_dict, "slots": generate_slots}
    for name in (["dict", "slots"] if args.command == "all" else [args.command] if args.command in steps else []):
        res = await steps[name](g, dataset, args.limit) if name == "dict" else await steps[name](g, dataset)
        meta = _meta()
        prev = meta.get(name, {})
        rej = defaultdict(int, prev.get("rejected", {}))
        for k, v in res.pop("rejected_this_run").items():
            rej[k] += v
        meta[name] = {**prev, **res, "rejected": dict(rej),
                      "kept_total": sum(1 for _ in (OUT_DIR / ("dictionary_anchored.jsonl" if name == "dict" else "ud_slots.jsonl")).open())}
        _save_meta(meta)
        print(name, json.dumps(meta[name], ensure_ascii=False))
    meta = _meta()
    meta.update({"model": g.model, "seed": SEED, "dataset": dataset.name,
                 "prompts": {"round_trip": RT_PROMPT, "dict": DICT_PROMPT, "slots": SLOT_PROMPT},
                 "cost_usd_total": round(meta.get("cost_usd_total", 0) + g.cost(), 4),
                 "gemini_usage_total": {k: meta.get("gemini_usage_total", {}).get(k, 0) + v for k, v in g.usage.items()}})
    _save_meta(meta)
    print(f"cost this run ${g.cost():.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["threshold", "dict", "slots", "all"])
    ap.add_argument("--limit", type=int, default=None, help="dict: only the first N entries (smoke test)")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
