"""Alias management subcommands for the sempath CLI."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.markup import escape

from sempath.config import load_config
from sempath.utils.console import console, err_console


def register_alias_commands(cli_group: click.Group) -> None:
    """Register the alias subgroup and commands."""

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
