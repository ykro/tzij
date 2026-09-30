"""BOUQuET (Meta FAIR): a multi-domain benchmark with human Spanish–K'iche' translations.

Gated on Hugging Face (the presenter accepted the terms; the token comes from
Secret Manager `hf-token`). Terms: EVALUATION ONLY — never training or
retrieval, and redistributed only privately. So this source is `test` role,
lives only in data/raw (gitignored) and the private bucket, and is excluded
from the evaluation rounds shown on stage (see duel/tzij_duel/deck.py).

Sentence-level dev and test splits are both used as our test data: we never
tune on BOUQuET, so its dev split is just more held-out evaluation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from data.normalize import orthography_flags
from pipeline.record import Pair, guess_kind
from pipeline.secrets import hf_token
from pipeline.sources.base import TEST, Source, download

BASE = "https://huggingface.co/datasets/facebook/bouquet/resolve/main/benchmark_data/sentence_level/"
HOME = "https://huggingface.co/datasets/facebook/bouquet"
LICENSE = "CC-BY-4.0, gated; terms: evaluation only, private redistribution (Meta BOUQuET)"
SPLITS = ("dev", "test")


def fetch(raw: Path) -> None:
    if all((raw / f"{split}.parquet").exists() for split in SPLITS):
        return
    if not hf_token():
        print("  bouquet: skipped (needs HF_TOKEN or Secret Manager `hf-token`)")
        return
    for split in SPLITS:
        download(f"{BASE}{split}/spa_Latn-quc_Latn.parquet", raw / f"{split}.parquet")


_SPEAKER_RE = re.compile(r"^<[^<>]{1,40}:>\s*")


def _unquote(text: str) -> str:
    """Undo CSV escaping ('"… ""dolma"" …"') and drop dialogue speaker tags ("<Yong:> ")."""
    text = _SPEAKER_RE.sub("", (text or "").strip())
    if len(text) > 1 and text.startswith('"') and text.endswith('"') and '""' in text:
        text = text[1:-1].replace('""', '"')
    return text


def parse(raw: Path) -> Iterable[Pair]:
    import pyarrow.parquet as pq

    for split in SPLITS:
        path = raw / f"{split}.parquet"
        if not path.exists():
            continue
        for row in pq.read_table(path).to_pylist():
            if row.get("src_lang") != "spa_Latn" or row.get("tgt_lang") != "quc_Latn":
                continue
            spa, quc = _unquote(row["src_text"]), _unquote(row["tgt_text"])
            yield Pair(
                quc=quc,
                spa=spa,
                source_name="bouquet",
                domain=(row.get("domain") or "general").split("|")[0].strip().replace(" ", "-"),
                license=LICENSE,
                url=HOME,
                kind=guess_kind(quc, spa),
                ref=f"{split}/{row.get('uniq_id', '')}",
                raw_flags=orthography_flags(quc),
            )


SOURCE = Source(
    name="bouquet",
    title="BOUQuET benchmark, Spanish–K'iche' (sentence level, dev + test)",
    owner="Meta FAIR and community translators",
    url=HOME,
    license=LICENSE,
    role=TEST,
    fetch=fetch,
    parse=parse,
)
