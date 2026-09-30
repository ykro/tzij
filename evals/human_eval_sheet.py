"""Build the blind human-evaluation sheet from an eval run (make human-eval-sheet).

50 test items (stable sample), each model's translation as a separate row, rows
shuffled, model names replaced by letters. The key goes to a separate file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import string
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "evals" / "runs"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="", help="eval run id (default: latest)")
    parser.add_argument("--variants", default="", help="comma-separated variant files stems (default: all)")
    parser.add_argument("--items", type=int, default=50)
    args = parser.parse_args()
    run = RUNS / args.run if args.run else max((p for p in RUNS.iterdir() if p.is_dir()), key=lambda p: p.name)
    files = sorted(run.glob("*.jsonl"))
    if args.variants:
        wanted = set(args.variants.split(","))
        files = [f for f in files if f.stem in wanted]
    rows_by_variant = {f.stem: {r["id"]: r for r in map(json.loads, f.read_text().splitlines())} for f in files}
    common = set.intersection(*(set(v) for v in rows_by_variant.values()))
    items = sorted(common, key=lambda i: hashlib.sha1(i.encode()).hexdigest())[: args.items]
    letters = dict(zip(sorted(rows_by_variant), string.ascii_uppercase))
    sources = _test_sources()
    sheet = []
    for item in items:
        for variant, rows in rows_by_variant.items():
            r = rows[item]
            sheet.append({"item": item, "sistema": letters[variant], "direccion": r["direction"],
                          "original": sources.get(item, ""), "traduccion": r["text"] if r["status"] == "ok" else "",
                          "adecuacion_1_5": "", "fluidez_1_5": "", "notas": ""})
    random.Random(2027).shuffle(sheet)
    with (run / "human_eval_sheet.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(sheet[0]))
        writer.writeheader()
        writer.writerows(sheet)
    (run / "human_eval_key.json").write_text(json.dumps({v: k for k, v in letters.items()}, indent=2))
    print(f"{len(sheet)} rows -> {run.relative_to(REPO)}/human_eval_sheet.csv (key in human_eval_key.json)")


def _test_sources() -> dict[str, str]:
    """record id -> source text, from the latest dataset's test split."""
    processed = REPO / "data" / "processed"
    version = (processed / "LATEST").read_text().strip()
    lines = (processed / version / "test.jsonl").read_text(encoding="utf-8").splitlines()
    return {r["id"]: r["source_text"] for r in map(json.loads, lines)}


if __name__ == "__main__":
    main()
