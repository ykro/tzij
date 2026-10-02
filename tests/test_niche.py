"""The pre-registered niche definition and the paired bootstrap comparison."""

from collections import Counter

from evals.niche_report import compare
from pipeline.niche import NicheModel, tokens


def _model() -> NicheModel:
    ngrams = Counter({("ja",): 50, ("ixim",): 0, ("uchaq'",): 3})
    return NicheModel(
        quc_ngrams=ngrams,
        function_words={"quc": {"ri", "le", "are'"}, "spa": {"el", "la", "de", "con"}},
        es_to_quc={"maíz": {("ixim",)}, "casa": {("ja",)}, "hermano": {("chaq'",), ("uchaq'",)}},
        quc_words={"ixim", "ja"},
        reference_sha="test",
    )


def test_tokens_normalize_glottal_and_case():
    assert tokens("Kutij IXIM ri ak’.", "quc") == ["kutij", "ixim", "ri", "ak'"]
    assert tokens("¿Dónde está el maíz?", "spa") == ["dónde", "está", "el", "maíz"]


def test_kiche_word_rare_only_if_unattested():
    m = _model()
    assert m.niche_words("Kutij ixim ri ak'.", "quc-es") == ["ixim"]
    assert m.niche_words("Le ja.", "quc-es") == []  # 50 times on the web: not rare


def test_spanish_word_uses_its_most_frequent_rendering():
    m = _model()
    assert m.niche_words("El maíz con la casa.", "es-quc") == ["maíz"]
    # one rendering (uchaq') occurs 3 times: with F_MAX=0 "hermano" is not rare, with 3 it is
    assert m.niche_words("Mi hermano.", "es-quc", f_max=0) == []
    assert m.niche_words("Mi hermano.", "es-quc", f_max=3) == ["hermano"]
    assert m.is_member("El maíz.", "es-quc", n_min=1, f_max=0)
    assert not m.is_member("El maíz.", "es-quc", n_min=2, f_max=0)


def _rows(texts, refs):
    from duel_core import chrf_pp
    return {str(i): {"text": t, "reference": r, "status": "ok", "chrf": chrf_pp(t, r)}
            for i, (t, r) in enumerate(zip(texts, refs))}


def test_compare_verdicts():
    refs = [f"le ak' kutij ixim {i}" for i in range(30)]
    good = _rows(refs, refs)
    bad = _rows(["jun jastaq"] * 30, refs)
    ids = [str(i) for i in range(30)]
    c = compare(ids, good, bad, seed=1)
    assert c["verdict"] == "David" and c["ci"][0] > 0 and c["win_rate"] == 1.0
    assert compare(ids, bad, good, seed=1)["verdict"] == "Goliath"
    tie = compare(ids, good, good, seed=1)
    assert tie["verdict"] == "empate" and tie["ties"] == 30
