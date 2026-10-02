"""The niche (pre-registered in evals/niche.md): one whole Pontoon product held out as a
translation-memory test, Spanish -> K'iche'.

Why: on dev, David beats Gemini where our data works as a translation memory (Pontoon es->quc
48.3 vs 26.2; COERLL es->quc 39.3 vs 30.7) and loses where the text is probably on the open web
(UD, Bloom). The Hugging Face snapshot of Pontoon has no product column, but Pontoon's public
K'iche' translation memory (TMX, same MPL-2.0 strings) labels every string with its project.

    uv run python -m pipeline.niche products   # train pairs per product (no model output involved)
    uv run python -m pipeline.niche build      # new dataset version (LATEST) + frozen terms

Rule, fixed before any test computation:
- Each Pontoon pair gets the set of products whose English string matches its English pivot.
- The held-out product is the one whose count of unambiguous es->quc train pairs is closest to
  150. Those pairs become the niche (`test_niche.jsonl`, es->quc only).
- Every other train record of that product (also strings shared with other products) and every
  train record repeating a held-out Spanish or K'iche' text leaves train, hence the retrieval index
  and fine-tuning. The other products stay as translation memory. Dev is untouched. The 30%
  religious cap is re-applied.

The new version also adds two terminology sources to the translation memory (lexicon rows: index
only, never trained): Unicode CLDR K'iche' names and the FLORES-Mayas glossary, deduplicated
against dev, test and the niche.

Terminology (WMT-style exact match): for each niche pair, the train entries that are a
dictionary/glossary row (kind=lexicon) or come from Pontoon's own `terminology` project, with a
Spanish side of 1-3 words (at least one content word) found in the source and a K'iche' side found
in the reference. Frozen in evals/niche_terms.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "duel")]

from data.normalize import match_key, normalize, normalize_kiche  # noqa: E402

TARGET_PAIRS, SOURCE, PRODUCT = 150, "pontoon_mozilla", "focus-for-android"
TMX_URL = "https://pontoon.mozilla.org/translation-memory/quc.all-projects.tmx"
TMX = ROOT / "data" / "raw" / "pontoon_mozilla" / "quc.all-projects.tmx"
TERMS = ROOT / "evals" / "niche_terms.json"
SPLIT = "test_niche"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
SPANISH_STOP = {
    "a", "al", "con", "de", "del", "el", "ella", "ellos", "en", "es", "esta", "este", "esto", "la", "las",
    "le", "les", "lo", "los", "me", "mi", "mis", "muy", "no", "nos", "o", "para", "pero", "por", "que",
    "se", "si", "sí", "su", "sus", "te", "tu", "tú", "un", "una", "y", "ya", "yo", "hay", "son", "está",
}
_WORD_RE = re.compile(r"[^\W\d_][\w']*", re.UNICODE)


def tokens(text: str, lang: str) -> list[str]:
    """Normalized word tokens ('spa' or 'quc')."""
    key = match_key(normalize(text, lang))
    return [t.strip("'") if lang == "spa" else t.lstrip("'") for t in _WORD_RE.findall(key)]


def _read(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def product_index() -> dict[str, set[str]]:
    """English string -> Pontoon projects that use it (from the public K'iche' TMX)."""
    from pipeline.sources.base import download

    if not TMX.exists():
        download(TMX_URL, TMX)
    index: dict[str, set[str]] = defaultdict(set)
    for tu in ET.parse(TMX).iter("tu"):
        project = tu.get("tuid", "").split(":", 1)[0]
        for tuv in tu.iter("tuv"):
            if tuv.get(XML_LANG) == "en-US":
                english = (tuv.findtext("seg") or "").strip()
                index[english].add(project)
                index[english[:80]].add(project)  # records keep the English pivot cut at 80 chars
    return index


def products_of(record: dict, index: dict[str, set[str]]) -> set[str]:
    return index.get((record.get("ref") or "").strip(), set())


def product_counts(dataset: Path) -> Counter:
    index = product_index()
    return Counter(next(iter(p)) for r in _read(dataset / "train.jsonl")
                   if r["source_name"] == SOURCE and r["direction"] == "es-quc"
                   and len(p := products_of(r, index)) == 1)


def held_out_product(dataset: Path) -> str:
    counts = product_counts(dataset)
    return min(sorted(counts), key=lambda p: abs(counts[p] - TARGET_PAIRS))


def _contains(text_tokens: list[str], phrase: list[str]) -> bool:
    n = len(phrase)
    return n > 0 and any(text_tokens[i:i + n] == phrase for i in range(len(text_tokens) - n + 1))


def terms_for(test: list[dict], train: list[dict], index: dict[str, set[str]]) -> dict[str, list[list[str]]]:
    entries = []
    for r in train:
        if r["direction"] != "es-quc" or r["source_name"] not in ORIGINAL_SOURCES:
            continue
        if not (r["kind"] == "lexicon" or (r["source_name"] == SOURCE and "terminology" in products_of(r, index))):
            continue
        es = tokens(r["source_text"], "spa")
        quc = match_key(normalize_kiche(r["target_text"]))
        content = [w for w in es if w not in SPANISH_STOP and len(w) >= 3]
        if 1 <= len(es) <= 3 and content and quc and not any(ch in r["target_text"] for ch in "()/=[]"):
            entries.append((es, quc))
    out = {}
    for t in test:
        src, ref = tokens(t["source_text"], "spa"), match_key(normalize_kiche(t["target_text"]))
        found: dict[str, str] = {}
        for es, quc in entries:
            if _contains(src, es) and quc in ref:
                found.setdefault(" ".join(es), quc)
        out[t["id"]] = [[k, v] for k, v in sorted(found.items())]
    return out


# Terms were frozen (pre-registration) from the sources of dataset 20261002-022500 only.
ORIGINAL_SOURCES = {"bloom_kiche", "bouquet", "ud_kiche_iu", "coerll_kiche", "udhr_ohchr", "pontoon_mozilla",
                    "ebible_quctt", "gatitos", "panlex", "wiktionary_es"}


def recap_religious(train: list[dict]) -> tuple[list[dict], int]:
    """Removing secular pairs pushes the religious share over the 30% cap: drop religious sentence
    pairs again with the pipeline's own rule (pipeline/split.py: stable hash order)."""
    from pipeline.split import RELIGIOUS_CAP

    sentences = [r for r in train if r["kind"] == "sentence" and r["direction"] == "es-quc"]
    secular = sum(r["domain"] != "religious" for r in sentences)
    budget = math.floor(secular * RELIGIOUS_CAP / (1 - RELIGIOUS_CAP))
    religious = sorted({r["pair_id"] for r in sentences if r["domain"] == "religious"},
                       key=lambda pid: hashlib.sha1(pid.encode()).hexdigest())
    drop = set(religious[budget:])
    return [r for r in train if r["pair_id"] not in drop], len(drop)


