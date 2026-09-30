"""Universal Declaration of Human Rights, K'iche' and Spanish (OHCHR via UDHR in Unicode).

Articles align by number; paragraphs inside an article align when both
versions have the same count, otherwise the whole article is one pair.
Terms: OHCHR translations may be reproduced citing the OHCHR site as source.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from data.normalize import orthography_flags
from pipeline.record import Pair
from pipeline.sources.base import TRAIN, Source, download

BASE = "https://raw.githubusercontent.com/eric-muller/udhr/main/data/udhr/"
HOME = "https://github.com/eric-muller/udhr/blob/main/data/udhr/udhr_quc.xml"
OHCHR = "https://www.ohchr.org/en/human-rights/universal-declaration/universal-declaration-human-rights/about-universal-declaration-human-rights-translation-project"
LICENSE = "OHCHR UDHR translation: free reproduction citing OHCHR as source (UDHR in Unicode XML)"
NS = {"u": "http://efele.net/udhr"}


def fetch(raw: Path) -> None:
    for code in ("quc", "spa"):
        download(f"{BASE}udhr_{code}.xml", raw / f"udhr_{code}.xml")


def _text(element) -> str:
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip()


def _articles(path: Path) -> dict[str, list[str]]:
    root = ET.parse(path).getroot()
    units: dict[str, list[str]] = {}
    title = root.find("u:title", NS)
    if title is not None:
        units["title"] = [_text(title)]
    for article in root.findall("u:article", NS):
        units[article.get("number")] = [_text(p) for p in article.iter(f"{{{NS['u']}}}para")]
    return units


def parse(raw: Path) -> Iterable[Pair]:
    quc_units = _articles(raw / "udhr_quc.xml")
    spa_units = _articles(raw / "udhr_spa.xml")
    for number, quc_paras in quc_units.items():
        spa_paras = spa_units.get(number)
        if not spa_paras:
            continue
        if len(quc_paras) != len(spa_paras):
            quc_paras, spa_paras = [" ".join(quc_paras)], [" ".join(spa_paras)]
        for index, (quc, spa) in enumerate(zip(quc_paras, spa_paras)):
            yield Pair(
                quc=quc,
                spa=spa,
                source_name="udhr_ohchr",
                domain="legal",
                license=LICENSE,
                url=HOME,
                ref=f"article {number}.{index + 1}",
                raw_flags=orthography_flags(quc),
            )


SOURCE = Source(
    name="udhr_ohchr",
    title="Universal Declaration of Human Rights (K'iche' Central, Spanish)",
    owner="OHCHR; XML by the UDHR in Unicode project",
    url=HOME,
    license=LICENSE,
    role=TRAIN,
    fetch=fetch,
    parse=parse,
)
