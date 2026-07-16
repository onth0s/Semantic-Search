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
from rich.markup import escape

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
    """Custom Click Group to preprocess shorthand arguments before Click parsing.

    Rewrites:
      -5          ->  --top-n 5           (output clamp)
      -h8         ->  --handlers h8       (single handler)
      -h1-6       ->  --handlers h1-6     (range)
      -h2,h4,h5   ->  --handlers h2,h4,h5 (explicit list)
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        new_args = []
        i = 0
        while i < len(args):
            arg = args[i]
            if re.match(r"^-\d+$", arg):
                # -5 -> --top-n 5
                new_args.append("--top-n")
                new_args.append(arg[1:])
            elif re.match(r"^-h(\d[\d,\-]*)$", arg):
                # -h8, -h1-6, -h2,h4,h5 -> --handlers <spec>
                new_args.append("--handlers")
                new_args.append(arg[2:])
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
# Helpers
# ---------------------------------------------------------------------------

_ALL_HANDLERS = ["h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8", "h9"]


def _parse_handler_spec(spec: str) -> list[str]:
    """Parse a handler spec string into an ordered list of handler IDs.

    Accepted formats::

        "h1-8"      -> [h1, h2, h3, h4, h5, h6, h7, h8]
        "h8"        -> [h8]
        "h2,h4,h5"  -> [h2, h4, h5]
        "1-6"       -> [h1, h2, h3, h4, h5, h6]   (leading h optional)
        "1,3,7"     -> [h1, h3, h7]
    """
    spec = spec.strip().lstrip("-")
    handlers: list[str] = []

    # Range pattern: [h]N-[h]M
    range_m = re.fullmatch(r"h?(\d+)-h?(\d+)", spec)
    if range_m:
        lo, hi = int(range_m.group(1)), int(range_m.group(2))
        handlers = [f"h{n}" for n in range(lo, hi + 1)]
        return [h for h in handlers if h in _ALL_HANDLERS]

    # Comma-separated list: h1,h3,h8 or 1,3,8
    if "," in spec:
        for part in spec.split(","):
            part = part.strip().lstrip("-")
            hid = part if part.startswith("h") else f"h{part}"
            if hid in _ALL_HANDLERS and hid not in handlers:
                handlers.append(hid)
        return handlers

    # Single handler: h8 or 8
    hid = spec if spec.startswith("h") else f"h{spec}"
    if hid in _ALL_HANDLERS:
        return [hid]

    raise click.BadParameter(
        f"'{spec}' is not a valid handler spec. Use e.g. --h1, --h8, --h1-6, --h2,h4,h5.",
        param_hint="--handlers",
    )


def _human_size(size_bytes: int) -> str:
    """Format bytes as human-readable string with 2 decimal places."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def _human_mtime(mtime: float) -> str:
    """Format a modification timestamp as a human-readable date-time string."""
    from datetime import datetime

    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")


def _format_file_meta(path: Path) -> str:
    """Return a compact '[size, date]' dimmed suffix for *path*."""
    try:
        st = path.stat()
        sz = _human_size(st.st_size) if path.is_file() else "DIR"
        dt = _human_mtime(st.st_mtime)
        return f" [dim][{sz}, {dt}][/]"
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Result grouping
# ---------------------------------------------------------------------------

_GENERIC_STEMS: frozenset[str] = frozenset(
    {
        "unnamed",
        "unname2d",
        "untitled",
        "temp",
        "tmp",
        "test",
        "var",
        "deleteme",
        "copy",
        "newfolder",
    }
)


def _is_generic_stem(stem: str) -> bool:
    """Return True if the stem is a placeholder/generic filename."""
    cleaned = re.sub(r"[\s\-_0-9()]+", "", stem.lower())
    return cleaned in _GENERIC_STEMS


# Group label constants - add more groupers here in the future.
_GROUP_OTHER = "Other matches"
_GROUP_GENERIC = "Generic/placeholder files"


def _classify_match(path: Path, search_root: Path) -> str:
    """Return the display group label for a near-miss match."""
    if _is_generic_stem(path.stem):
        return _GROUP_GENERIC

    # Determine if it has a subfolder parent relative to search_root
    try:
        rel_path = path.resolve().relative_to(search_root.resolve())
        # If the parent is just '.' or the path itself is '.'
        if rel_path.parent == Path("."):
            return _GROUP_OTHER
        # Return parent directory string with forward slashes
        return str(rel_path.parent).replace("\\", "/")
    except Exception:
        return _GROUP_OTHER


