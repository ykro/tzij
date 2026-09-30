"""Render the training split as chat JSONL for the LoRA fine-tune (make train-data).

Only `train` sentence pairs, both directions, rendered with the exact prompt the
duel uses (without retrieval context: the fine-tuned model has to carry the
language itself; the FT+RAG variant adds context at inference). Religious
text is already capped at 30% by the pipeline; this script checks it again,
because a fine-tune is where that bias would stick.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO), str(REPO / "duel")]

from pipeline.split import RELIGIOUS_CAP  # noqa: E402
from tzij_duel.prompts import translation_messages  # noqa: E402

OUT = REPO / "data" / "train" / "chat.jsonl"


def build(dataset_dir: Path, out: Path = OUT) -> dict:
    records = [json.loads(line) for line in (dataset_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()]
    sentences = [r for r in records if r["kind"] == "sentence" and r["split"] == "train"]
    religious = sum(r["domain"] == "religious" for r in sentences) / max(len(sentences), 1)
    if religious > RELIGIOUS_CAP + 1e-9:
        raise SystemExit(f"religious share {religious:.1%} exceeds the {RELIGIOUS_CAP:.0%} cap")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for r in sentences:
            messages = translation_messages(r["source_text"], r["direction"])
            messages.append({"role": "assistant", "content": r["target_text"]})
            fh.write(json.dumps({"messages": messages, "id": r["id"]}, ensure_ascii=False) + "\n")
    return {"examples": len(sentences), "religious_share": round(religious, 4), "out": str(out.relative_to(REPO))}


if __name__ == "__main__":
    processed = REPO / "data" / "processed"
    version = (processed / "LATEST").read_text().strip()
    print({"dataset": version, **build(processed / version)})
