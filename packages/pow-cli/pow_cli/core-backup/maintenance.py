"""Core logic for Isaac Sim maintenance and info."""

import subprocess
import click
from .path import get_isaacsim_path


def check_compatibility() -> bool:
    """Run Isaac Sim compatibility check."""
    isaacsim_path = get_isaacsim_path()
    if isaacsim_path is None:
        click.echo("Error: Isaac Sim not found.")
        return False

    try:
        subprocess.run(
            ["uv", "run", "isaacsim", "isaacsim.exp.compatibility_check"],
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        click.echo(f"Compatibility check failed: {e}")
        return False


def get_sim_info() -> None:
    """Print Isaac Sim information."""
    isaacsim_path = get_isaacsim_path()
    if isaacsim_path:
        click.echo(f"Isaac Sim Path: {isaacsim_path}")
    else:
        click.echo("Isaac Sim not found.")
