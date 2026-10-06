"""Where the current dataset lives: data/processed/LATEST points at the version in use."""

from __future__ import annotations

from pathlib import Path


def latest_dataset(processed: Path) -> Path | None:
    pointer = processed / "LATEST"
    if not pointer.exists():
        return None
    path = processed / pointer.read_text().strip()
    return path if path.exists() else None