def terminology_records(held_keys: set[str], train_keys: set[tuple[str, str]]) -> tuple[list[dict], dict]:
    """CLDR + FLORES-Mayas as lexicon train records (translation memory only)."""
    from pipeline.clean import clean
    from pipeline.domains import tag_domain
    from pipeline.sources import cldr, floresmayas

    out, stats = [], {}
    for source in (cldr.SOURCE, floresmayas.SOURCE):
        raw = source.raw_dir(ROOT / "data" / "raw")
        source.fetch(raw)
        pairs = [p.normalized() for p in source.parse(raw)]
        pairs, dropped = clean(pairs)
        kept = 0
        for p in map(tag_domain, pairs):
            keys = (match_key(p.spa), match_key(p.quc))
            if keys[0] in held_keys or keys[1] in held_keys or keys in train_keys:
                continue
            train_keys.add(keys)
            out += p.to_records("train", "clean")
            kept += 1
        stats[source.name] = {"parsed": len(pairs) + len(dropped), "kept_pairs": kept}
    return out, stats


def build(dataset: Path) -> dict:
    index = product_index()
    product = held_out_product(dataset)
    assert product == PRODUCT, f"rule picked {product}, pre-registered {PRODUCT}"
    train = _read(dataset / "train.jsonl")
    pontoon = [r for r in train if r["source_name"] == SOURCE]
    held = [r for r in pontoon if r["direction"] == "es-quc" and products_of(r, index) == {product}]
    touching = {r["pair_id"] for r in pontoon if product in products_of(r, index)}
    keys = {match_key(r["source_text"]) for r in held} | {match_key(r["target_text"]) for r in held}
    kept, dup = [], 0
    for r in train:
        if r["pair_id"] in touching:
            continue
        if match_key(r["source_text"]) in keys or match_key(r["target_text"]) in keys:
            dup += 1
            continue
        kept.append(r)
    kept, religious_dropped = recap_religious(kept)
    terms = terms_for([{**r} for r in held], kept, index)  # frozen definition: original sources only

    held_keys = set(keys)
    for split in ("dev", "test"):
        for r in _read(dataset / f"{split}.jsonl"):
            held_keys |= {match_key(r["source_text"]), match_key(r["target_text"])}
    train_keys = {(match_key(r["source_text"]), match_key(r["target_text"])) for r in kept if r["direction"] == "es-quc"}
    terminology, term_stats = terminology_records(held_keys, train_keys)

    version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = dataset.parent / version
    shutil.copytree(dataset, out)
    for stale in out.glob("test_niche*.jsonl"):
        stale.unlink()
    rows = kept + terminology
    (out / "train.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    niche = [{**r, "split": SPLIT, "status": "auto_validated", "product": product} for r in held]
    (out / f"{SPLIT}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in niche), encoding="utf-8")
    manifest = json.loads((out / "manifest.json").read_text())
    summary = {"product": product, "product_counts": dict(product_counts(dataset)), "niche_pairs_es_quc": len(niche),
               "train_records_removed": len(train) - len(kept), "duplicates_removed": dup,
               "religious_pairs_dropped_for_cap": religious_dropped, "tmx": TMX_URL,
               "terminology_added": term_stats}
    manifest.update(version=version, derived_from=dataset.name, niche=summary)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    refresh_manifest(out)
    (dataset.parent / "LATEST").write_text(version + "\n")
    frozen = {"dataset": version, "definition": "evals/niche.md",
              "terms": {r["id"]: terms[r["id"]] for r in held}}
    TERMS.write_text(json.dumps(frozen, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {**summary, "version": version, "kinds": dict(Counter(r["kind"] for r in niche)),
            "pairs_with_terms": sum(bool(v) for v in terms.values()), "terms": sum(len(v) for v in terms.values())}


def refresh_manifest(out: Path) -> dict:
    """Counts in the manifest follow the files (the model card on stage reads them)."""
    from pipeline.sources import cldr, floresmayas

    manifest = json.loads((out / "manifest.json").read_text())
    by_source: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_split: dict[str, int] = {}
    for split in ("train", "dev", "test", "test_niche"):
        path = out / f"{split}.jsonl"
        if not path.exists():
            continue
        rows = [r for r in _read(path) if r["direction"] == "es-quc"]
        by_split[split] = len(rows)
        for r in rows:
            by_source[r["source_name"]][split] += 1
    known = {s["name"] for s in manifest["sources"]}
    for src in (cldr.SOURCE, floresmayas.SOURCE):
        if src.name not in known:
            manifest["sources"].append({"name": src.name, "title": src.title, "owner": src.owner, "url": src.url,
                                        "license": src.license, "role": src.role})
    manifest["pairs_by_source"] = {k: dict(v) for k, v in by_source.items()}
    manifest["pairs_by_split"] = by_split
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


def niche_dataset(processed: Path) -> Path | None:
    """The latest dataset version that has a niche slice."""
    pointer = processed / "LATEST"
    if pointer.exists():
        path = processed / pointer.read_text().strip()
        if (path / f"{SPLIT}.jsonl").exists():
            return path
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["products", "build"])
    ap.add_argument("--dataset", type=Path, default=ROOT / "data" / "processed" / "20261002-022500")
    args = ap.parse_args()
    if args.command == "products":
        for p, n in product_counts(args.dataset).most_common():
            print(n, p)
        print("held out:", held_out_product(args.dataset))
    else:
        print(json.dumps(build(args.dataset), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
