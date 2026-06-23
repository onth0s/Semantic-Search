"""CLI entry point for sempath.

Uses Click for subcommand routing and Rich for styled terminal output.
All user-facing messages are rendered through Rich's console for
consistent colored output.

Rich Click configuration
-----------------------
``rich_click`` patches Click's help formatter so ``--help`` output is
colored and styled to match the rest of the CLI.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import click
import rich_click

from sempath import __version__
from sempath.config import load_config
from sempath.utils.console import console, err_console

rich_click.STYLE_OPTION = "bold cyan"
rich_click.STYLE_ARGUMENT = "cyan"
rich_click.STYLE_COMMAND = "bold green"
rich_click.STYLE_ERRORS_OPTION = "bold red"
rich_click.STYLE_METAVAR = "dim"
rich_click.STYLE_HELPTEXT = ""


# ---------------------------------------------------------------------------
def print_full_help(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    """Callback to print comprehensive help for all commands and subcommands recursively."""
    if not value or ctx.resilient_parsing:
        return

    def _print_command_help(cmd: click.Command, prefix_args: list[str]) -> None:
        cmd_ctx = cmd.context_class(cmd, info_name=" ".join(prefix_args))
        full_name = " ".join(prefix_args)
        # Blank line separator between blocks (not before the first one)
        if prefix_args != [ctx.info_name]:
            console.print()
        console.print(f"[dim]COMMAND: [bold cyan]{full_name}[/][/]")
        console.print("=" * (len(full_name) + 9))
        help_text = cmd.get_help(cmd_ctx)
        if isinstance(cmd, click.Group):
            cmds_idx = help_text.find("┌─ Commands")
            if cmds_idx != -1:
                help_text = help_text[:cmds_idx].rstrip()
        console.print(help_text, markup=False)
        if isinstance(cmd, click.Group):
            sub_names = sorted(cmd.list_commands(cmd_ctx))
            for name in sub_names:
                sub_cmd = cmd.get_command(cmd_ctx, name)
                if sub_cmd:
                    _print_command_help(sub_cmd, [*prefix_args, name])

    _print_command_help(ctx.command, [ctx.info_name])
    ctx.exit()


class SempathGroup(rich_click.RichGroup):
    """Custom Click Group to preprocess arguments like -5 into --top-n 5."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        new_args = []
        i = 0
        while i < len(args):
            arg = args[i]
            if re.match(r"^-\d+$", arg):
                val = arg[1:]
                new_args.append("--top-n")
                new_args.append(val)
            else:
                new_args.append(arg)
            i += 1
        return super().parse_args(ctx, new_args)


# CLI group
@rich_click.group(cls=SempathGroup)
@rich_click.version_option(__version__, prog_name="sempath")
@click.option(
    "--help-full",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=print_full_help,
    help="Show comprehensive help for every command and subcommand, then exit.",
)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """sempath — find filesystem paths by vague, colloquial, fuzzy, or wildcard descriptions."""
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
    "--top-n", default=5, type=int, show_default=True, help="Number of results to return."
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
    smallest: bool,
    ext: str | None,
) -> None:
    """Search for filesystem paths matching QUERY.

    QUERY is a vague, colloquial, fuzzy, or wildcard-based (e.g. *.txt) description
    of the path you're looking for. Supports configured category keyword tags (e.g. docs, pics)
    exact, fuzzy, and phonetic matching.

    ROOT_DIR (default: current directory) is the starting point for the search.
    """
    search_root = root or root_dir

    try:
        config = load_config()
    except (FileNotFoundError, ValueError) as exc:
        err_console.print(f"[bold red]Error loading config:[/] {exc}")
        sys.exit(1)

    verbose_final = verbose or config.get("verbose", False)
    exhaustive = config.get("exhaustive", False)

    from click.core import ParameterSource

    top_n_explicit = ctx.get_parameter_source("top_n") == ParameterSource.COMMANDLINE
    top_n_final = top_n if (top_n_explicit or not exhaustive) else 999999

    no_index_final = no_index or exhaustive
    non_interactive_final = non_interactive or exhaustive

    # Store options in context for handler access
    ctx.obj.update(
        {
            "query": query,
            "root": search_root,
            "depth": depth,
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
            "ext": ext,
        }
    )

    if verbose_final:
        console.print(f"[dim]Query:[/]  [bold cyan]{query}[/]")
        console.print(f"[dim]Root:[/]   [bold]{search_root}[/]")
        console.print(f"[dim]Depth:[/]  {depth}")
        console.print()

    from sempath.engine import SearchEngine

    try:
        engine = SearchEngine(config)
        search_result = engine.find_path(
            query=query,
            root_dir=search_root,
            depth=depth,
            min_confidence=min_confidence,
            top_n=top_n_final,
            non_interactive=non_interactive_final,
            no_index=no_index_final,
            latest=latest,
            largest=largest,
            smallest=smallest,
            ext=ext,
            verbose=verbose_final,
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
            if search_result.message:
                console.print(f"[yellow]ℹ {search_result.message}[/]")  # noqa: RUF001
            res = search_result.match
            meta = (
                f" [dim]({res.handler}, confidence: {res.confidence:.2f})[/]"
                if verbose_final
                else ""
            )
            console.print(f"[bold green]✔ Success:[/] Found match: [bold cyan]{res.path}[/]{meta}")
            if search_result.near_misses and top_n_final > 1:
                console.print("[bold]Other matches:[/]")
                for nm in search_result.near_misses[: top_n_final - 1]:
                    nm_meta = (
                        f" [dim]({nm.handler}, confidence: {nm.confidence:.2f})[/]"
                        if verbose_final
                        else ""
                    )
                    console.print(f"  - [cyan]{nm.path}[/]{nm_meta}")
            sys.exit(0)
        elif search_result.status == "ambiguous":
            console.print(f"[bold yellow]⚠ Ambiguous query:[/] {search_result.message}")
            console.print("[bold]Near misses:[/]")
            for nm in search_result.near_misses[:top_n_final]:
                nm_meta = (
                    f" [dim]({nm.handler}, confidence: {nm.confidence:.2f})[/]"
                    if verbose_final
                    else ""
                )
                console.print(f"  - [cyan]{nm.path}[/]{nm_meta}")
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
        from sempath.index import IndexManager

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
        from sempath.index import IndexManager

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
        from sempath.index import IndexManager

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
        from sempath.index import IndexManager

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
    from sempath.utils.memory import add_or_update_memory

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
    from sempath.utils.memory import get_memory_file_path

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
    from sempath.utils.memory import merge_memory_files

    try:
        merge_memory_files(file_path)
        console.print(f"[bold green]✔ Success:[/] Imported memory from [bold]{file_path}[/]")
    except Exception as exc:
        err_console.print(f"[bold red]Error importing memory:[/] {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# config subgroup
# ---------------------------------------------------------------------------


@cli.group()
def config() -> None:
    """Manage the persistent configuration settings."""
    pass


@config.command("verbose")
@click.argument("value", type=click.Choice(["on", "off", "true", "false"], case_sensitive=False))
def config_verbose(value: str) -> None:
    """Enable or disable verbose output globally.

    Usage:
        sempath config verbose on
        sempath config verbose off
    """
    is_verbose = value.lower() in ("on", "true")
    try:
        from sempath.config import save_config

        save_config({"verbose": is_verbose})
        status_str = "enabled" if is_verbose else "disabled"
        console.print(f"[bold green]✔ Success:[/] Verbose logging has been [bold]{status_str}[/].")
    except Exception as exc:
        err_console.print(f"[bold red]Error updating configuration:[/] {exc}")
        sys.exit(1)
