"""Automatic validation of the test set: no human step between the web and `make eval`.

A test pair is `auto_validated` when it passes every check below; otherwise it is
`auto_rejected` and stays out of evaluation (kept in the file, with the reason, so the
datasheet can count it). A native speaker can still review the set later with
`make review-test` / `make apply-review`, which upgrades pairs to `validated` — optional, never
a prerequisite.

Criteria (all must hold):
  1. source-level split      the pair comes from a test-only source (pipeline/split.py)
  2. cleaning                passed pipeline/clean.py (markup, glosses, other Mayan languages,
                             Spanish on the K'iche' side, untranslated text, 3x length ratio)
  3. tight length ratio      K'iche'/Spanish character ratio within [0.5, 2.0] for anything
                             longer than 20 characters: a page that paraphrases or summarizes
                             is a bad reference even if it passed the looser cleaning ratio
  4. Spanish looks Spanish   3+ words on the Spanish side include at least one Spanish
                             function word (catches K'iche' or English copied into both columns)
  5. no overlap with train   neither side matches (case/punctuation-insensitive) any pair in
                             train or dev — i.e. nothing the retrieval index or a fine-tune saw
  6. sentence, not glossary  kind == sentence (single-word glossary lines make poor references)
"""

from __future__ import annotations

from collections import Counter

from pipeline.clean import SPANISH_FUNCTION_WORDS
from pipeline.record import SENTENCE, Pair

AUTO_VALIDATED = "auto_validated"
AUTO_REJECTED = "auto_rejected"
MIN_RATIO, MAX_RATIO = 0.5, 2.0

CRITERIA = (
    "source-level split (test-only sources)",
    "pipeline/clean.py filters",
    f"K'iche'/Spanish character ratio in [{MIN_RATIO}, {MAX_RATIO}] above 20 characters",
    "Spanish side contains a Spanish function word (3+ words)",
    "no case/punctuation-insensitive overlap with any train or dev sentence",
    "kind == sentence",
)


def rejection(pair: Pair, seen_quc: set[str], seen_spa: set[str]) -> str | None:
    if pair.kind != SENTENCE:
        return "not_a_sentence"
    quc_key, spa_key = pair.key
    if quc_key in seen_quc or spa_key in seen_spa:
        return "overlaps_train"
    if max(len(pair.quc), len(pair.spa)) > 20:
        ratio = len(pair.quc) / max(len(pair.spa), 1)
        if not MIN_RATIO <= ratio <= MAX_RATIO:
            return "loose_translation_ratio"
    words = [w.strip(".,;:!?¿¡\"()").lower() for w in pair.spa.split()]
    if len(words) >= 3 and not any(w in SPANISH_FUNCTION_WORDS or w in _MORE_SPANISH for w in words):
        return "spanish_side_not_spanish"
    return None


# Short, very common Spanish words not in the cleaning list (that list avoids words that also
# exist in K'iche'; here we look at the Spanish side, so they are safe).
_MORE_SPANISH = frozenset("la le lo me mi te tu yo ya a o e tú él".split())


def validate(test: list[Pair], train_like: list[Pair]) -> tuple[dict[str, str], Counter]:
    """pair_id -> status, plus a Counter of rejection reasons."""
    seen_quc = {p.key[0] for p in train_like}
    seen_spa = {p.key[1] for p in train_like}
    statuses: dict[str, str] = {}
    reasons: Counter = Counter()
    for pair in test:
        reason = rejection(pair, seen_quc, seen_spa)
        statuses[pair.pair_id] = AUTO_REJECTED if reason else AUTO_VALIDATED
        if reason:
            reasons[reason] += 1
    return statuses, reasons
