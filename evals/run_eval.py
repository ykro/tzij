"""make eval: every available variant on the test set -> evals/report.md.

Variants (see duel/tzij_duel/variants.py): each Gemma in BASE_MODEL_TAGS (and
FINETUNED_MODEL_TAGS once they exist) with and without retrieval, Gemini alone
and Gemini with the same retrieval. The best David variant goes on stage; the
report shows all of them, including the ones that lose.

Honest-eval rules this script follows:
  * test pairs come only from test sources (never in the retrieval index);
  * chrF++ is corpus-level, on normalized text (same apostrophe for everyone);
  * local models run one request at a time, like on stage, so latency is real;
  * predictions are cached per run so an interrupted eval resumes.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO), str(REPO / "duel")]

from duel_core import Connectivity, corpus_chrf_pp, summarize  # noqa: E402
from rag.retrieve import Retriever  # noqa: E402
from tzij_duel.deck import latest_dataset  # noqa: E402
from tzij_duel.settings import Settings, get_settings  # noqa: E402
from tzij_duel.variants import Variant, eval_variants, translate  # noqa: E402

RUNS = REPO / "evals" / "runs"
REPORT = REPO / "evals" / "report.md"
DIRECTION_LABEL = {"es-quc": "español → K'iche'", "quc-es": "K'iche' → español"}


def load_test(dataset: Path, limit: int | None, per_source: int | None = None, split: str = "test") -> list[dict]:
    """Test sentences; optionally a stable sample of `per_source` pairs per source and direction.

    Sampling by a hash of the pair id keeps the same pairs in every run, so reports
    from different days compare the same sentences.
    """
    records = [json.loads(line) for line in (dataset / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()]
    # auto_rejected pairs failed pipeline/validate_test.py; they never count.
    # The niche keeps its short UI terms (kind=lexicon) too: the slice is the whole held-out product.
    records = [r for r in records if (r["kind"] == "sentence" or split == "test_niche")
               and r["status"] not in ("rejected", "auto_rejected")]
    if per_source:
        groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for r in records:
            groups[(r["source_name"], r["direction"])].append(r)
        records = [r for group in groups.values()
                   for r in sorted(group, key=lambda r: hashlib.sha1(r["pair_id"].encode()).hexdigest())[:per_source]]
    if limit:
        by_direction: dict[str, list[dict]] = defaultdict(list)
        for r in records:
            if len(by_direction[r["direction"]]) < limit:
                by_direction[r["direction"]].append(r)
        records = [r for rs in by_direction.values() for r in rs]
    return records


async def run_variant(variant: Variant, records: list[dict], out: Path, *, retriever, online: bool,
                      concurrency: int, k: int) -> list[dict]:
    done = {}
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[row["id"]] = row
    todo = [r for r in records if r["id"] not in done]
    semaphore = asyncio.Semaphore(concurrency)

    async def one(record: dict) -> dict:
        async with semaphore:
            result = await translate(variant, record["source_text"], record["direction"], retriever=retriever,
                                     online=online, reference=record["target_text"], k=k)
        row = {"id": record["id"], "direction": record["direction"], "source_name": record["source_name"],
               "reference": record["target_text"], **result.to_dict()}
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    started = time.perf_counter()
    for i in range(0, len(todo), 50):
        rows = await asyncio.gather(*(one(r) for r in todo[i:i + 50]))
        for row in rows:
            done[row["id"]] = row
        print(f"  {variant.name}: {min(i + 50, len(todo))}/{len(todo)} ({time.perf_counter() - started:.0f}s)", flush=True)
    return [done[r["id"]] for r in records if r["id"] in done]


def score(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["status"] == "ok"]
    # Failed or offline answers count as empty translations: a model that can't answer scores 0.
    chrf = corpus_chrf_pp([r["text"] if r["status"] == "ok" else "" for r in rows], [r["reference"] for r in rows])
    latency = summarize([r["latency_ms"] for r in ok])
    return {
        "n": len(rows), "ok": len(ok), "chrf": round(chrf, 1),
        "p50_ms": latency["p50"], "p95_ms": latency["p95"],
        "cost_usd": sum(r.get("cost_usd") or 0 for r in rows),
        "statuses": {s: sum(1 for r in rows if r["status"] == s) for s in ("ok", "offline", "error")},
    }


LENGTH_BUCKETS = (("short phrase (1–4 words)", 1, 4), ("sentence (5–12 words)", 5, 12), ("long sentence (13+ words)", 13, 10_000))


def _bucket(words: int) -> str:
    return next(name for name, lo, hi in LENGTH_BUCKETS if lo <= words <= hi)


def breakdown(results: dict[str, list[dict]], ranking: list, records: list[dict]) -> list[str]:
    """Where David wins or comes close, not just the headline average."""
    by_id = {r["id"]: r for r in records}
    local = [(v, sc) for v, sc in ranking if not v.requires_network]
    cloud = [(v, sc) for v, sc in ranking if v.requires_network and not v.uses_rag]
    if not local or not cloud:
        return []
    david_v, _ = max(local, key=lambda x: x[1]["chrf"])
    goliath_v, _ = cloud[0]
    names = [v.name for v, _ in ranking]
    lines = ["## Where the gap is (chrF++ by slice)", "",
             "Same test pairs, sliced. `David` = best local variant "
             f"(`{david_v.name}`), `Goliath` = `{goliath_v.name}`.", ""]

    def table(title: str, key) -> None:
        groups = sorted({key(by_id[r["id"]]) for r in results[david_v.name] if r["id"] in by_id})
        lines.extend([f"### {title}", "", "| variant | " + " | ".join(groups) + " |",
                      "| --- | " + " | ".join("---:" for _ in groups) + " |"])
        for name in names:
            rows = results[name]
            cells = []
            for g in groups:
                sub = [r for r in rows if r["id"] in by_id and key(by_id[r["id"]]) == g]
                cells.append(f"{score(sub)['chrf']:.1f} (n={len(sub)})" if sub else "—")
            lines.append(f"| `{name}` | " + " | ".join(cells) + " |")
        lines.append("")

    table("By length of the source text", lambda r: _bucket(len(r["source_text"].split())))
    table("By direction and test source", lambda r: f"{DIRECTION_LABEL[r['direction']]} · {r['source_name']}")
    table("By domain", lambda r: r["domain"])

    # Head to head, sentence by sentence.
    d = {r["id"]: r for r in results[david_v.name]}
    g = {r["id"]: r for r in results[goliath_v.name]}
    common = [i for i in d if i in g and d[i]["status"] == "ok" and g[i]["status"] == "ok"]
    wins = sum(d[i]["chrf"] > g[i]["chrf"] for i in common)
    close = sum(abs(d[i]["chrf"] - g[i]["chrf"]) <= 5 for i in common)
    lines += ["### Head to head, sentence by sentence", "",
              f"- David scores higher than Goliath on **{wins} of {len(common)}** sentences "
              f"({wins / max(len(common), 1):.0%}) and within 5 chrF++ points on {close} ({close / max(len(common), 1):.0%}).",
              f"- Cost of these {len(results[goliath_v.name])} translations: David $0, Goliath "
              f"${sum(r.get('cost_usd') or 0 for r in results[goliath_v.name]):.2f}.",
              "- With no internet, Goliath produces nothing (shown as offline on stage); David's numbers above "
              "are unchanged because everything it uses — model, index, embeddings — is on the laptop.", ""]
    return lines


def ablation(results: dict[str, list[dict]], records: list[dict]) -> list[str]:
    """What each step bought: ABLATION_STEPS="label=variant;label=variant;..." in order."""
    spec = os.environ.get("ABLATION_STEPS", "")
    steps = [s.split("=", 1) for s in spec.split(";") if "=" in s]
    steps = [(label.strip(), name.strip()) for label, name in steps if name.strip() in results]
    if len(steps) < 2:
        return []
    lines = ["## Ablation: what each step bought (test set)", "",
             "| step | variant | es → quc | quc → es | both | Δ both | p50 |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    previous = None
    for label, name in steps:
        rows = results[name]
        both = score(rows)
        es = score([r for r in rows if r["direction"] == "es-quc"])["chrf"]
        quc = score([r for r in rows if r["direction"] == "quc-es"])["chrf"]
        delta = "—" if previous is None else f"{both['chrf'] - previous:+.1f}"
        lines.append(f"| {label} | `{name}` | {es:.1f} | {quc:.1f} | **{both['chrf']:.1f}** | {delta} | {_fmt_ms(both['p50_ms'])} |")
        previous = both["chrf"]
    return lines + [""]


def _fmt_ms(ms: float | None) -> str:
    return "—" if ms is None else f"{ms / 1000:.2f} s"


def _fmt_cost_per_1k(cost: float, n: int) -> str:
    return "$0 (local)" if cost == 0 else f"${cost / max(n, 1) * 1000:.3f}"


def render(results: dict[str, dict], variants: list[Variant], records: list[dict], s: Settings,
           dataset_version: str, run_id: str, notes: list[str]) -> str:
    directions = ("es-quc", "quc-es")
    sources = sorted({r["source_name"] for r in records})
    lines = [
        "# Evaluation report — Tzij",
        "",
        f"Generated by `evals/run_eval.py` (run `{run_id}`) on dataset `{dataset_version}`.",
        f"Test set: {len(records)} sentence records ({', '.join(f'{sum(r['direction'] == d for r in records)} {DIRECTION_LABEL[d]}' for d in directions)}) "
        f"from held-out sources ({', '.join(f'`{x}`' for x in sources)}), never in the retrieval index.",
        "Status of references: " + ", ".join(f"{sum(r['status'] == s for r in records)} {s}" for s in sorted({r['status'] for r in records}))
        + (" — references validated automatically (`pipeline/validate_test.py`); a native-speaker review is optional."
           if any(r["status"] == "auto_validated" for r in records) else "."),
        "",
    ]
    if s.mock_ai:
        lines += ["> **MOCK_AI=1**: mock models, numbers are not meaningful.", ""]
    for note in notes:
        lines += [f"> {note}", ""]

    lines += ["## chrF++ (corpus, higher is better)", "",
              "| variant | where it runs | retrieval | " + " | ".join(DIRECTION_LABEL[d] for d in directions) + " | both | p50 latency | p95 latency | cost per 1,000 translations |",
              "| --- | --- | --- | " + " | ".join("---:" for _ in directions) + " | ---: | ---: | ---: | ---: |"]
    ranking = []
    for v in variants:
        rows = results.get(v.name)
        if not rows:
            continue
        overall = score(rows)
        per_dir = {d: score([r for r in rows if r["direction"] == d]) for d in directions}
        ranking.append((v, overall))
        lines.append(
            f"| `{v.name}` | {'cloud' if v.requires_network else 'laptop'} | {'yes' if v.uses_rag else 'no'} | "
            + " | ".join(f"{per_dir[d]['chrf']:.1f}" for d in directions)
            + f" | **{overall['chrf']:.1f}** | {_fmt_ms(overall['p50_ms'])} | {_fmt_ms(overall['p95_ms'])} | "
            f"{_fmt_cost_per_1k(overall['cost_usd'], overall['n'])} |"
        )
    lines.append("")

    local = [(v, sc) for v, sc in ranking if not v.requires_network]
    cloud = [(v, sc) for v, sc in ranking if v.requires_network]
    if local:
        best_v, best = max(local, key=lambda x: x[1]["chrf"])
        lines += ["## Which David goes on stage", "",
                  f"Best local variant: **`{best_v.name}`** (chrF++ {best['chrf']:.1f}). "
                  f"Set `LOCAL_MODEL_TAG={best_v.model}` — the duel always adds retrieval to David, so pick a "
                  "`+rag` variant unless the table shows retrieval hurting."]
        if cloud:
            goliath = next(((v, sc) for v, sc in cloud if not v.uses_rag), cloud[0])
            delta = best["chrf"] - goliath[1]["chrf"]
            lines.append(f"Against Goliath (`{goliath[0].name}`, {goliath[1]['chrf']:.1f}): "
                         f"**{'+' if delta >= 0 else ''}{delta:.1f} chrF++** for David.")
        finetuned = [(v, sc) for v, sc in local if v.model in s.finetuned_model_tags]
        base = {v.name: sc for v, sc in local if v.model in s.base_model_tags}
        if finetuned and base:
            lines += ["", "**Fine-tuning, honestly** (same retrieval and decoding, fine-tuned vs base):"]
            for v, sc in finetuned:
                suffix = v.name[len(v.model):]
                matches = [(n, b) for n, b in base.items() if n.endswith(suffix) and n[: len(n) - len(suffix)] in s.base_model_tags]
                if not matches:
                    continue
                name, b = max(matches, key=lambda x: x[1]["chrf"])
                delta = sc["chrf"] - b["chrf"]
                lines.append(f"- `{v.name}` {sc['chrf']:.1f} vs `{name}` {b['chrf']:.1f} (**{'+' if delta >= 0 else ''}{delta:.1f}**)")
        lines.append("")

    lines += ["## By test source (chrF++, both directions)", "",
              "| variant | " + " | ".join(f"`{x}`" for x in sources) + " |",
              "| --- | " + " | ".join("---:" for _ in sources) + " |"]
    for v, _ in ranking:
        rows = results[v.name]
        lines.append(f"| `{v.name}` | " + " | ".join(
            f"{score([r for r in rows if r['source_name'] == x])['chrf']:.1f}" for x in sources) + " |")
    lines.append("")

    lines += ablation(results, records)
    lines += breakdown(results, ranking, records)

    lines += ["## Failures", "", "| variant | ok | offline | error |", "| --- | ---: | ---: | ---: |"]
    for v, sc in ranking:
        st = sc["statuses"]
        lines.append(f"| `{v.name}` | {st['ok']} | {st['offline']} | {st['error']} |")
    lines += ["", "Failed or offline answers count as empty translations in chrF++.", ""]

    lines += ["## Method", "",
              "- chrF++ = sacrebleu CHRF with word_order=2, corpus level, on text normalized by `data/normalize.py` "
              "(hypotheses and references alike).",
              "- Same instructions for every model (`duel/tzij_duel/prompts.py`, version `tzij-translate-v1`); "
              f"`+rag` variants also get the top {s.rag_k} examples and glossary entries from the retrieval index "
              "(train split only).",
              "- Latency: wall clock per translation, retrieval included; local models one request at a time.",
              f"- Cost: Gemini tokens × list price (input ${s.gemini_input_usd_per_m}/M, output ${s.gemini_output_usd_per_m}/M, "
              "thinking billed as output). Local inference counted as $0.",
              "- Fine-tuned variants appear here automatically when `FINETUNED_MODEL_TAGS` lists them.",
              ""]

    fertility = REPO / "evals" / "fertility.md"
    if fertility.exists():
        body = fertility.read_text(encoding="utf-8").split("\n", 1)[1]
        lines += ["## Token fertility", "", body.replace("\n## ", "\n### ")]
    return "\n".join(lines).rstrip() + "\n"


async def main_async(args) -> None:
    s = get_settings()
    dataset = latest_dataset(s.processed_dir)
    if dataset is None:
        raise SystemExit("No dataset: run `make data` (or `make data-pull`).")
    records = load_test(dataset, args.limit, args.per_source or None, args.split)
    variants = [v for v in eval_variants(s) if not args.only or v.name in args.only.split(",")]
    retrievers: dict[str, Retriever] = {}
    if any(v.uses_rag for v in variants):
        if not s.rag_index.exists():
            raise SystemExit("No retrieval index: run `make index`.")
        # "vector" = the original baseline; "hybrid" = BM25 + vectors + fuzzy glossary, tuned on dev.
        retrievers["vector"] = Retriever(s.rag_index)
        retrievers["hybrid"] = Retriever(s.rag_index, mode="hybrid", order=s.rag_order, fuzzy=s.rag_fuzzy,
                                         trigram=s.rag_trigram, select=s.rag_select)
        retriever = retrievers["vector"]
        if retriever.dataset_version != dataset.name:
            # Retrieval from another dataset version could contain sentences that are now in test.
            raise SystemExit(f"Retrieval index is from dataset {retriever.dataset_version}, "
                             f"but data/processed/LATEST is {dataset.name}: run `make index` first.")
    online = s.mock_ai or await Connectivity(force_offline=s.force_offline).is_online()
    notes = [] if online else ["No internet during this run: Gemini variants are reported as offline."]
    run_id = args.run or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for v in variants:
        print(f"variant {v.name}")
        concurrency = args.cloud_concurrency if v.requires_network else 1
        out = run_dir / f"{v.name.replace('/', '_').replace(':', '_')}.jsonl"
        results[v.name] = await run_variant(v, records, out, retriever=retrievers.get(v.retrieval), online=online,
                                            concurrency=concurrency, k=v.k)
    # The report covers every variant with results in this run, so new variants (e.g. a
    # fine-tuned tag) can be added later with --run <id> --only <names> without rerunning all.
    all_variants = eval_variants(s)
    ids = {r["id"] for r in records}
    for v in all_variants:
        out = run_dir / f"{v.name.replace('/', '_').replace(':', '_')}.jsonl"
        if v.name not in results and out.exists():
            rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
            results[v.name] = [r for r in rows if r["id"] in ids]
    report = render(results, all_variants, records, s, dataset.name, run_id, notes)
    out_path = Path(args.out) if args.out else REPORT
    out_path.write_text(report, encoding="utf-8")
    print(f"-> {out_path.relative_to(REPO) if out_path.is_relative_to(REPO) else out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="max records per direction (quick runs)")
    parser.add_argument("--per-source", type=int, default=int(os.environ.get("EVAL_PER_SOURCE", "150")),
                        help="stable sample of pairs per test source and direction (0 = all)")
    parser.add_argument("--only", default="", help="comma-separated variant names")
    parser.add_argument("--run", default="", help="resume an existing run id")
    parser.add_argument("--cloud-concurrency", type=int, default=8)
    parser.add_argument("--out", default="")
    parser.add_argument("--split", choices=["test", "dev", "test_niche"], default="test",
                        help="dev = tuning and stop decisions between data rounds; test = final numbers only")
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
