"""CLI entry point for sempath.

Uses Click for subcommand routing and Rich for styled terminal output.
All user-facing messages are rendered through Rich's console for
consistent colored output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console

from src import __version__
from src.config import load_config

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
        }
    )

    if verbose:
        console.print(f"[dim]Query:[/]  [bold cyan]{query}[/]")
        console.print(f"[dim]Root:[/]   [bold]{search_root}[/]")
        console.print(f"[dim]Depth:[/]  {depth}")
        console.print()

    # Phase 1 placeholder — chain execution will be wired in Phase 2
    if json_output:
        placeholder = {
            "status": "failed",
            "query": query,
            "message": "Handler chain not yet implemented (Phase 1 scaffold).",
            "near_misses": [],
        }
        click.echo(json.dumps(placeholder, indent=2))
    else:
        console.print(
            "[yellow]⚠[/]  Handler chain not yet implemented (Phase 1 scaffold).\n"
            f"   Query: [bold cyan]{query}[/]\n"
            f"   Root:  [bold]{search_root}[/]"
        )


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
    console.print(
        f"[yellow]⚠[/]  Alias add not yet implemented. "
        f"Name: [bold cyan]{name}[/] → Path: [bold]{path}[/]"
    )


@alias.command("list")
def alias_list() -> None:
    """List all configured and learned aliases."""
    console.print("[yellow]⚠[/]  Alias listing not yet implemented.")


@alias.command("remove")
@click.argument("name")
def alias_remove(name: str) -> None:
    """Remove alias NAME."""
    console.print(f"[yellow]⚠[/]  Alias removal not yet implemented. Name: [bold cyan]{name}[/]")


@alias.command("clear")
def alias_clear() -> None:
    """Clear all learned aliases."""
    console.print("[yellow]⚠[/]  Alias clear not yet implemented.")


@alias.command("undo")
def alias_undo() -> None:
    """Undo the last learned alias (chronological undo stack)."""
    console.print("[yellow]⚠[/]  Alias undo not yet implemented.")


# ---------------------------------------------------------------------------
# Memory import / export
# ---------------------------------------------------------------------------


@cli.command("export-memory")
@click.argument("file_path", type=click.Path(path_type=Path))
def export_memory(file_path: Path) -> None:
    """Export learned aliases and memory to FILE_PATH."""
    console.print(f"[yellow]⚠[/]  Memory export not yet implemented. Target: [bold]{file_path}[/]")


@cli.command("import-memory")
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
def import_memory(file_path: Path) -> None:
    """Import learned aliases and memory from FILE_PATH."""
    console.print(f"[yellow]⚠[/]  Memory import not yet implemented. Source: [bold]{file_path}[/]")
