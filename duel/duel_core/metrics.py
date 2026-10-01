"""chrF++ via sacrebleu.

Why chrF++ and not BLEU: low-resource languages like K'iche' have spelling variants (k'ak' /
kʼakʼ, lax vowels or not), rich morphology (one word can be a whole sentence) and short
sentences. Character n-grams (plus word bigrams, the "++") give partial credit where
BLEU gives zero, and it is the standard metric for low-resource MT (WMT).
"""

from __future__ import annotations

from sacrebleu.metrics import CHRF

_CHRF_PP = CHRF(word_order=2)  # word_order=2 is what makes it chrF++


def chrf_pp(hypothesis: str, reference: str) -> float:
    """Sentence-level chrF++ in [0, 100]. Good for one duel round on screen."""
    return float(_CHRF_PP.sentence_score(hypothesis or "", [reference]).score)


def corpus_chrf_pp(hypotheses: list[str], references: list[str]) -> float:
    """Corpus-level chrF++ (not the mean of sentence scores). Use this for reports."""
    if not hypotheses:
        return 0.0
    return float(_CHRF_PP.corpus_score([h or "" for h in hypotheses], [references]).score)
