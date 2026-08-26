"""Core Search Engine for sempath.

Orchestrates candidate gathering (on-the-fly vs. persistent indexing),
applies heuristics extraction, manages sorting/filtering, and executes
the handler chain of responsibility.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from sempath.chain import build_chain
from sempath.config import get_index_store_path, load_config
from sempath.constants import (
    CONTENT_SEARCH_EXACT_CONFIDENCE,
    NEAR_MISS_MIN_CONFIDENCE,
)
from sempath.directory_matcher import match_directory_content
from sempath.handlers.h6_alias import AliasHandler
from sempath.heuristics import HeuristicsResult, extract_heuristics
from sempath.index import IndexManager
from sempath.models import MatchResult, SearchResult
from sempath.pipeline import (
    filter_by_age,
    filter_by_extensions,
    filter_by_intent,
    sort_candidates,
    sort_match_results,
)
from sempath.scanner import scan_directory
from sempath.search_context import SearchContext
from sempath.utils.file_ops import extract_matching_snippets, is_text_file
from sempath.utils.logging import verbose_log
from sempath.utils.matching import merge_matches

if TYPE_CHECKING:
    from sempath.handlers.base import BaseHandler


def _is_text_file(path: Path) -> bool:
    """Return True if path points to a readable text file (non-binary and < 5MB)."""
    return is_text_file(path)


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
        self.index_manager = IndexManager(get_index_store_path(self.config))

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
        self,
        search_root: Path,
        depth: int,
        use_index: bool,
        exclude_patterns: list[str],
        respect_gitignore: bool = True,
    ) -> tuple[list[Path], str]:
        """Gather candidates using SQLite index or on-the-fly scanning."""
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
                    respect_gitignore=respect_gitignore,
                )
            cands = self.index_manager.get_candidates(search_root)
            elapsed = time.perf_counter() - t0
            verbose_log(
                f"[dim]Gathered {len(cands)} candidates from "
                f"[bold green]SQLite index (index.db)[/] in {elapsed:.3f}s[/]"
            )
            return cands, "index.db"

        cands = scan_directory(
            search_root,
            depth=depth,
            exclude_patterns=exclude_patterns,
            respect_gitignore=respect_gitignore,
        )
        elapsed = time.perf_counter() - t0
        verbose_log(
            f"[dim]Gathered {len(cands)} candidates via [bold yellow]on-the-fly directory walk[/] "
            f"in {elapsed:.3f}s[/]"
        )
        return cands, "filesystem_walk"

    def _apply_filters(
        self,
        candidates: list[Path],
        heuristics: HeuristicsResult,
        exts_final: list[str],
        h_age_limit: int | None,
    ) -> list[Path]:
        """Filter candidates by intent, extensions, and age."""
        intent_candidates = filter_by_intent(
            candidates,
            directory_only=heuristics.directory_only,
            file_only=heuristics.file_only,
        )

        filtered_candidates = list(intent_candidates)
        if not heuristics.directory_only:
            filtered_candidates = filter_by_extensions(filtered_candidates, exts_final)

        filtered_candidates = filter_by_age(filtered_candidates, h_age_limit)
        return filtered_candidates

    def _execute_chain(
        self,
        chain: BaseHandler,
        clean_query: str,
        filtered_candidates: list[Path],
        read_content: bool,
        top_n: int,
        context: SearchContext,
        all_candidates: list[Path] | None = None,
    ) -> list[MatchResult]:
        """Execute the handler chain on candidates, including text search if enabled."""
        collected_initial = []
        if read_content:
            content_query = context.raw_query
            text_files = [p for p in (all_candidates or filtered_candidates) if is_text_file(p)]
            verbose_log(
                f"[bold blue]>> Content scan:[/] checking [bold]{len(text_files)}[/] text files "
                f"for '[bold]{content_query}[/]'"
            )
            for p in text_files:
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    if content_query in content:
                        snippets = extract_matching_snippets(
                            content, content_query, max_snippets=10
                        )
                        if snippets:
                            collected_initial.append(
                                MatchResult(
                                    p,
                                    CONTENT_SEARCH_EXACT_CONFIDENCE,
                                    "content_search",
                                    snippets=tuple(snippets),
                                )
                            )
                            verbose_log(
                                f"  [bold green]✔[/] [cyan]{p.name}[/] contains "
                                f"'[bold]{content_query}[/]' ({len(snippets)} line match(es), "
                                f"confidence: [bold]{CONTENT_SEARCH_EXACT_CONFIDENCE:.2f}[/])"
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

        # Collect handler names for the phase log
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
    ) -> None:
        """Sort confident matches based on size/date flags or confidence descending."""
        sort_match_results(
            confident_matches,
            latest=latest_final,
            largest=largest_final,
            smallest=smallest_final,
            oldest=oldest_final,
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

        # Early-bypass check for alias matching
        query, search_root, early_result = self._resolve_early_alias(query, search_root)
        if early_result:
            return _with_timing(early_result)

        context = SearchContext(
            raw_query=query,
            search_root=search_root,
            top_n=top_n,
            non_interactive=non_interactive,
            config=self.config,
        )

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

        if respect_gitignore is None:
            respect_gitignore_final = self.config.get("index", {}).get("respect_gitignore", True)
        else:
            respect_gitignore_final = respect_gitignore

        if latest_final or largest_final or smallest_final or oldest_final or depth == 1:
            use_index = False

        candidates, _candidate_source = self._gather_candidates(
            search_root,
            depth,
            use_index,
            exclude_patterns,
            respect_gitignore=respect_gitignore_final,
        )

        # 3. Filter candidates
        filtered_candidates = self._apply_filters(candidates, heuristics, exts_final, h_age_limit)
        intent_candidates = filter_by_intent(
            candidates,
            directory_only=heuristics.directory_only,
            file_only=heuristics.file_only,
        )

        # 3b. Check for Directory Content Matching
        # (only if not flat search, not content search, and no candidate directly matches)
        if (
            not read_content
            and depth != 1
            and (exts_final or heuristics.file_only)
            and clean_query not in ("", ".", "*")
        ):
            # If any candidate filename contains the clean_query token, let handler chain run first
            clean_q_lower = clean_query.lower()
            direct_filename_match = any(
                clean_q_lower in fc.stem.lower() or clean_q_lower in fc.name.lower()
                for fc in filtered_candidates
                if fc.is_file()
            )
            if not direct_filename_match:
                dir_res = self._try_directory_content_match(
                    query, clean_query, search_root, candidates, filtered_candidates
                )
                if dir_res:
                    return _with_timing(dir_res)

        # 4. Sort candidates
        sort_candidates(
            filtered_candidates,
            latest=latest_final,
            largest=largest_final,
            smallest=smallest_final,
            oldest=oldest_final,
        )

        # 5. Check for direct bypass
        original_query_placeholder = query.strip() in ("", ".", "*")
        query_fully_consumed_with_sort = clean_query in ("", ".", "*") and (
            latest_final or largest_final or smallest_final or oldest_final
        )
        if (original_query_placeholder or query_fully_consumed_with_sort) and filtered_candidates:
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
            # Pre-check exact raw query match against candidates so filenames containing
            # category/modifier words (e.g. 'formal_verification_latest') match with 1.0.
            from sempath.handlers.h1_exact import ExactMatchHandler

            raw_exact_matches = ExactMatchHandler(self.config).match_all(
                query.strip(), filtered_candidates, context=context
            )
            if raw_exact_matches:
                match_results.extend(raw_exact_matches)

        chain_matches = self._execute_chain(
            chain,
            clean_query,
            filtered_candidates,
            read_content,
            chain_top_n,
            context,
            all_candidates=candidates,
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
                f"(name_query: '[bold]{heuristics.name_query}[/]')"
            )
            name_matches = name_chain.handle(
                heuristics.name_query, intent_candidates, top_n=top_n, context=context
            )
            if exts_final:
                allowed_name_matches = [nm for nm in name_matches if nm.handler != "category_match"]
                name_matches = allowed_name_matches

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
            confident_matches, latest_final, largest_final, smallest_final, oldest_final
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
            dir_res_fallback = self._try_directory_content_match(
                query, clean_query, search_root, candidates, filtered_candidates
            )
            if dir_res_fallback:
                return _with_timing(dir_res_fallback)

        # Collect near-misses by scanning all handlers
        verbose_log(
            "[bold blue]>> Phase:[/] [italic]near-miss collection (re-scanning all handlers)[/]"
        )
        seen_paths = {}
        try:
            res_list = chain.collect_all_matches(clean_query, filtered_candidates, context=context)
            for r in res_list:
                if r.path not in seen_paths or r.confidence > seen_paths[r.path].confidence:
                    seen_paths[r.path] = r
        except Exception as exc:
            verbose_log(f"[dim yellow]Warning during near-miss collection: {exc}[/]")

        near_misses = list(seen_paths.values())
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