def _print_grouped_matches(
    matches: list,
    limit: int,
    verbose: bool,
) -> None:
    """Print *matches* (up to *limit*) sorted into display groups.

    Groups are rendered in declaration order; empty groups are skipped.
    Each group gets a styled header. Within a group, items are listed
    with confidence metadata when *verbose* is True.
    """
    from collections import defaultdict

    ctx = click.get_current_context(silent=True)
    search_root = ctx.obj.get("root", Path(".")) if (ctx and ctx.obj) else Path(".")

    # Bucket all matches first (without early clamping)
    groups: dict[str, list] = defaultdict(list)
    for nm in matches:
        group_lbl = _classify_match(nm.path, search_root)
        groups[group_lbl].append(nm)

    # Determine sorting order of groups:
    # 1. Custom parent-directory groups (sorted by insertion, preserving match order)
    # 2. "Other matches"
    # 3. "Generic/placeholder files"
    all_groups = list(groups.keys())

    # We want "Other matches" first if present, then subfolders, then generic files at the very end.
    subfolder_groups = [g for g in all_groups if g not in (_GROUP_OTHER, _GROUP_GENERIC)]

    group_order = []
    if _GROUP_OTHER in groups:
        group_order.append(_GROUP_OTHER)
    group_order.extend(subfolder_groups)
    if _GROUP_GENERIC in groups:
        group_order.append(_GROUP_GENERIC)

    printed_count = 0
    for group_name in group_order:
        if printed_count >= limit:
            break
        items = groups.get(group_name, [])
        if not items:
            continue

        # Render group header
        style = "[bold]" if group_name != _GROUP_GENERIC else "[bold dim]"
        console.print(f"{style}{escape(group_name)}:[/]")

        for nm in items:
            if printed_count >= limit:
                break
            nm_meta = _format_file_meta(nm.path) + (
                f" [dim]({nm.handler}, confidence: {nm.confidence:.2f})[/]" if verbose else ""
            )
            color = "cyan" if group_name != _GROUP_GENERIC else "dim cyan"
            console.print(f"  - [{color}]{escape(str(nm.path))}[/]{nm_meta}")
            printed_count += 1


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
    "--oldest", is_flag=True, default=False, help="Sort matches to return the oldest path."
)
@click.option(
    "--ext",
    type=str,
    default=None,
    help="Filter candidates to keep only those with specified extension.",
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
    oldest: bool,
    ext: str | None,
    handler_spec: str | None,
    gitignore: bool,
    read_content: bool,
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

    # --- Handler filtering ---------------------------------------------------
    if handler_spec is not None:
        try:
            selected = _parse_handler_spec(handler_spec)
        except click.BadParameter as exc:
            err_console.print(f"[bold red]Invalid handler spec:[/] {exc}")
            sys.exit(1)
        # Override the enabled handler list in config
        config.setdefault("handlers", {})["enabled"] = selected
        if verbose or config.get("verbose", False):
            console.print(f"[dim]Handlers:[/] {', '.join(selected)}")

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
            "oldest": oldest,
            "ext": ext,
        }
    )

    if verbose_final:
        console.print(f"[dim]Query:[/]  [bold cyan]{query}[/]")
        console.print(f"[dim]Root:[/]   [bold]{escape(str(search_root))}[/]")
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
            oldest=oldest,
            ext=ext,
            verbose=verbose_final,
            respect_gitignore=gitignore,
            read_content=read_content,
        )
    except Exception as exc:
        err_console.print(f"[bold red]Search Engine error:[/] {exc}")
        sys.exit(1)

    # Output results
    if json_output:
        click.echo(json.dumps(search_result.to_dict(), indent=2))
        sys.exit(0 if search_result.status == "success" else 1)

    if search_result.status == "success":
        if search_result.message:
            console.print(f"[yellow]ℹ {search_result.message}[/]")  # noqa: RUF001

        # If the engine's top result is a generic/placeholder file,
        # promote the first real match to primary and push the generic
        # back into the pool so it appears in the grouped display.
        # However, do not demote it if the user specifically asked for a sorted item (e.g. latest).
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

        meta = _format_file_meta(primary.path) + (
            f" [dim]({primary.handler}, confidence: {primary.confidence:.2f})[/]"
            if verbose_final
            else ""
        )
        escaped_path = escape(str(primary.path))
        console.print(f"[bold green]✔ Success:[/] Found match: [bold cyan]{escaped_path}[/]{meta}")
        if near_misses and top_n_final > 1:
            _print_grouped_matches(
                near_misses,
                limit=top_n_final - 1,
                verbose=verbose_final,
            )
        sys.exit(0)
    elif search_result.status == "ambiguous":
        console.print(f"[bold yellow]⚠ Ambiguous query:[/] {search_result.message}")
        _print_grouped_matches(
            search_result.near_misses,
            limit=top_n_final,
            verbose=verbose_final,
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
        respect_gi = config.get("index", {}).get("respect_gitignore", True)
        from sempath.index import IndexManager

        manager = IndexManager(Path(store))
        console.print(f"[yellow]Scanning and indexing:[/] {escape(str(path))} (depth: {depth})...")
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
        config = load_config()
        store = config.get("index", {}).get("store", "")
        exclude = config.get("index", {}).get("exclude_patterns", [])
        respect_gi = config.get("index", {}).get("respect_gitignore", True)
        from sempath.index import IndexManager

        manager = IndexManager(Path(store))
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
                escaped_root = escape(str(path))
                console.print(
                    f"[bold green]✔ Success:[/] Removed root [bold]{escaped_root}[/] from index."
                )
            else:
                console.print(
                    f"[yellow]⚠[/] Path [bold]{escape(str(path))}[/] was not found in the index."
                )
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
        escaped_name = escape(name)
        escaped_path = escape(str(path))
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
        console.print(
            f"[bold green]✔ Success:[/] Exported memory to [bold]{escape(str(file_path))}[/]"
        )
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
        console.print(
            f"[bold green]✔ Success:[/] Imported memory from [bold]{escape(str(file_path))}[/]"
        )
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


@config.command("gitignore")
@click.argument("value", type=click.Choice(["on", "off", "true", "false"], case_sensitive=False))
def config_gitignore(value: str) -> None:
    """Enable or disable respecting .gitignore rules globally.

    Usage:
        sempath config gitignore on
        sempath config gitignore off
    """
    respect = value.lower() in ("on", "true")
    try:
        from sempath.config import save_config

        save_config({"index": {"respect_gitignore": respect}})
        status_str = "enabled" if respect else "disabled"
        console.print(
            f"[bold green]✔ Success:[/] Respecting .gitignore rules has been [bold]{status_str}[/]."
        )
    except Exception as exc:
        err_console.print(f"[bold red]Error updating configuration:[/] {exc}")
        sys.exit(1)
