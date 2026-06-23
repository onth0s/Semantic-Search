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

    def fast_resolve(self, alias_name: str, search_root: Path) -> Path | None:
        """Fast resolve an alias name to a Path by checking learned and config aliases.

        Does not require a list of candidates. Uses BFS on search_root up to depth 5 for config aliases.
        """
        # 1. Check learned aliases
        from src.utils.memory import load_memory

        entries = load_memory()
        for entry in entries:
            if self._matches_key(alias_name, entry.get("query", "")):
                p = Path(entry["path"])
                if p.exists():
                    try:
                        if p.is_relative_to(search_root) or p == search_root:
                            return p
                    except ValueError:
                        pass

        # 2. Check config aliases
        aliases = self.config.get("aliases", {})
        import fnmatch
        import os

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

    def _resolve_alias_path(self, alias_name: str, candidates: list[Path]) -> Path | None:
        """Resolve an alias name to a Path by checking learned and config aliases."""
        # 1. Try fast resolve if click context is available
        import click

        ctx = click.get_current_context(silent=True)
        search_root = ctx.obj.get("root") if ctx else None
        if not search_root:
            search_root = self.config.get("_current_search_root")
        if search_root:
            res = self.fast_resolve(alias_name, Path(search_root))
            if res:
                return res

        # Fallback to candidates-based resolution
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
            if self._matches_key(alias_name, key) or any(
                self._matches_key(alias_name, target) for target in targets
            ):
                matched = []
                for p in candidates:
                    for target in targets:
                        target_lower = target.lower()
                        if "*" in target or "?" in target:
                            if fnmatch.fnmatch(p.name.lower(), target_lower) or fnmatch.fnmatch(
                                p.stem.lower(), target_lower
                            ):
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

        # 2. Try fast resolve for direct match if click context is available
        import click

        ctx = click.get_current_context(silent=True)
        search_root = ctx.obj.get("root") if ctx else None
        if not search_root:
            search_root = self.config.get("_current_search_root")
        if search_root:
            resolved = self.fast_resolve(query, Path(search_root))
            if resolved:
                return MatchResult(resolved, 0.95, self.name)

        # 3. Fallback to direct candidate-based matching (e.g. for testing)
        # 3.1 Check direct learned memory match
        from src.utils.memory import load_memory

        entries = load_memory()
        for entry in entries:
            if self._matches_key(query, entry.get("query", "")):
                p = Path(entry["path"])
                return MatchResult(p, 0.95, self.name)

        # 3.2 Check direct config alias match
        aliases = self.config.get("aliases", {})
        import fnmatch

        for key, targets in aliases.items():
            if self._matches_key(query, key) or any(
                self._matches_key(query, target) for target in targets
            ):
                matched = []
                for p in candidates:
                    for target in targets:
                        target_lower = target.lower()
                        if "*" in target or "?" in target:
                            if fnmatch.fnmatch(p.name.lower(), target_lower) or fnmatch.fnmatch(
                                p.stem.lower(), target_lower
                            ):
                                matched.append(p)
                        else:
                            if p.name.lower() == target_lower or p.stem.lower() == target_lower:
                                matched.append(p)
                if matched:
                    best = min(matched, key=lambda p: len(p.parts))
                    return MatchResult(best, 0.95, self.name)

        return None
