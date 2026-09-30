"""Orthography normalization for K'iche' and Spanish.

Why this exists: the same K'iche' word reaches us spelled in many ways. Sources
type the glottal stop with at least ten different characters (', ’, ʼ, ꞌ, ´, 7…),
some mark the "lax" vowels with a diaeresis (ä, ï) and others don't. To a model
or an embedding, `k'ak'`, `kʼakʼ` and `kꞌakꞌ` are three unrelated strings. We
normalize *before* indexing, training and evaluating so that retrieval matches,
training sees one spelling, and chrF++ doesn't punish a correct translation for
using a different apostrophe.

Reference: the unified K'iche' alphabet of the Academia de Lenguas Mayas de
Guatemala (ALMG, Acuerdo Gubernativo 1046-87 and later ALMG norms):

  vowels      a e i o u  (+ lax ä ë ï ö ü in the official alphabet)
  consonants  b' ch ch' j k k' l m n p q q' r s t t' tz tz' w x y  and ' (glottal stop)

Decisions (documented in data/DATASHEET.md):
  * Canonical glottal stop is the ASCII apostrophe U+0027. It's what users type
    on any keyboard and what ALMG prints; Unicode's U+02BC would be more
    "correct" but no one types it on a phone.
  * Lax vowels are folded (ä→a …) by default. Most modern K'iche' writing
    (Bible translations, MINEDUC books, the COERLL course) uses five vowels;
    keeping the diaeresis would split the vocabulary for no benefit.
  * Spanish keeps its accents; only whitespace, quotes and dashes are unified.
"""

from __future__ import annotations

import re
import unicodedata

GLOTTAL = "'"

# Every character we have seen used as a K'iche' glottal stop / ejective mark.
# Written as escapes on purpose: most of them look identical on screen.
GLOTTAL_VARIANTS = (
    "'"  # apostrophe
    "’"  # right single quotation mark (word processors)
    "‘"  # left single quotation mark (Firefox/Pontoon strings)
    "\u02bc"  # modifier letter apostrophe (linguists, Unicode UDHR)
    "\u02bb"  # modifier letter turned comma
    "\ua78c"  # Latin small letter saltillo (eBible)
    "\ua78b"  # Latin capital letter saltillo
    "\u00b4"  # acute accent typed alone
    "`"  # grave accent typed alone
    "\u2032"  # prime
    "\u02c8"  # modifier letter vertical line (older SIL texts)
    "\u02b9"  # modifier letter prime
    "\u201b"  # single high-reversed-9 quotation mark
)
_GLOTTAL_RE = re.compile("[" + re.escape(GLOTTAL_VARIANTS) + "]")

# A combining acute on a consonant is a glottal typed with a dead key: "k" +
# U+0301 composes to a single letter under NFC, so we catch it decomposed.
_ACUTE_AFTER_CONSONANT_RE = re.compile(r"(?<=[b-df-hj-np-tv-zB-DF-HJ-NP-TV-Z])́")

# "7" is used as a glottal stop in texting and in some linguistic notation
# (ja7 = ja', k7ak7 = k'ak'). Only replace it when it sits right after a letter
# and is not part of a number.
_DIGIT_GLOTTAL_RE = re.compile(r"(?<=[^\W\d_])7(?!\d)")

LAX_VOWELS = str.maketrans({"ä": "a", "ë": "e", "ï": "i", "ö": "o", "ü": "u",
                            "Ä": "A", "Ë": "E", "Ï": "I", "Ö": "O", "Ü": "U"})

_INVISIBLE_RE = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")
_SPACES_RE = re.compile(r"[\s\u00a0\u2000-\u200a\u202f\u205f\u3000]+")
_DOUBLE_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "‟": '"'})
_DASHES = str.maketrans({"–": "-", "—": "-", "―": "-", "‒": "-", "−": "-"})
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?)\]}])")
_SPACE_AFTER_OPENER_RE = re.compile(r"([¿¡(\[{])\s+")

