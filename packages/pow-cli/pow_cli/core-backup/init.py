"""Core logic for Isaac Sim initialization."""

import json
import re
import subprocess
from pathlib import Path
import click
import tomllib
from .path import get_isaacsim_path


def generate_vscode_settings() -> bool:
    """Generate VS Code settings for Isaac Sim development."""
    try:
        settings_path = Path.cwd() / ".vscode" / "settings.json"
        subprocess.run(
            ["uv", "run", "python", "-m", "isaacsim", "--generate-vscode-settings"],
            check=True,
        )
        
        if settings_path.exists():
            content = settings_path.read_text()
            updated_content = re.sub(
                r'"[^"]+/\.venv/',
                r'"${workspaceFolder}/.venv/',
                content,
            )
            if content != updated_content:
                settings_path.write_text(updated_content)
        return True
    except Exception:
        return False


def fix_asset_browser_cache(isaacsim_path: Path) -> bool:
    """Fix the Isaac Sim asset browser cache issue."""
    cache_path = (
        isaacsim_path
        / "exts"
        / "isaacsim.asset.browser"
        / "cache"
        / "isaacsim.asset.browser.cache.json"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not cache_path.exists():
        with open(cache_path, "w") as f:
            json.dump({}, f, indent=4)
        return True
    return False


def setup_ros_workspace(ros_config: dict, is_existing: bool) -> dict:
    """Setup ROS workspace for Isaac Sim project."""
    pow_dir = Path.home() / ".pow-dev"
    pow_dir.mkdir(parents=True, exist_ok=True)
    ros_workspace_path = pow_dir / "IsaacSim-ros_workspaces"

    if not is_existing:
        enable_ros = click.confirm(click.style("Enable ROS integration?", fg="bright_black"), default=True)
        if not enable_ros:
            return {"enable_ros": False}

        ros_distros = ["humble", "jazzy"]
        choice = click.prompt(click.style("Select ROS distro", fg="bright_black"), type=click.IntRange(1, 2), default=1)
        selected_distro = ros_distros[choice - 1]
        ros_config = {"enable_ros": True, "ros_distro": selected_distro}
    else:
        if not ros_config.get("enable_ros", False):
            return ros_config
        
        ws_path = ros_config.get("isaacsim_ros_ws", "")
        if ws_path:
            ros_workspace_path = Path(ws_path.replace("~", str(Path.home())))

    if not ros_workspace_path.exists():
        click.echo("Cloning IsaacSim-ros_workspaces...")
        subprocess.run(
            ["git", "clone", "-b", "IsaacSim-5.1.0", "--quiet", "https://github.com/isaac-sim/IsaacSim-ros_workspaces.git", str(ros_workspace_path)],
            check=True,
        )

    ros_distro = ros_config.get("ros_distro", "humble")
    click.echo(f"Building ROS {ros_distro} workspace...")
    ubuntu_version = "22.04" if ros_distro == "humble" else "24.04"
    subprocess.run(["./build_ros.sh", "-d", ros_distro, "-v", ubuntu_version], cwd=ros_workspace_path, check=True)

    ros_config["isaacsim_ros_ws"] = str(ros_workspace_path).replace(str(Path.home()), "~")
    return ros_config


def dump_toml(data: dict) -> str:
    """A very simple TOML dumper for the internal config object."""
    lines = []
    
    def format_value(v):
        if isinstance(v, bool):
            return str(v).lower()
        if isinstance(v, str):
            return f'"{v}"'
        if isinstance(v, list):
            return "[" + ", ".join(format_value(item) for item in v) + "]"
        return str(v)

    # Handle top-level keys first
    for k, v in data.items():
        if not isinstance(v, dict):
            lines.append(f"{k} = {format_value(v)}")
    
    # Handle dicts (tables)
    for k, v in data.items():
        if isinstance(v, dict):
            if lines: lines.append("")
            lines.append(f"[{k}]")
            for sub_k, sub_v in v.items():
                if not isinstance(sub_v, dict):
                    lines.append(f"{sub_k} = {format_value(sub_v)}")
                else:
                    # Handle one level of sub-tables (e.g. sim.ros)
                    lines.append("")
                    lines.append(f"[{k}.{sub_k}]")
                    for ssub_k, ssub_v in sub_v.items():
                         lines.append(f"{ssub_k} = {format_value(ssub_v)}")
    
    return "\n".join(lines)


def init_isaacsim() -> None:
    """Orchestrate Isaac Sim project initialization."""
    isaacsim_path = get_isaacsim_path()
    if isaacsim_path is None:
        raise click.ClickException("Isaac Sim not found.")

    pow_toml_path = Path.cwd() / "pow.toml"
    is_existing = pow_toml_path.exists()
    
    if not is_existing:
        # In a real scenario, this would copy from a template.
        pow_toml_path.write_text("[sim]\nversion = \"5.1.0\"\n\n[sim.ros]\nenable_ros = false\n")
    
    with open(pow_toml_path, "rb") as f:
        config = tomllib.load(f)
    generate_vscode_settings()
    fix_asset_browser_cache(isaacsim_path)
    
    ros_config = config.get("sim", {}).get("ros", {})
    updated_ros_config = setup_ros_workspace(ros_config, is_existing)
    
    config["sim"]["ros"] = updated_ros_config
    with open(pow_toml_path, "w") as f:
        f.write(dump_toml(config))
    
    click.echo(click.style("🎉 Successfully initialized Sim project 🎉", fg="green"))
