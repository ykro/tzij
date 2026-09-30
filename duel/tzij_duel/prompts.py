"""The translation prompt. Same instructions for every model; only the context differs.

David and "Gemini + retrieval" get a context block with dictionary entries and
example pairs from the licensed data; Goliath on stage gets none. Keeping the
instructions identical is what makes the comparison about *data*, not prompting.
"""

from __future__ import annotations

from duel_core import Message, PromptTemplate

LANGUAGE_NAMES = {"es": "Spanish", "quc": "K'iche' (Mayan language of Guatemala)"}
DIRECTIONS = {"es-quc": ("es", "quc"), "quc-es": ("quc", "es")}

TEMPLATE = PromptTemplate(
    version="tzij-translate-v1",
    system=(
        "You are a careful translator from {src_name} to {tgt_name}. "
        "Write K'iche' in the ALMG orthography and use the apostrophe (') for the glottal stop "
        "and ejective consonants (b', ch', k', q', t', tz'). "
        "Answer with the translation only: one line, no quotes, no explanations."
    ),
    user="{context}Translate to {tgt_name}:\n{text}",
)

CONTEXT_HEADER = (
    "Reference material from K'iche'-Spanish dictionaries and translated examples. "
    "Use it when it helps; it may not cover every word.\n"
)


def translation_messages(text: str, direction: str, context: str = "") -> list[Message]:
    src, tgt = DIRECTIONS[direction]
    block = f"{CONTEXT_HEADER}{context}\n\n" if context else ""
    return TEMPLATE.render(
        src_name=LANGUAGE_NAMES[src], tgt_name=LANGUAGE_NAMES[tgt], text=text, context=block
    )
