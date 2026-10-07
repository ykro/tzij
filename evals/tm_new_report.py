"""David vs Goliath on the newer Pontoon strings (evals/tm_new.jsonl), by product -> evals/tm_new_results.md.

Same statistics as the niche (evals/niche_report.py): corpus chrF++, paired bootstrap over sentences.
Not pre-registered: the check was added after the niche results, to have more phrases of the same use case.

    uv run python -m evals.run_eval --split tm_new --per-source 0 --run tm-new \\
        --only "tzij-2026-10-mix-s7+hybrid+mbr4,gemini-3.8-flash"
    uv run python -m evals.tm_new_report --run tm-new --david tzij-2026-10-mix-s7+hybrid+mbr4
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from evals.niche_report import HEADER, RESAMPLES, SEED, _row, compare, load_rows, variant_file
from evals.tm_new import OUT as PAIRS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evals" / "tm_new_results.md"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--david", required=True)
    ap.add_argument("--goliath", default="gemini-3.8-flash")
    args = ap.parse_args()
    records = {r["id"]: r for r in map(json.loads, PAIRS.read_text(encoding="utf-8").splitlines())}
    run = ROOT / "evals" / "runs" / args.run
    david, goliath = load_rows(variant_file(run, args.david)), load_rows(variant_file(run, args.goliath))
    ids = sorted(set(david) & set(goliath) & set(records))
    by_product: dict[str, list[str]] = defaultdict(list)
    for i in ids:
        by_product[records[i]["product_name"]].append(i)
    lines = ["# Newer Pontoon strings — more phrases of the translation-memory use case", "",
             f"Run `{run.name}`: {len(ids)} español → Kʼicheʼ pairs from Pontoon's live translation memory that are in no "
             "split of the dataset nor in David's index ([`evals/tm_new.py`](tm_new.py)). Firefox Focus is the held-out "
             "product of the niche; for the other products David has their older strings as translation memory. "
             f"David = `{args.david}`, Goliath = `{args.goliath}`. Paired bootstrap, {RESAMPLES:,} resamples, seed {SEED}. "
             "Not pre-registered (added on 2026-10-07, after the niche results).", "", HEADER]
    c = compare(ids, david, goliath)
    lines.append(_row("all", c))
    print(f"all: {c['david']:.1f} vs {c['goliath']:.1f} = {c['delta']:+.1f} [{c['ci'][0]:+.1f}, {c['ci'][1]:+.1f}]")
    for product, pids in sorted(by_product.items(), key=lambda kv: -len(kv[1])):
        if len(pids) >= 10:
            c = compare(pids, david, goliath)
            lines.append(_row(product, c))
            print(f"{product}: {c['david']:.1f} vs {c['goliath']:.1f} = {c['delta']:+.1f} [{c['ci'][0]:+.1f}, {c['ci'][1]:+.1f}]")
    small = {p: len(v) for p, v in by_product.items() if len(v) < 10}
    if small:
        lines += ["", "Products with fewer than 10 pairs count only in «all»: "
                  + ", ".join(f"{p} ({n})" for p, n in sorted(small.items())) + "."]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
