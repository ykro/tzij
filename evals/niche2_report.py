"""Niche v2 (evals/niche.md, pre-registered): David vs Goliath on a held-out Pontoon product.

    uv run python evals/niche2_report.py --run niche2 --david gemma4:e4b+hybrid+mbr4 [--david ...]

Primary: corpus chrF++ difference with a paired bootstrap (evals/niche_report.compare). Secondary:
WMT-style term exact-match accuracy on the frozen terms (evals/niche2_terms.json): the share of
terms whose K'iche' form appears in the hypothesis, with a bootstrap over the pairs that have terms.
Writes evals/niche2_results.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "duel")]

from data.normalize import match_key, normalize_kiche  # noqa: E402
from evals.niche_report import HEADER, RESAMPLES, SEED, _row, compare, load_rows, variant_file  # noqa: E402

TERMS = ROOT / "evals" / "niche2_terms.json"
OUT = ROOT / "evals" / "niche2_results.md"
EXCLUDED = ("tzij-2026-10-raft-bt-s3",)  # trained on the held-out product: no niche v2 claim


def term_hits(row: dict, terms: list[list[str]]) -> tuple[int, int]:
    hyp = match_key(normalize_kiche(row["text"])) if row["status"] == "ok" else ""
    return sum(quc in hyp for _, quc in terms), len(terms)


def term_accuracy(ids: list[str], rows: dict, terms: dict) -> tuple[float, np.ndarray, np.ndarray]:
    hits = np.array([term_hits(rows[i], terms[i])[0] for i in ids], dtype=float)
    total = np.array([len(terms[i]) for i in ids], dtype=float)
    return hits.sum() / total.sum(), hits, total


def term_compare(ids: list[str], david: dict, goliath: dict, terms: dict) -> dict:
    ids = [i for i in ids if terms.get(i)]
    d, dh, tot = term_accuracy(ids, david, terms)
    g, gh, _ = term_accuracy(ids, goliath, terms)
    rng = np.random.default_rng(SEED)
    deltas = []
    for _ in range(RESAMPLES):
        idx = rng.integers(0, len(ids), len(ids))
        deltas.append(dh[idx].sum() / tot[idx].sum() - gh[idx].sum() / tot[idx].sum())
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    return {"pairs": len(ids), "terms": int(tot.sum()), "david": d, "goliath": g, "delta": d - g, "ci": (lo, hi)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--david", action="append", required=True, help="repeatable")
    ap.add_argument("--goliath", default="gemini-3.8-flash")
    args = ap.parse_args()
    frozen = json.loads(TERMS.read_text(encoding="utf-8"))
    dataset = ROOT / "data" / "processed" / frozen["dataset"]
    records = {r["id"]: r for r in map(json.loads, (dataset / "test_niche2.jsonl").read_text().splitlines())}
    terms = frozen["terms"]
    run = ROOT / "evals" / "runs" / args.run
    goliath = load_rows(variant_file(run, args.goliath))
    lines = ["# Niche v2 results — a translation memory Goliath doesn't have", "",
             f"Run `{run.name}`, dataset `{dataset.name}`: {len(records)} held-out es→quc pairs of the Pontoon product "
             "`focus-for-android`. Definition and protocol pre-registered in [`evals/niche.md`](niche.md) (niche v2). "
             f"Goliath = `{args.goliath}`. Paired bootstrap, {RESAMPLES:,} resamples, seed {SEED}.", "",
             "## chrF++ (primary)", "", HEADER]
    term_lines = ["", "## Term exact-match accuracy (secondary)", "",
                  "| David variant | pairs with terms | terms | David | Goliath | David − Goliath [95% CI] |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name in args.david:
        if any(name.startswith(x) for x in EXCLUDED):
            raise SystemExit(f"{name} was trained on the held-out product: excluded from niche v2 (see evals/niche.md)")
        david = load_rows(variant_file(run, name))
        ids = sorted(set(david) & set(goliath) & set(records))
        c = compare(ids, david, goliath)
        lines.append(_row(f"`{name}`", c))
        t = term_compare(ids, david, goliath, terms)
        term_lines.append(f"| `{name}` | {t['pairs']} | {t['terms']} | {100 * t['david']:.0f}% | {100 * t['goliath']:.0f}% | "
                          f"**{100 * t['delta']:+.0f}** [{100 * t['ci'][0]:+.0f}, {100 * t['ci'][1]:+.0f}] |")
        print(f"{name}: chrF++ {c['david']:.1f} vs {c['goliath']:.1f} = {c['delta']:+.1f} "
              f"[{c['ci'][0]:+.1f}, {c['ci'][1]:+.1f}] -> {c['verdict']}; terms {100 * t['david']:.0f}% vs {100 * t['goliath']:.0f}%")
    OUT.write_text("\n".join(lines + term_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
