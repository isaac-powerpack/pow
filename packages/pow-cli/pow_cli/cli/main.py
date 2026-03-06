"""Pow CLI - Root commands."""

import click

from .init import init_cmd
from .add import add_group
from .lint import lint_cmd
from .run import run_cmd


@click.group()
def pow_group():
    """Isaac Powerpack CLI for Isaac ROS and Isaac Sim development."""
    pass


# Register commands
pow_group.add_command(init_cmd)
pow_group.add_command(add_group)
pow_group.add_command(lint_cmd)
pow_group.add_command(run_cmd)
