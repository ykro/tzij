"""COERLL "Chqeta'maj le qach'ab'al K'iche'!" — UT Austin online course.

The Spanish version of the 46 lessons lays vocabulary and example phrases out
as two-column tables (K'iche' | Spanish). We read the lessons through the
site's public WordPress REST API instead of scraping rendered pages.
License: CC BY 4.0 (stated on the course site).
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Iterable

from data.normalize import orthography_flags
from pipeline.record import Pair, guess_kind
from pipeline.sources.base import TRAIN, Source, download

API = "https://tzij.coerll.utexas.edu/wp-json/wp/v2/posts?per_page=100&page={page}"
HOME = "https://tzij.coerll.utexas.edu/"
LICENSE = "CC-BY-4.0 (COERLL, UT Austin)"

# Interlinear glosses ("x-im-b'ek COMP-1sing-ir") are linguistics, not translation.
_GLOSS_RE = re.compile(r"\b(COMP|INC|PERF|ABS|ERG|sing|pl)\b|\b\w+-\w+-\w+\b|^\d+\.\s")
_POS_TAG_RE = re.compile(r"\s*\((?:v\w{0,3}|adj|adv|sust|s|n|prep|pos|part)\.?\)")


def fetch(raw: Path) -> None:
    for page in range(1, 10):
        try:
            download(API.format(page=page), raw / f"posts_{page}.json")
        except RuntimeError:  # WordPress answers 400 past the last page
            if page == 1:
                raise
            break


def _cell_text(cell_html: str) -> str:
    cell_html = re.sub(r"<audio.*?</audio>", " ", cell_html, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", cell_html))
    return re.sub(r"\s+", " ", text).strip()


def _posts(raw: Path) -> list[dict]:
    posts: list[dict] = []
    for path in sorted(raw.glob("posts_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            posts.extend(data)
    return posts


def parse(raw: Path) -> Iterable[Pair]:
    for post in _posts(raw):
        if "/es/" not in post["link"]:  # Spanish edition only; the other one glosses into English
            continue
        body = post["content"]["rendered"]
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.S):
            cells = [_cell_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)]
            if len(cells) != 2:
                continue
            quc, spa = cells
            if len(quc) < 2 or len(spa) < 2 or quc.endswith(":") or spa.endswith(":"):
                continue  # dialogue speaker labels ("A:") and empty cells
            if _GLOSS_RE.search(quc) or _GLOSS_RE.search(spa):
                continue
            quc = _POS_TAG_RE.sub("", quc).strip()
            yield Pair(
                quc=quc,
                spa=spa,
                source_name="coerll_kiche",
                domain="everyday",
                license=LICENSE,
                url=post["link"],
                kind=guess_kind(quc, spa),
                ref=post["slug"],
                raw_flags=orthography_flags(quc),
            )


SOURCE = Source(
    name="coerll_kiche",
    title="Chqeta'maj le qach'ab'al K'iche'! (Spanish edition)",
    owner="COERLL / LLILAS / AILLA, University of Texas at Austin",
    url=HOME,
    license=LICENSE,
    role=TRAIN,
    fetch=fetch,
    parse=parse,
)
