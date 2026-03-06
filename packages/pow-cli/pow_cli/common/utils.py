"""Common utilities and shared objects."""

import tomllib
from pathlib import Path
from rich.console import Console

console = Console()

def get_global_dir_name():
    """Read global_dir_name from pyproject.toml or default to .pow"""
    pyproject_path = Path.cwd() / "pyproject.toml"
    if pyproject_path.exists():
        with open(pyproject_path, "rb") as f:
            try:
                data = tomllib.load(f)
                val = data.get("tool", {}).get("pow-cli", {}).get("global_dir_name")
                if val:
                    return val
            except Exception:
                pass
    return ".pow"
