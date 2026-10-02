"""Dictionary-guided decoding: push David toward the dictionary translations he retrieved.

When hybrid retrieval finds an exact dictionary entry for a content word of the input, its
translation becomes a constraint, and llama-server (duel_core/llama_client.py) adds a logit bias
to its tokens. Ollama has no logit bias, and its grammar support (`format`, a JSON schema) can't
say "must contain this word", so this needs llama-server. Asking for the forms in the prompt, or
filtering MBR candidates by them, gave nothing on dev and was removed.
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
