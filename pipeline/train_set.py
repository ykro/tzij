"""Render the training split as chat JSONL for the LoRA fine-tune (make train-data).

Two flavors:
  plain  bare prompt, no retrieval context (`tzij-2026-09`, a dead end: docs/BITACORA.md section 2).
  raft   retrieval-augmented fine-tuning: the prompt carries the top-k dictionary entries and
         example pairs exactly as the duel builds it at inference, so the model learns to *use*
         the context. The sentence being trained on is excluded from its own retrieval, or the
         answer would be sitting in the prompt.

Options for raft: --bt (Gemini back-translated pairs), --bt-both (also K'iche' -> Spanish),
--distilled N (the first N distilled pairs), --only-new SHARE (new data + SHARE of the web pairs as
replay), --es-weight W. The stage David `tzij-2026-10-mix-s7` was trained on
`--raft --bt --bt-both --distilled 2409 --only-new 0.3` (make train-data).

Only `train` sentence pairs, both directions. Religious text is already capped at 30% by the
pipeline; this script checks it again, because a fine-tune is where that bias would stick.
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
OUT_RAFT = REPO / "data" / "train" / "chat-raft.jsonl"
OUT_RAFT_BT = REPO / "data" / "train" / "chat-raft-bt.jsonl"
BACK_TRANSLATED = REPO / "data" / "train" / "back_translated_gemini.jsonl"


def build(dataset_dir: Path, out: Path = OUT, retriever=None, k: int = 6, extra: list[dict] | None = None,
          es_weight: float = 1.0, bt_both: bool = False, distilled: list[dict] | None = None,
          only_new: float = 0.0) -> dict:
    """es_weight > 1 repeats a stable share of the Spanish -> K'iche' examples (1.5 = every one once,
    half of them twice): the direction David is weakest in, and the one the niche measures."""
    records = [json.loads(line) for line in (dataset_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()]
    sentences = [r for r in records if r["kind"] == "sentence" and r["split"] == "train"]
    # Back-translated pairs (Gemini Spanish -> human K'iche') only teach Spanish -> K'iche'.
    back_translated = [r for r in (extra or []) if r["direction"] == "es-quc"]
    if bt_both:  # also K'iche' -> Spanish: human K'iche' in, the teacher's Spanish out (distillation of the strong direction)
        back_translated += [{**r, "id": r["id"].removesuffix("-es-quc") + "-quc-es", "direction": "quc-es",
                             "source_text": r["target_text"], "target_text": r["source_text"]} for r in list(back_translated)]
    distilled = distilled or []
    religious = sum(r["domain"] == "religious" for r in sentences) / max(len(sentences), 1)
    if religious > RELIGIOUS_CAP + 1e-9:
        raise SystemExit(f"religious share {religious:.1%} exceeds the {RELIGIOUS_CAP:.0%} cap")
    rows = sentences + back_translated + distilled
    if only_new:  # continuing a trained adapter: all new data plus a stable share of the web pairs as replay
        import hashlib

        keep = lambda r: int(hashlib.sha1(r["id"].encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < only_new  # noqa: E731
        rows = [r for r in sentences if keep(r)] + [r for r in back_translated if r.get("source_name") == "bloom_mono_quc"
                                                    or r["direction"] == "quc-es"] + distilled
    if es_weight > 1:
        import hashlib

        extra_share = es_weight - 1
        rows += [r for r in rows if r["direction"] == "es-quc"
                 and int(hashlib.sha1(r["id"].encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < extra_share]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            context = ""
            if retriever is not None:
                found = retriever.retrieve(r["source_text"], r["direction"], k,
                                           exclude={r["source_text"], r["target_text"]})
                context = found.as_prompt_context()
            messages = translation_messages(r["source_text"], r["direction"], context)
            messages.append({"role": "assistant", "content": r["target_text"]})
            fh.write(json.dumps({"messages": messages, "id": r["id"], "origin": r.get("origin", "web")},
                                ensure_ascii=False) + "\n")
    total = len(rows)
    return {"examples": total, "web_pairs": len(sentences), "distilled": len(distilled), "bt_both": bt_both, "only_new": only_new,
            "back_translated": len(back_translated), "es_weight": es_weight,
            "es_quc_examples": sum(r["direction"] == "es-quc" for r in rows), "religious_share_of_web": round(religious, 4),
            "out": str(out.relative_to(REPO))}


def raft_retriever(dataset_version: str):
    """The stage index, with embeddings served from the build cache (train sentences are already
    embedded there), so building RAFT data barely touches Ollama."""
    from rag.embedder import CachedEmbedder, OllamaEmbedder
    from rag.retrieve import Retriever
    from tzij_duel.settings import get_settings

    s = get_settings()
    embedder = CachedEmbedder(OllamaEmbedder(), REPO / "rag" / ".cache" / "embeddings.sqlite")
    # Same retrieval settings as David at inference (RAG_MODE / RAG_K / RAG_ORDER / RAG_FUZZY).
    retriever = Retriever(s.rag_index, embedder=embedder, mode=s.rag_mode, order=s.rag_order, fuzzy=s.rag_fuzzy,
                          trigram=s.rag_trigram, select=s.rag_select)
    if retriever.dataset_version != dataset_version:
        raise SystemExit(f"index is from {retriever.dataset_version}, dataset is {dataset_version}: run `make index`")
    return retriever, s.rag_k


if __name__ == "__main__":
    processed = REPO / "data" / "processed"
    version = (processed / "LATEST").read_text().strip()
    if "--raft" in sys.argv:
        retriever, k = raft_retriever(version)
        extra, out = None, OUT_RAFT
        if "--bt" in sys.argv:
            extra = [json.loads(line) for line in BACK_TRANSLATED.read_text(encoding="utf-8").splitlines()]
            out = OUT_RAFT_BT
        es_weight = 1.0
        if "--es-weight" in sys.argv:  # --es-weight 1.5 = Spanish -> K'iche' examples up-weighted
            es_weight = float(sys.argv[sys.argv.index("--es-weight") + 1])
            out = out.with_name(f"{out.stem}-es{round(es_weight * 10)}.jsonl")
        bt_both = "--bt-both" in sys.argv
        if bt_both:
            out = out.with_name(f"{out.stem}-both.jsonl")
        distilled = None
        if "--distilled" in sys.argv:  # --distilled N: the first N distilled pairs (both directions)
            from pipeline.distill import records as distilled_records

            n = int(sys.argv[sys.argv.index("--distilled") + 1])
            # File order: pairs.jsonl only grows at the end, so N = 2409 is always the first batch (mix-s7).
            rows = distilled_records()
            first = list(dict.fromkeys(r["pair_id"] for r in rows))[:n]
            distilled = [r for r in rows if r["pair_id"] in set(first)]
            out = out.with_name(f"{out.stem}-dst{n}.jsonl")
        only_new = 0.0
        if "--only-new" in sys.argv:  # --only-new 0.3: new data + 30% of the web pairs as replay
            only_new = float(sys.argv[sys.argv.index("--only-new") + 1])
            out = out.with_name(f"{out.stem}-new{round(only_new * 100)}.jsonl")
        print({"dataset": version, "k": k, **build(processed / version, out, retriever, k, extra, es_weight,
                                                     bt_both, distilled, only_new)})
    else:
        print({"dataset": version, **build(processed / version)})
