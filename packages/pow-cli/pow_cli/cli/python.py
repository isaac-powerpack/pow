"""Python command implementation."""

import click
from rich.panel import Panel
from ..common.utils import console
from ..core.runner import Runner


@click.command(
    name="python",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.pass_context
def python_cmd(ctx: click.Context):
    """Run Isaac Sim's bundled Python interpreter.

    \b
    Wraps .pow/isaacsim/<version>/python.sh, forwarding every
    argument and flag directly to it.

    \b
    Examples:
      pow python my_script.py
      pow python -c "import omni; print(omni.__version__)"
    """
    extra_args = ctx.args
    try:
        Runner.run_python(extra_args=extra_args)
    except click.ClickException:
        raise
    except Exception as e:
        console.print(
            Panel(
                f"[bold red]✘[/bold red]  {e}",
                title="[bold red]Python Error[/bold red]",
                border_style="red",
            )
        )
        raise SystemExit(1)
