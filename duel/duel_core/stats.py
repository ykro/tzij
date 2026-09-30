"""Latency stats. p50 is what the audience feels; p95 is what breaks a live demo."""

from __future__ import annotations

import math
from collections.abc import Iterable


def percentile(values: Iterable[float], p: float) -> float | None:
    """Linear-interpolated percentile (same as numpy's default). None for no data."""
    xs = sorted(v for v in values if v is not None and not math.isnan(v))
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (p / 100)
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def summarize(values: Iterable[float]) -> dict[str, float | int | None]:
    xs = [v for v in values if v is not None and not math.isnan(v)]
    return {
        "n": len(xs),
        "mean": sum(xs) / len(xs) if xs else None,
        "p50": percentile(xs, 50),
        "p95": percentile(xs, 95),
    }
