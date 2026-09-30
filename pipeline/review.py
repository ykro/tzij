"""Export the test set for the native speaker (make review-test).

One row per pair (not per direction): the reviewer reads Spanish and K'iche'
side by side and marks each pair. The verdict column accepts:
  ok       — correct translation, keep
  fix      — keep, using the corrected K'iche' in `corrected_kiche`
  reject   — drop from evaluation (wrong, partial, other language, other dialect…)
The CSV opens in Google Sheets / Excel; UTF-8 with BOM so accents survive.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COLUMNS = ["pair_id", "spanish", "kiche", "source_name", "domain", "url", "ref",
           "verdict", "corrected_kiche", "notes"]


def latest_version(processed: Path) -> str:
    return (processed / "LATEST").read_text().strip()


def export(processed: Path, version: str, out: Path) -> int:
    rows = []
    with (processed / version / "test.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            record = json.loads(line)
            if record["direction"] != "es-quc":
                continue  # both directions share the pair; review it once
            rows.append({
                "pair_id": record["pair_id"],
                "spanish": record["source_text"],
                "kiche": record["target_text"],
                "source_name": record["source_name"],
                "domain": record["domain"],
                "url": record["url"],
                "ref": record["ref"],
                "verdict": "",
                "corrected_kiche": "",
                "notes": "",
            })
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--processed", type=Path, default=REPO / "data" / "processed")
    parser.add_argument("--version", default=None)
    args = parser.parse_args()
    version = args.version or latest_version(args.processed)
    out = REPO / "data" / "review" / f"test_review_{version}.csv"
    count = export(args.processed, version, out)
    print(f"{count} pairs -> {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
