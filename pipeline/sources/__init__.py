"""Registry of every source the pipeline downloads.

Only sources marked `used` in data/SOURCES.md appear here. Order matters: when
two sources contain the same pair, deduplication keeps the first one, so the
most carefully curated sources come first.
"""

from pipeline.sources import bloom, bouquet, coerll, ebible, gatitos, panlex, pontoon, ud_kiche, udhr, wiktionary
from pipeline.sources.base import TEST, TRAIN, Source

SOURCES: list[Source] = [
    # Test sources first: a test pair is never dropped in favor of a train copy.
    bloom.SOURCE,
    bouquet.SOURCE,  # gated, evaluation-only; skipped when there is no HF token
    ud_kiche.SOURCE,
    coerll.SOURCE,
    udhr.SOURCE,
    pontoon.SOURCE,
    ebible.SOURCE,
    gatitos.SOURCE,
    panlex.SOURCE,
    wiktionary.SOURCE,
]

__all__ = ["SOURCES", "Source", "TEST", "TRAIN"]
