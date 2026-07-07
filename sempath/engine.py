"""Core Search Engine for sempath.

Orchestrates candidate gathering (on-the-fly vs. persistent indexing),
applies heuristics extraction, manages sorting/filtering, and executes
the handler chain of responsibility.
"""

from __future__ import annotations

from pathlib import Path

from sempath.chain import build_chain
from sempath.config import load_config
from sempath.directory_matcher import match_directory_content
from sempath.handlers.h6_alias import AliasHandler
from sempath.heuristics import HeuristicsResult, extract_heuristics
from sempath.index import IndexManager
from sempath.models import MatchResult, SearchResult
from sempath.pipeline import (
    filter_by_age,
    filter_by_extensions,
    filter_by_intent,
    get_path_mtime,
    get_path_size,
    sort_candidates,
)
from sempath.scanner import scan_directory
from sempath.utils.logging import verbose_log


def _build_category_failure_message(heuristics: HeuristicsResult) -> str:
    """Build a specific failure message based on matched heuristic categories."""
    msg = "No candidate paths or near-misses matched the query."
    if heuristics.matched_categories:
        matched_cats = heuristics.matched_categories
        keywords = heuristics.matched_category_keywords
        if "audio" in matched_cats:
            audio_kws = keywords.get("audio", [])
            if any(kw in ("song", "songs") for kw in audio_kws):
                msg = "No songs found!"
            elif any(kw in ("tune", "tunes") for kw in audio_kws):
                msg = "No tunes found!"
            else:
                msg = "No audio files found!"
        elif "image" in matched_cats:
            msg = "No image files found!"
        elif "document" in matched_cats:
            msg = "No documents found!"
        elif "code" in matched_cats:
            msg = "No code files found!"
        elif "video" in matched_cats:
            msg = "No video files found!"
        elif "archive" in matched_cats:
            msg = "No archive files found!"
        elif "backup_blend" in matched_cats:
            msg = "No backup blend files found!"
    return msg


