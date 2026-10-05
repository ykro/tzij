"""Render data/DATASHEET.md from a manifest. Numbers are never typed by hand.

When the split files sit next to the manifest, every count is recomputed from them
(pipeline.manifest.recount), so a version derived by pipeline/niche.py renders its own numbers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE_SPLITS = ("train", "dev", "test")

ORTHOGRAPHY_NOTES = """\
- **Glottal stop.** Sources write it with `'`, `’`, `‘`, `ʼ`, `ꞌ` (saltillo), `ˈ`, `´`
  and even `7`. `data/normalize.py` maps all of them to the ASCII apostrophe `'`
  before anything is indexed, trained or scored. Without this, `k'ak'`, `kʼakʼ` and
  `kꞌakꞌ` would be three different words for the tokenizer, the embeddings and chrF++.
- **Lax vowels.** The official ALMG alphabet distinguishes `ä ë ï ö ü`, but most modern
  K'iche' writing (the Totonicapán New Testament, MINEDUC books, the COERLL course) uses
  five vowels. We fold `ä→a` etc. so both spellings meet. Only the ALMG dictionary
  examples in UD K'iche'-IU mark lax vowels (`lax_vowels_marked` below).
- **Older spellings.** `c`/`qu` for /k/ (`qui biˈ` for `kib'i'`) is pre-1987 orthography.
  It shows up mostly in proper names and Spanish loans in our sources (`c_for_k` below);
  sources written entirely in older spelling (e.g. the SIL Bible in the
  Christodouloupoulos corpus) were not used.
- **Dialects.** K'iche' is written differently in Nahualá, Cantel, Totonicapán and
  Santa Cruz del Quiché (`le`/`ri` articles, `xuqe'`/`xuquje'`). We do not force one
  variety; the test set is reviewed by a native speaker who can mark dialect issues.
- **Spanish.** Accents and `¿ ¡` are kept; only whitespace, quotes and dashes are unified.
"""


def _table(rows: list[list], header: list[str]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _split_rows(counts: dict[str, dict], splits: tuple[str, ...]) -> list[list]:
    rows = []
    for name, per_split in counts.items():
        values = [per_split.get(s, 0) for s in splits]
        rows.append([f"`{name}`", *values, sum(values)])
    totals = [sum(counts[n].get(s, 0) for n in counts) for s in splits]
    rows.append(["**total**", *totals, sum(totals)])
    return rows


def render_datasheet(m: dict) -> str:
    ft = m["finetune"]
    test = m["test"]
    by_split = m["pairs_by_split"]
    per_direction = m["records_by_split_and_direction"]
    sources = {s["name"]: s for s in m["sources"]}
    splits = BASE_SPLITS + tuple(x for x in by_split if x not in BASE_SPLITS)  # e.g. test_niche

    source_rows = []
    for name, per_split in m["pairs_by_source"].items():
        s = sources.get(name, {})
        values = [per_split.get(x, 0) for x in splits]
        source_rows.append([f"`{name}`", s.get("role", ""), *values, s.get("license", "")])

    dropped_rows = [
        [f"`{name}`", sources.get(name, {}).get("parsed_pairs", ""),
         ", ".join(f"{reason} {n}" for reason, n in sorted(reasons.items(), key=lambda x: -x[1]))]
        for name, reasons in m["dropped"].items()
    ]
    flag_rows = [
        [f"`{s['name']}`", s["parsed_pairs"],
         ", ".join(f"{flag} {n}" for flag, n in sorted(s["orthography_flags"].items(), key=lambda x: -x[1])) or "-"]
        for s in m["sources"] if "parsed_pairs" in s
    ]
    direction_rows = [[split, per_direction[split]["es-quc"], per_direction[split]["quc-es"]]
                      for split in splits if split in per_direction]
    niche = m.get("niche")
    niche_section = ""
    if niche:
        added = ", ".join(f"`{k}` {v['kept_pairs']}" for k, v in niche.get("terminology_added", {}).items())
        niche_section = f"""
## Niche (specialty round)

