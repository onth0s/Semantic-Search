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
        self.config["_current_search_root"] = search_root

        # Early-bypass check for alias matching
        enabled_handlers = self.config.get("handlers", {}).get("enabled", [])
        if "h6" in enabled_handlers:
            import re

            from src.handlers.h6_alias import AliasHandler

            alias_handler = AliasHandler(self.config)

            # Check for sub-query routing ("<sub_query> on/in <alias>")
            routing_match = re.search(r"^(.*?)\s+(?:on|in)\s+(\S+)\s*$", query, re.IGNORECASE)
            if routing_match:
                routing_match.group(1).strip()
                alias_name = routing_match.group(2).strip()

                resolved_base_path = alias_handler.fast_resolve(alias_name, search_root)
                if resolved_base_path:
                    if verbose:
                        from src.utils.console import err_console

                        err_console.print(
                            f"[dim]Fast-resolved routing alias '{alias_name}' to '{resolved_base_path}'[/]"
                        )
                    # Restrict candidate gathering scope to resolved_base_path
                    search_root = resolved_base_path
                    self.config["_current_search_root"] = search_root
            else:
                # Check direct alias match
                resolved_path = alias_handler.fast_resolve(query, search_root)
                if resolved_path:
                    if verbose:
                        from src.utils.console import err_console

                        err_console.print(
                            f"[dim]Fast-resolved direct alias '{query}' to '{resolved_path}'[/]"
                        )
                    match_result = MatchResult(resolved_path, 0.95, "h6_alias")
                    return SearchResult(status="success", query=query, match=match_result)

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

            err_console.print(
                f"[dim]Heuristics extracted: clean_query='{clean_query}', extensions={exts_final}, latest={latest_final}, largest={largest_final}, dir_only={heuristics.get('directory_only')}, file_only={heuristics.get('file_only')}[/]"
            )

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

            err_console.print(
                f"[dim]Remaining candidates after applying filters: {len(filtered_candidates)}[/]"
            )

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

        match_results = chain.handle(clean_query, filtered_candidates)

        # Filter matches above min_confidence and sort them
        confident_matches = [m for m in match_results if m.confidence >= min_confidence]
        # Sort primary by confidence descending, secondary by path depth ascending
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
            return SearchResult(
                status="failed",
                query=query,
                message="No candidate paths or near-misses matched the query.",
            )
