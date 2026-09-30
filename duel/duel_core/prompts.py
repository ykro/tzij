"""Prompt templates are data owned by the app; duel_core only renders them.

Both contenders receive exactly the same messages: a duel is only fair if the prompt is identical.
The template carries a `version` so every generated pair and every eval row can record which
prompt produced it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .types import Message


@dataclass(frozen=True)
class PromptTemplate:
    version: str
    system: str
    user: str
    # Optional few-shot examples as (user_fields, answer) pairs rendered as chat turns.
    examples: tuple[tuple[dict[str, str], str], ...] = field(default_factory=tuple)

    def render(self, **fields: str) -> list[Message]:
        messages: list[Message] = [{"role": "system", "content": self.system.format_map(fields)}]
        for example_fields, answer in self.examples:
            messages.append({"role": "user", "content": self.user.format_map({**fields, **example_fields})})
            messages.append({"role": "assistant", "content": answer})
        messages.append({"role": "user", "content": self.user.format_map(fields)})
        return messages


_PREFIX = re.compile(r"^\s*(traducci[oó]n|translation|respuesta|answer)\s*:\s*", re.IGNORECASE)
_QUOTES = "\"'“”«»‘’"


def clean_translation(text: str) -> str:
    """Keep the first non-empty line, drop "Traducción:" style prefixes and wrapping quotes.

    Small models sometimes add a label or quotes; stripping them keeps chrF++ about the
    translation, not about formatting habits.
    """
    lines = [ln.strip() for ln in (text or "").strip().splitlines() if ln.strip()]
    if not lines:
        return ""
    out = _PREFIX.sub("", lines[0]).strip()
    if len(out) >= 2 and out[0] in _QUOTES and out[-1] in _QUOTES:
        out = out[1:-1].strip()
    return out
