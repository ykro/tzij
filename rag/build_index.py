"""Build the retrieval index from the retrieval-allowed splits (make index).

Only `train` is indexed (pipeline.split.RETRIEVAL_SPLITS): the test set comes
from sources that never enter the index, so retrieval can't "look up the
answer" during evaluation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.normalize import match_key
from pipeline.split import RETRIEVAL_SPLITS
from rag.embedder import CachedEmbedder, Embedder, OllamaEmbedder
from rag.store import create, serialize

REPO = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = REPO / "rag" / "index" / "tzij.sqlite"


def load_records(dataset_dir: Path) -> list[dict]:
    records = []
    for split in RETRIEVAL_SPLITS:
        with (dataset_dir / f"{split}.jsonl").open(encoding="utf-8") as fh:
            records.extend(json.loads(line) for line in fh)
    return records


def build(records: list[dict], embedder: Embedder, index_path: Path, dataset_version: str) -> int:
    if any(r["split"] not in RETRIEVAL_SPLITS for r in records):
        raise ValueError("refusing to index records outside the retrieval-allowed splits")
    vectors = embedder.embed([r["source_text"] for r in records])
    db = create(index_path, dimensions=len(vectors[0]) if vectors else 768)
    db.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("embedding_model", embedder.name),
        ("dataset_version", dataset_version),
        ("splits", ",".join(RETRIEVAL_SPLITS)),
    ])
    for entry_id, (record, vector) in enumerate(zip(records, vectors), start=1):
        db.execute(
            "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (entry_id, record["id"], record["direction"], record["kind"], record["source_text"],
             record["target_text"], record["source_name"], record["domain"], record["license"], record["url"]),
        )
        db.execute(
            "INSERT INTO vec_entries (entry_id, embedding, direction, kind) VALUES (?, ?, ?, ?)",
            (entry_id, serialize(vector), record["direction"], record["kind"]),
        )
        db.execute("INSERT INTO entries_fts (rowid, source_text, direction, kind) VALUES (?, ?, ?, ?)",
                   (entry_id, match_key(record["source_text"]), record["direction"], record["kind"]))
        if record["kind"] == "lexicon":
            db.execute("INSERT INTO glossary VALUES (?, ?, ?)",
                       (record["direction"], match_key(record["source_text"]), entry_id))
    db.commit()
    db.close()
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=REPO / "data" / "processed")
    parser.add_argument("--version", default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_INDEX)
    args = parser.parse_args()
    version = args.version or (args.processed / "LATEST").read_text().strip()
    records = load_records(args.processed / version)
    embedder = CachedEmbedder(OllamaEmbedder(), REPO / "rag" / ".cache" / "embeddings.sqlite")
    count = build(records, embedder, args.out, version)
    print(f"indexed {count} records from dataset {version} with {embedder.name} -> {args.out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
