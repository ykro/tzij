"""Render the training split as chat JSONL for the LoRA fine-tune (make train-data / train-data-raft).

Two flavors:
  plain  bare prompt, no retrieval context (tzij-2026-09).
  raft   retrieval-augmented fine-tuning: the prompt carries the top-k dictionary entries and
         example pairs exactly as the duel builds it at inference, so the model learns to *use*
         the context. The sentence being trained on is excluded from its own retrieval, or the
         answer would be sitting in the prompt.

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
OUT_RAFT = REPO / "data" / "train" / "chat-raft.jsonl"
OUT_RAFT_BT = REPO / "data" / "train" / "chat-raft-bt.jsonl"
BACK_TRANSLATED = REPO / "data" / "train" / "back_translated_gemini.jsonl"
SYNTHETIC_DIR = REPO / "data" / "train" / "synthetic"


def held_out_keys(dataset_dir: Path) -> set[str]:
    from data.normalize import match_key

    keys = set()
    for path in [dataset_dir / "dev.jsonl", dataset_dir / "test.jsonl", *dataset_dir.glob("test_*.jsonl")]:
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            keys |= {match_key(r["source_text"]), match_key(r["target_text"])}
    return keys


def synthetic_records(cap: float, base_examples: int, dataset_dir: Path) -> list[dict]:
    """Synthetic pairs (pipeline/synthetic.py) as train records in both directions, capped so they
    are at most `cap` of the final training examples. Stable selection: by hash of the pair id.
    Pairs anchored on a dictionary entry that is no longer in train (e.g. held out for the niche), or
    repeating any dev/test text, are dropped: synthetic data never reaches an evaluation slice."""
    import hashlib

    from data.normalize import match_key

    train_ids = {json.loads(line)["id"] for line in (dataset_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()}
    held = held_out_keys(dataset_dir)
    pairs = []
    for name in ("dictionary_anchored.jsonl", "ud_slots.jsonl"):
        path = SYNTHETIC_DIR / name
        if path.exists():
            pairs += [p for p in map(json.loads, path.read_text(encoding="utf-8").splitlines())
                      if (p.get("entry_id") is None or p["entry_id"] in train_ids)
                      and match_key(p["es"]) not in held and match_key(p["quc"]) not in held]
    pairs.sort(key=lambda p: hashlib.sha1(p["pair_id"].encode()).hexdigest())
    budget = int(cap / (1 - cap) * base_examples) // 2  # pairs; each pair gives two examples
    out = []
    for p in pairs[:budget]:
        for direction, src, tgt in (("es-quc", p["es"], p["quc"]), ("quc-es", p["quc"], p["es"])):
            out.append({"id": f"{p['pair_id']}-{direction}", "pair_id": p["pair_id"], "direction": direction,
                        "source_text": src, "target_text": tgt, "origin": "synthetic", "method": p["method"]})
    return out


def build(dataset_dir: Path, out: Path = OUT, retriever=None, k: int = 6, extra: list[dict] | None = None,
          synthetic: float = 0.0, es_weight: float = 1.0, bt_both: bool = False, distilled: list[dict] | None = None,
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
    synth = synthetic_records(synthetic, len(sentences) + len(back_translated), dataset_dir) if synthetic else []
    rows = sentences + back_translated + synth + distilled
    if only_new:  # continuing a trained adapter: all new data plus a stable share of the web pairs as replay
        import hashlib

        keep = lambda r: int(hashlib.sha1(r["id"].encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < only_new  # noqa: E731
        rows = [r for r in sentences if keep(r)] + [r for r in back_translated if r.get("source_name") == "bloom_mono_quc"
                                                    or r["direction"] == "quc-es"] + synth + distilled
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
            "back_translated": len(back_translated), "synthetic": len(synth),
            "synthetic_share": round(len(synth) / max(total, 1), 4), "es_weight": es_weight,
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


def hashlib_sha(x: str) -> str:
    import hashlib

    return hashlib.sha1(x.encode()).hexdigest()


if __name__ == "__main__":
    processed = REPO / "data" / "processed"
    version = (processed / "LATEST").read_text().strip()
    if "--raft" in sys.argv:
        retriever, k = raft_retriever(version)
        extra, out = None, OUT_RAFT
        if "--bt" in sys.argv:
            extra = [json.loads(line) for line in BACK_TRANSLATED.read_text(encoding="utf-8").splitlines()]
            out = OUT_RAFT_BT
        synthetic = 0.0
        if "--syn" in sys.argv:  # --syn 0.3 = synthetic pairs capped at 30% of training examples
            synthetic = float(sys.argv[sys.argv.index("--syn") + 1])
            out = out.with_name(f"{out.stem}-syn{round(synthetic * 100)}.jsonl")
        es_weight = 1.0
        if "--es-weight" in sys.argv:  # --es-weight 1.5 = Spanish -> K'iche' examples up-weighted
            es_weight = float(sys.argv[sys.argv.index("--es-weight") + 1])
            out = out.with_name(f"{out.stem}-es{round(es_weight * 10)}.jsonl")
        bt_both = "--bt-both" in sys.argv
        if bt_both:
            out = out.with_name(f"{out.stem}-both.jsonl")
        distilled = None
        if "--distilled" in sys.argv:  # --distilled N: N distilled pairs (both directions), stable order
            from pipeline.distill import records as distilled_records

            n = int(sys.argv[sys.argv.index("--distilled") + 1])
            pairs = sorted({r["pair_id"] for r in distilled_records()}, key=lambda x: hashlib_sha(x))[:n]
            distilled = [r for r in distilled_records() if r["pair_id"] in set(pairs)]
            out = out.with_name(f"{out.stem}-dst{n}.jsonl")
        only_new = 0.0
        if "--only-new" in sys.argv:  # --only-new 0.3: new data + 30% of the web pairs as replay
            only_new = float(sys.argv[sys.argv.index("--only-new") + 1])
            out = out.with_name(f"{out.stem}-new{round(only_new * 100)}.jsonl")
        print({"dataset": version, "k": k, **build(processed / version, out, retriever, k, extra, synthetic, es_weight,
                                                     bt_both, distilled, only_new)})
    else:
        print({"dataset": version, **build(processed / version)})
