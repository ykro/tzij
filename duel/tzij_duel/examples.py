"""Example phrases for the demo page: one click fills the box and both translate.

They come from the use case David wins: a translation memory (español → Kʼicheʼ, evals/niche_results.md:
37.4 vs 28.9 chrF++ on Firefox Focus). Each one is a licensed pair written by people (Mozilla Pontoon,
MPL-2.0) that was never in David's training data or retrieval index: the held-out Firefox Focus strings
of test_niche.jsonl, and the newer Pontoon strings of evals/tm_new.jsonl (more Firefox Focus, and new
strings of Mozilla Monitor, Mozilla accounts and Firefox Send, whose older strings David has). It was translated
ROUNDS times by David (his GPU service in the cloud, DAVID_URL) and by Goliath, exactly as the page
does, and is kept only if every time David stays at or above MIN_CHRF against the licensed
reference and beats Goliath by at least MIN_MARGIN. duel/examples.json is tracked; `make examples`
re-checks it.

  make examples                    # re-check the examples in duel/examples.json
  make examples IDS=id1,id2,...    # check these pair_ids (test_niche or evals/tm_new.jsonl), keep those that pass
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from .dataset import latest_dataset
from .settings import REPO_ROOT, get_settings

EXAMPLES = REPO_ROOT / "duel" / "examples.json"
MIN_CHRF = 50.0  # chrF++ against the licensed reference; above this the output is close to it
MIN_MARGIN = 15.0  # David − Goliath, chrF++ points: clearly better, not a coin flip
ROUNDS = 3
TM_NEW = REPO_ROOT / "evals" / "tm_new.jsonl"
PRODUCT_NAME = {"focus-for-android": "Firefox Focus", "focus-for-android-po": "Firefox Focus",
                "mozilla-monitor-website": "Mozilla Monitor", "test-pilot-firefox-send": "Firefox Send",
                "mozilla-accounts": "Mozilla accounts"}


def load_examples(path: Path = EXAMPLES) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["examples"]


def public(example: dict) -> dict:
    """What the page needs: the phrase, its correct translation, its direction and where it comes from."""
    out = {key: example[key] for key in ("pair_id", "direction", "text", "reference", "source", "url", "license")}
    out["product"] = example.get("product_name") or PRODUCT_NAME.get(example.get("product", ""), "Firefox Focus")
    return out


def niche_pairs(processed: Path, tm_new: Path = TM_NEW) -> dict[str, dict]:
    """Candidate pairs: the held-out Firefox Focus product (test_niche) and the newer Pontoon strings."""
    dataset = latest_dataset(processed)
    paths = [dataset / "test_niche.jsonl"] if dataset else []
    paths.append(tm_new)
    pairs: dict[str, dict] = {}
    for path in paths:
        if path.exists():
            for r in map(json.loads, path.read_text(encoding="utf-8").splitlines()):
                if r["direction"] == "es-quc":
                    r.setdefault("product", "focus-for-android")
                    pairs[r["pair_id"]] = r
    return pairs


def passes(runs: list[tuple[float | None, float | None]], rounds: int = ROUNDS, min_chrf: float = MIN_CHRF,
           min_margin: float = MIN_MARGIN) -> bool:
    """Every live run: David close to the reference and clearly ahead of Goliath (a failed call fails)."""
    return len(runs) == rounds and all(
        d is not None and g is not None and d >= min_chrf and d - g >= min_margin for d, g in runs)


async def verify(pair_ids: list[str], rounds: int = ROUNDS) -> list[dict]:
    from .page import Page

    s = get_settings()
    if not s.david_url:
        raise SystemExit("DAVID_URL is not set: the examples are checked against David's service in the cloud "
                         "(gcloud run services describe tzij-david --region europe-west4 --format='value(status.url)')")
    page = Page(s)
    pairs = niche_pairs(s.processed_dir)
    kept = []
    for pid in pair_ids:
        pair = pairs.get(pid)
        if pair is None:
            print(f"  fuera {pid}: no está en test_niche.jsonl ni en evals/tm_new.jsonl (español → Kʼicheʼ)")
            continue
        runs: list[tuple[float | None, float | None]] = []
        outputs: list[tuple[str, str]] = []
        times: list[tuple[float | None, float | None]] = []
        for _ in range(rounds):
            d, g = await asyncio.gather(
                page.side("david", pair["source_text"], "es-quc", pair["target_text"]),
                page.side("goliath", pair["source_text"], "es-quc", pair["target_text"]),
            )
            runs.append((d["closeness"], g["closeness"]))
            outputs.append((d["text"], g["text"]))
            times.append((d["latency_ms"], g["latency_ms"]))
            if not passes(runs, len(runs)):
                break
        ok = passes(runs, rounds)
        shown = ", ".join(f"{d}/{g}" for d, g in runs)
        print(f"  {'ok   ' if ok else 'fuera'} {pair['source_text']!r:44} David «{outputs[-1][0]}» · Goliath «{outputs[-1][1]}»"
              f"  chrF++ David/Goliath {shown}", flush=True)
        if ok:
            kept.append({"pair_id": pid, "direction": "es-quc", "text": pair["source_text"],
                         "reference": pair["target_text"], "english": pair.get("ref", ""),
                         "source": f"Mozilla Pontoon ({PRODUCT_NAME.get(pair['product'], pair['product'])})",
                         "product": pair["product"], "product_name": PRODUCT_NAME.get(pair["product"], pair["product"]),
                         "url": pair["url"], "license": pair["license"],
                         "david_outputs": [o[0] for o in outputs], "goliath_outputs": [o[1] for o in outputs],
                         "david_chrf": [d for d, _ in runs], "goliath_chrf": [g for _, g in runs],
                         "david_ms": [d for d, _ in times], "goliath_ms": [g for _, g in times]})
    return kept


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", default="", help="comma-separated pair_ids from test_niche or evals/tm_new.jsonl (default: the current examples)")
    args = ap.parse_args()
    s = get_settings()
    ids = [i.strip() for i in args.ids.split(",") if i.strip()] or [e["pair_id"] for e in load_examples()]
    if not ids:
        print("No hay ejemplos: make examples IDS=<pair_ids de test_niche>")
        return 1
    dataset = latest_dataset(s.processed_dir)
    kept = asyncio.run(verify(ids))
    EXAMPLES.write_text(json.dumps({
        "about": "Example buttons of the demo page: licensed español → Kʼicheʼ pairs from Mozilla Pontoon that David "
                 "never saw (Firefox Focus from test_niche, newer strings from evals/tm_new.jsonl), translated {ROUNDS} times by David (GPU service in the cloud) and Goliath; every time David "
                 f"had chrF++ >= {MIN_CHRF:g} against the reference and beat Goliath by >= {MIN_MARGIN:g}. Built by `make examples`.",
        "dataset": dataset.name if dataset else None, "david": s.david_model, "goliath": s.gemini_model,
        "min_chrf": MIN_CHRF, "min_margin": MIN_MARGIN,
        "checked": date.today().isoformat(), "examples": kept,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(kept)} de {len(ids)} ejemplos en {EXAMPLES.relative_to(REPO_ROOT)}")
    # With IDS, dropping candidates is the point; re-checking the current examples, every one must pass.
    return 0 if kept and (args.ids or len(kept) == len(ids)) else 1


if __name__ == "__main__":
    sys.exit(main())
