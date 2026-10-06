"""Example phrases for the translator page (/traductor/): one click fills the box and translates.

They come from the use case David wins: a translation memory (Firefox Focus, español → Kʼicheʼ,
evals/niche_results.md: 37.4 vs 28.9 chrF++). Each one is a licensed pair from test_niche.jsonl
(Mozilla Pontoon, MPL-2.0), never in David's training data or retrieval index, and was translated
live by David as on stage, ROUNDS times, staying at or above MIN_CHRF against the licensed
reference every time. duel/examples.json is tracked; `make examples` re-checks it.

  make examples                    # re-check the examples in duel/examples.json
  make examples IDS=id1,id2,...    # check these test_niche pair_ids and keep the ones that pass
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from .deck import latest_dataset
from .settings import REPO_ROOT, get_settings

EXAMPLES = REPO_ROOT / "duel" / "examples.json"
MIN_CHRF = 50.0  # chrF++ against the licensed reference; above this the output is close to it
ROUNDS = 3
SOURCE_LABEL = {"pontoon_mozilla": "Mozilla Pontoon (Firefox Focus)"}


def load_examples(path: Path = EXAMPLES) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["examples"]


def public(example: dict) -> dict:
    """What the page needs: the phrase, its direction and where it comes from."""
    return {key: example[key] for key in ("pair_id", "direction", "text", "source", "url", "license")}


def niche_pairs(processed: Path) -> dict[str, dict]:
    dataset = latest_dataset(processed)
    path = dataset / "test_niche.jsonl" if dataset else None
    if not path or not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    return {r["pair_id"]: r for r in rows if r["direction"] == "es-quc"}


def passes(scores: list[float | None], rounds: int = ROUNDS, min_chrf: float = MIN_CHRF) -> bool:
    return len(scores) == rounds and all(c is not None and c >= min_chrf for c in scores)


async def verify(pair_ids: list[str], rounds: int = ROUNDS) -> list[dict]:
    from .main import _load_retriever
    from .variants import stage_variants, translate

    s = get_settings()
    david, _ = stage_variants(s)
    retriever = _load_retriever(s)
    pairs = niche_pairs(s.processed_dir)
    kept = []
    for pid in pair_ids:
        pair = pairs.get(pid)
        if pair is None:
            print(f"  fuera {pid}: no está en test_niche.jsonl (español → Kʼicheʼ)")
            continue
        scores: list[float | None] = []
        outputs = []
        for _ in range(rounds):
            r = await translate(david, pair["source_text"], "es-quc", retriever=retriever, online=True,
                                reference=pair["target_text"])
            scores.append(r.chrf)
            outputs.append(r.text)
            if r.chrf is None or r.chrf < MIN_CHRF:
                break
        ok = passes(scores, rounds)
        print(f"  {'ok   ' if ok else 'fuera'} {pair['source_text']!r:44} → {outputs[-1]!r}  chrF++ {scores}", flush=True)
        if ok:
            kept.append({"pair_id": pid, "direction": "es-quc", "text": pair["source_text"],
                         "reference": pair["target_text"], "english": pair.get("ref", ""),
                         "source": SOURCE_LABEL.get(pair["source_name"], pair["source_name"]),
                         "product": pair.get("product", ""), "url": pair["url"], "license": pair["license"],
                         "david_outputs": outputs, "chrf": scores})
    return kept


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", default="", help="comma-separated test_niche pair_ids (default: the current examples)")
    args = ap.parse_args()
    s = get_settings()
    ids = [i.strip() for i in args.ids.split(",") if i.strip()] or [e["pair_id"] for e in load_examples()]
    if not ids:
        print("No hay ejemplos: make examples IDS=<pair_ids de test_niche>")
        return 1
    dataset = latest_dataset(s.processed_dir)
    kept = asyncio.run(verify(ids))
    EXAMPLES.write_text(json.dumps({
        "about": "Example buttons of /traductor/: licensed español → Kʼicheʼ pairs from the Firefox Focus "
                 f"translation memory (test_niche), translated live by David {ROUNDS} times with chrF++ >= {MIN_CHRF:g} "
                 "against the reference. Built by `make examples`.",
        "dataset": dataset.name if dataset else None, "david": s.david_model, "min_chrf": MIN_CHRF,
        "checked": date.today().isoformat(), "examples": kept,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(kept)} de {len(ids)} ejemplos en {EXAMPLES.relative_to(REPO_ROOT)}")
    # With IDS, dropping candidates is the point; re-checking the current examples, every one must pass.
    return 0 if kept and (args.ids or len(kept) == len(ids)) else 1


if __name__ == "__main__":
    sys.exit(main())
