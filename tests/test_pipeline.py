"""Pipeline tests: parsers on tiny fixtures, cleaning, dedupe, split rules, outputs.

All offline: the raw fixtures under tests/fixtures/raw mimic each source's
real file format with a handful of rows.
"""

import csv
import json
from pathlib import Path

import pytest

from pipeline import review
from pipeline.apply_review import apply
from pipeline.clean import rejection_reason
from pipeline.domains import tag_domain
from pipeline.record import LEXICON, RELIGIOUS, SENTENCE, Pair, guess_kind
from pipeline.sources import bloom, coerll, ebible, ud_kiche
from pipeline.split import RELIGIOUS_CAP, dedupe, religious_share, split_by_source

RAW = Path(__file__).parent / "fixtures" / "raw"


def pair(quc, spa, source="s", domain="everyday", kind=SENTENCE):
    return Pair(quc=quc, spa=spa, source_name=source, domain=domain, license="CC0", url="u", kind=kind)


# --- records -----------------------------------------------------------------

def test_pair_becomes_two_records_one_per_direction():
    records = pair("Utz awach.", "Estoy bien.").to_records("train", "clean")
    assert [r["direction"] for r in records] == ["es-quc", "quc-es"]
    assert records[0]["source_text"] == "Estoy bien." and records[0]["target_text"] == "Utz awach."
    assert records[1]["source_text"] == "Utz awach." and records[1]["target_text"] == "Estoy bien."
    for r in records:
        assert r["origin"] == "web" and r["license"] and r["url"]
        assert set(r) >= {"id", "direction", "source_text", "target_text", "source_name",
                          "domain", "split", "status", "origin", "license"}


def test_pair_id_is_stable_and_ignores_punctuation():
    assert pair("Utz awach.", "Estoy bien.").pair_id == pair("utz awach", "estoy bien").pair_id
    assert pair("Utz awach.", "Estoy bien.").pair_id != pair("Utz awach.", "Estoy bien.", source="t").pair_id


def test_normalized_pair_unifies_glottal():
    assert pair("kʼakʼ", "nuevo").normalized().quc == "k'ak'"


@pytest.mark.parametrize("quc,kind", [
    ("Kinb'e pa muxanik.", SENTENCE),
    ("Xinsachik.", SENTENCE),  # one agglutinated word, but a sentence
    ("lej", LEXICON),
    ("koq/ka", LEXICON),
])
def test_guess_kind(quc, kind):
    assert guess_kind(quc, "x") == kind


# --- parsers -----------------------------------------------------------------

def test_ud_parser_keeps_only_sentences_with_spanish_and_tags_bible():
    pairs = list(ud_kiche.parse(RAW / "ud_kiche_iu"))
    assert [(p.quc, p.spa) for p in pairs] == [
        ("Kʼakʼ ri abʼ.", "La hamaca es nueva."),
        ("Ri Dios xubʼan ri kaj.", "Dios hizo el cielo."),
    ]
    assert pairs[0].domain == "everyday" and pairs[1].domain == RELIGIOUS
    assert "nonascii_glottal" in pairs[0].raw_flags


def test_bloom_parser_aligns_translation_groups_and_skips_credits_and_nc_books():
    pairs = list(bloom.parse(RAW / "bloom_kiche"))
    assert [(p.quc, p.spa) for p in pairs] == [
        ("Le tzʼiʼ", "El perro"),
        ("Le tzʼiʼ kawar pa le ja.", "El perro duerme en la casa."),
    ]
    assert all(p.url.endswith("/BOOK1") for p in pairs)  # BOOK2 is CC BY-NC-SA
    assert "Ministerio" in pairs[0].license


def test_bloom_harvest_url():
    base = "https://s3.amazonaws.com/BloomLibraryBooks/a%40b.org%2fBOOKID%2fTitle%2f"
    assert bloom._harvest_base(base) == "https://s3.amazonaws.com/bloomharvest/a%40b.org%2fBOOKID/"


