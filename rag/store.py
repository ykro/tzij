"""The retrieval index: one SQLite file with sqlite-vec, fully offline.

Tables
  meta        embedding model and dataset version the index was built from
  entries     every retrievable pair, per direction (source text -> target text)
  glossary    exact lookup of dictionary headwords (embeddings are weak on single words)
  vec_entries sqlite-vec virtual table: one vector per entry, filterable by direction and kind
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    record_id TEXT, direction TEXT, kind TEXT,
    source_text TEXT, target_text TEXT,
    source_name TEXT, domain TEXT, license TEXT, url TEXT
);
CREATE TABLE IF NOT EXISTS glossary (direction TEXT, headword TEXT, entry_id INTEGER);
CREATE INDEX IF NOT EXISTS glossary_lookup ON glossary (direction, headword);
"""


def connect(path: Path) -> sqlite3.Connection:
    # The duel service queries from worker threads; Retriever serializes access with a lock.
    db = sqlite3.connect(path, check_same_thread=False)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    return db


def create(path: Path, dimensions: int) -> sqlite3.Connection:
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = connect(path)
    db.executescript(SCHEMA)
    db.execute(
        "CREATE VIRTUAL TABLE vec_entries USING vec0("
        f"entry_id INTEGER PRIMARY KEY, embedding float[{dimensions}] distance_metric=cosine, "
        "direction TEXT, kind TEXT)"
    )
    return db


def serialize(vector: list[float]) -> bytes:
    return sqlite_vec.serialize_float32(vector)
