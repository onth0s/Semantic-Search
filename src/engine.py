"""Core Search Engine for sempath.

Orchestrates candidate gathering (on-the-fly vs. persistent indexing),
applies heuristics extraction, manages sorting/filtering, and executes
the handler chain of responsibility.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

import click

from src.chain import build_chain
from src.config import load_config
from src.heuristics import extract_heuristics
from src.index import IndexManager
from src.models import MatchResult, SearchResult
from src.scanner import scan_directory


def _match_dir_name(q_tokens: set[str], dir_name: str, config: dict | None = None) -> bool:
    """Check if query tokens match a directory name (exact, fuzzy, phonetic, or alias)."""
    if not q_tokens or not dir_name:
        return False

    import fnmatch

    import jellyfish
    from rapidfuzz import fuzz

    from src.handlers.h3_token_normalized import _normalize_tokens_with_wildcards

    p_tokens = _normalize_tokens_with_wildcards(dir_name)
    if not p_tokens:
        return False

    aliases = config.get("aliases", {}) if config else {}
    token_to_aliases = {}
    for alias_key, alias_values in aliases.items():
        key_norm = alias_key.lower()
        val_norms = {v.lower() for v in alias_values}
        all_norms = val_norms.union({key_norm})
        for tok in all_norms:
            token_to_aliases.setdefault(tok, set()).add(key_norm)

    for q_tok in q_tokens:
        matched = False
        q_tok_lower = q_tok.lower()

        q_meta = None
        if q_tok_lower.isalpha():
            with contextlib.suppress(Exception):
                q_meta = jellyfish.metaphone(q_tok_lower)

        q_aliases = token_to_aliases.get(q_tok_lower, set())

        for p_tok in p_tokens:
            p_tok_lower = p_tok.lower()

            # 1. Exact match
            if q_tok_lower == p_tok_lower:
                matched = True
                break

            # 2. Wildcard/glob match
            if ("*" in q_tok_lower or "?" in q_tok_lower) and fnmatch.fnmatch(
                p_tok_lower, q_tok_lower
            ):
                matched = True
                break
            if ("*" in p_tok_lower or "?" in p_tok_lower) and fnmatch.fnmatch(
                q_tok_lower, p_tok_lower
            ):
                matched = True
                break

            # 3. Alias match
            p_aliases = token_to_aliases.get(p_tok_lower, set())
            if q_aliases and p_aliases and q_aliases.intersection(p_aliases):
                matched = True
                break

            # 4. Fuzzy match (requires length >= 4)
            if (
                len(q_tok_lower) >= 4
                and len(p_tok_lower) >= 4
                and fuzz.ratio(q_tok_lower, p_tok_lower) >= 80
            ):
                matched = True
                break

            # 5. Phonetic match (requires length >= 4)
            if len(q_tok_lower) >= 4 and len(p_tok_lower) >= 4 and q_meta and p_tok_lower.isalpha():
                try:
                    p_meta = jellyfish.metaphone(p_tok_lower)
                    if q_meta == p_meta and fuzz.ratio(q_tok_lower, p_tok_lower) >= 50:
                        matched = True
                        break
                except Exception:
                    pass

        if not matched:
            return False

    return True


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
                sub_query = routing_match.group(1).strip()
                alias_name = routing_match.group(2).strip()

                resolved_base_path = alias_handler.fast_resolve(alias_name, search_root)
                if resolved_base_path:
                    if verbose:
                        from src.utils.console import err_console

                        err_console.print(
                            f"[dim]Fast-resolved routing alias '{alias_name}' "
                            f"to '{resolved_base_path}'[/]"
                        )
                    # Restrict candidate gathering scope to resolved_base_path
                    search_root = resolved_base_path
                    self.config["_current_search_root"] = search_root
                    query = sub_query
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
                f"[dim]Heuristics extracted: clean_query='{clean_query}', "
                f"extensions={exts_final}, latest={latest_final}, "
                f"largest={largest_final}, "
                f"dir_only={heuristics.get('directory_only')}, "
                f"file_only={heuristics.get('file_only')}[/]"
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

        # Check if filtered_candidates is empty and we matched a category
        if not filtered_candidates:
            msg = "No candidate paths or near-misses matched the query."
            if heuristics.get("matched_categories"):
                matched_cats = heuristics["matched_categories"]
                keywords = heuristics.get("matched_category_keywords", {})
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
            return SearchResult(status="failed", query=query, message=msg)

        # 3b. Check for Directory Content Matching
        # If a category filter is active and clean_query is not a placeholder/empty
        if exts_final and clean_query not in ("", ".", "*"):
            from src.handlers.h3_token_normalized import _normalize_tokens_with_wildcards

            q_tokens = _normalize_tokens_with_wildcards(clean_query)
            if q_tokens:
                matching_dirs = []

                # 1. Check ancestors of search_root (including search_root itself)
                current = search_root.resolve()
                while True:
                    if _match_dir_name(q_tokens, current.name, self.config):
                        matching_dirs.append(current)
                    parent = current.parent
                    if parent == current:
                        break
                    current = parent

                # 2. Check candidate directories under search_root
                for p in candidates:
                    if p.is_dir() and _match_dir_name(q_tokens, p.name, self.config):
                        matching_dirs.append(p)

                # If we found matching directories, look for category files inside them
                if matching_dirs:
                    # Sort matching directories by path depth (shallowest first)
                    matching_dirs.sort(key=lambda d: len(d.parts))

                    descendants = []
                    matched_dir = None
                    for d in matching_dirs:
                        for fc in filtered_candidates:
                            try:
                                fc.relative_to(d)
                                descendants.append(fc)
                            except ValueError:
                                pass
                        if descendants:
                            matched_dir = d
                            break  # Use the first directory that has matching files

                    if descendants:
                        descendants.sort(key=lambda p: (len(p.parts), p.name.lower()))
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
            msg = "No candidate paths or near-misses matched the query."
            if heuristics.get("matched_categories"):
                matched_cats = heuristics["matched_categories"]
                keywords = heuristics.get("matched_category_keywords", {})
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

            return SearchResult(
                status="failed",
                query=query,
                message=msg,
            )
