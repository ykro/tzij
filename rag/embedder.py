"""Embeddings for retrieval: EmbeddingGemma served by the local Ollama.

The index must be built with the *same* embedding model that answers queries
on stage with Wi-Fi off. That's why the model name is stored inside the index
and checked at query time (see rag/store.py), and why we don't use a cloud
embedding API even to build it.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Protocol, Sequence

import httpx

# EmbeddingGemma was trained with task prompts. We compare an input sentence
# with stored source sentences in the same language: a similarity task, so
# query and documents use the same prompt.
TASK_PREFIX = "task: sentence similarity | query: "


class Embedder(Protocol):
    name: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class OllamaEmbedder:
    def __init__(self, model: str | None = None, host: str | None = None, batch_size: int = 64):
        self.name = model or os.environ.get("EMBEDDING_MODEL") or _missing("EMBEDDING_MODEL")
        self.host = (host or os.environ.get("OLLAMA_URL") or os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        if not self.host.startswith("http"):
            self.host = "http://" + self.host
        self.batch_size = batch_size
        self._client = httpx.Client(timeout=300)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = [TASK_PREFIX + t for t in texts[start:start + self.batch_size]]
            response = self._client.post(f"{self.host}/api/embed", json={"model": self.name, "input": batch, "keep_alive": "30m"})
            response.raise_for_status()
            vectors.extend(response.json()["embeddings"])
        return vectors


class CachedEmbedder:
    """Wraps an embedder with an on-disk cache so rebuilding the index is cheap."""

    def __init__(self, inner: Embedder, path: Path):
        self.inner = inner
        self.name = inner.name
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, vector BLOB)")

    def _key(self, text: str) -> str:
        return hashlib.sha1(f"{self.name}\x1f{TASK_PREFIX}\x1f{text}".encode()).hexdigest()

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        import struct

        keys = [self._key(t) for t in texts]
        found: dict[str, list[float]] = {}
        for i in range(0, len(keys), 500):
            chunk = keys[i:i + 500]
            rows = self._db.execute(
                f"SELECT key, vector FROM cache WHERE key IN ({','.join('?' * len(chunk))})", chunk
            ).fetchall()
            for key, blob in rows:
                found[key] = list(struct.unpack(f"{len(blob) // 4}f", blob))
        missing = [(k, t) for k, t in zip(keys, texts) if k not in found]
        if missing:
            vectors = self.inner.embed([t for _, t in missing])
            for (key, _), vector in zip(missing, vectors):
                found[key] = vector
                self._db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?)",
                                 (key, struct.pack(f"{len(vector)}f", *vector)))
            self._db.commit()
        return [found[k] for k in keys]


def _missing(var: str):
    raise RuntimeError(f"{var} is not set (see .env.example)")


class HashingEmbedder:
    """Deterministic character-trigram embeddings, no model at all.

    Only for MOCK_AI=1 (rehearsals without Ollama) and tests: similar spellings land close
    together, which is enough to exercise retrieval end to end. Never used for real rounds.
    """

    name = "hashing-trigram-mock"

    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            padded = f"  {text.lower()}  "
            for i in range(len(padded) - 2):
                digest = hashlib.md5(padded[i:i + 3].encode()).digest()
                vector[int.from_bytes(digest[:4], "little") % self.dimensions] += 1.0
            norm = sum(v * v for v in vector) ** 0.5 or 1.0
            vectors.append([v / norm for v in vector])
        return vectors
