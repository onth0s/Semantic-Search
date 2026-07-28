"""Main CLI group setup and help formatting for sempath."""

from __future__ import annotations

import re

import click
import rich_click

from sempath import __version__
from sempath.cli.commands import register_commands
from sempath.cli.find import register_find_command
from sempath.config import load_config
from sempath.utils.console import console

rich_click.STYLE_OPTION = "bold cyan"
rich_click.STYLE_ARGUMENT = "cyan"
rich_click.STYLE_COMMAND = "bold green"
rich_click.STYLE_ERRORS_OPTION = "bold red"
rich_click.STYLE_METAVAR = "dim"
rich_click.STYLE_HELPTEXT = ""


def print_full_help(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    """Callback to print comprehensive help for all commands and subcommands recursively."""
    if not value or ctx.resilient_parsing:
        return

    def _print_command_help(cmd: click.Command, prefix_args: list[str]) -> None:
        cmd_ctx = cmd.context_class(cmd, info_name=" ".join(prefix_args))
        full_name = " ".join(prefix_args)
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
    """Custom Click Group to preprocess shorthand arguments before Click parsing."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        new_args = []

        presets = {}
        try:
            cfg = load_config()
            presets = cfg.get("presets", {})
        except (OSError, ValueError):
            pass

        i = 0
        while i < len(args):
            arg = args[i]
            is_val_for_handlers = i > 0 and args[i - 1] == "--handlers"

            preset_name = None
            if arg.startswith("-p") and not arg.startswith("-h") and len(arg) > 2:
                preset_name = arg[2:]
            elif arg.startswith("--preset-") and len(arg) > 9:
                preset_name = arg[9:]

            if preset_name is not None and (preset_name in presets or str(preset_name) in presets):
                preset_val = presets.get(preset_name) or presets.get(str(preset_name))
                new_args.append("--handlers")
                new_args.append(str(preset_val))
            elif arg in ("-p", "--preset") and i + 1 < len(args):
                next_arg = args[i + 1]
                if next_arg in presets or str(next_arg) in presets:
                    preset_val = presets.get(next_arg) or presets.get(str(next_arg))
                    new_args.append("--handlers")
                    new_args.append(str(preset_val))
                    i += 2
                    continue
                else:
                    new_args.append(arg)
            elif re.match(r"^-\d+$", arg):
                new_args.append("--top-n")
                new_args.append(arg[1:])
            elif not is_val_for_handlers and re.match(r"^--?h(\d[\d,\-]*)$", arg):
                new_args.append("--handlers")
                prefix_len = 3 if arg.startswith("--") else 2
                new_args.append(arg[prefix_len:])
            else:
                new_args.append(arg)
            i += 1
        return super().parse_args(ctx, new_args)


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


register_find_command(cli)
register_commands(cli)
