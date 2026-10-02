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

import difflib
import os
import sqlite3
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
    score: float  # cosine similarity (vector), RRF score (hybrid), 1.0 exact, 0.9 fuzzy
    via: str  # "vector", "hybrid", "exact" or "fuzzy"


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


    def variants(self, n: int, seed: int = 2027) -> list[str]:
        """n prompt contexts for multi-prompt MBR: the original first, then the same material with
        the examples shuffled and, every other one, one example and one glossary entry left out."""
        import random

        out = [self.as_prompt_context()]
        for i in range(1, n):
            rng = random.Random(seed + i)
            examples, glossary = list(self.examples), list(self.glossary)
            rng.shuffle(examples)
            if i % 2 == 0:
                if len(examples) > 1:
                    examples.pop(rng.randrange(len(examples)))
                if len(glossary) > 1:
                    glossary.pop(rng.randrange(len(glossary)))
            out.append(RetrievalResult(self.query, self.direction, examples, glossary).as_prompt_context())
        return out


def _ngrams(text: str) -> set[str]:
    words = [w for w in match_key(text).split() if len(w) > 1]
    return set(words) | {" ".join(words[i:i + 2]) for i in range(len(words) - 1)}


def coverage_select(query: str, hits: list[Hit], k: int) -> list[Hit]:
    """Greedy n-gram coverage: each pick adds the example whose source covers the most words and
    bigrams of the input not yet covered (ties: fusion score). Falls back to score order once
    nothing new can be covered. Returned best (most coverage) first."""
    need, chosen, pool = _ngrams(query), [], list(hits)
    while pool and len(chosen) < k:
        best = max(pool, key=lambda h: (len(_ngrams(h.source_text) & need), h.score))
        chosen.append(best)
        pool.remove(best)
        need -= _ngrams(best.source_text)
    return chosen


RRF_K = 60  # reciprocal rank fusion constant (Cormack et al. 2009); 60 is the usual choice


