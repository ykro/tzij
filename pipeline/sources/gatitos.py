"""GATITOS (Google, part of SMOL): a ~4,000-entry lexicon translated from English.

Professional translators rendered the same English entries into K'iche' and
into Spanish; joining on the English entry gives a Spanish–K'iche' glossary.
Pivoting through English can pick the wrong sense ("spot" -> "punto" /
"k'olib'al" = place), so these entries are `lexicon`: retrieval context, never
counted as translation examples.
License: CC BY 4.0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from data.normalize import orthography_flags
from pipeline.record import LEXICON, Pair
from pipeline.sources.base import TRAIN, Source, download

BASE = "https://huggingface.co/datasets/google/smol/resolve/main/gatitos/"
HOME = "https://huggingface.co/datasets/google/smol"
LICENSE = "CC-BY-4.0 (Google SMOL/GATITOS)"


def fetch(raw: Path) -> None:
    for name in ("en_quc.jsonl", "en_es.jsonl"):
        download(BASE + name, raw / name)


def _load(path: Path) -> dict[str, list[str]]:
    entries = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        entries[row["src"]] = row["trgs"]
    return entries


def parse(raw: Path) -> Iterable[Pair]:
    kiche = _load(raw / "en_quc.jsonl")
    spanish = _load(raw / "en_es.jsonl")
    for english, quc_options in kiche.items():
        spa_options = spanish.get(english)
        if not spa_options or not quc_options:
            continue
        yield Pair(
            quc=quc_options[0],
            spa=spa_options[0],
            source_name="gatitos",
            domain="dictionary",
            license=LICENSE,
            url=HOME,
            kind=LEXICON,
            ref=f"en: {english}",
            raw_flags=orthography_flags(quc_options[0]),
        )


SOURCE = Source(
    name="gatitos",
    title="GATITOS lexicon, en-quc joined with en-es",
    owner="Google Research (SMOL / GATITOS)",
    url=HOME,
    license=LICENSE,
    role=TRAIN,
    fetch=fetch,
    parse=parse,
)
