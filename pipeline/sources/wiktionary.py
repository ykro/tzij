"""Spanish Wiktionary (Wikcionario): K'iche' translations listed on Spanish entries.

The Kaikki.org extraction of the Spanish edition is 1.4 GB; we stream it and
keep only the lines that mention K'iche' (`"quc"`), so the raw cache is tiny.
License: CC BY-SA 4.0 (Wiktionary).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import httpx

from data.normalize import orthography_flags
from pipeline.record import LEXICON, Pair
from pipeline.sources.base import TRAIN, USER_AGENT, Source

DUMP = "https://kaikki.org/eswiktionary/Espa%C3%B1ol/kaikki.org-dictionary-Espa%C3%B1ol.jsonl"
HOME = "https://es.wiktionary.org/"
LICENSE = "CC-BY-SA-4.0 (Wikcionario, via kaikki.org)"
FILTERED = "espanol_entries_with_quc.jsonl"


def fetch(raw: Path) -> None:
    dest = raw / FILTERED
    if dest.exists():
        return
    tmp = dest.with_suffix(".part")
    with httpx.stream("GET", DUMP, headers={"User-Agent": USER_AGENT}, timeout=600,
                      follow_redirects=True) as response, tmp.open("w", encoding="utf-8") as out:
        response.raise_for_status()
        for line in response.iter_lines():
            if '"quc"' in line:
                out.write(line + "\n")
    tmp.rename(dest)


def parse(raw: Path) -> Iterable[Pair]:
    for line in (raw / FILTERED).read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        for translation in entry.get("translations", []):
            if translation.get("lang_code") != "quc" or not translation.get("word"):
                continue
            yield Pair(
                quc=translation["word"],
                spa=entry["word"],
                source_name="wiktionary_es",
                domain="dictionary",
                license=LICENSE,
                url=f"https://es.wiktionary.org/wiki/{entry['word']}",
                kind=LEXICON,
                ref=f"sense {translation.get('sense_index', '')}",
                raw_flags=orthography_flags(translation["word"]),
            )


SOURCE = Source(
    name="wiktionary_es",
    title="Wikcionario (Spanish Wiktionary) translation tables",
    owner="Wiktionary contributors; extraction by kaikki.org (wiktextract)",
    url=HOME,
    license=LICENSE,
    role=TRAIN,
    fetch=fetch,
    parse=parse,
)
