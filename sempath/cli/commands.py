"""Subcommands and subcommand groups for the sempath CLI."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click
from rich.markup import escape

from sempath.config import get_index_store_path, load_config, save_config
from sempath.index import IndexManager
from sempath.utils.console import console, err_console


def register_commands(cli_group: click.Group) -> None:
    """Register all subcommands and groups onto the main root CLI group."""

    # ---------------------------------------------------------------------------
    # index subgroup
    # ---------------------------------------------------------------------------

    @cli_group.group()
    def index() -> None:
        """Manage the persistent path index."""

    @index.command("create")
    @click.argument("path", default=".", type=click.Path(exists=True, path_type=Path))
    @click.option("--depth", default=5, type=int, help="Maximum folder depth to traverse.")
    def index_create(path: Path, depth: int) -> None:
        """Build a new index for PATH."""
        try:
            cfg = load_config()
            exclude = cfg.get("index", {}).get("exclude_patterns", [])
            respect_gi = cfg.get("index", {}).get("respect_gitignore", True)

            manager = IndexManager(get_index_store_path(cfg))
            console.print(
                f"[yellow]Scanning and indexing:[/] {escape(str(path))} (depth: {depth})..."
            )
            added, deleted = manager.create_or_update_index(
                path, depth=depth, exclude_patterns=exclude, respect_gitignore=respect_gi
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
    @click.option("--depth", default=5, type=int, help="Maximum folder depth to traverse.")
    def index_update(path: Path, depth: int) -> None:
        """Incrementally update the index for PATH."""
        try:
            cfg = load_config()
            exclude = cfg.get("index", {}).get("exclude_patterns", [])
            respect_gi = cfg.get("index", {}).get("respect_gitignore", True)

            manager = IndexManager(get_index_store_path(cfg))
            console.print(f"[yellow]Updating index for:[/] {escape(str(path))}...")
            added, deleted = manager.create_or_update_index(
                path, depth=depth, exclude_patterns=exclude, respect_gitignore=respect_gi
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

    # ---------------------------------------------------------------------------
    # alias subgroup
    # ---------------------------------------------------------------------------

    @cli_group.group()
    def alias() -> None:
        """Manage path aliases and learned mappings."""

    @alias.command("add")
    @click.argument("name")
    @click.argument("path", type=click.Path(path_type=Path))
    def alias_add(name: str, path: Path) -> None:
        """Add a new alias NAME pointing to PATH."""
        from sempath.utils.memory import add_or_update_memory

        try:
            clean_path_str = str(path).strip("'\"")
            add_or_update_memory(name, clean_path_str)
            escaped_name = escape(name)
            escaped_path = escape(clean_path_str)
            console.print(
                "[bold green]✔ Success:[/] Added alias"
                f" [bold cyan]{escaped_name}[/] → [bold]{escaped_path}[/]"
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error adding alias:[/] {exc}")
            sys.exit(1)

    @alias.command("list")
    def alias_list() -> None:
        """List all configured and learned aliases."""
        from rich.table import Table

        from sempath.utils.memory import load_memory

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
        from sempath.utils.memory import load_memory, save_memory

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
        from sempath.utils.memory import save_memory

        try:
            save_memory([])
            console.print("[bold green]✔ Success:[/] All learned aliases cleared.")
        except Exception as exc:
            err_console.print(f"[bold red]Error clearing aliases:[/] {exc}")
            sys.exit(1)

    @alias.command("undo")
    def alias_undo() -> None:
        """Undo the last learned alias (chronological undo stack)."""
        from sempath.utils.memory import undo_last_memory

        try:
            popped = undo_last_memory()
            if popped is None:
                console.print("[yellow]⚠[/] No learned aliases to undo.")
            else:
                escaped_query = escape(popped.get("query", ""))
                escaped_path = escape(popped.get("path", ""))
                console.print(
                    f"[bold green]✔ Success:[/] Reverted last alias: "
                    f"[bold cyan]{escaped_query}[/] → [bold]{escaped_path}[/]"
                )
        except Exception as exc:
            err_console.print(f"[bold red]Error undoing alias:[/] {exc}")
            sys.exit(1)

    # ---------------------------------------------------------------------------
    # Memory import / export
    # ---------------------------------------------------------------------------

    @cli_group.command("export-memory")
    @click.argument("file_path", type=click.Path(path_type=Path))
    def export_memory(file_path: Path) -> None:
        """Export learned aliases and memory to FILE_PATH."""
        from sempath.utils.memory import get_memory_file_path

        src = get_memory_file_path()
        if not src.exists():
            console.print("[yellow]⚠[/] No learned aliases exist to export.")
            return

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, file_path)
            console.print(
                f"[bold green]✔ Success:[/] Exported memory to [bold]{escape(str(file_path))}[/]"
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error exporting memory:[/] {exc}")
            sys.exit(1)

    @cli_group.command("import-memory")
    @click.argument("file_path", type=click.Path(exists=True, path_type=Path))
    def import_memory(file_path: Path) -> None:
        """Import learned aliases and memory from FILE_PATH."""
        from sempath.utils.memory import merge_memory_files

        try:
            merge_memory_files(file_path)
            console.print(
                f"[bold green]✔ Success:[/] Imported memory from [bold]{escape(str(file_path))}[/]"
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error importing memory:[/] {exc}")
            sys.exit(1)

    # ---------------------------------------------------------------------------
    # config subgroup
    # ---------------------------------------------------------------------------

    @cli_group.group()
    def config() -> None:
        """Manage the persistent configuration settings."""

    @config.command("verbose")
    @click.argument(
        "value", type=click.Choice(["on", "off", "true", "false"], case_sensitive=False)
    )
    def config_verbose(value: str) -> None:
        """Enable or disable verbose output globally."""
        is_verbose = value.lower() in ("on", "true")
        try:
            save_config({"verbose": is_verbose})
            status_str = "enabled" if is_verbose else "disabled"
            console.print(
                f"[bold green]✔ Success:[/] Verbose logging has been [bold]{status_str}[/]."
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error updating configuration:[/] {exc}")
            sys.exit(1)

    @config.command("gitignore")
    @click.argument(
        "value", type=click.Choice(["on", "off", "true", "false"], case_sensitive=False)
    )
    def config_gitignore(value: str) -> None:
        """Enable or disable respecting .gitignore rules globally."""
        respect = value.lower() in ("on", "true")
        try:
            save_config({"index": {"respect_gitignore": respect}})
            status_str = "enabled" if respect else "disabled"
            console.print(
                "[bold green]✔ Success:[/] Respecting .gitignore rules has been "
                f"[bold]{status_str}[/]."
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error updating configuration:[/] {exc}")
            sys.exit(1)
