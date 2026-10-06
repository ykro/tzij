"""Tune retrieval on the DEV split only (make tune-retrieval) -> evals/tuning.md.

The test set is for final numbers; choosing k, ordering or the retrieval mode by looking at test
scores would leak. Dev is a 5% sample of the training sources' sentences, held out of the index
and of fine-tuning.

Configs compared with the stage model (LOCAL_MODEL_TAG): baseline vector retrieval, hybrid
(BM25 + vectors, RRF), fuzzy glossary on/off, k in {4, 6, 8}, best example first vs last.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO), str(REPO / "duel")]

from duel_core import Price, corpus_chrf_pp, summarize  # noqa: E402
from rag.retrieve import Retriever  # noqa: E402
from tzij_duel.dataset import latest_dataset  # noqa: E402
from tzij_duel.settings import get_settings  # noqa: E402
from tzij_duel.variants import Variant, ollama_client, translate  # noqa: E402

CONFIGS = [  # (name, mode, k, order, fuzzy)
    ("vector k6 (baseline)", "vector", 6, "best_first", False),
    ("hybrid k6", "hybrid", 6, "best_first", False),
    ("hybrid k6 + fuzzy", "hybrid", 6, "best_first", True),
    ("hybrid k6 + fuzzy, best last", "hybrid", 6, "best_last", True),
    ("hybrid k4 + fuzzy", "hybrid", 4, "best_first", True),
    ("hybrid k8 + fuzzy", "hybrid", 8, "best_first", True),
]
CACHE = REPO / "evals" / "runs" / "tuning"


async def main() -> None:
    s = get_settings()
    dataset = latest_dataset(s.processed_dir)
    records = [json.loads(line) for line in (dataset / "dev.jsonl").read_text(encoding="utf-8").splitlines()]
    records = [r for r in records if r["kind"] == "sentence"]
    client = ollama_client(s)
    CACHE.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, mode, k, order, fuzzy in CONFIGS:
        retriever = Retriever(s.rag_index, mode=mode, order=order, fuzzy=fuzzy)
        variant = Variant(name, name, client, s.david_model, Price.free(), True, False, retrieval=mode, k=k)
        out = CACHE / (name.replace(" ", "_").replace(",", "").replace("(", "").replace(")", "").replace("+", "plus") + ".jsonl")
        done = {json.loads(line)["id"]: json.loads(line) for line in out.read_text().splitlines()} if out.exists() else {}
        t0 = time.perf_counter()
        for r in records:
            if r["id"] in done:
                continue
            res = await translate(variant, r["source_text"], r["direction"], retriever=retriever, online=False,
                                  reference=r["target_text"], k=k)
            row = {"id": r["id"], "direction": r["direction"], "reference": r["target_text"], **res.to_dict()}
            done[r["id"]] = row
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        got = [done[r["id"]] for r in records]
        chrf = corpus_chrf_pp([g["text"] if g["status"] == "ok" else "" for g in got], [g["reference"] for g in got])
        by_dir = {d: corpus_chrf_pp([g["text"] if g["status"] == "ok" else "" for g in got if g["direction"] == d],
                                    [g["reference"] for g in got if g["direction"] == d]) for d in ("es-quc", "quc-es")}
        p50 = summarize([g["latency_ms"] for g in got if g["status"] == "ok"])["p50"]
        rows.append((name, mode, k, order, fuzzy, chrf, by_dir, p50))
        print(f"{name}: chrF++ {chrf:.1f} ({time.perf_counter() - t0:.0f}s)", flush=True)
    best = max(rows, key=lambda r: r[5])
    lines = [
        "# Retrieval tuning (dev split)", "",
        f"Model `{s.david_model}`, dataset `{dataset.name}`, {len(records)} dev sentence records "
        "(5% of the training sources, never indexed, never used for fine-tuning). Test is not used here.", "",
        "| config | es → quc | quc → es | both | p50 |", "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, *_rest, chrf, by_dir, p50 in rows:
        lines.append(f"| {name} | {by_dir['es-quc']:.1f} | {by_dir['quc-es']:.1f} | **{chrf:.1f}** | {p50 / 1000:.2f} s |")
    lines += ["", f"**Chosen:** {best[0]} → `RAG_MODE={best[1]}`, `RAG_K={best[2]}`, `RAG_ORDER={best[3]}`, "
              f"`RAG_FUZZY={int(best[4])}` (set in `.env.example`; the `+hybrid` eval variants and David on stage use it).", ""]
    (REPO / "evals" / "tuning.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
