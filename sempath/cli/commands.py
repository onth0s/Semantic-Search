"""Subcommands and subcommand groups for the sempath CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sempath.cli.subcommands.alias_cmd import register_alias_commands
from sempath.cli.subcommands.config_cmd import register_config_commands
from sempath.cli.subcommands.index_cmd import register_index_commands
from sempath.cli.subcommands.memory_cmd import register_memory_commands
from sempath.cli.subcommands.preset_cmd import register_preset_commands

if TYPE_CHECKING:
    import click


def register_commands(cli_group: click.Group) -> None:
    """Register all subcommands and groups onto the main root CLI group."""
    register_index_commands(cli_group)
    register_alias_commands(cli_group)
    register_memory_commands(cli_group)
    register_config_commands(cli_group)
    register_preset_commands(cli_group)
