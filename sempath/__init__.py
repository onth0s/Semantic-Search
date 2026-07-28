"""sempath — Semantic filesystem path finder."""

from importlib.metadata import PackageNotFoundError, version

from sempath.engine import SearchEngine
from sempath.models import MatchResult, SearchResult

try:
    __version__ = version("sempath")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = ["MatchResult", "SearchEngine", "SearchResult", "__version__"]
