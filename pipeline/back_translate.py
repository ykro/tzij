"""Back-translation with Goliath (make back-translate): Gemini Spanish for human K'iche'.

"Goliath teaches once in the cloud, David serves forever offline." Gemini is the best
K'iche' -> Spanish translator we have (chrF++ ~40 in that direction), so it translates the
licensed monolingual K'iche' (data/monolingual/quc.jsonl) into Spanish. The resulting pairs are
(synthetic Spanish -> human K'iche'): the K'iche' side, the one David learns to produce, stays
100% human-written, so the no-synthetic-K'iche' rule holds.

Use: training only, Spanish -> K'iche' direction only (the weak one). Never in test, never in the
retrieval index. Every record carries origin=back_translated_gemini, the model, the prompt
version and the seed; the one-time cost is written next to the data.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO), str(REPO / "duel")]

from data.normalize import normalize_spanish  # noqa: E402
from pipeline.clean import SPANISH_FUNCTION_WORDS  # noqa: E402
from tzij_duel.prompts import TEMPLATE, translation_messages  # noqa: E402
from tzij_duel.settings import get_settings  # noqa: E402

IN = REPO / "data" / "monolingual" / "quc.jsonl"
OUT = REPO / "data" / "train" / "back_translated_gemini.jsonl"
META = REPO / "data" / "train" / "back_translated_gemini.meta.json"
SEED = 2027
ORIGIN = "back_translated_gemini"


def acceptable(spa: str, quc: str) -> bool:
    words = [w.strip(".,;:!?¿¡\"()").lower() for w in spa.split()]
    if len(words) < 2:
        return False
    if not any(w in SPANISH_FUNCTION_WORDS or w in {"la", "le", "lo", "a", "y", "o"} for w in words):
        return False  # Gemini answered in K'iche' (or refused)
    ratio = len(spa) / max(len(quc), 1)
    return 1 / 3 <= ratio <= 3


async def main() -> None:
    from google import genai
    from google.genai import types

    s = get_settings()
    client = genai.Client(vertexai=True, project=s.project, location=s.location)
    rows = [json.loads(line) for line in IN.read_text(encoding="utf-8").splitlines()]
    done = {}
    if OUT.exists():
        done = {json.loads(line)["quc_id"]: json.loads(line) for line in OUT.read_text(encoding="utf-8").splitlines()}
    semaphore = asyncio.Semaphore(8)
    usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "rejected": 0}

    async def one(row: dict) -> dict | None:
        messages = translation_messages(row["quc"], "quc-es")
        system, user = messages[0]["content"], messages[-1]["content"]
        config = types.GenerateContentConfig(
            system_instruction=system, temperature=0.2, seed=SEED,
            thinking_config=types.ThinkingConfig(thinking_level=s.gemini_thinking_level) if s.gemini_thinking_level else None,
        )
        async with semaphore:
            for attempt in range(4):
                try:
                    res = await client.aio.models.generate_content(model=s.gemini_model, contents=user, config=config)
                    break
                except Exception:  # transient quota/network: back off and retry
                    await asyncio.sleep(3 * (attempt + 1))
            else:
                return None
        meta = res.usage_metadata
        usage["calls"] += 1
        usage["input_tokens"] += getattr(meta, "prompt_token_count", 0) or 0
        usage["output_tokens"] += (getattr(meta, "candidates_token_count", 0) or 0) + (getattr(meta, "thoughts_token_count", 0) or 0)
        spa = normalize_spanish((res.text or "").strip().splitlines()[0] if (res.text or "").strip() else "")
        if not acceptable(spa, row["quc"]):
            usage["rejected"] += 1
            return None
        return {
            "id": f"bt-{row['id']}-es-quc", "pair_id": f"bt-{row['id']}", "quc_id": row["id"],
            "direction": "es-quc", "source_text": spa, "target_text": row["quc"],
            "kind": "sentence", "split": "train", "status": "clean", "domain": "back_translated",
            "origin": ORIGIN, "model": s.gemini_model, "prompt_version": TEMPLATE.version, "seed": SEED,
            "source_name": row["source_name"], "license": row["license"], "url": row["url"],
        }

    t0 = time.perf_counter()
    todo = [r for r in rows if r["id"] not in done]
    results = await asyncio.gather(*(one(r) for r in todo))
    with OUT.open("a", encoding="utf-8") as fh:
        for rec in results:
            if rec:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    total = len(OUT.read_text(encoding="utf-8").splitlines()) if OUT.exists() else 0
    cost = (usage["input_tokens"] * s.gemini_input_usd_per_m + usage["output_tokens"] * s.gemini_output_usd_per_m) / 1e6
    meta = {"model": s.gemini_model, "prompt_version": TEMPLATE.version, "seed": SEED, "temperature": 0.2,
            "monolingual_sentences": len(rows), "pairs": total, **usage,
            "cost_usd": round(cost, 4), "seconds": round(time.perf_counter() - t0, 1),
            "prices_usd_per_m": [s.gemini_input_usd_per_m, s.gemini_output_usd_per_m]}
    previous = json.loads(META.read_text()) if META.exists() else {}
    meta["cost_usd_total"] = round(previous.get("cost_usd_total", 0) + cost, 4)
    META.write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
