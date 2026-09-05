"""The find command for the sempath CLI."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import click
from rich.markup import escape

from sempath.cli.formatting import (
    _format_elapsed_time,
    _format_file_meta,
    _format_snippet,
    _is_generic_stem,
    _print_grouped_matches,
    get_ordered_display_matches,
)
from sempath.config import load_config
from sempath.constants import DEFAULT_DEPTH
from sempath.engine import SearchEngine
from sempath.utils.clipboard import copy_to_clipboard
from sempath.utils.console import console, err_console
from sempath.utils.handlers import parse_handler_spec as _parse_handler_spec


class NormalizedPath(click.Path):
    """Click Path type that normalizes leading slashes on Windows relative paths."""

    def convert(self, value: Any, param: click.Parameter | None, ctx: click.Context | None) -> Any:
        if value is None:
            return None
        val_str = str(value).strip("'\"")

        if (
            val_str in ("./", ".\\", ".//", ".\\\\") or re.match(r"^\.[/\\]+$", val_str)
        ) and ctx is not None:
            if ctx.obj is None:
                ctx.obj = {}
            if isinstance(ctx.obj, dict):
                ctx.obj["flat_cwd"] = True

        p = Path(val_str)
        if not p.exists() and (val_str.startswith("/") or val_str.startswith("\\")):
            rel_candidate = Path(val_str.lstrip("/\\"))
            if rel_candidate.exists():
                return super().convert(str(rel_candidate), param, ctx)

        return super().convert(val_str, param, ctx)


def register_find_command(cli_group: click.Group) -> None:
    """Register the find command on the main CLI group."""

    @cli_group.command()
    @click.argument("query")
    @click.argument("root_dir", default=".", type=NormalizedPath(exists=True, path_type=Path))
    @click.option(
        "--root",
        type=NormalizedPath(exists=True, path_type=Path),
        default=None,
        help="Root directory to search (overrides ROOT_DIR argument).",
    )
    @click.option("--depth", default=None, type=int, help="Maximum folder depth to traverse.")
    @click.option(
        "--full-depth",
        is_flag=True,
        default=False,
        help="Search recursively with unlimited folder depth (equivalent to --depth -1).",
    )
    @click.option(
        "--min-confidence",
        default=0.3,
        type=float,
        show_default=True,
        help="Minimum confidence score (0.0-1.0) to return a match.",
    )
    @click.option(
        "--top-n", default=5, type=int, show_default=True, help="Number of results to return."
    )
    @click.option(
        "--non-interactive", is_flag=True, default=False, help="Disable interactive fallback (H9)."
    )
    @click.option(
        "--no-index", is_flag=True, default=False, help="Force on-the-fly traversal scan."
    )
    @click.option(
        "--json",
        "json_output",
        is_flag=True,
        default=False,
        help="Output structured JSON instead of styled text.",
    )
    @click.option(
        "--verbose",
        is_flag=True,
        default=False,
        help="Enable detailed under-the-hood diagnostics, category, and handler execution logs.",
    )
    @click.option(
        "--latest", is_flag=True, default=False, help="Sort matches to return the newest path."
    )
    @click.option(
        "--largest", is_flag=True, default=False, help="Sort matches to return the largest file."
    )
    @click.option(
        "--smallest", is_flag=True, default=False, help="Sort matches to return the smallest file."
    )
    @click.option(
        "--oldest", is_flag=True, default=False, help="Sort matches to return the oldest path."
    )
    @click.option(
        "--ext",
        type=str,
        default=None,
        help="Filter candidates to keep only those with specified extension.",
    )
    @click.option(
        "-p",
        "--preset",
        "preset_spec",
        type=str,
        default=None,
        metavar="PRESET",
        help="Use a handler preset (e.g. -p0 for h1-6, -pfast, -pllm).",
    )
    @click.option(
        "--handlers",
        "handler_spec",
        type=str,
        default=None,
        metavar="SPEC",
        help=(
            "Restrict which handler layers run. Examples: --h8 (only H8), "
            "--h1-6 (H1 through H6), --h2,h4,h5. Default: all enabled handlers."
        ),
    )
    @click.option(
        "--gitignore",
        is_flag=True,
        default=False,
        help="Flip the configured respect_gitignore setting.",
    )
    @click.option(
        "-c",
        "--read-content",
        is_flag=True,
        default=False,
        help="Search within the actual text content of human-readable files.",
    )
    @click.pass_context
    def find(
        ctx: click.Context,
        query: str,
        root_dir: Path,
        root: Path | None,
        depth: int | None,
        full_depth: bool,
        min_confidence: float,
        top_n: int,
        non_interactive: bool,
        no_index: bool,
        json_output: bool,
        verbose: bool,
        latest: bool,
        largest: bool,
        smallest: bool,
        oldest: bool,
        ext: str | None,
        preset_spec: str | None,
        handler_spec: str | None,
        gitignore: bool,
        read_content: bool,
    ) -> None:
        """Search for filesystem paths matching QUERY."""
        search_root = root or root_dir

        try:
            config = load_config()
        except (FileNotFoundError, ValueError) as exc:
            err_console.print(f"[bold red]Error loading config:[/] {exc}")
            sys.exit(1)

        from click.core import ParameterSource

        depth_explicit = ctx.get_parameter_source("depth") == ParameterSource.COMMANDLINE
        is_flat_cwd = bool(ctx.obj.get("flat_cwd", False)) if (ctx and ctx.obj) else False

        if full_depth or (depth is not None and depth == -1):
            depth_final = -1
        elif depth_explicit and depth is not None:
            depth_final = depth
        elif is_flat_cwd:
            depth_final = 1
        else:
            depth_final = config.get("depth", DEFAULT_DEPTH)

        verbose_final = verbose or config.get("verbose", False)
        exhaustive = config.get("exhaustive", False)

        # Check if root parameter was explicitly provided on CLI
        has_explicit_root = (
            root is not None
            or is_flat_cwd
            or ctx.get_parameter_source("root_dir") == ParameterSource.COMMANDLINE
        )
        config_respect = config.get("index", {}).get("respect_gitignore", True)
        default_respect = False if has_explicit_root else config_respect
        respect_gitignore_final = not default_respect if gitignore else default_respect

        # --- Handler filtering ---------------------------------------------------
        if handler_spec is None:
            presets = config.get("presets", {})
            target_preset = preset_spec if preset_spec is not None else "0"
            handler_spec = (
                presets.get(target_preset)
                or presets.get(str(target_preset))
                or (target_preset if preset_spec is not None else None)
            )

        if handler_spec is not None:
            try:
                selected = _parse_handler_spec(handler_spec)
            except click.BadParameter as exc:
                err_console.print(f"[bold red]Invalid handler spec:[/] {exc}")
                sys.exit(1)
            config.setdefault("handlers", {})["enabled"] = selected
            if verbose or config.get("verbose", False):
                console.print(f"[dim]Handlers:[/] {', '.join(selected)}")

        top_n_explicit = ctx.get_parameter_source("top_n") == ParameterSource.COMMANDLINE
        top_n_final = top_n if (top_n_explicit or not exhaustive) else 999999

        no_index_final = no_index or exhaustive or (is_flat_cwd and depth_final == 1)
        non_interactive_final = non_interactive or exhaustive

        ctx.obj.update(
            {
                "query": query,
                "root": search_root,
                "depth": depth_final,
                "min_confidence": min_confidence,
                "top_n": top_n_final,
                "non_interactive": non_interactive_final,
                "no_index": no_index_final,
                "json_output": json_output,
                "verbose": verbose_final,
                "config": config,
                "latest": latest,
                "largest": largest,
                "smallest": smallest,
                "oldest": oldest,
                "ext": ext,
            }
        )

        if verbose_final:
            console.print(f"[dim]Query:[/]  [bold cyan]{query}[/]")
            console.print(f"[dim]Root:[/]   [bold]{escape(str(search_root))}[/]")
            console.print(f"[dim]Depth:[/]  {depth_final}")
            console.print()

        try:
            engine = SearchEngine(config)
            search_result = engine.find_path(
                query=query,
                root_dir=search_root,
                depth=depth_final,
                min_confidence=min_confidence,
                top_n=top_n_final,
                non_interactive=non_interactive_final,
                no_index=no_index_final,
                latest=latest,
                largest=largest,
                smallest=smallest,
                oldest=oldest,
                ext=ext,
                respect_gitignore=respect_gitignore_final,
                read_content=read_content,
            )
        except Exception as exc:
            err_console.print(f"[bold red]Search Engine error:[/] {exc}")
            sys.exit(1)

        if search_result.status == "success":
            if search_result.message:
                console.print(f"[yellow]ℹ {search_result.message}[/]")  # noqa: RUF001

            primary = search_result.match
            near_misses: list = list(search_result.near_misses)

            is_sorted = (
                latest
                or largest
                or smallest
                or oldest
                or re.search(
                    r"\b(latest|newest|lastest|oldest|largest|biggest|smallest|tiniest)\b",
                    query,
                    re.IGNORECASE,
                )
            )

            if not is_sorted and _is_generic_stem(primary.path.stem):
                all_results = [primary, *near_misses]
                non_generic = [r for r in all_results if not _is_generic_stem(r.path.stem)]
                generic = [r for r in all_results if _is_generic_stem(r.path.stem)]
                if non_generic:
                    primary = non_generic[0]
                    near_misses = [*non_generic[1:], *generic]

            displayed_near_misses: list = []
            if near_misses and top_n_final > 1:
                displayed_near_misses = get_ordered_display_matches(
                    near_misses,
                    search_root=search_root,
                    limit=top_n_final - 1,
                )

            # Persist last-search snapshot matching the exact visual console numbering
            from sempath.models import SearchResult
            from sempath.utils.history import save_history

            snapshot_result = SearchResult(
                status="success",
                query=query,
                match=primary,
                near_misses=displayed_near_misses,
                elapsed_seconds=search_result.elapsed_seconds,
            )
            save_history(
                query=query,
                root_dir=search_root,
                elapsed_seconds=search_result.elapsed_seconds,
                search_result=snapshot_result,
            )

            # Output results
            if json_output:
                click.echo(json.dumps(search_result.to_dict(), indent=2))
                sys.exit(0)

            match_count_header = ""
            if primary.snippets:
                n_snip = len(primary.snippets)
                plural = "s" if n_snip > 1 else ""
                match_count_header = f" ({n_snip} line occurrence{plural})"
            meta = _format_file_meta(primary.path) + (
                f" [dim]({primary.handler}, confidence: {primary.confidence:.2f})[/]"
                if verbose_final
                else ""
            )
            copy_to_clipboard(str(primary.path))
            escaped_path = escape(str(primary.path))
            time_str = (
                f" [dim cyan]({_format_elapsed_time(search_result.elapsed_seconds)})[/]"
                if search_result.elapsed_seconds > 0
                else ""
            )

            msg_hdr = f"[bold green]✔ Success{time_str}:[/] Found match{match_count_header}:"

            console.print(f"{msg_hdr} [bold cyan]{escaped_path}[/]{meta}")
            if primary.snippets:
                for line_num, snippet_text in primary.snippets:
                    formatted_snippet = _format_snippet(snippet_text, query)
                    console.print(f"  [dim]└─ L{line_num}:[/] {formatted_snippet}")
            if displayed_near_misses:
                _print_grouped_matches(
                    displayed_near_misses,
                    limit=len(displayed_near_misses),
                    verbose=verbose_final,
                    query=query,
                    start_index=2,
                )

            sys.exit(0)
        elif search_result.status == "ambiguous":
            if not non_interactive_final and search_result.near_misses:
                top_candidates = list(search_result.near_misses)[:5]
                err_console.print(
                    "\n[bold yellow]?[/] No exact match found. Did you mean one of these?"
                )
                for idx, nm in enumerate(top_candidates, start=1):
                    nm_meta = _format_file_meta(nm.path)
                    if verbose_final:
                        nm_meta += f" [dim]({nm.handler}, confidence: {nm.confidence:.2f})[/]"
                    err_console.print(f"  {idx}. [cyan]{escape(str(nm.path))}[/]{nm_meta}")
                err_console.print(f"  {len(top_candidates) + 1}. [dim]None of the above[/]")

                try:
                    selection = click.prompt(
                        f"Select an option (1-{len(top_candidates) + 1})",
                        type=int,
                        default=len(top_candidates) + 1,
                        show_default=True,
                        err=True,
                    )
                except click.Abort:
                    displayed_ambiguous = get_ordered_display_matches(
                        search_result.near_misses,
                        search_root=search_root,
                        limit=top_n_final,
                    )
                    from sempath.models import SearchResult
                    from sempath.utils.history import save_history

                    snapshot_result = SearchResult(
                        status="ambiguous",
                        query=query,
                        near_misses=displayed_ambiguous,
                        elapsed_seconds=search_result.elapsed_seconds,
                    )
                    save_history(
                        query=query,
                        root_dir=search_root,
                        elapsed_seconds=search_result.elapsed_seconds,
                        search_result=snapshot_result,
                    )
                    console.print(f"[bold yellow]⚠ Ambiguous query:[/] {search_result.message}")
                    if displayed_ambiguous:
                        _print_grouped_matches(
                            displayed_ambiguous,
                            limit=len(displayed_ambiguous),
                            verbose=verbose_final,
                        )
                    sys.exit(1)

                if 1 <= selection <= len(top_candidates):
                    selected_nm = top_candidates[selection - 1]
                    try:
                        from sempath.utils.memory import add_or_update_memory

                        add_or_update_memory(query, selected_nm.path)
                        err_console.print(
                            f"[bold green]Confirmed:[/] Learned alias "
                            f"[cyan]{escape(query)}[/] -> [bold]{escape(str(selected_nm.path))}[/]"
                        )
                        err_console.print("[dim](run 'sempath alias undo' to revert)[/]")
                    except Exception as exc:
                        from sempath.utils.logging import verbose_log

                        verbose_log(f"[dim]Failed to save learned memory: {exc}[/]")

                    # Save confirmed match as primary in history
                    from sempath.models import SearchResult
                    from sempath.utils.history import save_history

                    remaining_candidates = [c for c in top_candidates if c.path != selected_nm.path]
                    snapshot_result = SearchResult(
                        status="success",
                        query=query,
                        match=selected_nm,
                        near_misses=remaining_candidates,
                        elapsed_seconds=search_result.elapsed_seconds,
                    )
                    save_history(
                        query=query,
                        root_dir=search_root,
                        elapsed_seconds=search_result.elapsed_seconds,
                        search_result=snapshot_result,
                    )

                    meta = _format_file_meta(selected_nm.path) + (
                        f" [dim]({selected_nm.handler}, "
                        f"confidence: {selected_nm.confidence:.2f})[/]"
                        if verbose_final
                        else ""
                    )
                    copy_to_clipboard(str(selected_nm.path))
                    console.print(
                        f"[bold green]✔ Success:[/] Found match: "
                        f"[bold cyan]{escape(str(selected_nm.path))}[/]{meta}"
                    )
                    sys.exit(0)

            displayed_ambiguous = get_ordered_display_matches(
                search_result.near_misses,
                search_root=search_root,
                limit=top_n_final,
            )
            from sempath.models import SearchResult
            from sempath.utils.history import save_history

            snapshot_result = SearchResult(
                status="ambiguous",
                query=query,
                near_misses=displayed_ambiguous,
                elapsed_seconds=search_result.elapsed_seconds,
            )
            save_history(
                query=query,
                root_dir=search_root,
                elapsed_seconds=search_result.elapsed_seconds,
                search_result=snapshot_result,
            )

            if json_output:
                click.echo(json.dumps(search_result.to_dict(), indent=2))
                sys.exit(1)

            console.print(f"[bold yellow]⚠ Ambiguous query:[/] {search_result.message}")
            if displayed_ambiguous:
                _print_grouped_matches(
                    displayed_ambiguous,
                    limit=len(displayed_ambiguous),
                    verbose=verbose_final,
                )
            sys.exit(1)
        else:
            if json_output:
                click.echo(json.dumps(search_result.to_dict(), indent=2))
                sys.exit(1)
            console.print(f"[bold red]❌ Failed:[/] {search_result.message}")
            sys.exit(1)
