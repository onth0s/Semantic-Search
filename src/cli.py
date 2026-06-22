"""CLI entry point for sempath.

Uses Click for subcommand routing and Rich for styled terminal output.
All user-facing messages are rendered through Rich's console for
consistent colored output.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import click
from rich.console import Console

from src import __version__
from src.chain import build_chain
from src.config import load_config
from src.models import MatchResult, SearchResult
from src.scanner import scan_directory

# ---------------------------------------------------------------------------
# Rich console — shared across all commands
# ---------------------------------------------------------------------------

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(__version__, prog_name="sempath")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """sempath — find filesystem paths by vague, colloquial, or fuzzy descriptions."""
    ctx.ensure_object(dict)


# ---------------------------------------------------------------------------
# find
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("query")
@click.argument("root_dir", default=".", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Root directory to search (overrides ROOT_DIR argument).",
)
@click.option(
    "--depth", default=5, type=int, show_default=True, help="Maximum folder depth to traverse."
)
@click.option(
    "--min-confidence",
    default=0.3,
    type=float,
    show_default=True,
    help="Minimum confidence score (0.0-1.0) to return a match.",
)
@click.option(
    "--top-n", default=1, type=int, show_default=True, help="Number of results to return."
)
@click.option(
    "--non-interactive", is_flag=True, default=False, help="Disable interactive fallback (H9)."
)
@click.option("--no-index", is_flag=True, default=False, help="Force on-the-fly traversal scan.")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Output structured JSON instead of styled text.",
)
@click.option(
    "--verbose", is_flag=True, default=False, help="Enable handler-by-handler execution logs."
)
@click.option(
    "--latest", is_flag=True, default=False, help="Sort matches to return the newest path."
)
@click.option(
    "--largest", is_flag=True, default=False, help="Sort matches to return the largest file."
)
@click.option(
    "--ext",
    type=str,
    default=None,
    help="Filter candidates to keep only those with specified extension.",
)
@click.pass_context
def find(
    ctx: click.Context,
    query: str,
    root_dir: Path,
    root: Path | None,
    depth: int,
    min_confidence: float,
    top_n: int,
    non_interactive: bool,
    no_index: bool,
    json_output: bool,
    verbose: bool,
    latest: bool,
    largest: bool,
    ext: str | None,
) -> None:
    """Search for filesystem paths matching QUERY.

    QUERY is a vague, colloquial, or fuzzy description of the path you're
    looking for. ROOT_DIR (default: current directory) is the starting
    point for the search.
    """
    search_root = root or root_dir

    try:
        config = load_config()
    except (FileNotFoundError, ValueError) as exc:
        err_console.print(f"[bold red]Error loading config:[/] {exc}")
        sys.exit(1)

    # Store options in context for handler access
    ctx.obj.update(
        {
            "query": query,
            "root": search_root,
            "depth": depth,
            "min_confidence": min_confidence,
            "top_n": top_n,
            "non_interactive": non_interactive,
            "no_index": no_index,
            "json_output": json_output,
            "verbose": verbose,
            "config": config,
            "latest": latest,
            "largest": largest,
            "ext": ext,
        }
    )

    if verbose:
        console.print(f"[dim]Query:[/]  [bold cyan]{query}[/]")
        console.print(f"[dim]Root:[/]   [bold]{search_root}[/]")
        console.print(f"[dim]Depth:[/]  {depth}")
        console.print()

    # Scan directory
    exclude_patterns = config.get("index", {}).get("exclude_patterns", [])
    candidates = scan_directory(search_root, depth=depth, exclude_patterns=exclude_patterns)

    # Apply extension filter if provided
    if ext:
        ext_clean = ext.lower().lstrip(".")
        candidates = [p for p in candidates if p.suffix.lower().lstrip(".") == ext_clean]

    # Sort by time or size if requested
    if latest:

        def get_mtime(p: Path) -> float:
            try:
                return p.stat().st_mtime
            except Exception:
                return 0.0

        candidates.sort(key=get_mtime, reverse=True)

    if largest:

        def get_size(p: Path) -> int:
            try:
                return p.stat().st_size if p.is_file() else 0
            except Exception:
                return 0

        candidates.sort(key=get_size, reverse=True)

    # Check for direct bypass when query is a placeholder and sorting/filtering is active
    if query in ("", ".", "*") and (latest or largest or ext) and candidates:
        match_result = MatchResult(candidates[0], 1.0, "explicit_flags")
    else:
        # Build and execute chain
        try:
            chain = build_chain(config)
        except ValueError as exc:
            err_console.print(f"[bold red]Error building handler chain:[/] {exc}")
            sys.exit(1)

        match_result = chain.handle(query, candidates)

    if match_result is not None and match_result.confidence >= min_confidence:
        search_result = SearchResult(
            status="success",
            query=query,
            match=match_result,
        )
    else:
        # Collect near-misses from all enabled handlers
        near_misses = []
        seen_paths = set()
        current = chain
        while current is not None:
            try:
                res = current.match(query, candidates)
                if res is not None and res.path not in seen_paths:
                    near_misses.append(res)
                    seen_paths.add(res.path)
            except Exception:
                pass
            current = getattr(current, "next_handler", None)

        # Filter near-misses above a minimum relevance threshold (e.g. 0.2)
        near_misses = [m for m in near_misses if m.confidence >= 0.2]
        # Rank by confidence descending
        near_misses.sort(key=lambda m: m.confidence, reverse=True)

        if near_misses:
            search_result = SearchResult(
                status="ambiguous",
                query=query,
                near_misses=near_misses,
                message="No match found above confidence threshold.",
            )
        else:
            search_result = SearchResult(
                status="failed",
                query=query,
                message="No candidate paths or near-misses matched the query.",
            )

    # Output results
    if json_output:
        click.echo(json.dumps(search_result.to_dict(), indent=2))
        sys.exit(0 if search_result.status == "success" else 1)
    else:
        if search_result.status == "success":
            res = search_result.match
            console.print(
                f"[bold green]✔ Success:[/] Found match: [bold cyan]{res.path}[/]"
                f" [dim]({res.handler}, confidence: {res.confidence:.2f})[/]"
            )
            sys.exit(0)
        elif search_result.status == "ambiguous":
            console.print(f"[bold yellow]⚠ Ambiguous query:[/] {search_result.message}")
            console.print("[bold]Near misses:[/]")
            for nm in search_result.near_misses[:top_n]:
                console.print(
                    f"  - [cyan]{nm.path}[/] "
                    f"[dim]({nm.handler}, confidence: {nm.confidence:.2f})[/]"
                )
            sys.exit(1)
        else:
            console.print(f"[bold red]❌ Failed:[/] {search_result.message}")
            sys.exit(1)


# ---------------------------------------------------------------------------
# index subgroup
# ---------------------------------------------------------------------------


@cli.group()
def index() -> None:
    """Manage the persistent path index."""


@index.command("create")
@click.argument("path", default=".", type=click.Path(exists=True, path_type=Path))
def index_create(path: Path) -> None:
    """Build a new index for PATH."""
    console.print(f"[yellow]⚠[/]  Index creation not yet implemented. Path: [bold]{path}[/]")


@index.command("update")
@click.argument("path", default=".", type=click.Path(exists=True, path_type=Path))
def index_update(path: Path) -> None:
    """Incrementally update the index for PATH."""
    console.print(f"[yellow]⚠[/]  Index update not yet implemented. Path: [bold]{path}[/]")


@index.command("list")
def index_list() -> None:
    """List all indexed paths."""
    console.print("[yellow]⚠[/]  Index listing not yet implemented.")


@index.command("remove")
def index_remove() -> None:
    """Remove the persistent index."""
    console.print("[yellow]⚠[/]  Index removal not yet implemented.")


# ---------------------------------------------------------------------------
# alias subgroup
# ---------------------------------------------------------------------------


@cli.group()
def alias() -> None:
    """Manage path aliases and learned mappings."""


@alias.command("add")
@click.argument("name")
@click.argument("path", type=click.Path(path_type=Path))
def alias_add(name: str, path: Path) -> None:
    """Add a new alias NAME pointing to PATH."""
    from src.utils.memory import add_or_update_memory

    try:
        add_or_update_memory(name, path)
        console.print(
            f"[bold green]✔ Success:[/] Added alias [bold cyan]{name}[/] → [bold]{path}[/]"
        )
    except Exception as exc:
        err_console.print(f"[bold red]Error adding alias:[/] {exc}")
        sys.exit(1)


@alias.command("list")
def alias_list() -> None:
    """List all configured and learned aliases."""
    from rich.table import Table

    from src.utils.memory import load_memory

    table = Table(title="sempath Path Aliases")
    table.add_column("Type", style="bold magenta")
    table.add_column("Alias / Query", style="cyan")
    table.add_column("Target / Path", style="green")
    table.add_column("Hits", justify="right")
    table.add_column("Decay Rank", justify="right")

    # Load config aliases
    try:
        cfg = load_config()
        config_aliases = cfg.get("aliases", {})
        for name, targets in config_aliases.items():
            table.add_row("Config", name, ", ".join(targets), "-", "-")
    except Exception as exc:
        err_console.print(f"[dim red]Warning: could not load config aliases: {exc}[/]")

    # Load learned aliases
    try:
        learned = load_memory()
        for entry in learned:
            table.add_row(
                "Learned",
                entry.get("query", ""),
                entry.get("path", ""),
                str(entry.get("hits", 1)),
                f"{entry.get('decay_rank', 0.0):.2f}",
            )
    except Exception as exc:
        err_console.print(f"[dim red]Warning: could not load learned memory: {exc}[/]")

    console.print(table)


@alias.command("remove")
@click.argument("name")
def alias_remove(name: str) -> None:
    """Remove alias NAME."""
    from src.utils.memory import load_memory, save_memory

    try:
        entries = load_memory()
        filtered = [e for e in entries if e.get("query", "").lower() != name.lower()]
        if len(filtered) == len(entries):
            console.print(f"[yellow]⚠[/] No learned alias found for [bold cyan]{name}[/].")
            return
        save_memory(filtered)
        console.print(f"[bold green]✔ Success:[/] Removed alias [bold cyan]{name}[/]")
    except Exception as exc:
        err_console.print(f"[bold red]Error removing alias:[/] {exc}")
        sys.exit(1)


@alias.command("clear")
def alias_clear() -> None:
    """Clear all learned aliases."""
    from src.utils.memory import save_memory

    try:
        save_memory([])
        console.print("[bold green]✔ Success:[/] All learned aliases cleared.")
    except Exception as exc:
        err_console.print(f"[bold red]Error clearing aliases:[/] {exc}")
        sys.exit(1)


@alias.command("undo")
def alias_undo() -> None:
    """Undo the last learned alias (chronological undo stack)."""
    from src.utils.memory import undo_last_memory

    try:
        popped = undo_last_memory()
        if popped is None:
            console.print("[yellow]⚠[/] No learned aliases to undo.")
        else:
            console.print(
                f"[bold green]✔ Success:[/] Reverted last alias: "
                f"[bold cyan]{popped.get('query')}[/] → [bold]{popped.get('path')}[/]"
            )
    except Exception as exc:
        err_console.print(f"[bold red]Error undoing alias:[/] {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Memory import / export
# ---------------------------------------------------------------------------


@cli.command("export-memory")
@click.argument("file_path", type=click.Path(path_type=Path))
def export_memory(file_path: Path) -> None:
    """Export learned aliases and memory to FILE_PATH."""
    from src.utils.memory import get_memory_file_path

    src = get_memory_file_path()
    if not src.exists():
        console.print("[yellow]⚠[/] No learned aliases exist to export.")
        return

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, file_path)
        console.print(f"[bold green]✔ Success:[/] Exported memory to [bold]{file_path}[/]")
    except Exception as exc:
        err_console.print(f"[bold red]Error exporting memory:[/] {exc}")
        sys.exit(1)


@cli.command("import-memory")
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
def import_memory(file_path: Path) -> None:
    """Import learned aliases and memory from FILE_PATH."""
    from src.utils.memory import merge_memory_files

    try:
        merge_memory_files(file_path)
        console.print(f"[bold green]✔ Success:[/] Imported memory from [bold]{file_path}[/]")
    except Exception as exc:
        err_console.print(f"[bold red]Error importing memory:[/] {exc}")
        sys.exit(1)
