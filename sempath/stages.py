"""Decomposed search engine execution stages for sempath.

Provides modular, testable pipeline stages for query analysis,
candidate gathering, candidate filtering, handler chain execution,
directory matching, and near-miss processing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from sempath.chain import build_chain
from sempath.constants import (
    CONTENT_SEARCH_EXACT_CONFIDENCE,
    CONTENT_TIER_CI_SUBSTRING,
    CONTENT_TIER_CI_TOKEN,
    CONTENT_TIER_DELIMITED,
    CONTENT_TIER_EXACT_SUBSTRING,
    CONTENT_TIER_EXACT_TOKEN,
    NEAR_MISS_MIN_CONFIDENCE,
)
from sempath.directory_matcher import match_directory_content
from sempath.handlers.base import BaseHandler
from sempath.handlers.h6_alias import AliasHandler
from sempath.heuristics import HeuristicsResult, extract_heuristics
from sempath.heuristics_parser import (
    OrderingAndIntentParser,
    TemporalParser,
    normalize_whitespace,
)
from sempath.index import IndexManager
from sempath.models import MatchResult, SearchResult
from sempath.pipeline import (
    filter_by_age,
    filter_by_extensions,
    filter_by_intent,
    sort_candidates,
)
from sempath.scanner import scan_directory
from sempath.search_context import SearchContext
from sempath.utils.file_ops import (
    TIER_CI_SUBSTRING,
    TIER_CI_TOKEN,
    TIER_DELIMITED,
    TIER_EXACT_SUBSTRING,
    TIER_EXACT_TOKEN,
    extract_content_match_info,
    is_text_file,
)
from sempath.utils.logging import verbose_log
from sempath.utils.stat_cache import FileStatCache


def build_category_failure_message(heuristics: HeuristicsResult) -> str:
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


@dataclass
class QueryAnalysisResult:
    """Result of analyzing and normalizing the query with heuristics."""

    query: str
    search_root: Path
    heuristics: HeuristicsResult
    clean_query: str
    content_pattern: str | None
    latest_final: bool
    largest_final: bool
    smallest_final: bool
    oldest_final: bool
    exts_final: list[str]
    content_has_ext_filter: bool


class QueryAnalysisStage:
    """Extracts heuristics, processes alias fast-resolution, and normalizes search flags."""

    def __init__(self, config: dict) -> None:
        self.config = config

    def resolve_early_alias(
        self, query: str, search_root: Path
    ) -> tuple[str, Path, SearchResult | None]:
        """Check for early alias routing or direct alias matching."""
        enabled_handlers = self.config.get("handlers", {}).get("enabled", [])
        if "h6" not in enabled_handlers:
            return query, search_root, None

        import re

        alias_handler = AliasHandler(self.config)

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

    def analyze(
        self,
        query: str,
        search_root: Path,
        latest: bool,
        largest: bool,
        smallest: bool,
        oldest: bool,
        ext: str | None,
        read_content: bool,
    ) -> QueryAnalysisResult:
        """Parse query, extract heuristics, and determine content pattern & sorting flags."""
        heuristics = extract_heuristics(query, self.config)
        clean_query = heuristics.clean_query
        h_exts = heuristics.extensions
        h_age_limit = heuristics.age_limit
        h_latest = heuristics.latest

        content_pattern = None
        if read_content:
            pat, _ = TemporalParser.parse(query)
            pat, *_ = OrderingAndIntentParser.parse(pat)
            pat = normalize_whitespace(pat) or None

            if (
                pat
                and "." in pat
                and h_exts
                and clean_query
                and clean_query not in ("", ".", "*")
                and clean_query.lower() != pat.lower()
            ):
                content_pattern = clean_query
            else:
                content_pattern = pat

        latest_final = latest or h_latest
        largest_final = largest or heuristics.largest
        smallest_final = smallest or heuristics.smallest
        oldest_final = oldest or heuristics.oldest
        exts_final = [ext.lower().lstrip(".")] if ext else (h_exts or [])

        content_has_ext_filter = bool(ext) or (
            read_content
            and content_pattern == clean_query
            and bool(h_exts)
            and clean_query not in ("", ".", "*")
        )

        verbose_log(
            f"[dim]Heuristics extracted: clean_query='{clean_query}', "
            f"extensions={exts_final}, age_limit={h_age_limit}[/]"
        )

        return QueryAnalysisResult(
            query=query,
            search_root=search_root,
            heuristics=heuristics,
            clean_query=clean_query,
            content_pattern=content_pattern,
            latest_final=latest_final,
            largest_final=largest_final,
            smallest_final=smallest_final,
            oldest_final=oldest_final,
            exts_final=exts_final,
            content_has_ext_filter=content_has_ext_filter,
        )


class CandidateGatheringStage:
    """Gathers candidate filesystem paths from index or direct scanning."""

    def __init__(self, config: dict, index_manager: IndexManager) -> None:
        self.config = config
        self.index_manager = index_manager

    def gather(
        self,
        search_root: Path,
        depth: int,
        no_index: bool,
        respect_gitignore: bool | None,
        is_sorting_or_flat: bool,
    ) -> tuple[list[Path], str]:
        """Gather candidates using SQLite index or on-the-fly directory scanning."""
        exclude_patterns = self.config.get("index", {}).get("exclude_patterns", [])
        use_index = not no_index and self.config.get("index", {}).get("auto", True)

        if respect_gitignore is None:
            respect_gitignore_final = self.config.get("index", {}).get("respect_gitignore", True)
        else:
            respect_gitignore_final = respect_gitignore

        if is_sorting_or_flat:
            use_index = False

        t0 = time.perf_counter()
        if use_index:
            needs_init = not self.index_manager.is_indexed(search_root)
            needs_update = False
            if not needs_init:
                needs_update = self.index_manager.check_index_needs_update(search_root)

            if needs_init or needs_update:
                action_str = "Auto-indexing" if needs_init else "Updating index for"
                verbose_log(f"[dim]{action_str} directory: {search_root}...[/]")
                self.index_manager.create_or_update_index(
                    search_root,
                    depth=depth,
                    exclude_patterns=exclude_patterns,
                    respect_gitignore=respect_gitignore_final,
                )
            cands = self.index_manager.get_candidates(search_root)
            t_ms = (time.perf_counter() - t0) * 1000
            verbose_log(
                f"[bold blue]>> Gather:[/] retrieved [bold]{len(cands)}[/] paths "
                f"from index for [cyan]{search_root}[/] in [bold]{t_ms:.2f}ms[/]"
            )
            return cands, "index"

        cands = scan_directory(
            search_root,
            depth=depth,
            exclude_patterns=exclude_patterns,
            respect_gitignore=respect_gitignore_final,
        )
        elapsed = time.perf_counter() - t0
        verbose_log(
            f"[dim]Gathered {len(cands)} candidates via [bold yellow]on-the-fly directory walk[/] "
            f"in {elapsed:.3f}s[/]"
        )
        return cands, "filesystem_walk"


class CandidateFilteringStage:
    """Applies directory/file intent, extension, age, and sorting to candidate pools."""

    @staticmethod
    def filter_candidates(
        candidates: list[Path],
        heuristics: HeuristicsResult,
        exts_final: list[str],
        stat_cache: FileStatCache | None = None,
    ) -> tuple[list[Path], list[Path]]:
        """Filter candidates by intent, extensions, and age; returns (filtered, intent_only)."""
        intent_candidates = filter_by_intent(
            candidates,
            directory_only=heuristics.directory_only,
            file_only=heuristics.file_only,
        )
        filtered = list(intent_candidates)
        if not heuristics.directory_only:
            filtered = filter_by_extensions(filtered, exts_final)
        filtered = filter_by_age(filtered, heuristics.age_limit, stat_cache=stat_cache)
        return filtered, intent_candidates

    @staticmethod
    def sort(
        candidates: list[Path],
        latest: bool,
        largest: bool,
        smallest: bool,
        oldest: bool,
        stat_cache: FileStatCache | None = None,
    ) -> None:
        """Sort candidate list in-place based on ordering flags."""
        sort_candidates(
            candidates,
            latest=latest,
            largest=largest,
            smallest=smallest,
            oldest=oldest,
            stat_cache=stat_cache,
        )


class HandlerExecutionStage:
    """Executes content scan, handler chain of responsibility, and secondary chains."""

    def __init__(self, config: dict) -> None:
        self.config = config

    def execute_chain(
        self,
        chain: BaseHandler,
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
        collected_initial = []
        if read_content and content_pattern:
            content_query = content_pattern
            candidate_pool = (
                filtered_candidates
                if has_extension_filter
                else (all_candidates or filtered_candidates)
            )
            text_files = [p for p in candidate_pool if is_text_file(p)]
            verbose_log(
                f"[bold blue]>> Content scan:[/] checking [bold]{len(text_files)}[/] text files "
                f"for '[bold]{content_query}[/]'"
            )

            for p in text_files:
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    info = extract_content_match_info(content, content_query, max_snippets=10)
                    if info and info.snippets:
                        tier_map = {
                            TIER_EXACT_TOKEN: CONTENT_TIER_EXACT_TOKEN,
                            TIER_CI_TOKEN: CONTENT_TIER_CI_TOKEN,
                            TIER_EXACT_SUBSTRING: CONTENT_TIER_EXACT_SUBSTRING,
                            TIER_CI_SUBSTRING: CONTENT_TIER_CI_SUBSTRING,
                            TIER_DELIMITED: CONTENT_TIER_DELIMITED,
                        }
                        base_conf = tier_map.get(info.best_tier, CONTENT_SEARCH_EXACT_CONFIDENCE)
                        freq_bonus = min(0.04, max(0, info.total_occurrences - 1) * 0.005)
                        confidence = round(min(0.99, base_conf + freq_bonus), 4)

                        collected_initial.append(
                            MatchResult(
                                p,
                                confidence,
                                "content_search",
                                snippets=tuple(info.snippets),
                            )
                        )
                        verbose_log(
                            f"  [bold green]✔[/] [cyan]{p.name}[/] contains "
                            f"'[bold]{content_query}[/]' (tier {info.best_tier}, "
                            f"{info.total_occurrences} occurrence(s), "
                            f"confidence: [bold]{confidence:.2f}[/])"
                        )
                except (OSError, UnicodeDecodeError):
                    pass
            if collected_initial:
                verbose_log(
                    f"[bold green]>> Content scan complete:[/] "
                    f"[bold]{len(collected_initial)}[/] match(es) found"
                )
            else:
                verbose_log(
                    f"[yellow]>> Content scan complete:[/] no matches found for "
                    f"'[bold]{content_query}[/]'"
                )

        if read_content or clean_query in ("", ".", "*"):
            return collected_initial

        handler_names: list[str] = []
        h = chain
        while h is not None:
            handler_names.append(h.name)
            h = getattr(h, "next_handler", None)

        content_count = len(collected_initial)
        if content_count and content_count < top_n:
            verbose_log(
                f"[bold blue]>> Chain:[/] top_n=[bold]{top_n}[/] > "
                f"([bold]{content_count}[/] content match(es)), "
                f"running handlers: [cyan]{', '.join(handler_names)}[/]"
            )
        elif content_count >= top_n:
            verbose_log(
                f"[bold blue]>> Chain:[/] top_n=[bold]{top_n}[/] ≤ "
                f"([bold]{content_count}[/] content match(es)), "
                f"skipping all handlers"
            )
        else:
            verbose_log(
                f"[bold blue]>> Chain:[/] top_n=[bold]{top_n}[/], "
                f"no content pre-matches, "
                f"running handlers: [cyan]{', '.join(handler_names)}[/]"
            )

        return chain.handle(
            clean_query,
            filtered_candidates,
            collected=collected_initial,
            top_n=top_n,
            context=context,
        )

    def execute_secondary_name_chain(
        self,
        chain: BaseHandler,
        name_query: str,
        intent_candidates: list[Path],
        exts_final: list[str],
        top_n: int,
        context: SearchContext,
    ) -> list[MatchResult]:
        """Execute fast secondary chain on singularized name_query."""
        try:
            fast_cfg = dict(self.config)
            fast_cfg["handlers"] = dict(self.config.get("handlers", {}))
            fast_cfg["handlers"]["enabled"] = [
                h for h in fast_cfg["handlers"].get("enabled", []) if h not in ("h7", "h8")
            ]
            name_chain = build_chain(fast_cfg) if fast_cfg["handlers"]["enabled"] else chain
        except Exception:
            name_chain = chain

        verbose_log(
            f"[bold blue]>> Phase:[/] [italic]name_query secondary chain[/] "
            f"(name_query: '[bold]{name_query}[/]')"
        )
        name_matches = name_chain.handle(
            name_query, intent_candidates, top_n=top_n, context=context
        )
        if exts_final:
            name_matches = [nm for nm in name_matches if nm.handler != "category_match"]
        return name_matches


class DirectoryMatchStage:
    """Matches files contained within matching directories."""

    def __init__(self, config: dict) -> None:
        self.config = config

    def try_directory_content_match(
        self,
        query: str,
        clean_query: str,
        search_root: Path,
        candidates: list[Path],
        filtered_candidates: list[Path],
    ) -> SearchResult | None:
        """Attempt to match files inside a matching directory."""
        if clean_query in ("", ".", "*"):
            return None
        matched_dir, descendants = match_directory_content(
            clean_query=clean_query,
            search_root=search_root,
            candidates=candidates,
            filtered_candidates=filtered_candidates,
            config=self.config,
        )
        if matched_dir and descendants:
            match_result = MatchResult(descendants[0], 0.95, "directory_content_match")
            near_misses = [MatchResult(p, 0.95, "directory_content_match") for p in descendants[1:]]
            return SearchResult(
                status="success",
                query=query,
                match=match_result,
                near_misses=near_misses,
                message=f"Matching files inside directory: {matched_dir.resolve()}",
            )
        return None


class NearMissStage:
    """Collects near-misses across all enabled handlers in the chain."""

    @staticmethod
    def collect(
        chain: BaseHandler,
        clean_query: str,
        filtered_candidates: list[Path],
        context: SearchContext,
    ) -> list[MatchResult]:
        """Collect near-misses across all handlers and return sorted by confidence."""
        verbose_log(
            "[bold blue]>> Phase:[/] [italic]near-miss collection (re-scanning all handlers)[/]"
        )
        seen_paths: dict[Path, MatchResult] = {}
        try:
            res_list = chain.collect_all_matches(clean_query, filtered_candidates, context=context)
            for r in res_list:
                if r.path not in seen_paths or r.confidence > seen_paths[r.path].confidence:
                    seen_paths[r.path] = r
        except Exception as exc:
            verbose_log(f"[dim yellow]Warning during near-miss collection: {exc}[/]")

        near_misses = [m for m in seen_paths.values() if m.confidence >= NEAR_MISS_MIN_CONFIDENCE]
        near_misses.sort(key=lambda m: (-m.confidence, len(m.path.parts)))
        return near_misses
