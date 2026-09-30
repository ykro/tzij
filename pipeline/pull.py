"""Download the latest dataset version produced by the Cloud Run Job (make data-pull)."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from pipeline import storage

REPO = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gcs-uri", default=os.environ.get("DATA_BUCKET_URI"))
    parser.add_argument("--version", default=None)
    args = parser.parse_args()
    if not args.gcs_uri:
        raise SystemExit("DATA_BUCKET_URI is not set (see .env.example)")
    uri = args.gcs_uri.rstrip("/")
    version = args.version or storage.read_text(f"{uri}/datasets/LATEST").strip()
    processed = REPO / "data" / "processed"
    count = storage.pull_tree(f"{uri}/datasets/{version}", processed / version)
    (processed / "LATEST").write_text(version + "\n")
    print(f"pulled dataset {version} ({count} files) -> data/processed/{version}")


if __name__ == "__main__":
    main()
