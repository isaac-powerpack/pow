"""Core logic for running Isaac Sim."""

import os
import platform
import shlex
import subprocess
from pathlib import Path
import click
import tomllib


def find_project_root(start_path: Path | None = None) -> Path | None:
    """Find the project root by locating pow.toml."""
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    while current != current.parent:
        if (current / "pow.toml").exists():
            return current
        current = current.parent

    if (current / "pow.toml").exists():
        return current

    return None


def load_config(project_root: Path) -> dict:
    """Load pow.toml configuration."""
    config_path = project_root / "pow.toml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def source_setup_file(
    file_path: Path,
    shell_type: str,
    description: str = "",
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


def source_isaacsim_ros_workspace(config: dict) -> dict:
    """Check and prepare ROS workspace environment variables."""
    ros_config = config.get("sim", {}).get("ros", {})
    isaacsim_ros_ws = ros_config.get("isaacsim_ros_ws", "")
    ros_distro = ros_config.get("ros_distro", "humble")

    if not isaacsim_ros_ws:
        raise click.ClickException("isaacsim_ros_ws is not set in pow.toml.")

    ros_ws_path = Path(isaacsim_ros_ws).expanduser()
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
        raise click.ClickException("ROS setup files not found.")

    distro_env = source_setup_file(distro_local_setup, shell_type)
    output_env = source_setup_file(isaac_sim_ros_setup, shell_type, env=distro_env)

    return output_env


def get_target_profile(config: dict, profile_name: str = "default") -> dict:
    """Get the target profile, merging with default profile if needed."""
    profiles = config.get("sim", {}).get("profiles", [])
    default_profile = next((p for p in profiles if p.get("name") == "default"), None)
    target_profile = next((p for p in profiles if p.get("name") == profile_name), None)

    if target_profile is None:
        raise click.ClickException(f"No profile named '{profile_name}' found.")

    if default_profile:
        merged_profile = default_profile.copy()
        merged_profile.update(target_profile)
        target_profile = merged_profile

    return target_profile


def build_launch_command(
    config: dict,
    project_root: Path,
    profile_name: str = "default",
    extra_args: list[str] | None = None,
) -> str:
    """Build the Isaac Sim launch command from configuration."""
    launch_cmd = "uv run isaacsim"
    ext_folders = config.get("sim", {}).get("ext_folders", [])

    for folder in ext_folders:
        launch_cmd += f" --ext-folder {folder}"

    target_profile = get_target_profile(config, profile_name)

    if target_profile.get("headless", False):
        launch_cmd += " --no-window"

    for ext in target_profile.get("extensions", []):
        launch_cmd += f" --enable {ext}"

    for arg in target_profile.get("raw_args", []):
        launch_cmd += f" {arg}"

    open_scene_path = target_profile.get("open_scene_path", "")
    if open_scene_path:
        full_scene_path = project_root / open_scene_path
        launch_cmd += f' --exec "open_stage.py file://{full_scene_path}"'

    if extra_args:
        launch_cmd += f" {' '.join(shlex.quote(arg) for arg in extra_args)}"

    return launch_cmd


def run_isaacsim(profile: str, extra_args: list[str] | None = None) -> None:
    """Run an Isaac Sim App based on profile."""
    project_root = find_project_root()
    if project_root is None:
        raise click.ClickException("Not initialized.")

    config = load_config(project_root)

    if platform.machine().lower() not in ("x86_64", "amd64"):
        raise click.ClickException("Unsupported platform.")

    ros_config = config.get("sim", {}).get("ros", {})
    source_env = source_isaacsim_ros_workspace(config) if ros_config.get("enable_ros", False) else None
    
    launch_cmd = build_launch_command(config, project_root, profile, extra_args)
    target_profile = get_target_profile(config, profile)

    if target_profile.get("cpu_performance_mode", False):
        subprocess.run(shlex.split("sudo cpupower frequency-set -g performance"), check=True)

    subprocess.run(shlex.split(launch_cmd), check=True, env=source_env)
