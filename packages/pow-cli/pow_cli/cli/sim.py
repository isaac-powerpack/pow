"""Sim command implementation."""

import click
from rich.panel import Panel
from ..common.installation import download_with_progress
from ..common.utils import console
from ..core.initializer import Initializer
from ..core.models.pow_config import PowConfig
from ..core.runner import Runner


def _default_sim_version() -> str:
    """Version used when ``-v`` is omitted.

    Precedence: ``[sim] default_version`` in ``<global>/system.toml``, then
    whatever is actually installed (the newest when several are).  click
    evaluates a callable default at parse time, so both the file read and the
    scan of ``<global>/isaacsim`` happen per invocation rather than at import.
    """
    return PowConfig.configured_default_version() or PowConfig.resolve_installed_version()


def _ensure_sim_ready(version: str, *, check: bool = False) -> None:
    """Complete init's global setup steps without reading project settings."""
    global_path = PowConfig.resolve_global_path()
    isaacsim_path = PowConfig.version_dir(version, global_path)
    initializer = Initializer(global_path=global_path)
    installed = initializer.isaacsim_ready(isaacsim_path, check=check)
    if not installed:
        # Reject unavailable versions before making any setup changes. Existing
        # manually installed versions need not be in the download allowlist.
        PowConfig.release(version)

    global_ready = all(
        (global_path / sub).is_dir() for sub in Initializer.GLOBAL_SUBFOLDERS
    ) and (global_path / "system.toml").is_file()
    if not global_ready:
        console.print(
            f"[blue]Preparing global configuration at [dim]{global_path}[/dim]...[/blue]"
        )
        initializer.create_global_folder()
        initializer.create_system_toml()

    if not installed:
        download_with_progress(initializer, version, check=check)
    if not initializer.isaacsim_ready(isaacsim_path, check=check):
        raise click.ClickException(
            f"Isaac Sim installation at {isaacsim_path} is missing required scripts."
        )

    cache_path = initializer.asset_browser_cache_path(isaacsim_path)
    if not cache_path.is_file():
        console.print("[blue]Creating the missing Isaac Sim asset browser cache...[/blue]")
        initializer.fix_asset_browser_cache(isaacsim_path)
    if not cache_path.is_file():
        raise click.ClickException(f"Isaac Sim asset browser cache is missing at {cache_path}.")


def _guarded(action, *, check: bool = False, **kwargs):
    """Ensure prerequisites, then run the action with consistent error output."""
    try:
        _ensure_sim_ready(kwargs["version"], check=check)
        action(**kwargs)
    except click.ClickException:
        raise
    except Exception as e:
        console.print(
            Panel(
                f"[bold red]✘[/bold red]  {e}",
                title="[bold red]Sim Error[/bold red]",
                border_style="red",
            )
        )
        raise SystemExit(1)


class SimGroup(click.Group):
    """Group that falls through to `launch` for unrecognized arguments."""

    def resolve_command(self, ctx, args):
        if args and self.get_command(ctx, args[0]) is not None:
            return super().resolve_command(ctx, args)
        launch = self.get_command(ctx, "launch")
        return launch.name, launch, args

    def format_options(self, ctx, formatter):
        """List `launch`'s options as the group's own.

        Bare `pow sim` accepts them through :meth:`resolve_command`, so they
        belong in `pow sim --help` too - declared once, on `launch_cmd`.
        """
        launch = self.get_command(ctx, "launch")
        rows = []
        for param in launch.get_params(ctx):
            if param.name == "help":
                continue
            record = param.get_help_record(ctx)
            if record is not None:
                rows.append(record)
        for param in self.get_params(ctx):
            record = param.get_help_record(ctx)
            if record is not None:
                rows.append(record)
        if rows:
            with formatter.section("Options"):
                formatter.write_dl(rows)
        self.format_commands(ctx, formatter)


@click.group(
    name="sim",
    cls=SimGroup,
    invoke_without_command=True,
    context_settings={"ignore_unknown_options": True},
)
@click.pass_context
def sim_group(ctx: click.Context):
    """Run Isaac Sim from any directory, ignoring pow.toml.

    \b
    Unlike `pow run` this needs no project: no pyproject.toml is required and
    pow.toml is never read. Every unrecognized argument is forwarded verbatim
    to .pow/isaacsim/<version>/isaac-sim.sh.

    \b
    The version is resolved in this order:
      1. the -v/--version option
      2. [sim] default_version in .pow/system.toml
      3. the newest version installed under .pow/isaacsim/
      4. the latest release supported by this pow CLI

    Missing global folders, configuration, supported installations and the
    asset browser cache are set up automatically before launch or check.
    A missing pinned version is installed. Setup failures stop the command.

    \b
    Subcommands:
      launch  Explicitly launch Isaac Sim (same as bare `pow sim`).
      check   Run the Isaac Sim compatibility check.

    \b
    Examples:
      pow sim
      pow sim --no-ros
      pow sim -v 5.1.0
      pow sim -- --no-window --/renderer/enabled=gpu
      pow sim check
    """
    if ctx.invoked_subcommand is None:
        _guarded(
            Runner.run_sim,
            version=_default_sim_version(),
            ros_bridge=PowConfig.ROS_BRIDGE,
            extra_args=[],
        )


@sim_group.command(
    name="launch",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option(
    "-v",
    "--version",
    "sim_version",
    default=_default_sim_version,
    show_default="system.toml, else installed, else latest supported",
    help="Isaac Sim version to run.",
)
@click.option(
    "--ros",
    "ros_bridge",
    type=click.Choice(PowConfig.SUPPORTED_ROS_BRIDGES),
    default=PowConfig.ROS_BRIDGE,
    show_default=True,
    help="ROS 2 bridge distro to load into the environment.",
)
@click.option(
    "--no-ros",
    is_flag=True,
    default=False,
    help="Launch without the ROS 2 bridge environment.",
)
@click.pass_context
def launch_cmd(ctx: click.Context, sim_version: str, ros_bridge: str, no_ros: bool):
    """Set up missing prerequisites, then launch Isaac Sim with extra args."""
    _guarded(
        Runner.run_sim,
        version=sim_version,
        ros_bridge=None if no_ros else ros_bridge,
        extra_args=ctx.args,
    )


@sim_group.command(
    name="check",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option(
    "-v",
    "--version",
    "sim_version",
    default=_default_sim_version,
    show_default="system.toml, else installed, else latest supported",
    help="Isaac Sim version to check.",
)
@click.pass_context
def check_cmd(ctx: click.Context, sim_version: str):
    """Set up missing prerequisites, then run the Isaac Sim compatibility check.

    \b
    Runs .pow/isaacsim/<version>/isaac-sim.compatibility_check.sh, which
    reports whether this machine meets the Isaac Sim requirements. Needs no
    project, and the script builds its own ROS environment - forward
    `-- --no-ros-env` to skip that step.
    """
    _guarded(Runner.run_sim_check, check=True, version=sim_version, extra_args=ctx.args)
