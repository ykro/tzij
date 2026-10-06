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


def test_recount_follows_the_files_of_a_derived_version(tmp_path):
    import json

    from pipeline.datasheet import render_datasheet
    from pipeline.manifest import recount

    def write(split, recs):
        both = [r for rec in recs for r in (rec, {**rec, "id": rec["id"].replace("es-quc", "quc-es"),
                                                  "direction": "quc-es"})]
        (tmp_path / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in both))

    write("train", [_rec("s1", "a", "b", domain="everyday"), _rec("r1", "a", "b", domain="religious"),
                    _rec("l1", "a", "b", kind="lexicon", source="cldr_quc", domain="dictionary")])
    write("dev", [_rec("d1", "a", "b", domain="everyday")])
    write("test", [_rec("t1", "a", "b", source="bloom_kiche", domain="education")])
    (tmp_path / "test_niche.jsonl").write_text(json.dumps(_rec("n1", "a", "b")) + "\n")  # es->quc only
    stale = {"version": "20261002-000001", "created_at": "2026-10-02", "git_sha": "x", "sources": [], "dropped": {},
             "religious_cap": 0.3, "pairs_by_split": {"train": 99}, "finetune": {"threshold_sentence_pairs": 2},
             "test": {"sentence_pairs": 1, "pairs_per_direction": 1}, "derived_from": "20261002-000000",
             "niche": {"product": "focus", "niche_pairs_es_quc": 1, "train_records_removed": 2,
                       "religious_pairs_dropped_for_cap": 0, "terminology_added": {}}}
    m = recount(stale, tmp_path)
    assert m["pairs_by_split"] == {"train": 3, "dev": 1, "test": 1, "test_niche": 1}
    assert m["records_by_split_and_direction"]["test_niche"] == {"es-quc": 1, "quc-es": 0}
    assert m["pairs_by_kind"]["lexicon"] == {"train": 1}
    assert m["religious_share_of_train_sentences"] == 0.5
    assert m["finetune"] == {"threshold_sentence_pairs": 2, "sentence_pairs_outside_test": 3,
                             "non_religious_sentence_pairs_outside_test": 2, "threshold_met": True}
    sheet = render_datasheet(m)
    assert "Pairs: train 3, dev 1, test 1, test_niche 1." in sheet and "## Niche (specialty test)" in sheet
