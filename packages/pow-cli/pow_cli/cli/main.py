"""Pow CLI - Root commands."""

import click


@click.group()
def pow_group():
    """Isaac Powerpack CLI for Isaac ROS and Isaac Sim development."""
    pass


@pow_group.command()
def init():
    """Initialize Isaac ROS project."""
    click.echo("Initializing Isaac ROS project... (Mockup)")


@pow_group.command()
def run():
    """Run Isaac Sim or Isaac ROS workflows."""
    click.echo("Running workflow... (Mockup)")


@pow_group.group()
def add():
    """Add resources to the project."""
    pass


@add.command()
@click.option("--isaac-sim", is_flag=True, default=True, help="Add Isaac Sim assets (default)")
@click.option("--all", is_flag=True, help="Add all available assets")
@click.option("--url", help="Asset URL to download")
@click.option("--path", help="Path to keep the asset")
def asset(isaac_sim, all, url, path):
    """Add assets to the project."""
    if url and path:
        click.echo(f"Adding asset from {url} to {path}... (Mockup)")
    elif all:
        click.echo("Adding all assets... (Mockup)")
    else:
        click.echo("Adding Isaac Sim assets... (Mockup)")


@pow_group.command()
@click.argument("file", type=click.Path(exists=True), required=False)
def lint(file):
    """Check .usda file for compatibility and errors."""
    if file:
        click.echo(f"Linting {file}... (Mockup)")
    else:
        click.echo("Linting all .usda files... (Mockup)")