class Retriever:
    """mode="vector": EmbeddingGemma nearest neighbours only.
    mode="hybrid": BM25 (SQLite FTS5) and vectors, fused with reciprocal rank fusion. BM25 catches
    rare exact words (names, K'iche' roots) that embeddings blur; vectors catch paraphrases.
    fuzzy=True also looks up dictionary headwords one edit away (k'ak' vs k'aak', typos).
    order="best_last" puts the most similar example right before the question.
    trigram=True adds a third ranked list from a trigram index (substring matches: K'iche' roots inside
    inflected words). select="coverage" picks examples greedily so together they cover the most
    words and bigrams of the input, instead of the top-k by score."""

    def __init__(self, index_path: Path = DEFAULT_INDEX, embedder: Embedder | None = None,
                 mode: str = "vector", order: str = "best_first", fuzzy: bool = False,
                 trigram: bool = False, select: str = "rank"):
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
        self.has_fts = bool(self.db.execute("SELECT 1 FROM sqlite_master WHERE name = 'entries_fts'").fetchone())
        if mode == "hybrid" and not self.has_fts:
            raise RuntimeError("index has no BM25 table (built before hybrid retrieval): rebuild with `make index`")
        self.has_tri = bool(self.db.execute("SELECT 1 FROM sqlite_master WHERE name = 'entries_tri'").fetchone())
        if trigram and not self.has_tri:
            raise RuntimeError("index has no trigram table: rebuild with `make index`")
        self.mode, self.order, self.fuzzy, self.trigram, self.select = mode, order, fuzzy, trigram, select
        self._headwords: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    # --- candidate generators (entry ids, best first) -----------------------------------------
    def _knn_ids(self, vector: list[float], direction: str, kind: str, n: int) -> list[tuple[int, float]]:
        return self.db.execute(
            """SELECT entry_id, distance FROM vec_entries
               WHERE embedding MATCH ? AND k = ? AND direction = ? AND kind = ? ORDER BY distance""",
            (serialize(vector), n, direction, kind),
        ).fetchall()

    def _bm25_ids(self, query: str, direction: str, kind: str, n: int) -> list[int]:
        words = [w for w in match_key(query).split() if len(w) > 1]
        if not words:
            return []
        fts_query = " OR ".join('"' + w.replace('"', "") + '"' for w in words)
        try:
            rows = self.db.execute(
                """SELECT rowid FROM entries_fts WHERE entries_fts MATCH ? AND direction = ? AND kind = ?
                   ORDER BY bm25(entries_fts) LIMIT ?""",
                (fts_query, direction, kind, n),
            ).fetchall()
        except sqlite3.Error:  # an odd query string must never break a round
            return []
        return [r[0] for r in rows]

    def _tri_ids(self, query: str, direction: str, kind: str, n: int) -> list[int]:
        words = [w for w in match_key(query).split() if len(w) >= 3]
        if not words:
            return []
        fts_query = " OR ".join('"' + w.replace('"', "") + '"' for w in words)
        try:
            rows = self.db.execute(
                """SELECT rowid FROM entries_tri WHERE entries_tri MATCH ? AND direction = ? AND kind = ?
                   ORDER BY bm25(entries_tri) LIMIT ?""",
                (fts_query, direction, kind, n),
            ).fetchall()
        except sqlite3.Error:
            return []
        return [r[0] for r in rows]

    def _hits(self, ids: list[int], scores: dict[int, float], via: str) -> list[Hit]:
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        rows = {r[0]: r[1:] for r in self.db.execute(
            f"SELECT id, source_text, target_text, kind, source_name, domain FROM entries WHERE id IN ({placeholders})",
            ids).fetchall()}
        return [Hit(*rows[i], round(scores.get(i, 0.0), 4), via) for i in ids if i in rows]

    def _ranked(self, vector, query: str, direction: str, kind: str, k: int) -> list[Hit]:
        n = max(20, 3 * k)
        knn = self._knn_ids(vector, direction, kind, n)
        if self.mode == "vector":
            ids = [i for i, _ in knn][:k]
            return self._hits(ids, {i: 1 - d for i, d in knn}, "vector")
        fused: dict[int, float] = {}
        for rank, (i, _) in enumerate(knn):
            fused[i] = fused.get(i, 0.0) + 1 / (RRF_K + rank + 1)
        for rank, i in enumerate(self._bm25_ids(query, direction, kind, n)):
            fused[i] = fused.get(i, 0.0) + 1 / (RRF_K + rank + 1)
        if self.trigram:
            for rank, i in enumerate(self._tri_ids(query, direction, kind, n)):
                fused[i] = fused.get(i, 0.0) + 1 / (RRF_K + rank + 1)
        ranked = sorted(fused, key=fused.get, reverse=True)
        if self.select == "coverage" and kind == "sentence":
            hits = self._hits(ranked[:n], fused, "hybrid")
            return coverage_select(query, hits, k)
        return self._hits(ranked[:k], fused, "hybrid")

    # --- glossary ---------------------------------------------------------------------------------
    def _headwords_for(self, direction: str) -> list[str]:
        if direction not in self._headwords:
            self._headwords[direction] = [r[0] for r in self.db.execute(
                "SELECT DISTINCT headword FROM glossary WHERE direction = ?", (direction,)).fetchall()]
        return self._headwords[direction]

    def _glossary_rows(self, direction: str, headword: str) -> list[tuple]:
        return self.db.execute(
            """SELECT e.source_text, e.target_text, e.kind, e.source_name, e.domain
               FROM glossary g JOIN entries e ON e.id = g.entry_id
               WHERE g.direction = ? AND g.headword = ? LIMIT 3""",
            (direction, headword),
        ).fetchall()

    def _exact_glossary(self, text: str, direction: str, k: int) -> list[Hit]:
        words = match_key(text).split()
        # Whole input, word bigrams, then single words: longest match first.
        candidates = [" ".join(words)] + [" ".join(words[i:i + 2]) for i in range(len(words) - 1)] + words
        hits, seen, matched = [], set(), set()
        for headword in candidates:
            rows = self._glossary_rows(direction, headword)
            if rows:
                matched.add(headword)
            for s, t, kd, src, dom in rows:
                if (s, t) not in seen:
                    seen.add((s, t))
                    hits.append(Hit(s, t, kd, src, dom, 1.0, "exact"))
        if self.fuzzy:
            vocabulary = self._headwords_for(direction)
            for word in words:
                if word in matched or len(word) < 4:
                    continue
                for close in difflib.get_close_matches(word, vocabulary, n=1, cutoff=0.85):
                    for s, t, kd, src, dom in self._glossary_rows(direction, close):
                        if (s, t) not in seen:
                            seen.add((s, t))
                            hits.append(Hit(s, t, kd, src, dom, 0.9, "fuzzy"))
        return hits[:k]

    def retrieve(self, text: str, direction: str, k: int = 8, exclude: set[str] | None = None) -> RetrievalResult:
        """`exclude`: texts that must not appear on either side of a hit, e.g. the training sentence
        and its translation when building retrieval-augmented training data (otherwise the answer
        would be in the prompt, through the pair itself or a duplicate with the same translation)."""
        with self._lock:
            return self._retrieve(text, direction, k, exclude or set())

    def _retrieve(self, text: str, direction: str, k: int, exclude: set[str] = frozenset()) -> RetrievalResult:
        if direction not in SOURCE_LANG:
            raise ValueError(f"direction must be one of {sorted(SOURCE_LANG)}")
        query = normalize(text, SOURCE_LANG[direction])
        result = RetrievalResult(query=query, direction=direction)
        if not query:
            return result
        vector = self.embedder.embed([query])[0]
        extra = 4 if exclude else 0  # ask for more so excluded hits don't shrink the context
        banned = {match_key(x) for x in exclude}  # ignore case and punctuation: "b'e." == "b'e"

        def keep(hits: list[Hit]) -> list[Hit]:
            return [h for h in hits if match_key(h.source_text) not in banned and match_key(h.target_text) not in banned]

        result.examples = keep(self._ranked(vector, query, direction, "sentence", k + extra))[:k]
        if self.order == "best_last":
            result.examples.reverse()
        glossary = keep(self._exact_glossary(query, direction, k + extra))[:k]
        seen = {(h.source_text, h.target_text) for h in glossary}
        for hit in keep(self._ranked(vector, query, direction, "lexicon", k + extra)):
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
