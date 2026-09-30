"""Mozilla Pontoon: Firefox/Mozilla UI strings localized into K'iche'.

Pontoon pairs every locale with English. K'iche' and Spanish are two
independent human translations of the same English string, so joining on the
English source gives a Spanish–K'iche' pair without any machine translation.
Latin American Spanish (es-MX) first, Spain Spanish as fallback.
License: MPL-2.0 (Mozilla localizations).
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Iterable

from data.normalize import orthography_flags
from pipeline.record import Pair, guess_kind
from pipeline.sources.base import TRAIN, Source, download

BASE = "https://huggingface.co/datasets/ayymen/Pontoon-Translations/resolve/main/"
HOME = "https://huggingface.co/datasets/ayymen/Pontoon-Translations"
LICENSE = "MPL-2.0 (Mozilla Pontoon localizations)"
FILES = ("en-quc.tsv", "en-es-MX.tsv", "en-es-ES.tsv")

# Placeholders, markup and escapes make a string about software, not language.
_MARKUP_RE = re.compile(r"[{}<>%$#]|\\n|&[a-z]+;|\bhttps?://")


def fetch(raw: Path) -> None:
    for name in FILES:
        download(BASE + name, raw / name)


def _load(path: Path) -> dict[str, str]:
    csv.field_size_limit(sys.maxsize)
    with path.open(encoding="utf-8", newline="") as fh:
        return {row["source_string"]: row["target_string"] for row in csv.DictReader(fh, delimiter="\t")}


def parse(raw: Path) -> Iterable[Pair]:
    kiche = _load(raw / "en-quc.tsv")
    spanish_mx = _load(raw / "en-es-MX.tsv")
    spanish_es = _load(raw / "en-es-ES.tsv")
    for english, quc in kiche.items():
        spa = spanish_mx.get(english) or spanish_es.get(english)
        if not spa or _MARKUP_RE.search(english) or _MARKUP_RE.search(quc) or _MARKUP_RE.search(spa):
            continue
        yield Pair(
            quc=quc,
            spa=spa,
            source_name="pontoon_mozilla",
            domain="software",
            license=LICENSE,
            url=HOME,
            kind=guess_kind(quc, spa),
            ref=english[:80],
            raw_flags=orthography_flags(quc),
        )


SOURCE = Source(
    name="pontoon_mozilla",
    title="Mozilla Pontoon translations (en-quc joined with en-es-MX/en-es-ES)",
    owner="Mozilla localization community (dataset packaged by ayymen on Hugging Face)",
    url=HOME,
    license=LICENSE,
    role=TRAIN,
    fetch=fetch,
    parse=parse,
)
