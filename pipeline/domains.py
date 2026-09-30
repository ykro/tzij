"""Domain tagging.

Each source declares a default domain (a Bible is `religious`, Firefox strings
are `software`). General-purpose sources — a language course, dictionary
examples — get a finer tag from the Spanish side when it clearly talks about
health or school, so the datasheet and the evals can report per-domain.
"""

from __future__ import annotations

import re

from pipeline.record import Pair

REFINABLE = {"everyday"}

KEYWORDS = {
    "health": r"enferm|medicin|médic|doctor|salud|hospital|vacun|dolor|fiebre|covid|curad|remedio|embaraz",
    "education": r"escuela|maestr|estudi|aprend|clase|libro|leer|escrib|alumn",
}
_COMPILED = {domain: re.compile(rf"\b({pattern})", re.I) for domain, pattern in KEYWORDS.items()}


def tag_domain(pair: Pair) -> Pair:
    if pair.domain in REFINABLE:
        for domain, regex in _COMPILED.items():
            if regex.search(pair.spa):
                pair.domain = domain
                break
    return pair
