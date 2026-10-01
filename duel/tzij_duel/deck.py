"""Phrases for evaluation rounds: test-set pairs with their reference translation.

Only the test split is used (never train): an evaluation round on stage must
not be something David has in its retrieval index. Short sentences read
better from the back of the room, so the deck keeps 2–14 words.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

MIN_WORDS, MAX_WORDS = 2, 14
# auto_validated: passed pipeline/validate_test.py; validated: a native speaker also approved it.
# pending_native_review is accepted for datasets built before automatic validation existed.
USABLE = {"auto_validated", "validated", "pending_native_review"}


@dataclass
class DeckItem:
    pair_id: str
    direction: str
    source_text: str
    reference: str
    source_name: str
    url: str
    license: str
    status: str
    domain: str

    def meta(self) -> dict:
        return {"pair_id": self.pair_id, "source_name": self.source_name, "url": self.url,
                "license": self.license, "status": self.status, "domain": self.domain}


def latest_dataset(processed: Path) -> Path | None:
    pointer = processed / "LATEST"
    if not pointer.exists():
        return None
    path = processed / pointer.read_text().strip()
    return path if path.exists() else None


class Deck:
    def __init__(self, processed: Path | None, *, require_validated: bool = False, seed: int = 2027,
                 exclude_sources: tuple[str, ...] = ("bouquet",), test_file: Path | None = None):
        # BOUQuET's terms allow evaluation but only private redistribution: `make eval` uses
        # it, the projector doesn't show it.
        self.items: list[DeckItem] = []
        if test_file is None:
            dataset = latest_dataset(processed) if processed else None
            test_file = dataset / "test.jsonl" if dataset else None
        if test_file and test_file.exists():
            for line in test_file.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                if r["kind"] != "sentence" or not (MIN_WORDS <= len(r["source_text"].split()) <= MAX_WORDS):
                    continue
                if r["source_text"].isupper() or r["target_text"].isupper():
                    continue  # book headings ("CHAB'ANA K'OB'AL CHI'J") read poorly on stage
                if r["source_name"] in exclude_sources:
                    continue
                if r["status"] not in USABLE or (require_validated and r["status"] != "validated"):
                    continue
                self.items.append(DeckItem(r["pair_id"], r["direction"], r["source_text"], r["target_text"],
                                           r["source_name"], r["url"], r["license"], r["status"], r["domain"]))
        random.Random(seed).shuffle(self.items)
        self._used: set[tuple[str, str]] = set()

    def next(self, direction: str, used: set[tuple[str, str]] | None = None) -> DeckItem | None:
        taken = self._used | (used or set())
        for item in self.items:
            if item.direction == direction and (item.pair_id, direction) not in taken:
                self._used.add((item.pair_id, direction))
                return item
        return None

    def suggestions(self, direction: str, limit: int = 8) -> list[dict]:
        """Source phrases (from licensed data) the presenter can pick for a live round."""
        out = [i for i in self.items if i.direction == direction][:limit]
        return [{"text": i.source_text, "source_name": i.source_name} for i in out]

    def reset(self) -> None:
        self._used.clear()
