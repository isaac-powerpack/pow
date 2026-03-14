"""Runner core logic."""

import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path

import click
from rich.console import Console

from .models.pow_config import PowConfig

console = Console()

class Runner:
    """Handles execution of Isaac Sim and related tools."""

    @staticmethod
    def check_compatibility() -> dict:
        """Run the Isaac Sim built-in compatibility check.

        Uses the ``isaacsim`` CLI entry point installed via pip.
        Streams output to the terminal, waits for the process to finish,
        then reports passed/failed based on ``System checking result:``.

        Returns a dict with keys:
            status  – "passed" | "failed" | "aborted" | "not_found"
        """
        isaacsim_cmd = shutil.which("isaacsim")
        if isaacsim_cmd is None:
            return {
                "status": "not_found",
                "message": (
                    "The `isaacsim` command was not found. "
                    'Install it with: uv add "isaacsim[compatibility-check]" --index https://pypi.nvidia.com'
                ),
            }

        try:
            process = subprocess.Popen(
                [isaacsim_cmd, "isaacsim.exp.compatibility_check"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError as e:
            return {"status": "failed", "message": f"Failed to launch compatibility check: {e}"}

        output_lines: list[str] = []
        try:
            for line in process.stdout:
                print(line, end="", flush=True)
                output_lines.append(line)
            process.wait()
        except KeyboardInterrupt:
            process.kill()
            process.wait()
            return {"status": "aborted"}

        full_output = "".join(output_lines)
        if "System checking result: PASSED" in full_output:
            return {"status": "passed"}
        return {"status": "failed"}

    @staticmethod
    def source_setup_file(
        file_path: Path,
        shell_type: str,
        env: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Source a shell setup file and return the resulting environment variables."""
        safe_path = shlex.quote(str(file_path))
        command = [
            shell_type,
            "-c",
            f"source {safe_path} && env",
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )

            new_env = {}
            for line in result.stdout.splitlines():
                if "=" in line:
                    key, _, value = line.partition("=")
                    new_env[key] = value

            return new_env

        except subprocess.CalledProcessError as e:
            raise click.ClickException(
                click.style(
                    f"Failed to source setup file {file_path}: {e.stderr}",
                    fg="red",
                )
            )

    @staticmethod
    def source_isaacsim_ros_workspace(config: PowConfig) -> dict:
        """Check and prepare ROS workspace environment variables."""
        ros_ws_path = config.ros_ws_path
        ros_distro = config.ros_distro

        shell_path = os.environ.get("SHELL", "")
        shell_type = Path(shell_path).name if shell_path else "bash"

        distro_local_setup = (
            ros_ws_path
            / "build_ws"
            / ros_distro
            / f"{ros_distro}_ws"
            / "install"
            / f"local_setup.{shell_type}"
        )
        isaac_sim_ros_setup = (
            ros_ws_path
            / "build_ws"
            / ros_distro
            / "isaac_sim_ros_ws"
            / "install"
            / f"local_setup.{shell_type}"
        )

        if not distro_local_setup.exists() or not isaac_sim_ros_setup.exists():
            raise click.ClickException(f"ROS setup files not found. Are you sure you ran `pow init` properly?")

        distro_env = Runner.source_setup_file(distro_local_setup, shell_type, env=os.environ.copy())
        output_env = Runner.source_setup_file(isaac_sim_ros_setup, shell_type, env=distro_env)

        return output_env

    @staticmethod
    def build_launch_command(
        config: PowConfig,
        profile_name: str = "default",
        extra_args: list[str] | None = None,
    ) -> list[str]:
        """Build the Isaac Sim launch command from configuration."""
        isaacsim_version = config.get("version", PowConfig.ISAACSIM_VERSION)
        isaacsim_dir = config.global_path / "isaacsim" / isaacsim_version
        
        launch_script = isaacsim_dir / "isaac-sim.sh"
        if not launch_script.exists():
            raise click.ClickException(f"Isaac Sim script not found at {launch_script}")

        cmd = [str(launch_script)]

        ext_folders = config.get("ext_folders", [], profile=profile_name)
        for folder in ext_folders:
            cmd.extend(["--ext-folder", folder])

        if config.get("headless", False, profile=profile_name):
            cmd.append("--no-window")

        for ext in config.get("exts", [], profile=profile_name):
            cmd.extend(["--enable", ext])

        for arg in config.get("raw_args", [], profile=profile_name):
            cmd.append(arg)

        if extra_args:
            cmd.extend(extra_args)

        return cmd

    @staticmethod
    def run_isaacsim(profile: str = "default", extra_args: list[str] | None = None) -> None:
        """Run an Isaac Sim App based on profile."""
        config = PowConfig()
        if config.project_root is None:
            raise click.ClickException("Not initialized. Run `pow init` first.")

        if platform.machine().lower() not in ("x86_64", "amd64"):
            raise click.ClickException("Unsupported platform. Only x86_64 is supported by Isaac Sim.")

        enable_ros = config.get("enable_ros", False, profile=profile)
        source_env = Runner.source_isaacsim_ros_workspace(config) if enable_ros else os.environ.copy()

        cmd = Runner.build_launch_command(config, profile, extra_args)

        if config.get("cpu_performance_mode", False, profile=profile):
            console.print("[yellow]Setting CPU to performance mode (requires sudo)...[/yellow]")
            try:
                subprocess.run(["sudo", "cpupower", "frequency-set", "-g", "performance"], check=True)
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Failed to set CPU performance mode: {e}[/red]")

        console.print(f"[blue]Running: {' '.join(shlex.quote(c) for c in cmd)}[/blue]")
        
        try:
            subprocess.run(cmd, check=True, env=source_env)
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"Isaac Sim process failed with exit code {e.returncode}")
        except KeyboardInterrupt:
            console.print("[yellow]Isaac Sim launch aborted by user.[/yellow]")
