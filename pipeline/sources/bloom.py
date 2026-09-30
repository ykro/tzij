"""Bloom Library: children's books in K'iche', most published by MINEDUC Guatemala.

Bilingual Bloom books keep both languages inside the same "translation group"
on every page (`<div class="bloom-editable" lang="quc">` next to `lang="es"`),
so pages align without guessing. We keep CC BY books only; CC BY-NC-* books
are left out (see data/SOURCES.md).

This is the TEST source: children's narrative in modern ALMG spelling, a
domain none of the training sources cover, and unlikely to be in the
pretraining data of either model.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

import httpx

from data.normalize import orthography_flags
from pipeline.record import Pair, guess_kind
from pipeline.sources.base import TEST, USER_AGENT, Source, download

HOME = "https://bloomlibrary.org/language:quc"
PARSE_API = "https://server.bloomlibrary.org/parse/classes/books"
# The public application id that bloomlibrary.org's own web client sends; no account involved.
PARSE_APP_ID = "R6qNTeumQXjJCMutAJYAwPtip1qBulkFyLefkCE5"
ALLOWED_LICENSES = {"cc-by"}

# Front/back matter fields that are credits, not story text.
SKIP_FIELDS = {
    "smallCoverCredits", "copyright", "licenseNotes", "originalAcknowledgments",
    "versionAcknowledgments", "originalCopyrightAndLicense", "funding", "ISBN",
    "licenseUrl", "originalContributions", "insideFontCover", "insideBackCover",
    "outsideBackCover", "topic", "credits",
}


def _harvest_base(base_url: str) -> str:
    """Book upload URL -> the harvester bucket that holds the read-online HTML."""
    base = base_url[:-3] if base_url.endswith("%2f") else base_url.rstrip("/")
    cut = base.rfind("%2f")
    return base[:cut].replace("BloomLibraryBooks", "bloomharvest") + "/"


def fetch(raw: Path) -> None:
    books_path = raw / "books.json"
    if not books_path.exists():
        where = {
            "langPointers": {"$inQuery": {"where": {"isoCode": "quc"}, "className": "language"}},
            "inCirculation": {"$ne": False},
        }
        response = httpx.get(
            PARSE_API,
            params={
                "where": json.dumps(where),
                "limit": 1000,
                "keys": "title,license,copyright,baseUrl,harvestState,createdAt",
            },
            headers={"X-Parse-Application-Id": PARSE_APP_ID, "User-Agent": USER_AGENT},
            timeout=60,
        )
        response.raise_for_status()
        books_path.write_text(json.dumps(response.json()["results"], ensure_ascii=False, indent=1))
    for book in json.loads(books_path.read_text(encoding="utf-8")):
        if book.get("license") not in ALLOWED_LICENSES or book.get("harvestState") != "Done":
            continue
        url = _harvest_base(book["baseUrl"]) + "bloomdigital%2findex.htm"
        try:
            download(url, raw / "books" / f"{book['objectId']}.htm")
        except RuntimeError as error:  # one missing book should not sink the run
            print(f"  bloom: skipped {book['objectId']}: {error}")


class _TranslationGroups(HTMLParser):
    """Collect {lang: (text, data-book)} for every bloom-translationGroup."""

    def __init__(self) -> None:
        super().__init__()
        self.groups: list[dict[str, tuple[str, str | None]]] = []
        self._depth = 0
        self._current: dict | None = None

    def handle_starttag(self, tag, attrs):
        self._depth += 1
        attrs = dict(attrs)
        classes = attrs.get("class") or ""
        if "bloom-translationGroup" in classes:
            self.groups.append({})
        if "bloom-editable" in classes and self.groups:
            self._current = {"lang": attrs.get("lang"), "field": attrs.get("data-book"),
                             "depth": self._depth, "text": []}

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and self._current:
            self._current["text"].append(" ")

    def handle_endtag(self, tag):
        if self._current and self._depth == self._current["depth"]:
            text = re.sub(r"\s+", " ", "".join(self._current["text"])).strip()
            if self._current["lang"] and text:
                self.groups[-1][self._current["lang"]] = (text, self._current["field"])
            self._current = None
        self._depth -= 1

    def handle_data(self, data):
        if self._current:
            self._current["text"].append(data)


def parse(raw: Path) -> Iterable[Pair]:
    books = {b["objectId"]: b for b in json.loads((raw / "books.json").read_text(encoding="utf-8"))}
    for path in sorted((raw / "books").glob("*.htm")):
        book = books.get(path.stem)
        if not book or book.get("license") not in ALLOWED_LICENSES:
            continue
        parser = _TranslationGroups()
        parser.feed(path.read_text(encoding="utf-8"))
        holder = (book.get("copyright") or "").replace("Copyright ", "")
        for group in parser.groups:
            if "quc" not in group or "es" not in group:
                continue
            (quc, field), (spa, _) = group["quc"], group["es"]
            if field in SKIP_FIELDS:
                continue
            yield Pair(
                quc=quc,
                spa=spa,
                source_name="bloom_kiche",
                domain="education",
                license=f"CC-BY-4.0 ({holder})" if holder else "CC-BY-4.0",
                url=f"https://bloomlibrary.org/book/{path.stem}",
                kind=guess_kind(quc, spa),
                ref=book.get("title", ""),
                raw_flags=orthography_flags(quc),
            )


SOURCE = Source(
    name="bloom_kiche",
    title="Bloom Library K'iche' books (CC BY subset)",
    owner="Ministerio de Educación de Guatemala / USAID and others, via SIL Bloom Library",
    url=HOME,
    license="CC-BY-4.0 (per book)",
    role=TEST,
    fetch=fetch,
    parse=parse,
)
