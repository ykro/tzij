"""Dictionary-guided decoding: make David *use* the dictionary translations it retrieved.

The niche evaluation showed that David often has the right word in his retrieved glossary and
still doesn't write it. When hybrid retrieval finds an exact dictionary entry for a content
word of the input, its translation becomes a constraint:

  prompt   the required target forms are listed as "use these" in David's context;
  select   among the MBR candidates, only those that satisfy the most constraints compete
           (consensus chrF++ breaks the tie); if none satisfies any, plain MBR decides.

Ollama has no logit bias, and its grammar support (`format`, a JSON schema) can't say "must
contain this word", so token-level forcing isn't available. That's why it works by prompt +
selection. Tuned on dev only (evals/constraints_tuning.md).
"""

from __future__ import annotations

import re

from data.normalize import match_key
from rag.retrieve import RetrievalResult

# Very frequent Spanish words that dictionaries also list: as constraints they'd be noise.
SPANISH_STOP = {
    "a", "al", "con", "de", "del", "el", "ella", "ellos", "en", "es", "esta", "este", "esto", "la", "las",
    "le", "les", "lo", "los", "me", "mi", "mis", "muy", "no", "nos", "o", "para", "pero", "por", "que",
    "se", "si", "sí", "su", "sus", "te", "tu", "tú", "un", "una", "y", "ya", "yo", "hay", "son", "está",
}
KICHE_STOP = {"ri", "le", "are'", "xa", "chi", "pa", "ruk'", "kuk'", "we", "jun", "k'o", "man", "ta", "wa'",
              "ne", "xuquje'", "pero", "kab'", "ech", "rech", "che"}


def _alternatives(target: str) -> list[str]:
    """'camino, calle' -> ['camino', 'calle']; keeps K'iche' apostrophes."""
    parts = re.split(r"[;,/]| o ", target)
    return [k for k in (match_key(p) for p in parts) if k]


def constraints_from(found: RetrievalResult, max_constraints: int = 3) -> list[tuple[str, list[str]]]:
    """(source headword, acceptable target forms) for exact single-word dictionary hits."""
    stop = SPANISH_STOP if found.direction == "es-quc" else KICHE_STOP
    query_words = set(match_key(found.query).split())
    grouped: dict[str, list[str]] = {}
    for h in found.glossary:
        if h.via != "exact" or h.kind != "lexicon":
            continue
        head = match_key(h.source_text)
        if " " in head or head not in query_words or head in stop or len(head) < 3:
            continue
        for alt in _alternatives(h.target_text):
            if alt not in grouped.setdefault(head, []):
                grouped[head].append(alt)
    return [(h, alts) for h, alts in grouped.items() if alts][:max_constraints]


def _satisfies(candidate: str, alternative: str, target_lang: str) -> bool:
    cand = match_key(candidate)
    if target_lang == "quc":
        # K'iche' adds prefixes (nu-ja, u-chaq'): the dictionary form inside a word counts.
        return all(tok in cand for tok in alternative.split())
    words = cand.split()
    # Spanish inflects the ending (comer -> come, comemos): match on the stem.
    return all(any(w.startswith(tok[:max(4, len(tok) - 2)]) for w in words) for tok in alternative.split())


def coverage(candidate: str, constraints: list[tuple[str, list[str]]], direction: str) -> int:
    target_lang = "quc" if direction == "es-quc" else "es"
    return sum(any(_satisfies(candidate, alt, target_lang) for alt in alts) for _, alts in constraints)


def prompt_block(constraints: list[tuple[str, list[str]]]) -> str:
    if not constraints:
        return ""
    lines = ["Traducciones obligatorias del diccionario (úsalas):"]
    lines += [f"- {head} = {' / '.join(alts)}" for head, alts in constraints]
    return "\n".join(lines)
