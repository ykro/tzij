"""Numbers about a dataset version: what went in, what came out, and why.

The manifest is the single source for data/DATASHEET.md and for the model
card's "pairs and data date" panel. Everything is counted in *pairs*; each
pair is two records (es-quc and quc-es), so per-direction counts equal pair
counts by construction.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone

from pipeline.record import DIRECTIONS, RELIGIOUS, SENTENCE, Pair
from pipeline.sources.base import Source
from pipeline.split import FINETUNE_SPLITS, RELIGIOUS_CAP, SplitResult, religious_share

FINETUNE_THRESHOLD = 2000  # clean sentence pairs outside the test set


def build_manifest(
    *,
    version: str,
    sources: list[Source],
    parsed: dict[str, int],
    raw_flags: dict[str, Counter],
    dropped: list[tuple[Pair, str]],
    result: SplitResult,
    git_sha: str,
) -> dict:
    splits = result.by_split()
    by_source: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    by_domain: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    by_kind: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    for split_name, pairs in splits.items():
        for pair in pairs:
            by_source[pair.source_name][split_name] += 1
            by_domain[pair.domain][split_name] += 1
            by_kind[pair.kind][split_name] += 1

    dropped_reasons: dict[str, Counter] = defaultdict(Counter)
    for pair, reason in dropped + result.dropped:
        dropped_reasons[pair.source_name][reason] += 1

    finetune_sentences = sum(
        1 for name in FINETUNE_SPLITS for p in splits[name] if p.kind == SENTENCE
    )
    secular_finetune_sentences = sum(
        1 for name in FINETUNE_SPLITS for p in splits[name] if p.kind == SENTENCE and p.domain != RELIGIOUS
    )
    test_sentences = sum(1 for p in result.test if p.kind == SENTENCE)
    return {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": git_sha,
        "origin": "web",
        "directions": list(DIRECTIONS),
        "sources": [
            {
                "name": s.name, "title": s.title, "owner": s.owner, "url": s.url,
                "license": s.license, "role": s.role, "parsed_pairs": parsed.get(s.name, 0),
                "orthography_flags": dict(raw_flags.get(s.name, {})),
            }
            for s in sources
        ],
        "pairs_by_split": {name: len(pairs) for name, pairs in splits.items()},
        "records_by_split_and_direction": {
            name: {d: len(pairs) for d in DIRECTIONS} for name, pairs in splits.items()
        },
        "pairs_by_source": {k: dict(v) for k, v in sorted(by_source.items())},
        "pairs_by_domain": {k: dict(v) for k, v in sorted(by_domain.items())},
        "pairs_by_kind": {k: dict(v) for k, v in sorted(by_kind.items())},
        "dropped": {k: dict(v) for k, v in sorted(dropped_reasons.items())},
        "religious_cap": RELIGIOUS_CAP,
        "religious_share_of_train_sentences": round(religious_share(result.train), 4),
        "finetune": {
            "threshold_sentence_pairs": FINETUNE_THRESHOLD,
            "sentence_pairs_outside_test": finetune_sentences,
            "non_religious_sentence_pairs_outside_test": secular_finetune_sentences,
            "threshold_met": finetune_sentences >= FINETUNE_THRESHOLD,
        },
        "test": {
            "sentence_pairs": test_sentences,
            "pairs_per_direction": len(result.test),
            "status": "pending_native_review",
        },
    }
