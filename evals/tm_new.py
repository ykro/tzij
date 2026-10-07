"""Pontoon strings that are in no split of the dataset: more phrases for the translation-memory use case.

The dataset's Pontoon pairs come from a Hugging Face snapshot. Pontoon's live K'iche' translation
memory (TMX, same MPL-2.0 strings, labelled by project) has strings the snapshot lacks. Joined with
the Spanish (es-MX) translation memory through the English source string, they give Spanish–K'iche'
pairs written by people that David never saw: not in train, dev, test, test_niche or the retrieval
index (checked on both sides with match_key, so case and punctuation don't hide a duplicate).

  - focus-for-android: more strings of the held-out product (the pre-registered niche, evals/niche.md).
  - Other products (Mozilla Monitor, Firefox Send, Mozilla accounts): new strings of products whose
    older strings are in David's translation memory. Same use case: an organization translating its
    next release with the memory of its previous ones.

This check was added after the niche results (2026-10-07), so it is not pre-registered.

  uv run python -m evals.tm_new                      # -> evals/tm_new.jsonl (tracked)
  uv run python -m evals.run_eval --split tm_new     # David and Goliath on all of them
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "duel")]
from data.normalize import match_key  # noqa: E402

TMX_URL = "https://pontoon.mozilla.org/translation-memory/{locale}.all-projects.tmx"
OUT = ROOT / "evals" / "tm_new.jsonl"
LICENSE = "MPL-2.0 (Mozilla Pontoon localizations)"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
# Same rule as pipeline/sources/pontoon.py: placeholders and markup make a string about software.
MARKUP = re.compile(r"[{}<>%$#]|\\n|&[a-z]+;|\bhttps?://")
SPLITS = ("train", "dev", "test", "test_niche")
PRODUCTS = {
    "focus-for-android": "Firefox Focus",
    "focus-for-android-po": "Firefox Focus",
    "mozilla-monitor-website": "Mozilla Monitor",
    "test-pilot-firefox-send": "Firefox Send",
    "mozilla-accounts": "Mozilla accounts",
}


def load_tmx(path: Path, locale: str) -> dict[str, list[tuple[str, str]]]:
    """English string -> [(translation, project)]."""
    out: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for tu in ET.parse(path).getroot().iter("tu"):
        project = (tu.get("tuid") or "").split(":", 1)[0]
        segs = {tuv.get(XML_LANG): (tuv.findtext("seg") or "").strip() for tuv in tu.findall("tuv")}
        english, text = segs.get("en-US"), segs.get(locale)
        if english and text:
            out[english].append((text, project))
    return out


def known_texts(dataset: Path, index: Path) -> set[str]:
    known: set[str] = set()
    for split in SPLITS:
        for line in (dataset / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            known.update((match_key(r["source_text"]), match_key(r["target_text"])))
    if index.exists():
        db = sqlite3.connect(index)
        for source, target in db.execute("SELECT source_text, target_text FROM entries"):
            known.update((match_key(source), match_key(target)))
    return known


def build(quc_tmx: Path, es_tmx: Path, dataset: Path, index: Path) -> list[dict]:
    kiche, spanish = load_tmx(quc_tmx, "quc"), load_tmx(es_tmx, "es-MX")
    known = known_texts(dataset, index)
    pairs: dict[str, dict] = {}
    for english, translations in kiche.items():
        if english not in spanish or MARKUP.search(english):
            continue
        by_project = {project: text for text, project in spanish[english]}
        for quc, project in translations:
            if project not in PRODUCTS:
                continue
            spa = by_project.get(project) or spanish[english][0][0]
            if MARKUP.search(quc) or MARKUP.search(spa) or len(spa) < 4:
                continue
            if match_key(quc) in known or match_key(spa) in known:
                continue
            key = match_key(spa)
            if key in pairs:  # one K'iche' reference per Spanish string: keep the first
                continue
            pid = "pontoon_tmx-" + hashlib.sha1(f"{spa}\x1f{quc}".encode()).hexdigest()[:12]
            pairs[key] = {"id": f"{pid}-es-quc", "pair_id": pid, "direction": "es-quc", "kind": "sentence", "domain": "software",
                          "status": "human_translation", "source_text": spa, "target_text": quc,
                          "ref": english, "product": project, "product_name": PRODUCTS[project],
                          "source_name": "pontoon_tmx", "url": TMX_URL.format(locale="quc"), "license": LICENSE}
    return sorted(pairs.values(), key=lambda p: (p["product"], p["source_text"]))


def main() -> None:
    from tzij_duel.dataset import latest_dataset
    from tzij_duel.settings import get_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "raw" / "pontoon_tmx")
    args = ap.parse_args()
    s = get_settings()
    dataset = latest_dataset(s.processed_dir)
    if dataset is None:
        raise SystemExit("No dataset: make data-pull")
    args.cache.mkdir(parents=True, exist_ok=True)
    paths = {}
    for locale in ("quc", "es-MX"):
        paths[locale] = args.cache / f"{locale}.all-projects.tmx"
        if not paths[locale].exists():
            urllib.request.urlretrieve(TMX_URL.format(locale=locale), paths[locale])
    pairs = build(paths["quc"], paths["es-MX"], dataset, s.rag_index)
    OUT.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in pairs), encoding="utf-8")
    print(f"{len(pairs)} pairs -> {OUT.relative_to(ROOT)}", Counter(p["product_name"] for p in pairs))


if __name__ == "__main__":
    main()
