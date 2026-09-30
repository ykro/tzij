"""Cleaning: throw away pairs that would teach the model something wrong.

Every rule returns a reason string so the datasheet can say *why* data was
dropped, per source. Rules are deliberately conservative; the test set is also
checked by a native speaker, which catches what heuristics can't.
"""

from __future__ import annotations

import re

from data.normalize import match_key
from pipeline.record import LEXICON, Pair

MAX_WORDS = 120
MIN_CHAR_RATIO = 1 / 3  # K'iche' and Spanish sentences have similar lengths;
MAX_CHAR_RATIO = 3.0  # a 3x difference means a loose or partial translation.

# If most of the "K'iche'" side is Spanish function words, it isn't K'iche'.
# Words that also exist in K'iche' (la, le, ya', lo', we, xa…) are left out on purpose.
SPANISH_FUNCTION_WORDS = frozenset(
    "el los las de del que y en un una por para con no se su sus es al como más pero "
    "este esta son fue ha muy también hay".split()
)

# Letter sequences that don't exist in K'iche' but are common in Mam or other
# Mayan languages (Bloom has a few books tagged K'iche' that are really Mam).
OTHER_MAYAN_RE = re.compile(r"\b\w*(tx|ky|ẍ)\w*\b", re.I)

# Linguistic glosses and segmentations are grammar notes, not translations.
GLOSS_RE = re.compile(r"\b(COMP|INC|PERF|ABS|ERG|1sg|3sg|sing)\b|\w+-\w+-\w+-\w+")

MARKUP_RE = re.compile(r"</?\w+[^>]*>|\{\{|\}\}|%[sd]|\$\{")


def rejection_reason(pair: Pair) -> str | None:
    """None if the pair is clean, otherwise a short reason code."""
    quc, spa = pair.quc.strip(), pair.spa.strip()
    if not quc or not spa:
        return "empty"
    if match_key(quc) == match_key(spa):
        return "untranslated"  # copied across, or a proper name: teaches nothing
    if MARKUP_RE.search(quc) or MARKUP_RE.search(spa):
        return "markup"
    if GLOSS_RE.search(quc) or GLOSS_RE.search(spa):
        return "linguistic_gloss"
    quc_words, spa_words = quc.split(), spa.split()
    if len(quc_words) > MAX_WORDS or len(spa_words) > MAX_WORDS:
        return "too_long"
    if pair.kind != LEXICON:
        ratio = len(quc) / max(len(spa), 1)
        if max(len(quc), len(spa)) > 20 and not (MIN_CHAR_RATIO <= ratio <= MAX_CHAR_RATIO):
            return "length_ratio"
        lowered = [w.strip(".,;:!?¿¡\"()").lower() for w in quc_words]
        spanish_share = sum(w in SPANISH_FUNCTION_WORDS for w in lowered) / len(lowered)
        if len(lowered) >= 3 and spanish_share >= 0.4:
            return "kiche_side_is_spanish"
        if len(OTHER_MAYAN_RE.findall(quc)) >= 2:
            return "other_mayan_language"
    return None


def clean(pairs: list[Pair]) -> tuple[list[Pair], list[tuple[Pair, str]]]:
    kept, dropped = [], []
    for pair in pairs:
        reason = rejection_reason(pair)
        if reason:
            dropped.append((pair, reason))
        else:
            kept.append(pair)
    return kept, dropped
