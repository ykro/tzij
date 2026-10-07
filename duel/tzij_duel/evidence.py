"""Help to judge a typed phrase, which has no example's correct translation.

Two honest aids, both from licensed data only:

  reference(text, direction)  if the phrase is in the licensed data (the test sets, David's
                              translation memory or the dictionary), its correct translation: then
                              the page measures both sides against it, as with the examples.
  evidence(text, direction, outputs)
                              otherwise, what lets a person judge: the closest phrases in the
                              translation memory, translated by people, and, in each side's
                              translation, the words that also appear in those human translations
                              (the memory's terminology). It is a hint, not a score.

Why not a dictionary check: on the examples, the share of words found in the dictionary did not
follow which translation was right (Goliath's wrong answers often use more dictionary words), so it
would mislead.

Runs next to the retrieval index, on David's GPU service (or in-process in tests).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from data.normalize import match_key
from rag.retrieve import Retriever

SOURCE_LABEL = {
    "pontoon_mozilla": "Mozilla Pontoon",
    "bloom_kiche": "Bloom Library",
    "coerll_kiche": "COERLL (UT Austin)",
    "ud_kiche_iu": "UD Kʼicheʼ (Indiana University)",
    "ebible_quctt": "Nuevo Testamento en Kʼicheʼ (eBible)",
    "udhr_ohchr": "Declaración Universal de Derechos Humanos (OHCHR)",
    "cldr_quc": "Unicode CLDR",
    "gatitos": "GATITOS (Google Research)",
    "floresmayas_quc": "Glosario FLORES-Mayas",
    "panlex": "PanLex",
    "wiktionary_es": "Wikcionario",
}
# BOUQuET may be used for evaluation only, never shown.
HIDDEN_SOURCES = {"bouquet"}
WORD_RE = re.compile(r"[\w'ʼ’]+", re.UNICODE)
MEMORY_SHOWN = 3


def label(source_name: str) -> str:
    return SOURCE_LABEL.get(source_name, source_name)


class Evidence:
    def __init__(self, retriever: Retriever | None, references: Path | None = None) -> None:
        self.retriever = retriever
        # (direction, match_key(source)) -> correct translation, test sets first.
        self._refs: dict[tuple[str, str], dict] = {}
        if references is not None and references.exists():
            for line in references.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                if r.get("source_name") in HIDDEN_SOURCES:
                    continue
                self._refs.setdefault((r["direction"], match_key(r["source_text"])), {
                    "text": r["target_text"], "source": label(r["source_name"]), "license": r.get("license", ""),
                    "url": r.get("url", ""), "where": "prueba"})
        if retriever is not None:
            for kind, src, tgt, name, lic, url, direction in retriever.db.execute(
                    "SELECT kind, source_text, target_text, source_name, license, url, direction FROM entries"):
                if name in HIDDEN_SOURCES:
                    continue
                self._refs.setdefault((direction, match_key(src)), {
                    "text": tgt, "source": label(name), "license": lic or "", "url": url or "",
                    "where": "diccionario" if kind == "lexicon" else "memoria"})

    def reference(self, text: str, direction: str) -> dict | None:
        """The licensed correct translation of exactly this phrase (ignoring case and punctuation), if any."""
        key = match_key(text)
        return dict(self._refs[(direction, key)]) if key and (direction, key) in self._refs else None

    def memory(self, text: str, direction: str) -> list[dict]:
        if self.retriever is None:
            return []
        found = self.retriever.retrieve(text, direction, MEMORY_SHOWN)
        hits = sorted(found.examples, key=lambda h: h.score, reverse=True)[:MEMORY_SHOWN]
        return [{"source_text": h.source_text, "target_text": h.target_text, "source": label(h.source_name)}
                for h in hits if h.source_name not in HIDDEN_SOURCES]

    def marked(self, translation: str, memory: list[dict]) -> list[dict]:
        """Each word of a translation, marked when it also appears in the memory's human translations."""
        known = {match_key(w) for m in memory for w in WORD_RE.findall(m["target_text"])}
        return [{"word": w, "in_memory": match_key(w) in known} for w in WORD_RE.findall(translation)]

    def evidence(self, text: str, direction: str, outputs: dict[str, str]) -> dict:
        memory = self.memory(text, direction)
        return {"memory": memory, "words": {side: self.marked(out, memory) for side, out in outputs.items() if out}}
