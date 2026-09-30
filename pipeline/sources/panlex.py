"""PanLex: expressions linked by shared meaning across thousands of lexicons.

We keep only K'iche' expressions whose meaning has a Spanish (spa-000)
expression attached directly — no chains through a third language.
License: CC0 1.0.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from data.normalize import orthography_flags
from pipeline.record import LEXICON, Pair
from pipeline.sources.base import TRAIN, Source, download

BASE = "https://huggingface.co/datasets/cointegrated/panlex-meanings/resolve/main/data/"
HOME = "https://panlex.org/"
LICENSE = "CC0-1.0 (PanLex)"


def fetch(raw: Path) -> None:
    for code in ("quc", "spa"):
        download(f"{BASE}{code}.tsv", raw / f"{code}.tsv")


def parse(raw: Path) -> Iterable[Pair]:
    kiche_by_meaning: dict[str, list[str]] = defaultdict(list)
    with (raw / "quc.tsv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            kiche_by_meaning[row["meaning"]].append(row["txt"])
    seen: set[tuple[str, str]] = set()
    with (raw / "spa.tsv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["langvar_uid"] != "spa-000" or row["meaning"] not in kiche_by_meaning:
                continue
            for quc in kiche_by_meaning[row["meaning"]]:
                if (quc, row["txt"]) in seen:
                    continue
                seen.add((quc, row["txt"]))
                yield Pair(
                    quc=quc,
                    spa=row["txt"],
                    source_name="panlex",
                    domain="dictionary",
                    license=LICENSE,
                    url=HOME,
                    kind=LEXICON,
                    ref=f"meaning {row['meaning']}",
                    raw_flags=orthography_flags(quc),
                )


SOURCE = Source(
    name="panlex",
    title="PanLex meanings (quc joined with spa-000)",
    owner="PanLex / The Long Now Foundation (packaged by cointegrated on Hugging Face)",
    url=HOME,
    license=LICENSE,
    role=TRAIN,
    fetch=fetch,
    parse=parse,
)
