"""The niche: a Pontoon product held out as a translation-memory test (evals/niche.md)."""

from evals.niche_report import compare, term_compare
from pipeline.niche import products_of, recap_religious, terms_for, tokens


def _rec(pid, es, quc, kind="sentence", source="pontoon_mozilla", ref="", domain="software"):
    return {"id": f"{pid}-es-quc", "pair_id": pid, "direction": "es-quc", "source_text": es, "target_text": quc,
            "kind": kind, "source_name": source, "ref": ref, "domain": domain}


def test_tokens_normalize_glottal_and_case():
    assert tokens("Kutij IXIM ri ak’.", "quc") == ["kutij", "ixim", "ri", "ak'"]
    assert tokens("¿Dónde está el maíz?", "spa") == ["dónde", "está", "el", "maíz"]


def test_products_come_from_the_english_pivot():
    index = {"Add search engine": {"focus-for-android"}}
    assert products_of(_rec("p1", "Agregar", "Chaya'", ref="Add search engine"), index) == {"focus-for-android"}
    assert products_of(_rec("p2", "x", "y", ref="unknown"), index) == set()


def test_terms_need_the_spanish_in_the_source_and_the_kiche_in_the_reference():
    train = [_rec("l1", "motor de búsqueda", "ch'ich' rech tzukub'al", kind="lexicon", source="gatitos"),
             _rec("l2", "de", "rech", kind="lexicon", source="gatitos"),  # no content word
             _rec("l3", "pestaña", "uxaq", kind="lexicon", source="gatitos")]  # not in the source
    test = [_rec("t1", "Agregar otro motor de búsqueda", "Chaya' jun chik ch'ich' rech tzukub'al")]
    assert terms_for(test, train, {}) == {"t1-es-quc": [["motor de búsqueda", "ch'ich' rech tzukub'al"]]}


def test_religious_cap_is_reapplied():
    train = [_rec(f"s{i}", "a", "b", domain="everyday") for i in range(7)]
    train += [_rec(f"r{i}", "a", "b", domain="religious") for i in range(5)]
    kept, dropped = recap_religious(train)
    assert dropped == 2 and sum(r["domain"] == "religious" for r in kept) == 3  # 3 / 10 = 30%


def _rows(texts, refs):
    from duel_core import chrf_pp
    return {str(i): {"text": t, "reference": r, "status": "ok", "chrf": chrf_pp(t, r)}
            for i, (t, r) in enumerate(zip(texts, refs))}


def test_compare_and_term_accuracy_verdicts():
    refs = [f"chaya' jun chik ch'ich' {i}" for i in range(30)]
    good, bad = _rows(refs, refs), _rows(["jun jastaq"] * 30, refs)
    ids = [str(i) for i in range(30)]
    c = compare(ids, good, bad, seed=1)
    assert c["verdict"] == "David" and c["ci"][0] > 0 and c["win_rate"] == 1.0
    assert compare(ids, bad, good, seed=1)["verdict"] == "Goliath"
    assert compare(ids, good, good, seed=1)["verdict"] == "empate"
    terms = {i: [["agregar", "chaya'"]] for i in ids}
    t = term_compare(ids, good, bad, terms)
    assert t["david"] == 1.0 and t["goliath"] == 0.0 and t["ci"][0] > 0
