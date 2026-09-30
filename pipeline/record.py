"""The unit of data in Tzij: a Spanish–K'iche' pair, and the JSONL records it becomes.

A *pair* is what a source gives us (one K'iche' text, one Spanish text). A
*record* is what we train, index and evaluate on: every pair becomes two
records, one per translation direction, so each split is balanced by
construction and the test set has the same pairs in both directions.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from data.normalize import match_key, normalize_kiche, normalize_spanish

DIRECTIONS = ("es-quc", "quc-es")

# Kinds of pair. The fine-tuning threshold counts sentences only: a dictionary
# entry is useful context for retrieval but it is not a translation example.
SENTENCE = "sentence"
LEXICON = "lexicon"

RELIGIOUS = "religious"


@dataclass
class Pair:
    quc: str
    spa: str
    source_name: str
    domain: str
    license: str
    url: str
    kind: str = SENTENCE
    # Free-form provenance inside a source (book id, verse ref, lesson…).
    ref: str = ""
    # Orthography markers seen on the raw K'iche' text (for the datasheet).
    raw_flags: set[str] = field(default_factory=set)

    def normalized(self) -> "Pair":
        """Same pair with both sides in canonical orthography."""
        return Pair(
            quc=normalize_kiche(self.quc),
            spa=normalize_spanish(self.spa),
            source_name=self.source_name,
            domain=self.domain,
            license=self.license,
            url=self.url,
            kind=self.kind,
            ref=self.ref,
            raw_flags=set(self.raw_flags),
        )

    @property
    def key(self) -> tuple[str, str]:
        return match_key(self.quc), match_key(self.spa)

    @property
    def pair_id(self) -> str:
        """Stable across runs: depends only on source and text."""
        digest = hashlib.sha1(
            f"{self.source_name}\x1f{self.key[0]}\x1f{self.key[1]}".encode()
        ).hexdigest()
        return f"{self.source_name}-{digest[:12]}"

    def to_records(self, split: str, status: str) -> list[dict]:
        records = []
        for direction in DIRECTIONS:
            src, tgt = (self.spa, self.quc) if direction == "es-quc" else (self.quc, self.spa)
            records.append(
                {
                    "id": f"{self.pair_id}-{direction}",
                    "pair_id": self.pair_id,
                    "direction": direction,
                    "source_text": src,
                    "target_text": tgt,
                    "source_name": self.source_name,
                    "domain": self.domain,
                    "kind": self.kind,
                    "split": split,
                    "status": status,
                    "origin": "web",
                    "url": self.url,
                    "license": self.license,
                    "ref": self.ref,
                }
            )
        return records


def guess_kind(quc: str, spa: str) -> str:
    """Tell a translation example from a glossary entry, looking at the K'iche' side.

    K'iche' is agglutinative: "Xinsachik." is a full sentence ("Me perdí.") in
    one word, so a single capitalized word ending in . ? ! counts as a sentence.
    A lowercase single word with a long Spanish explanation is a dictionary entry.
    """
    quc = quc.strip()
    words = len(quc.split())
    if words >= 2:
        return SENTENCE
    if quc[:1].isupper() and quc.endswith((".", "?", "!")):
        return SENTENCE
    return LEXICON
