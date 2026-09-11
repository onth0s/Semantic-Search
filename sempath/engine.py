"""Core Search Engine for sempath.

Orchestrates candidate gathering (on-the-fly vs. persistent indexing),
applies heuristics extraction, manages sorting/filtering, and executes
the handler chain of responsibility via decomposed stages.
"""

from __future__ import annotations

import time
from pathlib import Path

from sempath.chain import build_chain
from sempath.config import get_index_store_path, load_config
from sempath.constants import NEAR_MISS_MIN_CONFIDENCE
from sempath.handlers.h1_exact import ExactMatchHandler
from sempath.heuristics import HeuristicsResult
from sempath.index import IndexManager
from sempath.models import MatchResult, SearchResult
from sempath.pipeline import sort_match_results
from sempath.scanner import scan_directory
from sempath.search_context import SearchContext

__all__ = ["SearchEngine", "_build_category_failure_message", "scan_directory"]
from sempath.stages import (
    CandidateFilteringStage,
    CandidateGatheringStage,
    DirectoryMatchStage,
    HandlerExecutionStage,
    NearMissStage,
    QueryAnalysisStage,
    build_category_failure_message,
)
from sempath.utils.logging import verbose_log
from sempath.utils.matching import merge_matches
from sempath.utils.stat_cache import FileStatCache


def _build_category_failure_message(heuristics: HeuristicsResult) -> str:
    """Build a specific failure message based on matched heuristic categories."""
    return build_category_failure_message(heuristics)