# Letters of the ALMG K'iche' alphabet (lowercase, after folding).
KICHE_LETTERS = frozenset("abeijklmnopqrstuwxy") | frozenset("äëïöü")
KICHE_DIGRAPHS = ("ch", "tz")


def _common(text: str) -> str:
    """Shared cleanup for both languages: Unicode form, spaces, quotes, dashes."""
    text = unicodedata.normalize("NFC", text)
    text = _INVISIBLE_RE.sub("", text)
    text = text.translate(_DOUBLE_QUOTES).translate(_DASHES)
    text = text.replace("…", "...")
    text = _SPACES_RE.sub(" ", text).strip()
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = _SPACE_AFTER_OPENER_RE.sub(r"\1", text)
    return text


def normalize_kiche(text: str, *, fold_lax_vowels: bool = True) -> str:
    """Normalize K'iche' text to the canonical orthography used across Tzij."""
    if not text:
        return ""
    # A combining acute after a consonant is a glottal mark typed with a dead
    # key ("k´" -> "ḱ" once composed). Decompose, rewrite it, then recompose so
    # vowel + diaeresis becomes one code point again.
    text = unicodedata.normalize("NFD", text)
    text = _ACUTE_AFTER_CONSONANT_RE.sub(GLOTTAL, text)
    text = unicodedata.normalize("NFC", text)
    text = _GLOTTAL_RE.sub(GLOTTAL, text)
    text = _DIGIT_GLOTTAL_RE.sub(GLOTTAL, text)
    if fold_lax_vowels:
        text = text.translate(LAX_VOWELS)
    text = _common(text)
    # Word-internal glottal stops never take spaces around them ("k' ak'" is a
    # typo for "k'ak'") but a leading space before a word-final one is common.
    text = re.sub(r"(?<=\w) '(?=\s|$|[,.;:!?])", "'", text)
    return text


def normalize_spanish(text: str) -> str:
    """Normalize Spanish text. Accents and ¿¡ are part of the language: kept."""
    if not text:
        return ""
    text = _common(text)
    return text.replace("’", "'").replace("‘", "'")


def normalize(text: str, lang: str) -> str:
    """Dispatch by ISO 639-3 code: 'quc' (K'iche') or 'spa' (Spanish)."""
    if lang in ("quc", "kiche"):
        return normalize_kiche(text)
    if lang in ("spa", "es"):
        return normalize_spanish(text)
    raise ValueError(f"unsupported language: {lang}")


def match_key(text: str) -> str:
    """Aggressive key for deduplication and leakage checks.

    Lowercase, no punctuation, single spaces. Two records with the same key are
    the same sentence for our purposes, even if one ends in a period.
    """
    text = text.lower()
    text = re.sub(r"[^\w\s']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def outside_alphabet(text: str) -> set[str]:
    """Letters in a (normalized) K'iche' string that are not in the ALMG alphabet.

    Useful to spot Spanish loans, older orthographies (c/qu for k) or text that
    is not K'iche' at all. `h` is allowed only inside the digraph `ch`.
    """
    lowered = text.lower()
    stripped = lowered.replace("ch", "")
    return {c for c in stripped if c.isalpha() and c not in KICHE_LETTERS}


def orthography_flags(text: str) -> set[str]:
    """Heuristic markers of non-ALMG spelling in *raw* K'iche' text.

    Used for the datasheet, not for filtering: a flag is a hint for a human.
    """
    flags: set[str] = set()
    lowered = text.lower()
    if re.search(r"[äëïöü]", lowered):
        flags.add("lax_vowels_marked")
    if re.search(r"c(?!h)", lowered):
        flags.add("c_for_k")  # colonial/older spelling (or a Spanish loan)
    if re.search(r"\bqu[ei]", lowered):
        flags.add("qu_for_k")
    if _DIGIT_GLOTTAL_RE.search(lowered):
        flags.add("digit_glottal")
    glottals = {ch for ch in text if ch in GLOTTAL_VARIANTS and ch != GLOTTAL}
    if glottals:
        flags.add("nonascii_glottal")
    return flags
