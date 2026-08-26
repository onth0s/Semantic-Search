"""Index management subcommands for the sempath CLI."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.markup import escape

from sempath.config import get_index_store_path, load_config
from sempath.constants import DEFAULT_DEPTH
from sempath.index import IndexManager
from sempath.utils.console import console, err_console


def register_index_commands(cli_group: click.Group) -> None:
    """Register the index subgroup and commands."""

    @cli_group.group()
    def index() -> None:
        """Manage the persistent path index."""

    @index.command("create")
    @click.argument("path", default=".", type=click.Path(exists=True, path_type=Path))
    @click.option("--depth", default=None, type=int, help="Maximum folder depth to traverse.")
    @click.option(
        "--full-depth",
        is_flag=True,
        default=False,
        help="Index recursively with unlimited depth (-1).",
    )
    def index_create(path: Path, depth: int | None, full_depth: bool) -> None:
        """Build a new index for PATH."""
        try:
            cfg = load_config()
            exclude = cfg.get("index", {}).get("exclude_patterns", [])
            respect_gi = cfg.get("index", {}).get("respect_gitignore", True)
            if full_depth or (depth is not None and depth == -1):
                depth_final = -1
            elif depth is not None:
                depth_final = depth
            else:
                depth_final = cfg.get("depth", DEFAULT_DEPTH)

            manager = IndexManager(get_index_store_path(cfg))
            depth_str = "unlimited" if depth_final == -1 else str(depth_final)
            console.print(
                f"[yellow]Scanning and indexing:[/] {escape(str(path))} (depth: {depth_str})..."
            )
            added, deleted = manager.create_or_update_index(
                path, depth=depth_final, exclude_patterns=exclude, respect_gitignore=respect_gi
            )
            console.print(
                f"[bold green]✔ Success:[/] Indexed root: [bold]{path}[/] "
                f"([cyan]+{added}[/] added, [magenta]-{deleted}[/] deleted)."
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error building index:[/] {exc}")
            sys.exit(1)

    @index.command("update")
    @click.argument("path", default=".", type=click.Path(exists=True, path_type=Path))
    @click.option("--depth", default=None, type=int, help="Maximum folder depth to traverse.")
    @click.option(
        "--full-depth",
        is_flag=True,
        default=False,
        help="Update index recursively with unlimited depth (-1).",
    )
    def index_update(path: Path, depth: int | None, full_depth: bool) -> None:
        """Incrementally update the index for PATH."""
        try:
            cfg = load_config()
            exclude = cfg.get("index", {}).get("exclude_patterns", [])
            respect_gi = cfg.get("index", {}).get("respect_gitignore", True)
            if full_depth or (depth is not None and depth == -1):
                depth_final = -1
            elif depth is not None:
                depth_final = depth
            else:
                depth_final = cfg.get("depth", DEFAULT_DEPTH)

            manager = IndexManager(get_index_store_path(cfg))
            console.print(f"[yellow]Updating index for:[/] {escape(str(path))}...")
            added, deleted = manager.create_or_update_index(
                path, depth=depth_final, exclude_patterns=exclude, respect_gitignore=respect_gi
            )
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
            cfg = load_config()

            manager = IndexManager(get_index_store_path(cfg))
            roots = manager.get_indexed_roots()
            if not roots:
                console.print("[yellow]No roots are currently indexed.[/]")
            else:
                console.print("[bold]Indexed root directories:[/]")
                for r in roots:
                    console.print(f"  - [cyan]{escape(r)}[/]")
        except Exception as exc:
            err_console.print(f"[bold red]Error listing index:[/] {exc}")
            sys.exit(1)

    @index.command("remove")
    @click.argument("path", default=".", type=click.Path(path_type=Path))
    @click.option("--all", "all_roots", is_flag=True, help="Clear the entire index database.")
    def index_remove(path: Path, all_roots: bool) -> None:
        """Remove the persistent index for PATH or clear ALL."""
        try:
            cfg = load_config()

            manager = IndexManager(get_index_store_path(cfg))
            if all_roots:
                manager.clear_index()
                console.print("[bold green]✔ Success:[/] Entire index database cleared.")
            else:
                removed = manager.remove_root(path)
                if removed:
                    escaped_root = escape(str(path))
                    console.print(
                        "[bold green]✔ Success:[/] Removed root "
                        f"[bold]{escaped_root}[/] from index."
                    )
                else:
                    console.print(
                        "[yellow]⚠[/] Path "
                        f"[bold]{escape(str(path))}[/] was not found in the index."
                    )
        except Exception as exc:
            err_console.print(f"[bold red]Error removing from index:[/] {exc}")
            sys.exit(1)
