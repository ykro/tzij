"""What every data source looks like to the pipeline.

A source knows three things: where its data lives (`fetch`), how to turn the
raw files into pairs (`parse`), and its paperwork (license, owner, role).
`role` is decided here, per source, never per sentence: test sources are held
out entirely so no sentence, book or lesson leaks into training or retrieval.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import httpx

from pipeline.record import Pair

USER_AGENT = "tzij-data-pipeline/0.1 (+research; Spanish-K'iche' translation demo)"

TRAIN = "train"  # usable for fine-tuning and retrieval
TEST = "test"  # held out: evaluation only, reviewed by a native speaker


@dataclass(frozen=True)
class Source:
    name: str
    title: str
    owner: str
    url: str
    license: str
    role: str
    fetch: Callable[[Path], None]
    parse: Callable[[Path], Iterable[Pair]]

    def raw_dir(self, raw_root: Path) -> Path:
        path = raw_root / self.name
        path.mkdir(parents=True, exist_ok=True)
        return path


def download(url: str, dest: Path, *, headers: dict | None = None, retries: int = 3) -> Path:
    """Download once. Raw files are a cache: if it's there, we don't hit the site again."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with httpx.stream(
                "GET",
                url,
                headers={"User-Agent": USER_AGENT, **(headers or {})},
                follow_redirects=True,
                timeout=120,
            ) as response:
                response.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in response.iter_bytes():
                        fh.write(chunk)
            tmp.rename(dest)
            return dest
        except httpx.HTTPStatusError as error:
            if error.response.status_code < 500:  # 4xx won't fix itself: fail now
                raise RuntimeError(f"download failed: {url}: {error.response.status_code}") from error
            last_error = error
        except (httpx.HTTPError, OSError) as error:  # network hiccups are common on big files
            last_error = error
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"download failed: {url}: {last_error}")
