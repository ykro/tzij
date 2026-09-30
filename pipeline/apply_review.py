"""Fold the native speaker's verdicts back into the test set.

ok -> status=validated; fix -> K'iche' replaced by the correction, validated;
reject -> removed. Pairs without a verdict stay pending_native_review and
`make eval` reports them separately.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from data.normalize import normalize_kiche
from pipeline.review import REPO, latest_version

VALIDATED = "validated"


def apply(test_path: Path, review_csv: Path) -> Counter:
    with review_csv.open(encoding="utf-8-sig", newline="") as fh:
        verdicts = {row["pair_id"]: row for row in csv.DictReader(fh)}
    tally: Counter = Counter()
    kept = []
    for line in test_path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        row = verdicts.get(record["pair_id"])
        verdict = (row or {}).get("verdict", "").strip().lower()
        if verdict == "reject":
            tally["rejected"] += 1
            continue
        if verdict == "fix" and row["corrected_kiche"].strip():
            fixed = normalize_kiche(row["corrected_kiche"])
            key = "target_text" if record["direction"] == "es-quc" else "source_text"
            record[key] = fixed
            record["status"] = VALIDATED
            tally["fixed"] += 1
        elif verdict == "ok":
            record["status"] = VALIDATED
            tally["validated"] += 1
        else:
            tally["pending"] += 1
        kept.append(json.dumps(record, ensure_ascii=False))
    test_path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    # Two records per pair: report pairs.
    return Counter({k: v // 2 for k, v in tally.items()})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--processed", type=Path, default=REPO / "data" / "processed")
    parser.add_argument("--version", default=None)
    args = parser.parse_args()
    version = args.version or latest_version(args.processed)
    print(dict(apply(args.processed / version / "test.jsonl", args.csv)))


if __name__ == "__main__":
    main()
