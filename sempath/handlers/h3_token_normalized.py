"""Token-normalized match handler — unordered set comparison.

Strips non-alphanumeric characters from both the query and each
candidate basename, splits the result into lowercase tokens, and
compares the resulting sets. Catches reordered or differently-
delimited names (e.g. "my_project" vs "project-my"). Returns a
MatchResult with confidence 0.9 on match.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from sempath.handlers.base import BaseHandler
from sempath.models import MatchResult
from sempath.utils.tokenize import normalize_tokens_with_wildcards


def _match_token_sets(query_tokens: set[str], candidate_tokens: set[str]) -> bool:
    """Compare query token patterns to candidate tokens using bijection/wildcard matching."""
    has_wildcard = any("*" in q or "?" in q for q in query_tokens)
    if not has_wildcard:
        return query_tokens == candidate_tokens

    q_list = list(query_tokens)
    c_list = list(candidate_tokens)

    def search(q_idx: int, c_idx_set: set[int]) -> bool:
        if q_idx == len(q_list):
            if len(c_idx_set) == len(c_list):
                return True
            return "*" in q_list

        q_tok = q_list[q_idx]

        if q_tok == "*":
            # Match zero candidate tokens
            if search(q_idx + 1, c_idx_set):
                return True
            # Match remaining candidate tokens
            remaining_indices = [i for i in range(len(c_list)) if i not in c_idx_set]
            return bool(search(q_idx + 1, c_idx_set.union(remaining_indices)))

        for i, c_tok in enumerate(c_list):
            if i in c_idx_set:
                continue
            if fnmatch.fnmatch(c_tok, q_tok) and search(q_idx + 1, c_idx_set.union({i})):
                return True

        return False

    return search(0, set())


class TokenNormalizedHandler(BaseHandler):
    """Strip non-alphanumeric, split tokens, compare unordered sets. Confidence: 0.9."""

    name: str = "h3_token_normalized"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt a token-normalized match against candidate basenames."""
        matches = self.match_all(query, candidates)
        if not matches:
            return None

        # Tie-breaker: shortest path depth first
        return min(matches, key=lambda m: len(m.path.parts))

    def match_all(self, query: str, candidates: list[Path]) -> list[MatchResult]:
        """Attempt a token-normalized and token-subset match against candidates."""
        if not query or not candidates:
            return []

        query_tokens = normalize_tokens_with_wildcards(query)
        if not query_tokens:
            return []

        # Split query by path separators to check subpath suffixes
        query_parts = [p for p in query.replace("\\", "/").split("/") if p]
        k = len(query_parts)

        results = []
        for p in candidates:
            p_name_tokens = normalize_tokens_with_wildcards(p.name)
            p_stem_tokens = normalize_tokens_with_wildcards(p.stem)

            confidence = 0.0

            # 1. Exact token sets matching name or stem
            if _match_token_sets(query_tokens, p_name_tokens) or _match_token_sets(
                query_tokens, p_stem_tokens
            ):
                confidence = 0.90

            # 2. Path suffix tokens matching (for multi-part queries)
            elif k > 1 and len(p.parts) >= k:
                suffix_parts = p.parts[-k:]
                suffix_str = "/".join(suffix_parts)
                if _match_token_sets(query_tokens, normalize_tokens_with_wildcards(suffix_str)):
                    confidence = 0.90

            # 3. Token-subset fallback (only if no wildcard in query)
            if confidence == 0.0 and not any("*" in q or "?" in q for q in query_tokens):
                if query_tokens.issubset(p_name_tokens) or query_tokens.issubset(p_stem_tokens):
                    confidence = 0.90
                elif k > 1 and len(p.parts) >= k:
                    suffix_parts = p.parts[-k:]
                    suffix_str = "/".join(suffix_parts)
                    if query_tokens.issubset(normalize_tokens_with_wildcards(suffix_str)):
                        confidence = 0.90

            if confidence > 0.0:
                results.append(MatchResult(p, confidence, self.name))

        return results
