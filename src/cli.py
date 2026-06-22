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

from src import __version__
from src.config import load_config
from src.utils.console import console, err_console

# ---------------------------------------------------------------------------
# Rich console — shared across all commands
# ---------------------------------------------------------------------------

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

    from src.engine import SearchEngine

    try:
        engine = SearchEngine(config)
        search_result = engine.find_path(
            query=query,
            root_dir=search_root,
            depth=depth,
            min_confidence=min_confidence,
            top_n=top_n,
            non_interactive=non_interactive,
            no_index=no_index,
            latest=latest,
            largest=largest,
            ext=ext,
            verbose=verbose,
        )
    except Exception as exc:
        err_console.print(f"[bold red]Search Engine error:[/] {exc}")
        sys.exit(1)

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
@click.option("--depth", default=5, type=int, help="Maximum folder depth to traverse.")
def index_create(path: Path, depth: int) -> None:
    """Build a new index for PATH."""
    try:
        config = load_config()
        store = config.get("index", {}).get("store", "")
        exclude = config.get("index", {}).get("exclude_patterns", [])
        from src.index import IndexManager

        manager = IndexManager(Path(store))
        console.print(f"[yellow]Scanning and indexing:[/] {path} (depth: {depth})...")
        added, deleted = manager.create_or_update_index(path, depth=depth, exclude_patterns=exclude)
        console.print(
            f"[bold green]✔ Success:[/] Indexed root: [bold]{path}[/] "
            f"([cyan]+{added}[/] added, [magenta]-{deleted}[/] deleted)."
        )
    except Exception as exc:
        err_console.print(f"[bold red]Error building index:[/] {exc}")
        sys.exit(1)


@index.command("update")
@click.argument("path", default=".", type=click.Path(exists=True, path_type=Path))
@click.option("--depth", default=5, type=int, help="Maximum folder depth to traverse.")
def index_update(path: Path, depth: int) -> None:
    """Incrementally update the index for PATH."""
    try:
        config = load_config()
        store = config.get("index", {}).get("store", "")
        exclude = config.get("index", {}).get("exclude_patterns", [])
        from src.index import IndexManager

        manager = IndexManager(Path(store))
        console.print(f"[yellow]Updating index for:[/] {path}...")
        added, deleted = manager.create_or_update_index(path, depth=depth, exclude_patterns=exclude)
        console.print(
            f"[bold green]✔ Success:[/] Updated root: [bold]{path}[/] "
            f"([cyan]+{added}[/] updated, [magenta]-{deleted}[/] removed)."
        )
    except Exception as exc:
        err_console.print(f"[bold red]Error updating index:[/] {exc}")
        sys.exit(1)


@index.command("list")
def index_list() -> None:
    """List all indexed paths."""
    try:
        config = load_config()
        store = config.get("index", {}).get("store", "")
        from src.index import IndexManager

        manager = IndexManager(Path(store))
        roots = manager.get_indexed_roots()
        if not roots:
            console.print("[yellow]No roots are currently indexed.[/]")
        else:
            console.print("[bold]Indexed root directories:[/]")
            for r in roots:
                console.print(f"  - [cyan]{r}[/]")
    except Exception as exc:
        err_console.print(f"[bold red]Error listing index:[/] {exc}")
        sys.exit(1)


@index.command("remove")
@click.argument("path", default=".", type=click.Path(path_type=Path))
@click.option("--all", "all_roots", is_flag=True, help="Clear the entire index database.")
def index_remove(path: Path, all_roots: bool) -> None:
    """Remove the persistent index for PATH or clear ALL."""
    try:
        config = load_config()
        store = config.get("index", {}).get("store", "")
        from src.index import IndexManager

        manager = IndexManager(Path(store))
        if all_roots:
            manager.clear_index()
            console.print("[bold green]✔ Success:[/] Entire index database cleared.")
        else:
            removed = manager.remove_root(path)
            if removed:
                console.print(f"[bold green]✔ Success:[/] Removed root [bold]{path}[/] from index.")
            else:
                console.print(f"[yellow]⚠[/] Path [bold]{path}[/] was not found in the index.")
    except Exception as exc:
        err_console.print(f"[bold red]Error removing from index:[/] {exc}")
        sys.exit(1)


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