def test_coerll_parser_reads_spanish_edition_tables_only():
    pairs = list(coerll.parse(RAW / "coerll_kiche"))
    assert [(p.quc, p.spa) for p in pairs] == [("Utz awach.", "Estoy bien."), ("tij(o)", "comer")]
    assert pairs[0].kind == SENTENCE and pairs[1].kind == LEXICON


def test_ebible_parser_skips_ranges_and_empty_verses():
    pairs = list(ebible.parse(RAW / "ebible_quctt"))
    assert [p.ref for p in pairs] == ["MAT 1:1", "MAT 1:4"]
    assert all(p.domain == RELIGIOUS for p in pairs)


# --- cleaning ----------------------------------------------------------------

@pytest.mark.parametrize("quc,spa,reason", [
    ("", "hola", "empty"),
    ("Brasil", "Brasil", "untranslated"),
    ("Chaya' <b>ub'i'</b>", "Escribe <b>el nombre</b>", "markup"),
    ("x-in-b'e-k", "COMP-1sg-ir", "linguistic_gloss"),
    ("Utz.", "Estoy muy bien, gracias por preguntar, y usted cómo ha estado todos estos días", "length_ratio"),
    ("el perro de la casa es muy grande", "El perro de la casa es muy grande y bonito", "kiche_side_is_spanish"),
    ("Aqe t-xb'oj kyaqil e' tzaj kyja txin", "Sus amigos volvieron felices a casa", "other_mayan_language"),
])
def test_rejection_reasons(quc, spa, reason):
    assert rejection_reason(pair(quc, spa)) == reason


def test_clean_pairs_pass():
    assert rejection_reason(pair("La utz awach?", "¿Cómo estás?")) is None
    assert rejection_reason(pair("Le tz'i' kawar pa le ja.", "El perro duerme en la casa.")) is None
    # Lexicon entries skip the sentence-shape checks: "rojo" vs "kaq" is fine.
    assert rejection_reason(pair("kaq", "rojo", kind=LEXICON)) is None


def test_domain_refinement_only_for_general_sources():
    assert tag_domain(pair("Yawab' le ala.", "El muchacho está enfermo.")).domain == "health"
    assert tag_domain(pair("Yawab' le ala.", "El muchacho está enfermo.", domain="legal")).domain == "legal"


# --- dedupe and split --------------------------------------------------------

def test_dedupe_keeps_first_source():
    a = pair("Utz awach.", "Estoy bien.", source="first")
    b = pair("utz awach", "estoy bien", source="second")
    kept, dropped = dedupe([a, b])
    assert kept == [a] and dropped == [(b, "duplicate")]


def _many(n, source, domain="everyday", prefix="x"):
    return [pair(f"{prefix} quc {i} ri", f"{prefix} spa {i} el", source=source, domain=domain) for i in range(n)]


def test_split_is_by_source():
    pairs = _many(50, "trainsrc") + _many(20, "testsrc", prefix="t")
    result = split_by_source(pairs, test_sources={"testsrc"})
    assert {p.source_name for p in result.test} == {"testsrc"}
    assert {p.source_name for p in result.train + result.dev} == {"trainsrc"}


def test_leakage_removes_train_pairs_that_repeat_a_test_sentence():
    test_pair = pair("Le tz'i' kawar.", "El perro duerme.", source="testsrc")
    same_kiche = pair("Le tz'i' kawar.", "El perrito duerme.", source="trainsrc")
    same_spanish = pair("Kawar le tz'i'.", "El perro duerme.", source="trainsrc")
    unrelated = pair("Utz awach.", "Estoy bien.", source="trainsrc")
    result = split_by_source([test_pair, same_kiche, same_spanish, unrelated], test_sources={"testsrc"})
    assert result.train + result.dev == [unrelated]
    assert {reason for _, reason in result.dropped} == {"leaks_test_sentence"}


