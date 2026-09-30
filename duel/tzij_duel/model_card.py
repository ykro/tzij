"""The model card panel on the presenter screen: what David knows and since when."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .deck import latest_dataset
from .settings import Settings

# Short Spanish names for the panel on stage (full titles live in data/SOURCES.md).
SOURCE_LABELS = {
    "bloom_kiche": "Libros infantiles de Bloom Library (MINEDUC)",
    "bouquet": "BOUQuET (Meta), solo evaluación",
    "ud_kiche_iu": "Ejemplos del vocabulario ALMG (UD Kʼicheʼ-IU)",
    "coerll_kiche": "Curso Chqetaʼmaj le qachʼabʼal Kʼicheʼ (UT Austin)",
    "udhr_ohchr": "Declaración Universal de Derechos Humanos",
    "pontoon_mozilla": "Firefox en Kʼicheʼ (Mozilla Pontoon)",
    "ebible_quctt": "Nuevo Testamento de Totonicapán (máx. 30 %)",
    "gatitos": "Léxico GATITOS (Google)",
    "panlex": "PanLex",
    "wiktionary_es": "Wikcionario",
}

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def _index_meta(path: Path) -> dict:
    if not path.exists():
        return {}
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
        meta["entries"] = db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        return meta
    except sqlite3.Error:
        return {}
    finally:
        db.close()


def model_card(s: Settings) -> dict:
    card: dict = {"david_model": s.david_model or None, "goliath_model": s.gemini_model or None,
                  "retrieval": True, "sources": None, "pairs": None, "data_date": None,
                  "dataset_version": None, "test_pairs": None, "index_entries": None}
    dataset = latest_dataset(s.processed_dir)
    if dataset and (dataset / "manifest.json").exists():
        m = json.loads((dataset / "manifest.json").read_text())
        created = datetime.fromisoformat(m["created_at"])
        used = [src for src in m["sources"] if src["name"] in m["pairs_by_source"]]
        card |= {
            "sources": len(used),
            "source_names": [SOURCE_LABELS.get(src["name"], src["title"]) for src in used],
            "train_sources": [SOURCE_LABELS.get(src["name"], src["title"]) for src in used if src["role"] == "train"],
            "test_sources": [SOURCE_LABELS.get(src["name"], src["title"]) for src in used if src["role"] == "test"],
            "pairs": sum(m["pairs_by_split"].values()),
            "test_pairs": m["pairs_by_split"].get("test"),
            "data_date": f"{MONTHS[created.month - 1]} {created.year}",
            "dataset_version": m["version"],
            "finetune_threshold_met": m["finetune"]["threshold_met"],
        }
    index = _index_meta(s.rag_index)
    card["index_entries"] = index.get("entries")
    card["embedding_model"] = index.get("embedding_model")
    return card
