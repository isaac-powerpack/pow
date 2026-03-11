"""Check command implementation."""

import click
from rich.panel import Panel

from ..common.utils import console
from ..core.runner import Runner


@click.command(name="check")
def check_cmd():
    """Run Isaac Sim compatibility check."""
    console.print("[bold blue]🔍 Running Isaac Sim compatibility check...[/bold blue]")

    result = Runner.check_compatibility()
    status = result["status"]

    if status == "passed":
        pass
    elif status == "aborted":
        console.print("[yellow]⊖ Compatibility check aborted.[/yellow]")
    elif status == "not_found":
        console.print(f"[bold yellow]⚠ {result.get('message', 'isaacsim command not found.')}[/bold yellow]")
    else:
        console.print(Panel("[bold red]❌ Compatibility check failed.[/bold red]", border_style="red"))
