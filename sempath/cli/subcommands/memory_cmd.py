"""Memory import/export commands for the sempath CLI."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click
from rich.markup import escape

import sempath.utils.memory
from sempath.utils.console import console, err_console


def register_memory_commands(cli_group: click.Group) -> None:
    """Register the memory export/import commands."""

    @cli_group.command("export-memory")
    @click.argument("file_path", type=click.Path(path_type=Path))
    def export_memory(file_path: Path) -> None:
        """Export learned aliases and memory to FILE_PATH."""
        src = sempath.utils.memory.get_memory_file_path()
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
        try:
            sempath.utils.memory.merge_memory_files(file_path)
            console.print(
                f"[bold green]✔ Success:[/] Imported memory from [bold]{escape(str(file_path))}[/]"
            )
        except Exception as exc:
            err_console.print(f"[bold red]Error importing memory:[/] {exc}")
            sys.exit(1)
