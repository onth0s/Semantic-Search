"""Alias handler — synonym expansion from config and learned memory.

Expands the query using aliases and synonyms defined in the
configuration file as well as aliases learned from previous
interactive sessions. Supports fuzzy and phonetic alias key
matching, regex patterns, and context splitting for compound
queries. Returns a MatchResult with confidence 0.95 on match.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import jellyfish
from rapidfuzz import fuzz

from sempath.handlers.base import BaseHandler
from sempath.models import MatchResult

if TYPE_CHECKING:
    from sempath.search_context import SearchContext


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

        if ("*" in query_lower or "?" in query_lower) and fnmatch.fnmatch(key_lower, query_lower):
            return True
        if ("*" in key_lower or "?" in key_lower) and fnmatch.fnmatch(query_lower, key_lower):
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

        if fuzz.ratio(query_lower, key_lower) >= 80.0:
            return True

        # 4. Phonetic match (jellyfish)

        try:
            q_code = jellyfish.metaphone(query_lower)
            k_code = jellyfish.metaphone(key_lower)
            if q_code and k_code and q_code == k_code:
                return True
        except Exception:
            pass

        return False

    def fast_resolve(self, alias_name: str, search_root: Path) -> Path | None:
        """Fast resolve an alias name to a Path by checking learned and config aliases.

        Does not require candidates. Uses BFS on search_root up to depth 5 for config aliases.
        """
        # 1. Check learned aliases
        from sempath.utils.memory import load_memory

        entries = load_memory()
        for entry in entries:
            if self._matches_key(alias_name, entry.get("query", "")):
                p = Path(entry["path"])
                try:
                    if p.is_relative_to(search_root) or p == search_root:
                        return p
                except ValueError:
                    pass

        # 2. Check config aliases
        aliases = self.config.get("aliases", {})

        for key, targets in aliases.items():
            if self._matches_key(alias_name, key) or any(
                self._matches_key(alias_name, target) for target in targets
            ):
                # We found a matching config alias!
                # We check the search_root itself first
                search_root = Path(search_root).resolve()
                for target in targets:
                    target_lower = target.lower()
                    if "*" in target or "?" in target:
                        if fnmatch.fnmatch(
                            search_root.name.lower(), target_lower
                        ) or fnmatch.fnmatch(search_root.stem.lower(), target_lower):
                            return search_root
                    else:
                        if (
                            search_root.name.lower() == target_lower
                            or search_root.stem.lower() == target_lower
                        ):
                            return search_root

                # BFS search under search_root
                exclude_patterns = self.config.get("index", {}).get("exclude_patterns", [])
                queue = [search_root]
                for _level in range(5):
                    next_queue = []
                    matched_paths = []
                    for current_dir in queue:
                        try:
                            for entry in os.scandir(current_dir):
                                if entry.name.startswith(".") or entry.name in exclude_patterns:
                                    continue

                                entry_name_lower = entry.name.lower()
                                matched_target = False
                                for target in targets:
                                    target_lower = target.lower()
                                    if "*" in target or "?" in target:
                                        stem = Path(entry.name).stem.lower()
                                        if fnmatch.fnmatch(
                                            entry_name_lower, target_lower
                                        ) or fnmatch.fnmatch(stem, target_lower):
                                            matched_target = True
                                            break
                                    else:
                                        stem = Path(entry.name).stem.lower()
                                        if entry_name_lower == target_lower or stem == target_lower:
                                            matched_target = True
                                            break

                                if matched_target:
                                    matched_paths.append(Path(entry.path))

                                if entry.is_dir(follow_symlinks=False):
                                    next_queue.append(Path(entry.path))
                        except Exception:
                            pass

                    if matched_paths:
                        return min(matched_paths, key=lambda p: len(p.parts))

                    queue = next_queue
        return None

    def match(
        self,
        query: str,
        candidates: list[Path],
        context: SearchContext | None = None,
    ) -> MatchResult | None:
        """Attempt an alias-based match against candidate paths."""
        matches = self.match_all(query, candidates, context=context)
        if not matches:
            return None
        return min(matches, key=lambda m: len(m.path.parts))

    def match_all(
        self,
        query: str,
        candidates: list[Path],
        context: SearchContext | None = None,
    ) -> list[MatchResult]:
        """Attempt an alias-based match against candidate paths, returning all matches."""
        if not candidates:
            return []

        # Determine raw query and clean query to check
        raw_query = context.raw_query if context else self.config.get("_raw_query", query)
        search_root = context.search_root if context else self.config.get("_current_search_root")
        if not search_root:
            try:
                import click

                ctx = click.get_current_context(silent=True)
                search_root = ctx.obj.get("root") if (ctx and ctx.obj) else None
            except Exception:
                search_root = None

        results: list[MatchResult] = []
        seen_paths: set[Path] = set()

        def _add_match(p: Path, conf: float = 0.95) -> None:
            if p not in seen_paths:
                seen_paths.add(p)
                results.append(MatchResult(p, conf, self.name))

        # 1. Try fast resolve for direct match
        if search_root:
            if raw_query:
                resolved = self.fast_resolve(raw_query, Path(search_root))
                if resolved:
                    _add_match(resolved)
            if query and query != raw_query:
                resolved = self.fast_resolve(query, Path(search_root))
                if resolved:
                    _add_match(resolved)

        # 2. Check direct learned memory match
        from sempath.utils.memory import load_memory

        entries = load_memory()
        for entry in entries:
            entry_q = entry.get("query", "")
            if (raw_query and self._matches_key(raw_query, entry_q)) or (
                query and query != raw_query and self._matches_key(query, entry_q)
            ):
                p = Path(entry["path"])
                _add_match(p)

        # 3. Check direct config alias match
        aliases = self.config.get("aliases", {})
        for key, targets in aliases.items():
            matches_raw = raw_query and (
                self._matches_key(raw_query, key)
                or any(self._matches_key(raw_query, target) for target in targets)
            )
            matches_clean = (
                query
                and query != raw_query
                and (
                    self._matches_key(query, key)
                    or any(self._matches_key(query, target) for target in targets)
                )
            )

            if matches_raw or matches_clean:
                for p in candidates:
                    for target in targets:
                        target_lower = target.lower()
                        if "*" in target or "?" in target:
                            if fnmatch.fnmatch(p.name.lower(), target_lower) or fnmatch.fnmatch(
                                p.stem.lower(), target_lower
                            ):
                                _add_match(p)
                        else:
                            if p.name.lower() == target_lower or p.stem.lower() == target_lower:
                                _add_match(p)

        return results
