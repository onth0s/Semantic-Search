"""Core Search Engine for sempath.

Orchestrates candidate gathering (on-the-fly vs. persistent indexing),
applies heuristics extraction, manages sorting/filtering, and executes
the handler chain of responsibility.
"""

from __future__ import annotations

import time
from pathlib import Path

import click

from src.chain import build_chain
from src.config import load_config
from src.heuristics import extract_heuristics
from src.index import IndexManager
from src.models import MatchResult, SearchResult
from src.scanner import scan_directory


class SearchEngine:
    """Orchestrates candidate scanning, index lookups, and chain execution."""

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or load_config()
        # Initialize IndexManager using the configured store path
        index_store = self.config.get("index", {}).get("store", "")
        self.index_manager = IndexManager(Path(index_store))

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
        ext: str | None = None,
        verbose: bool = False,
    ) -> SearchResult:
        """Search for paths matching the query under root_dir."""
        search_root = Path(root_dir).resolve()

        # 1. Gather candidates (SQLite index vs on-the-fly)
        exclude_patterns = self.config.get("index", {}).get("exclude_patterns", [])
        use_index = not no_index and self.config.get("index", {}).get("auto", True)

        if use_index:
            # If not indexed and auto is true, index it now
            if not self.index_manager.is_indexed(search_root):
                if verbose:
                    click.echo(f"[dim]Auto-indexing directory: {search_root}...[/]")
                self.index_manager.create_or_update_index(
                    search_root,
                    depth=depth,
                    exclude_patterns=exclude_patterns,
                )
            candidates = self.index_manager.get_candidates(search_root)
        else:
            candidates = scan_directory(
                search_root,
                depth=depth,
                exclude_patterns=exclude_patterns,
            )

        if verbose:
            from src.utils.console import err_console
            err_console.print(f"[dim]Gathered {len(candidates)} candidates from scan/index...[/]")

        # 2. Extract heuristics
        heuristics = extract_heuristics(query, self.config)
        clean_query = heuristics["clean_query"]
        h_exts = heuristics["extensions"]
        h_age_limit = heuristics["modified_within_seconds"]
        h_latest = heuristics["latest"]

        # Merge CLI arguments and heuristics
        latest_final = latest or h_latest
        largest_final = largest or heuristics.get("largest", False)
        exts_final = [ext.lower().lstrip(".")] if ext else (h_exts or [])

        if verbose:
            from src.utils.console import err_console
            err_console.print(f"[dim]Heuristics extracted: clean_query='{clean_query}', extensions={exts_final}, latest={latest_final}, largest={largest_final}, dir_only={heuristics.get('directory_only')}, file_only={heuristics.get('file_only')}[/]")

        # 3. Filter candidates
        filtered_candidates = candidates

        # Filter by directory/file intent
        if heuristics.get("directory_only"):
            filtered_candidates = [p for p in filtered_candidates if p.is_dir()]
        elif heuristics.get("file_only"):
            filtered_candidates = [p for p in filtered_candidates if p.is_file()]

        # Filter by extensions (supporting wildcards)
        if exts_final:
            import fnmatch
            new_filtered = []
            for p in filtered_candidates:
                suffix = p.suffix.lower().lstrip(".")
                matched = False
                for ext_pat in exts_final:
                    if fnmatch.fnmatch(suffix, ext_pat.lower()):
                        matched = True
                        break
                if matched:
                    new_filtered.append(p)
            filtered_candidates = new_filtered

        # Filter by modification time from heuristics
        if h_age_limit is not None:
            now = time.time()
            valid_candidates = []
            for p in filtered_candidates:
                try:
                    if now - p.stat().st_mtime <= h_age_limit:
                        valid_candidates.append(p)
                except Exception:
                    pass
            filtered_candidates = valid_candidates

        if verbose:
            from src.utils.console import err_console
            err_console.print(f"[dim]Remaining candidates after applying filters: {len(filtered_candidates)}[/]")

        # 4. Sort candidates
        if latest_final:

            def get_mtime(p: Path) -> float:
                try:
                    return p.stat().st_mtime
                except Exception:
                    return 0.0

            filtered_candidates.sort(key=get_mtime, reverse=True)

        elif largest_final:

            def get_size(p: Path) -> int:
                try:
                    return p.stat().st_size if p.is_file() else 0
                except Exception:
                    return 0

            filtered_candidates.sort(key=get_size, reverse=True)

        # 5. Check for direct bypass
        # If query is a placeholder and we sorted/filtered, return the top candidate
        if (
            clean_query in ("", ".", "*")
            and (latest_final or largest_final or exts_final)
            and filtered_candidates
        ):
            match_result = MatchResult(filtered_candidates[0], 1.0, "explicit_flags")
            return SearchResult(status="success", query=query, match=match_result)

        # 6. Build and execute Chain of Responsibility
        try:
            chain = build_chain(self.config)
        except ValueError as exc:
            raise ValueError(f"Error building handler chain: {exc}") from exc

        match_result = chain.handle(clean_query, filtered_candidates)

        if match_result is not None and match_result.confidence >= min_confidence:
            return SearchResult(
                status="success",
                query=query,
                match=match_result,
            )

        # Collect near-misses
        near_misses = []
        seen_paths = set()
        current = chain
        while current is not None:
            try:
                res = current.match(clean_query, filtered_candidates)
                if res is not None and res.path not in seen_paths:
                    near_misses.append(res)
                    seen_paths.add(res.path)
            except Exception:
                pass
            current = getattr(current, "next_handler", None)

        # Filter near-misses above a minimum relevance threshold (e.g. 0.2)
        near_misses = [m for m in near_misses if m.confidence >= 0.2]
        near_misses.sort(key=lambda m: m.confidence, reverse=True)

        if near_misses:
            return SearchResult(
                status="ambiguous",
                query=query,
                near_misses=near_misses,
                message="No match found above confidence threshold.",
            )
        else:
            return SearchResult(
                status="failed",
                query=query,
                message="No candidate paths or near-misses matched the query.",
            )
