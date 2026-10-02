"""David vs Goliath on the niche (pre-registered in evals/niche.md): a held-out Pontoon product,
Spanish -> K'iche', where David has a translation memory Goliath doesn't.

Reads the predictions an eval run already produced (evals/runs/<run>/<variant>.jsonl):

    uv run python evals/niche_report.py --run niche --david gemma4:e4b+hybrid+mbr4

Primary: corpus chrF++ difference, paired bootstrap over sentences (2,000 resamples, seed 2027).
Secondary: WMT-style term exact-match accuracy on the frozen terms (evals/niche_terms.json), with a
bootstrap over the pairs that have terms. Writes evals/niche_results.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sacrebleu.metrics import CHRF

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "duel")]

from data.normalize import match_key, normalize_kiche  # noqa: E402


CHRF_PP = CHRF(word_order=2)
RESAMPLES, SEED = 2000, 2027
OUT = ROOT / "evals" / "niche_results.md"


def variant_file(run: Path, name: str) -> Path:
    return run / (name.replace(":", "_").replace("/", "_") + ".jsonl")


def load_rows(path: Path) -> dict[str, dict]:
    return {r["id"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())}


def _stats(rows: list[dict]) -> np.ndarray:
    hyps = [r["text"] if r["status"] == "ok" else "" for r in rows]
    return np.array(CHRF_PP._extract_corpus_statistics(hyps, [[r["reference"] for r in rows]]), dtype=float)


def _score(stats: np.ndarray) -> float:
    return float(CHRF_PP._compute_score_from_stats(stats.sum(0).tolist()).score)


def compare(ids: list[str], david: dict[str, dict], goliath: dict[str, dict], seed: int = SEED) -> dict:
    """Corpus chrF++ for each side, difference and win rate, with paired bootstrap 95% CIs."""
    d_rows, g_rows = [david[i] for i in ids], [goliath[i] for i in ids]
    d_st, g_st = _stats(d_rows), _stats(g_rows)
    d_sent = np.array([r["chrf"] if r["status"] == "ok" else 0.0 for r in d_rows])
    g_sent = np.array([r["chrf"] if r["status"] == "ok" else 0.0 for r in g_rows])
    wins, ties = d_sent > g_sent, d_sent == g_sent
    rng = np.random.default_rng(seed)
    deltas, rates = [], []
    n = len(ids)
    for _ in range(RESAMPLES):
        idx = rng.integers(0, n, n)
        deltas.append(_score(d_st[idx]) - _score(g_st[idx]))
        rates.append(wins[idx].mean())
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    rlo, rhi = np.percentile(rates, [2.5, 97.5])
    d, g = _score(d_st), _score(g_st)
    verdict = "David" if lo > 0 else "Goliath" if hi < 0 else "empate"
    return {"n": n, "david": d, "goliath": g, "delta": d - g, "ci": (float(lo), float(hi)),
            "win_rate": float(wins.mean()), "win_ci": (float(rlo), float(rhi)), "ties": int(ties.sum()),
            "verdict": verdict}


def _row(label: str, c: dict) -> str:
    return (f"| {label} | {c['n']} | {c['david']:.1f} | {c['goliath']:.1f} | **{c['delta']:+.1f}** "
            f"[{c['ci'][0]:+.1f}, {c['ci'][1]:+.1f}] | {100 * c['win_rate']:.0f}% "
            f"[{100 * c['win_ci'][0]:.0f}, {100 * c['win_ci'][1]:.0f}] | {c['ties']} | {c['verdict']} |")


HEADER = ("| slice | n | David chrF++ | Goliath chrF++ | David − Goliath [95% CI] | David wins [95% CI] | ties | verdict |\n"
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")


TERMS = ROOT / "evals" / "niche_terms.json"
EXCLUDED = ("tzij-2026-10-raft-bt-s3",)  # trained on the held-out product: no niche claim


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
    records = {r["id"]: r for r in map(json.loads, (dataset / "test_niche.jsonl").read_text().splitlines())}
    terms = frozen["terms"]
    run = ROOT / "evals" / "runs" / args.run
    goliath = load_rows(variant_file(run, args.goliath))
    lines = ["# Niche results — a translation memory Goliath doesn't have", "",
             f"Run `{run.name}`, dataset `{dataset.name}`: {len(records)} held-out es→quc pairs of the Pontoon product "
             "`focus-for-android` (Firefox Focus). Definition and protocol pre-registered in [`evals/niche.md`](niche.md). "
             f"Goliath = `{args.goliath}`. Paired bootstrap, {RESAMPLES:,} resamples, seed {SEED}.", "",
             "## chrF++ (primary)", "", HEADER]
    term_lines = ["", "## Term exact-match accuracy (secondary)", "",
                  "| David variant | pairs with terms | terms | David | Goliath | David − Goliath [95% CI] |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name in args.david:
        if any(name.startswith(x) for x in EXCLUDED):
            raise SystemExit(f"{name} was trained on the held-out product: excluded from the niche (see evals/niche.md)")
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
