"""New Testament in K'iche' (Totonicapán) aligned verse by verse with a Spanish Bible.

Religious text is tagged `religious`: it never enters the test set and is
capped at 30% of the training sentences (see pipeline/split.py). The K'iche'
translation is CC BY 4.0; the Spanish "Biblia Libre para el Mundo" is public
domain and uses modern Spanish (no "he aquí").
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from data.normalize import orthography_flags
from pipeline.record import RELIGIOUS, Pair
from pipeline.sources.base import TRAIN, Source, download

CORPUS = "https://raw.githubusercontent.com/BibleNLP/ebible/main/"
KICHE = "quc-quctt"
SPANISH = "spa-spablm"
HOME = "https://ebible.org/quctt/"
LICENSE = "CC-BY-4.0 (K'iche' NT (c) 2022 Pioneer Bible Translators); Spanish BLM: public domain"


def fetch(raw: Path) -> None:
    download(CORPUS + "metadata/vref.txt", raw / "vref.txt")
    for name in (KICHE, SPANISH):
        download(f"{CORPUS}corpus/{name}.txt", raw / f"{name}.txt")


def parse(raw: Path) -> Iterable[Pair]:
    refs = (raw / "vref.txt").read_text(encoding="utf-8").splitlines()
    kiche = (raw / f"{KICHE}.txt").read_text(encoding="utf-8").splitlines()
    spanish = (raw / f"{SPANISH}.txt").read_text(encoding="utf-8").splitlines()
    for ref, quc, spa in zip(refs, kiche, spanish):
        # "<range>" marks a verse merged into the previous one: not a 1:1 pair.
        if not quc.strip() or not spa.strip() or "<range>" in (quc, spa):
            continue
        yield Pair(
            quc=quc,
            spa=spa,
            source_name="ebible_quctt",
            domain=RELIGIOUS,
            license=LICENSE,
            url=HOME,
            ref=ref,
            raw_flags=orthography_flags(quc),
        )


SOURCE = Source(
    name="ebible_quctt",
    title="Ri K'ak' Testamento pa Tzijob'al K'iche' (Totonicapán) + Biblia Libre para el Mundo",
    owner="Pioneer Bible Translators; eBible.org; BibleNLP eBible corpus",
    url=HOME,
    license=LICENSE,
    role=TRAIN,
    fetch=fetch,
    parse=parse,
)
