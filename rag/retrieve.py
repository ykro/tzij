"""retrieve(text, direction, k): the context David gets before translating.

Two lookups, because they fail differently:
  * examples — nearest sentence pairs by embedding (how is this *said*?)
  * glossary — dictionary entries: exact headword matches for the input's
    words first (embeddings are unreliable for single words), then nearest
    dictionary entries by embedding.
The input is normalized with the same rules as the data, so "kʼakʼ" typed on
a phone finds "k'ak'".
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from data.normalize import match_key, normalize
from rag.embedder import Embedder, OllamaEmbedder
from rag.store import connect, serialize

DEFAULT_INDEX = Path(__file__).resolve().parent / "index" / "tzij.sqlite"
SOURCE_LANG = {"es-quc": "spa", "quc-es": "quc"}


@dataclass
class Hit:
    source_text: str
    target_text: str
    kind: str
    source_name: str
    domain: str
    score: float  # cosine similarity, 1.0 for exact glossary matches
    via: str  # "vector" or "exact"


@dataclass
class RetrievalResult:
    query: str
    direction: str
    examples: list[Hit] = field(default_factory=list)
    glossary: list[Hit] = field(default_factory=list)

    def as_prompt_context(self) -> str:
        """Plain-text block to paste into David's prompt."""
        lines = []
        if self.glossary:
            lines.append("Glosario:")
            lines += [f"- {h.source_text} = {h.target_text}" for h in self.glossary]
        if self.examples:
            lines.append("Ejemplos:")
            lines += [f"- {h.source_text} => {h.target_text}" for h in self.examples]
        return "\n".join(lines)


class Retriever:
    def __init__(self, index_path: Path = DEFAULT_INDEX, embedder: Embedder | None = None):
        if not Path(index_path).exists():
            raise FileNotFoundError(f"retrieval index not found: {index_path} (run `make index`)")
        self.db = connect(index_path)
        meta = dict(self.db.execute("SELECT key, value FROM meta").fetchall())
        self.embedder = embedder or OllamaEmbedder()
        if meta.get("embedding_model") != self.embedder.name:
            raise RuntimeError(
                f"index built with {meta.get('embedding_model')!r} but queries use {self.embedder.name!r}; "
                "rebuild with `make index`"
            )
        self.dataset_version = meta.get("dataset_version")
        self._lock = threading.Lock()

    def _knn(self, vector: list[float], direction: str, kind: str, k: int) -> list[Hit]:
        rows = self.db.execute(
            """
            SELECT e.source_text, e.target_text, e.kind, e.source_name, e.domain, v.distance
            FROM vec_entries v JOIN entries e ON e.id = v.entry_id
            WHERE v.embedding MATCH ? AND k = ? AND v.direction = ? AND v.kind = ?
            ORDER BY v.distance
            """,
            (serialize(vector), k, direction, kind),
        ).fetchall()
        return [Hit(s, t, kd, src, dom, round(1 - dist, 4), "vector") for s, t, kd, src, dom, dist in rows]

    def _exact_glossary(self, text: str, direction: str, k: int) -> list[Hit]:
        words = match_key(text).split()
        # Whole input, word bigrams, then single words: longest match first.
        candidates = [" ".join(words)] + [" ".join(words[i:i + 2]) for i in range(len(words) - 1)] + words
        hits, seen = [], set()
        for headword in candidates:
            rows = self.db.execute(
                """SELECT e.source_text, e.target_text, e.kind, e.source_name, e.domain
                   FROM glossary g JOIN entries e ON e.id = g.entry_id
                   WHERE g.direction = ? AND g.headword = ? LIMIT 3""",
                (direction, headword),
            ).fetchall()
            for s, t, kd, src, dom in rows:
                if (s, t) not in seen:
                    seen.add((s, t))
                    hits.append(Hit(s, t, kd, src, dom, 1.0, "exact"))
        return hits[:k]

    def retrieve(self, text: str, direction: str, k: int = 8) -> RetrievalResult:
        with self._lock:
            return self._retrieve(text, direction, k)

    def _retrieve(self, text: str, direction: str, k: int) -> RetrievalResult:
        if direction not in SOURCE_LANG:
            raise ValueError(f"direction must be one of {sorted(SOURCE_LANG)}")
        query = normalize(text, SOURCE_LANG[direction])
        result = RetrievalResult(query=query, direction=direction)
        if not query:
            return result
        vector = self.embedder.embed([query])[0]
        result.examples = self._knn(vector, direction, "sentence", k)
        glossary = self._exact_glossary(query, direction, k)
        seen = {(h.source_text, h.target_text) for h in glossary}
        for hit in self._knn(vector, direction, "lexicon", k):
            if len(glossary) >= k:
                break
            if (hit.source_text, hit.target_text) not in seen:
                glossary.append(hit)
        result.glossary = glossary
        return result


@lru_cache(maxsize=1)
def _default_retriever() -> Retriever:
    return Retriever(Path(os.environ.get("RAG_INDEX", DEFAULT_INDEX)))


def retrieve(text: str, direction: str, k: int = 8) -> RetrievalResult:
    """Module-level API used by the duel service."""
    return _default_retriever().retrieve(text, direction, k)


if __name__ == "__main__":
    import sys

    direction = sys.argv[2] if len(sys.argv) > 2 else "es-quc"
    print(retrieve(sys.argv[1], direction).as_prompt_context())
