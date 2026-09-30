"""The data pipeline, end to end: download -> clean -> normalize -> dedupe -> tag -> split.

Local:      uv run python -m pipeline.run                 (make data)
Cloud Run:  python -m pipeline.run --gcs-uri gs://BUCKET  (make data-cloud)

Outputs a versioned directory with train/dev/test JSONL (one record per pair
and direction), a manifest with every count, and the datasheet.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pipeline import storage
from pipeline.clean import clean
from pipeline.datasheet import render_datasheet
from pipeline.domains import tag_domain
from pipeline.manifest import build_manifest
from pipeline.record import Pair
from pipeline.sources import SOURCES, TEST
from pipeline.split import TEST as TEST_SPLIT
from pipeline.split import dedupe, split_by_source

REPO = Path(__file__).resolve().parent.parent
TEST_STATUS = "pending_native_review"  # until a native speaker validates it
CLEAN_STATUS = "clean"


def _git_sha() -> str:
    sha = os.environ.get("GIT_SHA")
    if sha:
        return sha
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run(*, raw_root: Path, out_root: Path, version: str, gcs_uri: str | None,
        only: set[str] | None, skip_fetch: bool, datasheet_path: Path | None) -> dict:
    sources = [s for s in SOURCES if not only or s.name in only]

    if gcs_uri:
        pulled = storage.pull_tree(f"{gcs_uri}/raw", raw_root)
        print(f"raw cache: pulled {pulled} files from {gcs_uri}/raw")

    if not skip_fetch:
        try:
            for source in sources:
                print(f"fetch  {source.name}", flush=True)
                source.fetch(source.raw_dir(raw_root))
        finally:
            # Keep whatever was downloaded, even if a later source failed.
            if gcs_uri:
                pushed = storage.push_tree(raw_root, f"{gcs_uri}/raw")
                print(f"raw cache: pushed {pushed} new files")

    pairs: list[Pair] = []
    parsed: dict[str, int] = {}
    raw_flags: dict[str, Counter] = defaultdict(Counter)
    for source in sources:
        source_pairs = list(source.parse(source.raw_dir(raw_root)))
        parsed[source.name] = len(source_pairs)
        for pair in source_pairs:
            raw_flags[source.name].update(pair.raw_flags)
        print(f"parse  {source.name}: {len(source_pairs)} pairs")
        pairs.extend(source_pairs)

    # Normalize first so cleaning and dedupe compare canonical spellings.
    pairs = [p.normalized() for p in pairs]
    pairs, dropped = clean(pairs)
    pairs = [tag_domain(p) for p in pairs]
    pairs, duplicates = dedupe(pairs)
    dropped += duplicates

    result = split_by_source(pairs, test_sources={s.name for s in sources if s.role == TEST})

    out_dir = out_root / version
    out_dir.mkdir(parents=True, exist_ok=True)
    for split_name, split_pairs in result.by_split().items():
        status = TEST_STATUS if split_name == TEST_SPLIT else CLEAN_STATUS
        with (out_dir / f"{split_name}.jsonl").open("w", encoding="utf-8") as fh:
            for pair in split_pairs:
                for record in pair.to_records(split_name, status):
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    manifest = build_manifest(version=version, sources=sources, parsed=parsed, raw_flags=raw_flags,
                              dropped=dropped, result=result, git_sha=_git_sha())
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    datasheet = render_datasheet(manifest)
    (out_dir / "DATASHEET.md").write_text(datasheet)
    if datasheet_path:
        datasheet_path.write_text(datasheet)
    (out_root / "LATEST").write_text(version + "\n")

    if gcs_uri:
        storage.push_tree(out_dir, f"{gcs_uri}/datasets/{version}", only_new=False)
        storage.write_text(f"{gcs_uri}/datasets/LATEST", version + "\n")
        print(f"uploaded {gcs_uri}/datasets/{version}/")

    print(json.dumps({k: manifest[k] for k in ("version", "pairs_by_split", "finetune",
                                               "religious_share_of_train_sentences")}, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-dir", type=Path, default=REPO / "data" / "raw")
    parser.add_argument("--out-dir", type=Path, default=REPO / "data" / "processed")
    parser.add_argument("--version", default=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--gcs-uri", default=os.environ.get("DATA_BUCKET_URI"),
                        help="gs://bucket to sync the raw cache and upload outputs")
    parser.add_argument("--sources", default="", help="comma-separated subset of source names")
    parser.add_argument("--skip-fetch", action="store_true", help="parse only what is already in the raw cache")
    parser.add_argument("--datasheet", type=Path, default=REPO / "data" / "DATASHEET.md",
                        help="where to write the datasheet ('' to skip)")
    args = parser.parse_args()
    run(
        raw_root=args.raw_dir,
        out_root=args.out_dir,
        version=args.version,
        gcs_uri=args.gcs_uri.rstrip("/") if args.gcs_uri else None,
        only={s for s in args.sources.split(",") if s} or None,
        skip_fetch=args.skip_fetch,
        datasheet_path=args.datasheet if str(args.datasheet) else None,
    )


if __name__ == "__main__":
    main()