Derived from **`{m.get('derived_from', '?')}`** by `pipeline/niche.py` (pre-registered in
`evals/niche.md`). The Pontoon product `{niche['product']}` is held out as `test_niche`:
{niche['niche_pairs_es_quc']} es→quc pairs. Every other train record of that product and every train
record repeating a held-out text leaves train ({niche['train_records_removed']} records), so it is
in neither the retrieval index nor fine-tuning; the religious cap is re-applied
({niche['religious_pairs_dropped_for_cap']} pairs dropped). Terminology added to the translation
memory as lexicon rows (pairs): {added or 'none'}.
"""
    threshold_line = (
        f"**Yes.** {ft['sentence_pairs_outside_test']} clean sentence pairs outside the test set "
        f"(threshold {ft['threshold_sentence_pairs']}), of which {ft['non_religious_sentence_pairs_outside_test']} are "
        f"non-religious (religious capped at {int(m['religious_cap'] * 100)}% of train). Fine-tuning is allowed; "
        f"`make eval` decides whether it actually beats retrieval."
        if ft["threshold_met"]
        else f"**No.** {ft['sentence_pairs_outside_test']} clean sentence pairs outside the test set "
        f"({ft['non_religious_sentence_pairs_outside_test']} non-religious), "
        f"below the {ft['threshold_sentence_pairs']} threshold: David runs on retrieval only "
        f"(Gemma base + retrieval index). Dictionary entries don't count toward the threshold."
    )

    validated_by_source = ", ".join(f"{k} {v}" for k, v in test.get("auto_validated_by_source", {}).items()) or "—"
    rejected_reasons = ", ".join(f"{k} {v}" for k, v in test.get("auto_rejected", {}).items()) or "none"
    criteria_lines = "\n".join(f"  - {c}" for c in test.get("criteria", []))

    return f"""# Datasheet — Tzij Spanish ↔ K'iche' data

Generated by `pipeline/datasheet.py` from `manifest.json` of dataset version
**`{m['version']}`** (created {m['created_at']}, code `{m['git_sha']}`). Do not edit
by hand: run `make datasheet` (or `make data`).

## Motivation and composition

Tzij translates between Spanish and K'iche' (`quc`) with a small offline Gemma model.
Every record comes from a licensed web source listed in `data/SOURCES.md`
(`origin=web`, with `url` and `license` on each record). There is **no synthetic
K'iche'** in the dataset, the retrieval index, dev or test: frontier models don't master the
language and would teach David their mistakes. Gemini-made training data (back-translation and
distillation) lives outside the dataset, only in fine-tuning files; see `MODEL_CARD.md`.

Each pair produces two records, one per direction (`es-quc`, `quc-es`), so
per-direction counts equal pair counts. `kind=sentence` records are translation
examples; `kind=lexicon` records are dictionary/glossary entries used as retrieval
context.

## Fine-tuning threshold

{threshold_line}

## Counts by split and direction (records)

{_table(direction_rows, ["split", "es-quc", "quc-es"])}

Pairs: {", ".join(f"{x} {by_split.get(x, 0)}" for x in splits)}.

## Counts by source (pairs)

{_table(source_rows, ["source", "role", *splits, "license"])}

## Counts by domain (pairs)

{_table(_split_rows(m['pairs_by_domain'], splits), ["domain", *splits, "total"])}

## Counts by kind (pairs)

{_table(_split_rows(m['pairs_by_kind'], splits), ["kind", *splits, "total"])}

## Religious share

Religious text is excluded from test and capped at {int(m['religious_cap'] * 100)}% of
training sentences. Share of religious sentences in train: **{m['religious_share_of_train_sentences'] * 100:.1f}%**.
Verses above the cap are dropped (`religious_cap` below), chosen by a stable hash so
the selection is reproducible and spread across the New Testament.

## Test set

- Source-level split: test sources are never used for training or retrieval, and any
  train/retrieval pair that repeats a test sentence is removed (`leaks_test_sentence`).
- {test['pairs_per_direction']} pairs per direction ({test['sentence_pairs']} of them sentences).
  **{test.get('auto_validated_pairs', '—')} are `auto_validated`** and used by `make eval` and the evaluation
  rounds ({validated_by_source}); the rest are `auto_rejected` ({rejected_reasons}).
- Validation is automatic, with no human step (`pipeline/validate_test.py`). Criteria:
{criteria_lines}
- Optional: a native speaker can review with `make review-test` / `make apply-review`
  (upgrades pairs to `validated`); the demo never waits for it.
- Target: ≥ 200 pairs per direction.
{niche_section}
## What was dropped and why (pairs)

{_table(dropped_rows, ["source", "parsed", "dropped (reason count)"])}

## Orthography

{ORTHOGRAPHY_NOTES}
Raw orthography markers per source (pairs whose raw K'iche' text shows the marker):

{_table(flag_rows, ["source", "parsed", "markers"])}

## Known limitations

- Pontoon (software strings) and GATITOS (dictionary) pair Spanish and K'iche' through a
  shared English original: both are human translations, but senses can diverge.
- Bloom books are page-aligned, not sentence-aligned; some Spanish pages paraphrase.
  The native-speaker review is the final filter for the test set.
- Dialect variation is not normalized (see Orthography).
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the datasheet from a manifest.json")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/DATASHEET.md"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if (args.manifest.parent / "train.jsonl").exists():
        from pipeline.manifest import recount

        manifest = recount(manifest, args.manifest.parent)
    args.out.write_text(render_datasheet(manifest))


if __name__ == "__main__":
    main()
