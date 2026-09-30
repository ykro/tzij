import pytest

from data.normalize import (
    GLOTTAL,
    match_key,
    normalize,
    normalize_kiche,
    normalize_spanish,
    orthography_flags,
    outside_alphabet,
)

# One K'iche' word ("k'ak'" = new) written with every glottal variant we've met.
GLOTTAL_SPELLINGS = [
    "k'ak'",
    "k’ak’",
    "k‘ak‘",
    "kʼakʼ",
    "kʻakʻ",
    "kꞌakꞌ",
    "k´ak´",
    "k`ak`",
    "k′ak′",
    "kˈakˈ",
    "kʹakʹ",
    "k‛ak‛",
    "ḱaḱ",
    "k7ak7",
]


@pytest.mark.parametrize("spelling", GLOTTAL_SPELLINGS)
def test_every_glottal_variant_becomes_ascii_apostrophe(spelling):
    assert normalize_kiche(spelling) == "k'ak'"


def test_canonical_glottal_is_ascii():
    assert GLOTTAL == "'"


def test_capital_saltillo():
    assert normalize_kiche("KꞋAKꞋ") == "K'AK'"


def test_digit_seven_only_inside_words():
    assert normalize_kiche("ja7") == "ja'"
    assert normalize_kiche("7 winaq") == "7 winaq"
    assert normalize_kiche("ri 1970 junab'") == "ri 1970 junab'"
    assert normalize_kiche("chi 17") == "chi 17"


def test_lax_vowels_are_folded_by_default():
    assert normalize_kiche("Sib'aläj nïm ri ab'äj") == "Sib'alaj nim ri ab'aj"
    assert normalize_kiche("ÄK'") == "AK'"


def test_lax_vowels_can_be_kept():
    assert normalize_kiche("ab'äj", fold_lax_vowels=False) == "ab'äj"


def test_decomposed_diaeresis_is_folded():
    assert normalize_kiche("äk'") == "ak'"


def test_ejective_digraphs_survive():
    text = "ch'ab'al tz'i' q'ij t'uy"
    assert normalize_kiche(text) == text


def test_whitespace_is_collapsed_and_trimmed():
    assert normalize_kiche("  utz \t  awach\n la  ") == "utz awach la"


def test_invisible_characters_are_removed():
    assert normalize_kiche("u​tz﻿") == "utz"


def test_space_before_punctuation_is_removed():
    assert normalize_kiche("La utz awach ?") == "La utz awach?"
    assert normalize_spanish("Hola , ¿ cómo estás ?") == "Hola, ¿cómo estás?"


def test_detached_word_final_glottal_is_reattached():
    assert normalize_kiche("xuquje ' ri") == "xuquje' ri"


def test_quotes_and_dashes_are_unified():
    assert normalize_spanish("«Hola» —dijo– “ya”…") == '"Hola" -dijo- "ya"...'


def test_acute_on_vowel_is_not_a_glottal():
    assert normalize_kiche("Jesús") == "Jesús"


def test_spanish_keeps_accents_and_inverted_marks():
    assert normalize_spanish("¿Cómo está? ¡Qué niño!") == "¿Cómo está? ¡Qué niño!"


def test_spanish_curly_apostrophe():
    assert normalize_spanish("l’agua") == "l'agua"


def test_spanish_does_not_touch_seven():
    assert normalize_spanish("Tengo 7 años") == "Tengo 7 años"


def test_normalize_dispatch():
    assert normalize("jaʼ", "quc") == "ja'"
    assert normalize("agua ", "spa") == "agua"
    with pytest.raises(ValueError):
        normalize("x", "eng")


def test_empty_input():
    assert normalize_kiche("") == ""
    assert normalize_spanish("") == ""


def test_idempotent():
    for s in GLOTTAL_SPELLINGS + ["Sib'aläj nïm ri ab'äj.", "  ¿La utz awach ?  "]:
        once = normalize_kiche(s)
        assert normalize_kiche(once) == once


def test_match_key_ignores_case_and_punctuation():
    assert match_key("¡Utz awach!") == match_key("utz awach")
    assert match_key("K'ak'.") == "k'ak'"


def test_outside_alphabet_flags_spanish_letters():
    assert outside_alphabet("k'ak' ch'ab'al") == set()
    assert outside_alphabet("Jesucristo") == {"c"}
    assert outside_alphabet("guitarra") == {"g"}


def test_orthography_flags():
    assert "c_for_k" in orthography_flags("cumal ri Dios")
    assert "qu_for_k" in orthography_flags("Are waˈ ri qui biˈ")
    assert "nonascii_glottal" in orthography_flags("kꞌakꞌ")
    assert "lax_vowels_marked" in orthography_flags("ab'äj")
    assert "digit_glottal" in orthography_flags("ja7")
    assert orthography_flags("k'ak' ch'ab'al") == set()