def test_religious_never_in_test_and_capped_in_train():
    secular = _many(70, "a")
    bible = _many(500, "bible", domain=RELIGIOUS, prefix="b")
    bible_in_test = _many(3, "testsrc", domain=RELIGIOUS, prefix="t")
    result = split_by_source(secular + bible + bible_in_test, test_sources={"testsrc"})
    assert all(p.domain != RELIGIOUS for p in result.test)
    assert religious_share(result.train) <= RELIGIOUS_CAP + 1e-9
    assert religious_share(result.train) > RELIGIOUS_CAP - 0.02  # the budget is used
    assert all(p.domain != RELIGIOUS for p in result.dev)
    assert any(reason == "religious_cap" for _, reason in result.dropped)


def test_split_is_deterministic():
    pairs = _many(200, "a") + _many(100, "bible", domain=RELIGIOUS, prefix="b")
    one = split_by_source(list(pairs), test_sources=set())
    two = split_by_source(list(reversed(pairs)), test_sources=set())
    assert {p.pair_id for p in one.dev} == {p.pair_id for p in two.dev}
    assert {p.pair_id for p in one.train} == {p.pair_id for p in two.train}


# --- end to end on fixtures ---------------------------------------------------

@pytest.fixture
def pipeline_output(tmp_path, monkeypatch):
    import shutil

    from pipeline import run as run_module
    from pipeline.sources import bloom as bloom_src
    from pipeline.sources import coerll as coerll_src
    from pipeline.sources import ebible as ebible_src
    from pipeline.sources import ud_kiche as ud_src

    raw = tmp_path / "raw"
    shutil.copytree(RAW, raw)
    sources = [bloom_src.SOURCE, ud_src.SOURCE, coerll_src.SOURCE, ebible_src.SOURCE]
    monkeypatch.setattr(run_module, "SOURCES", sources)
    manifest = run_module.run(raw_root=raw, out_root=tmp_path / "processed", version="v1",
                              gcs_uri=None, only=None, skip_fetch=True,
                              datasheet_path=tmp_path / "DATASHEET.md")
    return tmp_path, manifest


def test_end_to_end_outputs(pipeline_output):
    root, manifest = pipeline_output
    out = root / "processed" / "v1"
    assert (root / "processed" / "LATEST").read_text().strip() == "v1"
    test_records = [json.loads(line) for line in (out / "test.jsonl").read_text().splitlines()]
    assert test_records and all(r["status"] == "pending_native_review" for r in test_records)
    assert all(r["source_name"] == "bloom_kiche" for r in test_records)
    train_records = [json.loads(line) for line in (out / "train.jsonl").read_text().splitlines()]
    assert train_records and all(r["status"] == "clean" for r in train_records)
    assert not any("ʼ" in r["source_text"] + r["target_text"] for r in train_records + test_records)
    assert manifest["pairs_by_split"]["test"] == 2
    datasheet = (root / "DATASHEET.md").read_text()
    assert "Fine-tuning threshold" in datasheet and "`bloom_kiche`" in datasheet


def test_review_export_and_apply_roundtrip(pipeline_output):
    root, _ = pipeline_output
    processed = root / "processed"
    csv_path = root / "review.csv"
    assert review.export(processed, "v1", csv_path) == 2
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    rows[0]["verdict"], rows[1]["verdict"] = "reject", "fix"
    rows[1]["corrected_kiche"] = "Le tzʼiʼ kawar chupam le ja."
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=review.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    tally = apply(processed / "v1" / "test.jsonl", csv_path)
    assert tally == {"rejected": 1, "fixed": 1}
    records = [json.loads(line) for line in (processed / "v1" / "test.jsonl").read_text().splitlines()]
    assert len(records) == 2 and all(r["status"] == "validated" for r in records)
    assert records[0]["target_text"] == "Le tz'i' kawar chupam le ja."
