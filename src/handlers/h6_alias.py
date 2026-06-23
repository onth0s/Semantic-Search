"""Alias handler — synonym expansion from config and learned memory.

Expands the query using aliases and synonyms defined in the
configuration file as well as aliases learned from previous
interactive sessions. Supports fuzzy and phonetic alias key
matching, regex patterns, and context splitting for compound
queries. Returns a MatchResult with confidence 0.95 on match.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.handlers.base import BaseHandler
from src.models import MatchResult


class AliasHandler(BaseHandler):
    """Alias/synonym expansion from config and learned memory.

    Supports fuzzy/phonetic alias keys, regex patterns, and context splitting.
    Confidence: 0.95.
    """

    name: str = "h6_alias"

    def _matches_key(self, query: str, key: str) -> bool:
        """Check if query matches an alias key (exact, regex, fuzzy, or phonetic)."""
        query_lower = query.lower().strip()
        key_lower = key.lower().strip()

        # Glob match if query or key has wildcard
        import fnmatch
        if "*" in query_lower or "?" in query_lower:
            if fnmatch.fnmatch(key_lower, query_lower):
                return True
        if "*" in key_lower or "?" in key_lower:
            if fnmatch.fnmatch(query_lower, key_lower):
                return True

        # 1. Exact case-insensitive match
        if query_lower == key_lower:
            return True

        # 2. Regex match (if key contains regex special characters)
        if any(c in key for c in ("^", "$", "(", ")", "[", "]", "*", "+", "?")):
            try:
                pattern = re.compile(key, re.IGNORECASE)
                if pattern.search(query):
                    return True
            except Exception:
                pass

        # 3. Fuzzy match (rapidfuzz)
        from rapidfuzz import fuzz

        if fuzz.ratio(query_lower, key_lower) >= 80.0:
            return True

        # 4. Phonetic match (jellyfish)
        import jellyfish

        try:
            q_code = jellyfish.metaphone(query_lower)
            k_code = jellyfish.metaphone(key_lower)
            if q_code and k_code and q_code == k_code:
                return True
        except Exception:
            pass

        return False

    def _resolve_alias_path(self, alias_name: str, candidates: list[Path]) -> Path | None:
        """Resolve an alias name to a Path by checking learned and config aliases."""
        # 1. Check learned aliases
        from src.utils.memory import load_memory

        entries = load_memory()
        for entry in entries:
            if self._matches_key(alias_name, entry.get("query", "")):
                p = Path(entry["path"])
                return p

        # 2. Check config aliases
        aliases = self.config.get("aliases", {})
        import fnmatch
        for key, targets in aliases.items():
            if self._matches_key(alias_name, key) or any(self._matches_key(alias_name, target) for target in targets):
                matched = []
                for p in candidates:
                    for target in targets:
                        target_lower = target.lower()
                        if "*" in target or "?" in target:
                            if fnmatch.fnmatch(p.name.lower(), target_lower) or fnmatch.fnmatch(p.stem.lower(), target_lower):
                                matched.append(p)
                        else:
                            if p.name.lower() == target_lower or p.stem.lower() == target_lower:
                                matched.append(p)
                if matched:
                    # Shortest depth tie-breaker
                    return min(matched, key=lambda p: len(p.parts))

        return None

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt an alias-based match against candidate paths."""
        if not query or not candidates:
            return None

        # 1. Check for sub-query routing ("<sub_query> on/in <alias>")
        routing_match = re.search(r"^(.*?)\s+(?:on|in)\s+(\S+)\s*$", query, re.IGNORECASE)
        if routing_match:
            sub_query = routing_match.group(1).strip()
            alias_name = routing_match.group(2).strip()

            resolved_base_path = self._resolve_alias_path(alias_name, candidates)
            if resolved_base_path:
                # Find all descendants under the resolved base path
                descendants = [
                    p
                    for p in candidates
                    if p.is_relative_to(resolved_base_path) and p != resolved_base_path
                ]

                # Parse sub-query heuristics
                from src.heuristics import extract_heuristics

                heuristics = extract_heuristics(sub_query, self.config)
                clean_q = heuristics["clean_query"]
                exts = heuristics["extensions"]
                age_limit = heuristics["modified_within_seconds"]
                latest = heuristics["latest"]

                filtered = descendants

                # Filter by extensions
                if exts:
                    import fnmatch
                    new_filtered = []
                    for p in filtered:
                        suffix = p.suffix.lower().lstrip(".")
                        matched = False
                        for ext in exts:
                            if fnmatch.fnmatch(suffix, ext.lower()):
                                matched = True
                                break
                        if matched:
                            new_filtered.append(p)
                    filtered = new_filtered

                # Filter by modification time
                if age_limit is not None:
                    import time

                    now = time.time()
                    new_filtered = []
                    for p in filtered:
                        try:
                            mtime = p.stat().st_mtime
                            if now - mtime <= age_limit:
                                new_filtered.append(p)
                        except Exception:
                            pass
                    filtered = new_filtered

                # Match by clean query if it is not empty
                if clean_q:
                    matched = None
                    # Exact name match
                    for p in filtered:
                        if p.name == clean_q or p.stem == clean_q:
                            matched = p
                            break

                    # Case-insensitive name match
                    if not matched:
                        for p in filtered:
                            if (
                                p.name.lower() == clean_q.lower()
                                or p.stem.lower() == clean_q.lower()
                            ):
                                matched = p
                                break

                    # Fuzzy match
                    if not matched:
                        from rapidfuzz import fuzz

                        best_ratio = -1.0
                        for p in filtered:
                            r = max(
                                fuzz.ratio(clean_q.lower(), p.name.lower()),
                                fuzz.ratio(clean_q.lower(), p.stem.lower()),
                            )
                            if r >= 75.0 and r > best_ratio:
                                best_ratio = r
                                matched = p

                    if matched:
                        return MatchResult(matched, 0.95, self.name)
                else:
                    # If query is empty (e.g. "latest pic on MAIN"), sort and return the best option
                    if filtered:
                        if latest:
                            import contextlib

                            with contextlib.suppress(Exception):
                                filtered.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                        return MatchResult(filtered[0], 0.95, self.name)

                # Fallback to returning the base path itself if no sub-query files match
                return MatchResult(resolved_base_path, 0.95, self.name)

        # 2. Check direct learned memory match
        from src.utils.memory import load_memory

        entries = load_memory()
        for entry in entries:
            if self._matches_key(query, entry.get("query", "")):
                p = Path(entry["path"])
                return MatchResult(p, 0.95, self.name)

        # 3. Check direct config alias match
        aliases = self.config.get("aliases", {})
        import fnmatch
        for key, targets in aliases.items():
            if self._matches_key(query, key) or any(self._matches_key(query, target) for target in targets):
                matched = []
                for p in candidates:
                    for target in targets:
                        target_lower = target.lower()
                        if "*" in target or "?" in target:
                            if fnmatch.fnmatch(p.name.lower(), target_lower) or fnmatch.fnmatch(p.stem.lower(), target_lower):
                                matched.append(p)
                        else:
                            if p.name.lower() == target_lower or p.stem.lower() == target_lower:
                                matched.append(p)
                if matched:
                    best = min(matched, key=lambda p: len(p.parts))
                    return MatchResult(best, 0.95, self.name)

        return None
