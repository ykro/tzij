"""Niche v2 (pre-registered in evals/niche.md#niche-v2): one whole Pontoon product held out as a
translation-memory test, Spanish -> K'iche'.

Why: on dev, David beats Gemini where our data works as a translation memory (Pontoon es->quc
48.3 vs 26.2; COERLL es->quc 39.3 vs 30.7) and loses where the text is probably on the open web
(UD, Bloom). The Hugging Face snapshot of Pontoon has no product column, but Pontoon's public
K'iche' translation memory (TMX, same MPL-2.0 strings) labels every string with its project.

    uv run python -m pipeline.niche2 products   # train pairs per product (no model output involved)
    uv run python -m pipeline.niche2 build      # dataset <base>-niche2 + frozen terms

Rule, fixed before any test computation:
- Each Pontoon pair gets the set of products whose English string matches its English pivot.
- The held-out product is the one whose count of unambiguous es->quc train pairs is closest to
  150. Those pairs become the test slice (`test_niche2.jsonl`, es->quc only).
- Every other train record of that product (also strings shared with other products) and every
  train record repeating a held-out Spanish or K'iche' text leaves train, hence the retrieval index
  and fine-tuning. The other products stay as translation memory. Dev is untouched.

Terminology (WMT-style exact match): for each test pair, the entries left in train that are a
dictionary/glossary row (kind=lexicon) or come from Pontoon's own `terminology` project, with a
Spanish side of 1-3 content words found in the source and a K'iche' side found in the reference.
Accuracy = share of those terms whose K'iche' form appears in the hypothesis.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "duel")]

from data.normalize import match_key, normalize_kiche  # noqa: E402
from pipeline.niche import tokens  # noqa: E402
from pipeline.sources.base import download  # noqa: E402
from tzij_duel.constraints import SPANISH_STOP  # noqa: E402

TARGET_PAIRS, SOURCE = 150, "pontoon_mozilla"
TMX_URL = "https://pontoon.mozilla.org/translation-memory/quc.all-projects.tmx"
TMX = ROOT / "data" / "raw" / "pontoon_mozilla" / "quc.all-projects.tmx"
TERMS = ROOT / "evals" / "niche2_terms.json"
SPLIT = "test_niche2"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _read(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def product_index() -> dict[str, set[str]]:
    """English string -> Pontoon projects that use it (from the public K'iche' TMX)."""
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
        if r["direction"] != "es-quc":
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


def build(dataset: Path) -> dict:
    index = product_index()
    product = held_out_product(dataset)
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
    out = dataset.parent / f"{dataset.name}-niche2"
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(dataset, out)
    (out / "train.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
    test = [{**r, "split": SPLIT, "status": "auto_validated", "product": product} for r in held]
    (out / f"{SPLIT}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in test), encoding="utf-8")
    manifest = json.loads((out / "manifest.json").read_text())
    summary = {"product": product, "product_counts": dict(product_counts(dataset)), "test_pairs_es_quc": len(test),
               "train_records_removed": len(train) - len(kept), "duplicates_removed": dup, "tmx": TMX_URL}
    manifest.update(version=out.name, derived_from=dataset.name, niche2=summary)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    terms = terms_for(test, kept, index)
    TERMS.write_text(json.dumps({"dataset": out.name, "definition": "evals/niche.md (niche v2)", "terms": terms},
                                indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {**summary, "version": out.name, "kinds": dict(Counter(r["kind"] for r in test)),
            "pairs_with_terms": sum(bool(v) for v in terms.values()), "terms": sum(len(v) for v in terms.values())}


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
