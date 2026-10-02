"""FLORES-Mayas K'iche' glossary (transducens/floresmayas, quc/vocab.json).

Terms collected by the FLORES-Mayas translation task (Transducens, Universitat d'Alacant, with
PLFM translators) with a K'iche' definition for a Spanish term. Pinned to one commit because the
repo is still active. The terms come from FLORES Spanish sentences: never use this source together
with a FLORES-based test set. Only the vocabulary file is read (config/state files hold personal
data). License: Apache-2.0 (repo LICENSE).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from data.normalize import orthography_flags
from pipeline.record import LEXICON, Pair
from pipeline.sources.base import TRAIN, Source, download

COMMIT = "16bc3364ef"  # last change to quc/vocab.json (2026-02-13)
URL = f"https://raw.githubusercontent.com/transducens/floresmayas/{COMMIT}/flores_plus_translation_task/data/quc/vocab.json"
HOME = "https://github.com/transducens/floresmayas"
LICENSE = "Apache-2.0 (transducens/floresmayas)"


def fetch(raw: Path) -> None:
    download(URL, raw / "vocab.json")


def _definitions(value) -> list[str]:
    if isinstance(value, str):
        text = value
    elif isinstance(value, dict):
        text = next((str(v) for k, v in value.items() if k.lower() in ("quc", "definition", "def", "translation", "text") and v), "")
    else:
        text = ""
    return [t.strip() for t in text.split("/") if t.strip()]


def parse(raw: Path) -> Iterable[Pair]:
    vocab = json.loads((raw / "vocab.json").read_text(encoding="utf-8"))
    items = vocab.items() if isinstance(vocab, dict) else ((v.get("es") or v.get("term"), v) for v in vocab)
    for spanish, value in items:
        for kiche in _definitions(value):
            if not spanish or kiche.lower() == str(spanish).lower():
                continue  # loanwords written the same way
            yield Pair(quc=kiche, spa=str(spanish), source_name="floresmayas_quc", domain="dictionary",
                       license=LICENSE, url=HOME, kind=LEXICON, ref=f"vocab {spanish}"[:80],
                       raw_flags=orthography_flags(kiche))


SOURCE = Source(
    name="floresmayas_quc",
    title="FLORES-Mayas K'iche' glossary (quc/vocab.json, pinned commit)",
    owner="Transducens (Universitat d'Alacant) with PLFM translators",
    url=HOME,
    license=LICENSE,
    role=TRAIN,
    fetch=fetch,
    parse=parse,
)