class SearchEngine:
    """Orchestrates candidate scanning, index lookups, and chain execution."""

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or load_config()
        # Initialize IndexManager using the configured store path
        index_store = self.config.get("index", {}).get("store", "")
        self.index_manager = IndexManager(Path(index_store))

    def _resolve_early_alias(
        self, query: str, search_root: Path
    ) -> tuple[str, Path, SearchResult | None]:
        """Check for early alias routing or direct alias matching."""
        enabled_handlers = self.config.get("handlers", {}).get("enabled", [])
        if "h6" not in enabled_handlers:
            return query, search_root, None

        import re

        alias_handler = AliasHandler(self.config)

        # Check for sub-query routing
        routing_match = re.search(r"^(.*?)\s+(?:on|in)\s+(\S+)\s*$", query, re.IGNORECASE)
        if routing_match:
            sub_query = routing_match.group(1).strip()
            alias_name = routing_match.group(2).strip()

            resolved_base_path = alias_handler.fast_resolve(alias_name, search_root)
            if resolved_base_path:
                verbose_log(
                    f"[dim]Fast-resolved routing alias '{alias_name}' to '{resolved_base_path}'[/]"
                )
                return sub_query, resolved_base_path, None
        else:
            # Check direct alias match
            resolved_path = alias_handler.fast_resolve(query, search_root)
            if resolved_path:
                verbose_log(f"[dim]Fast-resolved direct alias '{query}' to '{resolved_path}'[/]")
                match_result = MatchResult(resolved_path, 0.95, "h6_alias")
                return (
                    query,
                    search_root,
                    SearchResult(status="success", query=query, match=match_result),
                )

        return query, search_root, None

    def _gather_candidates(
        self, search_root: Path, depth: int, use_index: bool, exclude_patterns: list[str]
    ) -> list[Path]:
        """Gather candidates using SQLite index or on-the-fly scanning."""
        if use_index:
            if not self.index_manager.is_indexed(search_root):
                verbose_log(f"[dim]Auto-indexing directory: {search_root}...[/]")
                self.index_manager.create_or_update_index(
                    search_root,
                    depth=depth,
                    exclude_patterns=exclude_patterns,
                )
            return self.index_manager.get_candidates(search_root)

        return scan_directory(
            search_root,
            depth=depth,
            exclude_patterns=exclude_patterns,
        )

    def find_path(
        self,
        query: str,
        root_dir: Path,
        depth: int = 5,
        min_confidence: float = 0.3,
        top_n: int = 1,
        non_interactive: bool = False,
        no_index: bool = False,
        latest: bool = False,
        largest: bool = False,
        smallest: bool = False,
        oldest: bool = False,
        ext: str | None = None,
        verbose: bool = False,
    ) -> SearchResult:
        """Search for paths matching the query under root_dir."""

        search_root = Path(root_dir).resolve()
        self.config["_raw_query"] = query  # original user query for H7/H8
        self.config["_top_n"] = top_n

        # Early-bypass check for alias matching
        query, search_root, early_result = self._resolve_early_alias(query, search_root)
        if early_result:
            return early_result

        self.config["_current_search_root"] = search_root

        # 1. Extract heuristics
        heuristics = extract_heuristics(query, self.config)
        clean_query = heuristics.clean_query
        h_exts = heuristics.extensions
        h_age_limit = heuristics.age_limit
        h_latest = heuristics.latest

        # Merge CLI arguments and heuristics
        latest_final = latest or h_latest
        largest_final = largest or heuristics.largest
        smallest_final = smallest or heuristics.smallest
        oldest_final = oldest or heuristics.oldest
        exts_final = [ext.lower().lstrip(".")] if ext else (h_exts or [])

        verbose_log(
            f"[dim]Heuristics extracted: clean_query='{clean_query}', "
            f"extensions={exts_final}, age_limit={h_age_limit}[/]"
        )

        # 2. Gather candidates (SQLite index vs on-the-fly)
        exclude_patterns = self.config.get("index", {}).get("exclude_patterns", [])
        use_index = not no_index and self.config.get("index", {}).get("auto", True)

        # If any dynamic sorting flag is used, skip the index to ensure
        # we don't miss newly created or modified files.
        if latest_final or largest_final or smallest_final or oldest_final:
            use_index = False

        candidates = self._gather_candidates(search_root, depth, use_index, exclude_patterns)
        verbose_log(f"[dim]Gathered {len(candidates)} candidates from scan/index...[/]")

        intent_candidates = filter_by_intent(
            candidates,
            directory_only=heuristics.directory_only,
            file_only=heuristics.file_only,
        )

        filtered_candidates = list(intent_candidates)
        if not heuristics.directory_only:
            filtered_candidates = filter_by_extensions(filtered_candidates, exts_final)

        filtered_candidates = filter_by_age(filtered_candidates, h_age_limit)

        verbose_log(
            f"[dim]Remaining candidates after applying filters: {len(filtered_candidates)}[/]"
        )

        # Check if filtered_candidates is empty and we matched a category
        # (Removed early return to allow name_query and directory content matching to execute)

        # 3b. Check for Directory Content Matching
        # If a category filter is active and clean_query is not a placeholder/empty
        if exts_final and clean_query not in ("", ".", "*"):
            matched_dir, descendants = match_directory_content(
                clean_query=clean_query,
                search_root=search_root,
                candidates=candidates,
                filtered_candidates=filtered_candidates,
                config=self.config,
            )

            if matched_dir and descendants:
                match_result = MatchResult(descendants[0], 0.95, "directory_content_match")
                near_misses = [
                    MatchResult(p, 0.95, "directory_content_match") for p in descendants[1:]
                ]
                return SearchResult(
                    status="success",
                    query=query,
                    match=match_result,
                    near_misses=near_misses,
                    message=f"Matching files inside directory: {matched_dir.resolve()}",
                )

        # 4. Sort candidates
        sort_candidates(
            filtered_candidates,
            latest=latest_final,
            largest=largest_final,
            smallest=smallest_final,
            oldest=oldest_final,
        )

        # 5. Check for direct bypass
        # If the original query is a literal placeholder or if all query terms were
        # consumed by heuristics AND a sorting flag is active, return the top candidate directly.
        original_query_placeholder = query.strip() in ("", ".", "*")
        query_fully_consumed_with_sort = clean_query in ("", ".", "*") and (
            latest_final or largest_final or smallest_final or oldest_final
        )
        if (original_query_placeholder or query_fully_consumed_with_sort) and filtered_candidates:
            match_result = MatchResult(filtered_candidates[0], 1.0, "explicit_flags")
            near_misses = [MatchResult(p, 1.0, "explicit_flags") for p in filtered_candidates[1:]]
            return SearchResult(
                status="success",
                query=query,
                match=match_result,
                near_misses=near_misses,
            )

        # 6. Build and execute Chain of Responsibility
        try:
            chain = build_chain(self.config)
        except ValueError as exc:
            raise ValueError(f"Error building handler chain: {exc}") from exc

        match_results = []
        if clean_query not in ("", ".", "*"):
            match_results = chain.handle(clean_query, filtered_candidates, top_n=top_n)

        if heuristics.name_query and heuristics.name_query != clean_query:
            name_matches = chain.handle(heuristics.name_query, intent_candidates, top_n=top_n)
            existing_paths = {m.path: m for m in match_results}
            for nm in name_matches:
                if nm.path in existing_paths:
                    if nm.confidence > existing_paths[nm.path].confidence:
                        existing_paths[nm.path] = nm
                else:
                    existing_paths[nm.path] = nm
            match_results = list(existing_paths.values())

        # Filter matches above min_confidence and sort them
        confident_matches = [m for m in match_results if m.confidence >= min_confidence]

        # If no confident matches, and clean_query is a placeholder/empty (e.g.,
        # category matching like "songs"), fall back to using the filtered candidates
        if not confident_matches and clean_query in ("", ".", "*") and filtered_candidates:
            match_result = MatchResult(filtered_candidates[0], 1.0, "explicit_flags")
            near_misses = [MatchResult(p, 1.0, "explicit_flags") for p in filtered_candidates[1:]]
            return SearchResult(
                status="success",
                query=query,
                match=match_result,
                near_misses=near_misses,
            )

        # If a sort flag is active, use size/date as primary sort key
        # (confidence as secondary tiebreaker).
        if latest_final:

            def _mtime_key(m: MatchResult) -> tuple:
                return (-get_path_mtime(m.path), -m.confidence)

            confident_matches.sort(key=_mtime_key)
        elif largest_final:

            def _size_desc_key(m: MatchResult) -> tuple:
                return (-get_path_size(m.path), -m.confidence)

            confident_matches.sort(key=_size_desc_key)
        elif smallest_final:

            def _size_asc_key(m: MatchResult) -> tuple:
                try:
                    sz = float(m.path.stat().st_size) if m.path.is_file() else float("inf")
                except Exception:
                    sz = float("inf")
                return (sz, -m.confidence)

            confident_matches.sort(key=_size_asc_key)
        elif oldest_final:

            def _mtime_asc_key(m: MatchResult) -> tuple:
                try:
                    mt = m.path.stat().st_mtime
                except Exception:
                    mt = float("inf")
                return (mt, -m.confidence)

            confident_matches.sort(key=_mtime_asc_key)
        else:
            # Default: sort by confidence descending, path depth ascending
            confident_matches.sort(key=lambda m: (-m.confidence, len(m.path.parts)))

        if confident_matches:
            top_match = confident_matches[0]
            other_matches = confident_matches[1:]
            return SearchResult(
                status="success",
                query=query,
                match=top_match,
                near_misses=other_matches,
            )

        # Collect near-misses by scanning all handlers
        seen_paths = {}
        current = chain
        while current is not None:
            try:
                res_list = current.match_all(clean_query, filtered_candidates)
                for r in res_list:
                    if r.path not in seen_paths or r.confidence > seen_paths[r.path].confidence:
                        seen_paths[r.path] = r
            except Exception:
                pass
            current = getattr(current, "next_handler", None)

        near_misses = list(seen_paths.values())
        # Filter near-misses above a minimum relevance threshold (e.g. 0.2)
        near_misses = [m for m in near_misses if m.confidence >= 0.2]
        near_misses.sort(key=lambda m: (-m.confidence, len(m.path.parts)))

        if near_misses:
            return SearchResult(
                status="ambiguous",
                query=query,
                near_misses=near_misses,
                message="No match found above confidence threshold.",
            )
        else:
            msg = _build_category_failure_message(heuristics)

            return SearchResult(
                status="failed",
                query=query,
                message=msg,
            )
