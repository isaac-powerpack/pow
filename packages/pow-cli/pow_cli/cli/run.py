"""Run command implementation."""

import click
from rich.panel import Panel
from ..common.utils import console

@click.command(name="run")
def run_cmd():
    """Run Isaac Sim or Isaac ROS workflows."""
    console.print(
        Panel(
            "[bold green]Running workflow... (Mockup)[/bold green]", border_style="cyan"
        )
    )
