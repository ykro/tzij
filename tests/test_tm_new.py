"""evals/tm_new.py: Pontoon strings outside every split, joined through English, never a known text."""

import json
import sqlite3

from evals import tm_new

TMX = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4"><header srclang="en-US"/><body>{}</body></tmx>"""


def tu(project: str, en: str, lang: str, text: str) -> str:
    return (f'<tu tuid="{project}:file:key"><tuv xml:lang="en-US"><seg>{en}</seg></tuv>'
            f'<tuv xml:lang="{lang}"><seg>{text}</seg></tuv></tu>')


def test_build_keeps_only_new_licensed_pairs(tmp_path):
    quc = tmp_path / "quc.tmx"
    es = tmp_path / "es.tmx"
    quc.write_text(TMX.format(
        tu("focus-for-android", "Close tab", "quc", "Chatz'apij k'utjaqb'al")
        + tu("focus-for-android", "Secure connection", "quc", "Chajital t'iqonem")       # known: in the dataset
        + tu("focus-for-android", "Open %1$s", "quc", "Chajaqa' %1$s")                  # markup: software, not language
        + tu("firefox", "Settings", "quc", "Taq jeqeb'al")                              # not a product we use
        + tu("mozilla-monitor-website", "Your data was leaked", "quc", "Xesax le awetamab'al")), encoding="utf-8")
    es.write_text(TMX.format(
        tu("focus-for-android", "Close tab", "es-MX", "Cerrar pestaña")
        + tu("focus-for-android", "Secure connection", "es-MX", "Conexión segura")
        + tu("focus-for-android", "Open %1$s", "es-MX", "Abrir %1$s")
        + tu("firefox", "Settings", "es-MX", "Ajustes")
        + tu("mozilla-monitor-website", "Your data was leaked", "es-MX", "Tus datos se filtraron")), encoding="utf-8")
    dataset = tmp_path / "ds"
    dataset.mkdir()
    for split in tm_new.SPLITS:
        rows = [{"source_text": "Conexión segura", "target_text": "Chajital t'iqonem"}] if split == "test_niche" else []
        (dataset / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    index = tmp_path / "index.sqlite"
    db = sqlite3.connect(index)
    db.execute("CREATE TABLE entries (source_text TEXT, target_text TEXT)")
    db.execute("INSERT INTO entries VALUES ('Tus datos se filtraron.', 'otra')")  # punctuation doesn't hide it
    db.commit()
    db.close()

    pairs = tm_new.build(quc, es, dataset, index)

    assert [(p["source_text"], p["target_text"], p["product_name"]) for p in pairs] == [
        ("Cerrar pestaña", "Chatz'apij k'utjaqb'al", "Firefox Focus")]
    assert pairs[0]["license"].startswith("MPL-2.0") and pairs[0]["direction"] == "es-quc"
    assert pairs[0]["id"] == pairs[0]["pair_id"] + "-es-quc"


def test_tracked_tm_new_pairs_are_licensed_and_unique():
    rows = [json.loads(line) for line in tm_new.OUT.read_text(encoding="utf-8").splitlines()]
    assert rows and len({r["pair_id"] for r in rows}) == len(rows)
    for r in rows:
        assert r["direction"] == "es-quc" and r["license"].startswith("MPL-2.0") and r["product"] in tm_new.PRODUCTS
        assert r["source_text"] and r["target_text"]
