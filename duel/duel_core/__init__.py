"""duel_core — small, app-agnostic toolkit for "small local model vs. big cloud model" duels.

Everything here is independent of the language pair or the task: the app injects its own
prompt templates, prices and model names (from env vars). Used by Genlingo (Gen Z <-> parents)
and Tzij (Spanish <-> K'iche'). Vendored with `_base/sync.sh`, never imported from `_base`.
"""

from .connectivity import Connectivity
from .cost import Price, cost_usd
from .duel import Contender, ContenderResult, run_duel
from .gemini_client import GeminiClient
from .metrics import chrf_pp, corpus_chrf_pp
from .mock import MockClient
from .ollama_client import OllamaClient
from .prompts import PromptTemplate, clean_translation
from .stats import percentile, summarize
from .types import Completion, Message, ModelClient, OfflineError

__all__ = [
    "Completion",
    "Connectivity",
    "Contender",
    "ContenderResult",
    "GeminiClient",
    "Message",
    "MockClient",
    "ModelClient",
    "OfflineError",
    "OllamaClient",
    "Price",
    "PromptTemplate",
    "chrf_pp",
    "clean_translation",
    "corpus_chrf_pp",
    "cost_usd",
    "percentile",
    "run_duel",
    "summarize",
]
