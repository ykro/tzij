"""The pre-registered niche: sentences built on vocabulary from our licensed dictionaries
that is rare in general web K'iche'.

Definition (see evals/niche.md, written and committed before any per-sentence test result
was looked at):

- A **content word** is a token of the source sentence (normalized with data/normalize.py,
  then `match_key`) that is not among the `FUNCTION_TOP` most frequent word types of the
  reference corpus of its language.
- A content word is **in our dictionaries** when a single-word entry of the training
  lexicon (`kind=lexicon` records of the train split: GATITOS, COERLL vocabulary, PanLex,
  Pontoon terms, Wiktionary) has exactly that normalized key on the same-language side.
- It is **rare in web K'iche'** when the K'iche' side occurs at most `F_MAX` times in the
  web K'iche' reference corpus. For a K'iche' word that is the word itself; for a Spanish
  word it is every K'iche' rendering the dictionary gives (the most frequent one decides,
  so a word with one common rendering is not rare).
- A sentence is **in the niche** when it has at least `N_MIN` distinct such words.

Reference corpus ("general web K'iche'"): the whole Totonicapán New Testament (the most
widely published K'iche' text on the web), the monolingual web K'iche' of
`data/monolingual/quc.jsonl` (Wikipedia on Incubator, Space Scoop) and the K'iche' side of
the Pontoon and UDHR pairs. Dictionaries, courses and test sources are left out of it on
purpose: "rare on the web" must not be measured with the dictionary itself or the test set.

The thresholds were chosen on dev only, without any model output (`python -m pipeline.niche
grid`). The frozen member list (`evals/niche_members.json`) is what evaluation and the stage
use, so new data or synthetic pairs never move the slice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.normalize import match_key, normalize  # noqa: E402

FUNCTION_TOP = 150
N_MIN = 1   # chosen on dev, see evals/niche.md
F_MAX = 0   # chosen on dev, see evals/niche.md
MAX_NGRAM = 4
MEMBERS = ROOT / "evals" / "niche_members.json"
REFERENCE_SOURCES = ("pontoon_mozilla", "udhr_ohchr")
_WORD_RE = re.compile(r"[^\W\d_][\w']*", re.UNICODE)


def tokens(text: str, lang: str) -> list[str]:
    key = match_key(normalize(text, lang))
    return [t.strip("'") if lang == "spa" else t.lstrip("'") for t in _WORD_RE.findall(key)]


@dataclass
class NicheModel:
    """Everything the definition needs, built once from frozen inputs."""

    quc_ngrams: Counter
    function_words: dict[str, set[str]]
    es_to_quc: dict[str, set[tuple[str, ...]]]
    quc_words: set[str]
    reference_sha: str

    def freq(self, quc_phrase: tuple[str, ...]) -> int:
        return self.quc_ngrams.get(quc_phrase, 0)

    def niche_words(self, text: str, direction: str, f_max: int = F_MAX) -> list[str]:
        lang = "spa" if direction == "es-quc" else "quc"
        out: list[str] = []
        for w in dict.fromkeys(tokens(text, lang)):
            if w in self.function_words[lang] or len(w) < 2:
                continue
            if lang == "quc":
                if w in self.quc_words and self.freq((w,)) <= f_max:
                    out.append(w)
            else:
                renderings = self.es_to_quc.get(w)
                if renderings and max(self.freq(r) for r in renderings) <= f_max:
                    out.append(w)
        return out

    def is_member(self, text: str, direction: str, n_min: int = N_MIN, f_max: int = F_MAX) -> bool:
        return len(self.niche_words(text, direction, f_max)) >= n_min


def _reference_lines(dataset: Path) -> tuple[list[str], list[str]]:
    quc, spa = [], []
    raw = ROOT / "data" / "raw" / "ebible_quctt"
    quc += [l for l in (raw / "quc-quctt.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    spa += [l for l in (raw / "spa-spablm.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    mono = ROOT / "data" / "monolingual" / "quc.jsonl"
    for line in mono.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["source_name"] in ("incubator_quc", "spacescoop_quc"):
            quc.append(r["quc"])
    for split in ("train", "dev"):
        for line in (dataset / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["source_name"] in REFERENCE_SOURCES and r["kind"] == "sentence" and r["direction"] == "es-quc":
                spa.append(r["source_text"])
                quc.append(r["target_text"])
    return quc, spa


def build(dataset: Path) -> NicheModel:
    quc_lines, spa_lines = _reference_lines(dataset)
    digest = hashlib.sha256("\n".join(quc_lines).encode()).hexdigest()[:16]
    ngrams: Counter = Counter()
    quc_unigrams: Counter = Counter()
    for line in quc_lines:
        toks = tokens(line, "quc")
        quc_unigrams.update(toks)
        for n in range(1, MAX_NGRAM + 1):
            ngrams.update(tuple(toks[i:i + n]) for i in range(len(toks) - n + 1))
    spa_unigrams: Counter = Counter(t for line in spa_lines for t in tokens(line, "spa"))
    function_words = {"quc": {w for w, _ in quc_unigrams.most_common(FUNCTION_TOP)},
                      "spa": {w for w, _ in spa_unigrams.most_common(FUNCTION_TOP)}}

    es_to_quc: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    quc_words: set[str] = set()
    for line in (dataset / "train.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["kind"] != "lexicon":
            continue
        es, quc = (r["source_text"], r["target_text"]) if r["direction"] == "es-quc" else (r["target_text"], r["source_text"])
        es_t, quc_t = tokens(es, "spa"), tokens(quc, "quc")
        if not es_t or not quc_t:
            continue
        if len(es_t) == 1:
            es_to_quc[es_t[0]].add(tuple(quc_t[:MAX_NGRAM]))
        if len(quc_t) == 1:
            quc_words.add(quc_t[0])
    return NicheModel(ngrams, function_words, dict(es_to_quc), quc_words, digest)


def _sentences(dataset: Path, split: str) -> list[dict]:
    rows = [json.loads(l) for l in (dataset / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()]
    return [r for r in rows if r["kind"] == "sentence" and r["status"] not in ("rejected", "auto_rejected")]


def grid(dataset: Path) -> list[dict]:
    """Dev coverage for each candidate threshold pair. No model output is used."""
    model = build(dataset)
    dev = _sentences(dataset, "dev")
    out = []
    for n_min in (1, 2, 3):
        for f_max in (0, 1, 2, 5, 10, 20):
            row = {"n_min": n_min, "f_max": f_max}
            for d in ("es-quc", "quc-es"):
                sub = [r for r in dev if r["direction"] == d]
                row[d] = sum(model.is_member(r["source_text"], d, n_min, f_max) for r in sub)
                row[f"{d}_n"] = len(sub)
            out.append(row)
    return out


def freeze(dataset: Path) -> dict:
    """Write the member list of the test split with the chosen thresholds."""
    model = build(dataset)
    members = [[r["pair_id"], r["direction"]] for r in _sentences(dataset, "test")
               if model.is_member(r["source_text"], r["direction"])]
    payload = {"definition": "evals/niche.md", "dataset": dataset.name, "n_min": N_MIN, "f_max": F_MAX,
               "function_top": FUNCTION_TOP, "reference_sha256_16": model.reference_sha,
               "members": sorted(members)}
    MEMBERS.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    return payload


def load_members(path: Path = MEMBERS) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    return {(p, d) for p, d in json.loads(path.read_text(encoding="utf-8"))["members"]}


def _latest(processed: Path) -> Path:
    return processed / (processed / "LATEST").read_text().strip()


def cli() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["grid", "freeze"])
    ap.add_argument("--dataset", type=Path, default=None)
    args = ap.parse_args()
    dataset = args.dataset or _latest(ROOT / "data" / "processed")
    if args.command == "grid":
        print("| N_MIN | F_MAX | dev es→quc | dev quc→es |")
        print("| ---: | ---: | ---: | ---: |")
        for r in grid(dataset):
            print(f"| {r['n_min']} | {r['f_max']} | {r['es-quc']}/{r['es-quc_n']} | {r['quc-es']}/{r['quc-es_n']} |")
    else:
        p = freeze(dataset)
        print(f"{len(p['members'])} test records in the niche -> {MEMBERS.relative_to(ROOT)}")


if __name__ == "__main__":
    cli()
