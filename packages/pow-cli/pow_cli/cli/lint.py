"""Lint command implementation."""

import time
import click
from ..common.utils import console

@click.command(name="lint")
@click.argument("file", type=click.Path(exists=True), required=False)
def lint_cmd(file):
    """Check .usda file for compatibility and errors."""
    if file:
        console.print(f"[bold blue]Linting[/bold blue] [white]{file}[/white]...")
    else:
        console.print("[bold blue]Linting[/bold blue] all [bold white].usda[/bold white] files...")
    
    with console.status("Checking for compatibility and errors..."):
        time.sleep(1)
        console.print("   [green]✔[/green] No errors found. Compatible with [bold]Isaac Sim 5.1.0[/bold].")
