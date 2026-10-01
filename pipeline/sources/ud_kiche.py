"""UD K'iche'-IU treebank: example sentences with Spanish translations.

Most sentences are the ALMG vocabulary examples and the UT Austin course; the
treebank authors obtained permission from ALMG and Telma Can Pixabaj and
release the text under CC BY-SA 4.0. Only sentences with a `# text[spa]` line
are parallel.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from data.normalize import orthography_flags
from pipeline.record import Pair
from pipeline.sources.base import TRAIN, Source, download

URL = "https://raw.githubusercontent.com/UniversalDependencies/UD_Kiche-IU/master/quc_iu-ud-test.conllu"
HOME = "https://github.com/UniversalDependencies/UD_Kiche-IU"
LICENSE = "CC-BY-SA-4.0 (UD K'iche'-IU; sentences used with permission of ALMG and T. Can Pixabaj)"

# The treebank mixes several origins; the sent_id prefix tells us which.
DOMAIN_BY_ORIGIN = {
    "almg-examples": "everyday",
    "utexas": "everyday",
    "example": "everyday",
    "biblia": "religious",
    "ley2009-9": "legal",
    "covid": "health",
    "wikipedia": "encyclopedic",
    "cuentos": "narrative",
}


def fetch(raw: Path) -> None:
    download(URL, raw / "quc_iu-ud-test.conllu")


def parse(raw: Path) -> Iterable[Pair]:
    text = (raw / "quc_iu-ud-test.conllu").read_text(encoding="utf-8")
    for block in text.split("\n\n"):
        meta = dict(re.findall(r"^# ([^=]+?) = (.*)$", block, flags=re.M))
        # The treebank spells the key `text[spa]` and, in the stories, `text[spa']`.
        spa = next((v for k, v in meta.items() if k.startswith("text[spa")), None)
        quc = meta.get("text[orig]") or meta.get("text")
        if not spa or not quc:
            continue
        sent_id = meta.get("sent_id", "")
        origin = sent_id.split(":")[0]
        yield Pair(
            quc=quc,
            spa=spa,
            source_name="ud_kiche_iu",
            domain=DOMAIN_BY_ORIGIN.get(origin, "everyday"),
            license=LICENSE,
            url=HOME,
            ref=sent_id,
            raw_flags=orthography_flags(quc),
        )


SOURCE = Source(
    name="ud_kiche_iu",
    title="UD K'iche'-IU treebank (Tyers & Henderson 2021)",
    owner="Francis M. Tyers, Robert Henderson / Universal Dependencies",
    url=HOME,
    license=LICENSE,
    role=TRAIN,
    fetch=fetch,
    parse=parse,
)