class SearchEngine:
    """Orchestrates candidate scanning, index lookups, and chain execution."""

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or load_config()
        self.index_manager = IndexManager(get_index_store_path(self.config))
        self.query_stage = QueryAnalysisStage(self.config)
        self.gather_stage = CandidateGatheringStage(self.config, self.index_manager)
        self.filter_stage = CandidateFilteringStage()
        self.handler_stage = HandlerExecutionStage(self.config)
        self.dir_stage = DirectoryMatchStage(self.config)
        self.near_miss_stage = NearMissStage()

    def _resolve_early_alias(
        self, query: str, search_root: Path
    ) -> tuple[str, Path, SearchResult | None]:
        """Check for early alias routing or direct alias matching."""
        return self.query_stage.resolve_early_alias(query, search_root)

    def _gather_candidates(
        self,
        search_root: Path,
        depth: int,
        use_index: bool,
        exclude_patterns: list[str],
        respect_gitignore: bool = True,
    ) -> tuple[list[Path], str]:
        """Gather candidates using SQLite index or on-the-fly scanning."""
        is_sorting_or_flat = not use_index
        return self.gather_stage.gather(
            search_root,
            depth=depth,
            no_index=not use_index,
            respect_gitignore=respect_gitignore,
            is_sorting_or_flat=is_sorting_or_flat,
        )

    def _apply_filters(
        self,
        candidates: list[Path],
        heuristics: HeuristicsResult,
        exts_final: list[str],
        h_age_limit: int | None,
        stat_cache: FileStatCache | None = None,
    ) -> list[Path]:
        """Filter candidates by intent, extensions, and age."""
        filtered, _ = self.filter_stage.filter_candidates(
            candidates, heuristics, exts_final, stat_cache=stat_cache
        )
        return filtered

    def _execute_chain(
        self,
        chain,
        clean_query: str,
        filtered_candidates: list[Path],
        read_content: bool,
        top_n: int,
        context: SearchContext,
        all_candidates: list[Path] | None = None,
        content_pattern: str | None = None,
        has_extension_filter: bool = False,
    ) -> list[MatchResult]:
        """Execute the handler chain on candidates, including text search if enabled."""
        return self.handler_stage.execute_chain(
            chain=chain,
            clean_query=clean_query,
            filtered_candidates=filtered_candidates,
            read_content=read_content,
            top_n=top_n,
            context=context,
            all_candidates=all_candidates,
            content_pattern=content_pattern,
            has_extension_filter=has_extension_filter,
        )

    def _merge_name_query_matches(
        self,
        match_results: list[MatchResult],
        name_matches: list[MatchResult],
    ) -> list[MatchResult]:
        """Merge name_query matches into primary match results keeping higher confidence."""
        return merge_matches(match_results, name_matches)

    def _sort_confident_matches(
        self,
        confident_matches: list[MatchResult],
        latest_final: bool,
        largest_final: bool,
        smallest_final: bool,
        oldest_final: bool,
        stat_cache: FileStatCache | None = None,
    ) -> None:
        """Sort confident matches based on size/date flags or confidence descending."""
        sort_match_results(
            confident_matches,
            latest=latest_final,
            largest=largest_final,
            smallest=smallest_final,
            oldest=oldest_final,
            stat_cache=stat_cache,
        )

    def _try_directory_content_match(
        self,
        query: str,
        clean_query: str,
        search_root: Path,
        candidates: list[Path],
        filtered_candidates: list[Path],
    ) -> SearchResult | None:
        """Attempt to match files inside a matching directory."""
        return self.dir_stage.try_directory_content_match(
            query=query,
            clean_query=clean_query,
            search_root=search_root,
            candidates=candidates,
            filtered_candidates=filtered_candidates,
        )

    def _execute_secondary_name_chain(
        self,
        chain,
        name_query: str,
        intent_candidates: list[Path],
        exts_final: list[str],
        top_n: int,
        context: SearchContext,
    ) -> list[MatchResult]:
        """Execute fast secondary chain on singularized name_query."""
        return self.handler_stage.execute_secondary_name_chain(
            chain=chain,
            name_query=name_query,
            intent_candidates=intent_candidates,
            exts_final=exts_final,
            top_n=top_n,
            context=context,
        )

    def _collect_near_misses(
        self,
        chain,
        clean_query: str,
        filtered_candidates: list[Path],
        context: SearchContext,
    ) -> list[MatchResult]:
        """Collect near-misses across all handlers and return sorted by confidence."""
        return self.near_miss_stage.collect(
            chain=chain,
            clean_query=clean_query,
            filtered_candidates=filtered_candidates,
            context=context,
        )

    def find_path(
        self,
        query: str,
        root_dir: Path,
        depth: int = 5,
        no_index: bool = False,
        respect_gitignore: bool | None = None,
        min_confidence: float = 0.3,
        ext: str | None = None,
        latest: bool = False,
        largest: bool = False,
        smallest: bool = False,
        oldest: bool = False,
        read_content: bool = False,
        top_n: int = 1,
        non_interactive: bool = False,
    ) -> SearchResult:
        """Find the best matching file path using semantics and heuristics."""
        t_search_start = time.perf_counter()

        def _with_timing(res: SearchResult) -> SearchResult:
            if res.elapsed_seconds <= 0:
                res.elapsed_seconds = time.perf_counter() - t_search_start
            return res

        search_root = Path(root_dir).resolve()
        stat_cache = FileStatCache()

        # Early-bypass check for alias matching
        query, search_root, early_result = self.query_stage.resolve_early_alias(query, search_root)
        if early_result:
            return _with_timing(early_result)

        context = SearchContext(
            raw_query=query,
            search_root=search_root,
            top_n=top_n,
            non_interactive=non_interactive,
            config=self.config,
        )

        # 1. Extract heuristics & analyze query
        qa = self.query_stage.analyze(
            query=query,
            search_root=search_root,
            latest=latest,
            largest=largest,
            smallest=smallest,
            oldest=oldest,
            ext=ext,
            read_content=read_content,
        )
        heuristics = qa.heuristics
        clean_query = qa.clean_query
        content_pattern = qa.content_pattern
        latest_final = qa.latest_final
        largest_final = qa.largest_final
        smallest_final = qa.smallest_final
        oldest_final = qa.oldest_final
        exts_final = qa.exts_final
        content_has_ext_filter = qa.content_has_ext_filter

        # 2. Gather candidates (SQLite index vs on-the-fly)
        is_sorting_or_flat = (
            latest_final or largest_final or smallest_final or oldest_final or depth == 1
        )
        candidates, _candidate_source = self.gather_stage.gather(
            search_root=search_root,
            depth=depth,
            no_index=no_index,
            respect_gitignore=respect_gitignore,
            is_sorting_or_flat=is_sorting_or_flat,
        )

        # 3. Filter candidates
        filtered_candidates, intent_candidates = self.filter_stage.filter_candidates(
            candidates=candidates,
            heuristics=heuristics,
            exts_final=exts_final,
            stat_cache=stat_cache,
        )

        # 3b. Check for Directory Content Matching
        # (only if not flat search, not content search, and no candidate directly matches)
        if (
            not read_content
            and depth != 1
            and (exts_final or heuristics.file_only)
            and clean_query not in ("", ".", "*")
        ):
            clean_q_lower = clean_query.lower()
            direct_filename_match = any(
                clean_q_lower in fc.stem.lower() or clean_q_lower in fc.name.lower()
                for fc in filtered_candidates
                if fc.is_file()
            )
            if not direct_filename_match:
                dir_res = self.dir_stage.try_directory_content_match(
                    query, clean_query, search_root, candidates, filtered_candidates
                )
                if dir_res:
                    return _with_timing(dir_res)

        # 4. Sort candidates
        self.filter_stage.sort(
            filtered_candidates,
            latest=latest_final,
            largest=largest_final,
            smallest=smallest_final,
            oldest=oldest_final,
            stat_cache=stat_cache,
        )

        # 5. Check for direct bypass
        original_query_placeholder = query.strip() in ("", ".", "*")
        query_fully_consumed_with_sort = clean_query in ("", ".", "*") and (
            latest_final or largest_final or smallest_final or oldest_final
        )
        bypass_blocked = read_content and not original_query_placeholder
        if (
            (original_query_placeholder or query_fully_consumed_with_sort)
            and filtered_candidates
            and not bypass_blocked
        ):
            match_result = MatchResult(filtered_candidates[0], 1.0, "explicit_flags")
            near_misses = [MatchResult(p, 1.0, "explicit_flags") for p in filtered_candidates[1:]]
            return _with_timing(
                SearchResult(
                    status="success",
                    query=query,
                    match=match_result,
                    near_misses=near_misses,
                )
            )

        # 6. Build and execute Chain of Responsibility
        try:
            chain = build_chain(self.config)
        except ValueError as exc:
            raise ValueError(f"Error building handler chain: {exc}") from exc

        chain_top_n = (
            len(filtered_candidates)
            if (latest_final or largest_final or smallest_final or oldest_final)
            else top_n
        )

        match_results = []
        if not read_content and query.strip() and query.strip() != clean_query:
            raw_exact_matches = ExactMatchHandler(self.config).match_all(
                query.strip(), intent_candidates, context=context
            )
            if raw_exact_matches:
                match_results.extend(raw_exact_matches)

        chain_matches = self.handler_stage.execute_chain(
            chain=chain,
            clean_query=clean_query,
            filtered_candidates=filtered_candidates,
            read_content=read_content,
            top_n=chain_top_n,
            context=context,
            all_candidates=candidates,
            content_pattern=content_pattern,
            has_extension_filter=content_has_ext_filter,
        )

        match_results = self._merge_name_query_matches(match_results, chain_matches)
        if match_results:
            verbose_log(
                f"[bold blue]>> Chain result:[/] [bold]{len(match_results)}[/] match(es) "
                f"(confidence range: [bold]{min(m.confidence for m in match_results):.2f}[/]-"
                f"[bold]{max(m.confidence for m in match_results):.2f}[/])"
            )
        else:
            verbose_log(
                "[yellow]>> Chain result:[/] no matches ≥ confidence threshold, "
                "continuing fallback search"
            )

        # 7. Merge name_query matches if applicable (only for filename searches, not content search)
        if not read_content and heuristics.name_query and heuristics.name_query != clean_query:
            name_matches = self.handler_stage.execute_secondary_name_chain(
                chain=chain,
                name_query=heuristics.name_query,
                intent_candidates=intent_candidates,
                exts_final=exts_final,
                top_n=top_n,
                context=context,
            )
            if clean_query in ("", ".", "*"):
                name_matches = [
                    nm
                    for nm in name_matches
                    if nm.handler in ("h1_exact", "h2_case_insensitive") or nm.confidence >= 0.95
                ]
            match_results = self._merge_name_query_matches(match_results, name_matches)

        confident_matches = [m for m in match_results if m.confidence >= min_confidence]

        if not confident_matches and clean_query in ("", ".", "*") and filtered_candidates:
            handler_name = (
                "explicit_flags"
                if (latest_final or largest_final or smallest_final or oldest_final)
                else "category_match"
            )
            match_result = MatchResult(filtered_candidates[0], 1.0, handler_name)
            near_misses = [MatchResult(p, 1.0, handler_name) for p in filtered_candidates[1:]]
            return _with_timing(
                SearchResult(
                    status="success",
                    query=query,
                    match=match_result,
                    near_misses=near_misses,
                )
            )

        self._sort_confident_matches(
            confident_matches,
            latest_final,
            largest_final,
            smallest_final,
            oldest_final,
            stat_cache=stat_cache,
        )

        if confident_matches:
            top_match = confident_matches[0]
            other_matches = confident_matches[1:]
            return _with_timing(
                SearchResult(
                    status="success",
                    query=query,
                    match=top_match,
                    near_misses=other_matches,
                )
            )

        # Fallback Directory Content Match (only for path searches, not flat CWD or content search)
        if not read_content and depth != 1:
            verbose_log("[bold blue]>> Phase:[/] [italic]fallback directory content match[/]")
            dir_res_fallback = self.dir_stage.try_directory_content_match(
                query, clean_query, search_root, candidates, filtered_candidates
            )
            if dir_res_fallback:
                return _with_timing(dir_res_fallback)

        # Collect near-misses by scanning all handlers
        near_misses = self.near_miss_stage.collect(
            chain=chain,
            clean_query=clean_query,
            filtered_candidates=filtered_candidates,
            context=context,
        )
        near_misses = [m for m in near_misses if m.confidence >= NEAR_MISS_MIN_CONFIDENCE]
        near_misses.sort(key=lambda m: (-m.confidence, len(m.path.parts)))

        if near_misses:
            return _with_timing(
                SearchResult(
                    status="ambiguous",
                    query=query,
                    near_misses=near_misses,
                    message="No match found above confidence threshold.",
                )
            )
        else:
            msg = _build_category_failure_message(heuristics)
            return _with_timing(
                SearchResult(
                    status="failed",
                    query=query,
                    message=msg,
                )
            )
