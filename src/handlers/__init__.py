"""Handler registry mapping handler names to their classes."""

from src.handlers.h1_exact import ExactMatchHandler
from src.handlers.h2_case_insensitive import CaseInsensitiveHandler
from src.handlers.h3_token_normalized import TokenNormalizedHandler
from src.handlers.h4_fuzzy import FuzzyMatchHandler
from src.handlers.h5_phonetic import PhoneticMatchHandler
from src.handlers.h6_alias import AliasHandler
from src.handlers.h7_embedding import EmbeddingHandler
from src.handlers.h8_llm import LLMHandler
from src.handlers.h9_interactive import InteractiveHandler

HANDLER_REGISTRY: dict[str, type] = {
    "h1": ExactMatchHandler,
    "h2": CaseInsensitiveHandler,
    "h3": TokenNormalizedHandler,
    "h4": FuzzyMatchHandler,
    "h5": PhoneticMatchHandler,
    "h6": AliasHandler,
    "h7": EmbeddingHandler,
    "h8": LLMHandler,
    "h9": InteractiveHandler,
}

__all__ = [
    "HANDLER_REGISTRY",
    "AliasHandler",
    "CaseInsensitiveHandler",
    "EmbeddingHandler",
    "ExactMatchHandler",
    "FuzzyMatchHandler",
    "InteractiveHandler",
    "LLMHandler",
    "PhoneticMatchHandler",
    "TokenNormalizedHandler",
]
