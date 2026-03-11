"""Run command implementation."""

import click
from rich.panel import Panel
from ..common.utils import console
from ..core.runner import Runner

@click.command(
    name="run",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option(
    "-p",
    "--profile",
    default="default",
    help="Profile name from pow.toml to use (default: 'default').",
)
@click.pass_context
def run_cmd(ctx: click.Context, profile: str):
    """Run Isaac Sim with the configured profile and extensions.
    
    Any unrecognized arguments are passed directly to Isaac Sim.
    """
    extra_args = ctx.args
    Runner.run_isaacsim(profile=profile, extra_args=extra_args)
