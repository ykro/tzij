"""Deduplicate and split — by source, never by sentence.

Why by source: a random sentence split lets near-copies of the same lesson,
book or chapter land on both sides, and the evaluation then measures memory,
not translation. Here a source is either entirely test or entirely train, and
any train pair that repeats a test sentence is removed (leakage check).

Religious text is capped at 30% of the training sentences: there are ~8,000
Bible verses and far fewer everyday sentences, and without a cap David would
translate "¿Dónde está el mercado?" in the voice of the Gospel of Mark.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from dataclasses import dataclass, field

from pipeline.record import LEXICON, RELIGIOUS, SENTENCE, Pair

RELIGIOUS_CAP = 0.30
DEV_PERCENT = 5

TRAIN, DEV, TEST = "train", "dev", "test"
# Only these splits may be used to build the retrieval index or to fine-tune.
RETRIEVAL_SPLITS = (TRAIN,)
FINETUNE_SPLITS = (TRAIN, DEV)


@dataclass
class SplitResult:
    train: list[Pair] = field(default_factory=list)
    dev: list[Pair] = field(default_factory=list)
    test: list[Pair] = field(default_factory=list)
    dropped: list[tuple[Pair, str]] = field(default_factory=list)

    def by_split(self) -> dict[str, list[Pair]]:
        return {TRAIN: self.train, DEV: self.dev, TEST: self.test}


def _bucket(pair: Pair) -> int:
    """Deterministic 0-99 bucket: the same pair always lands in the same place."""
    return int(hashlib.sha1(pair.pair_id.encode()).hexdigest(), 16) % 100


def dedupe(pairs: list[Pair]) -> tuple[list[Pair], list[tuple[Pair, str]]]:
    """Keep the first occurrence of each (K'iche', Spanish) pair, in source priority order."""
    seen: set[tuple[str, str]] = set()
    kept, dropped = [], []
    for pair in pairs:
        if pair.key in seen:
            dropped.append((pair, "duplicate"))
            continue
        seen.add(pair.key)
        kept.append(pair)
    return kept, dropped


def split_by_source(pairs: list[Pair], test_sources: set[str]) -> SplitResult:
    result = SplitResult()
    test = [p for p in pairs if p.source_name in test_sources]
    candidates = [p for p in pairs if p.source_name not in test_sources]

    # Religious text never goes to test, even if a test source contains some.
    for pair in test:
        if pair.domain == RELIGIOUS:
            result.dropped.append((pair, "religious_in_test_source"))
        else:
            result.test.append(pair)

    # Leakage: a train sentence that matches either side of a test sentence goes.
    test_quc = {p.key[0] for p in result.test if p.kind == SENTENCE}
    test_spa = {p.key[1] for p in result.test if p.kind == SENTENCE}
    test_keys = {p.key for p in result.test}
    clean_candidates = []
    for pair in candidates:
        leaks = pair.key in test_keys or (
            pair.kind == SENTENCE and (pair.key[0] in test_quc or pair.key[1] in test_spa)
        )
        if leaks:
            result.dropped.append((pair, "leaks_test_sentence"))
        else:
            clean_candidates.append(pair)

    religious = [p for p in clean_candidates if p.domain == RELIGIOUS]
    secular = [p for p in clean_candidates if p.domain != RELIGIOUS]

    # A small dev set from secular sentences, for fine-tuning validation.
    for pair in secular:
        if pair.kind == SENTENCE and _bucket(pair) < DEV_PERCENT:
            result.dev.append(pair)
        else:
            result.train.append(pair)

    # Cap religious sentences at RELIGIOUS_CAP of all training sentences:
    #   R / (S + R) <= cap  =>  R <= S * cap / (1 - cap)
    secular_sentences = sum(1 for p in result.train if p.kind == SENTENCE)
    budget = math.floor(secular_sentences * RELIGIOUS_CAP / (1 - RELIGIOUS_CAP))
    religious.sort(key=lambda p: hashlib.sha1(p.pair_id.encode()).hexdigest())
    result.train.extend(religious[:budget])
    result.dropped.extend((p, "religious_cap") for p in religious[budget:])
    return result


def religious_share(train: list[Pair]) -> float:
    sentences = [p for p in train if p.kind == SENTENCE]
    if not sentences:
        return 0.0
    return sum(p.domain == RELIGIOUS for p in sentences) / len(sentences)


def kind_counts(pairs: list[Pair]) -> Counter:
    return Counter(p.kind for p in pairs)


__all__ = [
    "DEV", "FINETUNE_SPLITS", "LEXICON", "RETRIEVAL_SPLITS", "SplitResult", "TEST", "TRAIN",
    "dedupe", "religious_share", "split_by_source",
]
