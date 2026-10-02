"""Unicode CLDR: K'iche' emoji names joined with Spanish on the code point.

CLDR's `annotations/quc.xml` gives a short name (`type="tts"`) for each emoji, written by human
vetters; `annotations/es.xml` has the Spanish one. Joined on the code point they are an everyday
vocabulary list (food, animals, objects, jobs, places), close to a terminology list.
License: Unicode License V3 (CLDR data).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from data.normalize import orthography_flags
from pipeline.record import LEXICON, Pair
from pipeline.sources.base import TRAIN, Source, download

BASE = "https://raw.githubusercontent.com/unicode-org/cldr/main/common/annotations/"
HOME = "https://github.com/unicode-org/cldr"
LICENSE = "Unicode-3.0 (Unicode CLDR data)"


def fetch(raw: Path) -> None:
    for lang in ("quc", "es"):
        download(f"{BASE}{lang}.xml", raw / f"{lang}.xml")


def _names(path: Path) -> dict[str, str]:
    out = {}
    for node in ET.parse(path).iter("annotation"):
        if node.get("type") == "tts" and (node.text or "").strip():
            out[node.get("cp")] = node.text.strip()
    return out


def parse(raw: Path) -> Iterable[Pair]:
    quc, spa = _names(raw / "quc.xml"), _names(raw / "es.xml")
    for cp, kiche in quc.items():
        spanish = spa.get(cp)
        if not spanish or kiche.lower() == spanish.lower():
            continue  # untranslated or a loan written the same: no K'iche' to learn
        yield Pair(quc=kiche, spa=spanish, source_name="cldr_quc", domain="dictionary", license=LICENSE,
                   url=HOME, kind=LEXICON, ref=f"emoji {cp}", raw_flags=orthography_flags(kiche))


SOURCE = Source(
    name="cldr_quc",
    title="Unicode CLDR K'iche' emoji names (joined with Spanish on the code point)",
    owner="Unicode CLDR contributors",
    url=HOME,
    license=LICENSE,
    role=TRAIN,
    fetch=fetch,
    parse=parse,
)
