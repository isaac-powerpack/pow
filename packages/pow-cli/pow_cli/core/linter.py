"""Linter — detects and fixes relative asset paths in .usda files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class LintIssue:
    """A single lint finding in a .usda file."""

    file: Path
    line: int
    original: str
    replacement: str
    message: str


@dataclass
class AliasGroup:
    """Categorised alias keys from omniverse.toml [aliases]."""

    pow_assets: dict[str, str]      # group a: pow-assets key
    sim_ready: dict[str, str]       # group b: staging S3 URLs
    nvidia_assets: dict[str, str]   # group c: everything else


# S3 URL prefixes used to classify aliases into groups
_SIM_READY_PREFIXES = (
    "http://omniverse-content-staging.s3.us-west-2.amazonaws.com",
    "https://omniverse-content-staging.s3.us-west-2.amazonaws.com",
)

# NVIDIA production S3 URL (used for non-Pow, non-SimReady assets)
_NVIDIA_PRODUCTION_S3 = "https://omniverse-content-production.s3.us-west-2.amazonaws.com"

# Regex: match @<one or more ../>.pow/assets/<rest>@ inside .usda
# Captures the path after .pow/assets/ so we can rewrite to @pow-assets/<rest>@
_RELATIVE_POW_ASSETS_RE = re.compile(
    r"@(?:\.\./)+\.pow/assets/(.+?)@"
)


# ── Alias config loader ──────────────────────────────────────────────────────


class AliasConfig:
    """Reads and categorises [aliases] from omniverse.toml."""

    OMNIVERSE_TOML_PATH = Path.home() / ".nvidia-omniverse" / "config" / "omniverse.toml"

    def __init__(self) -> None:
        self.groups = self._load()

    def _load(self) -> AliasGroup:
        aliases: dict[str, str] = {}

        if self.OMNIVERSE_TOML_PATH.exists():
            with open(self.OMNIVERSE_TOML_PATH, "rb") as f:
                doc = tomllib.load(f)
            aliases = doc.get("aliases", {})

        pow_assets: dict[str, str] = {}
        sim_ready: dict[str, str] = {}
        nvidia_assets: dict[str, str] = {}

        for key, value in aliases.items():
            if key == "pow-assets":
                pow_assets[key] = value
            elif key in _SIM_READY_PREFIXES:
                sim_ready[key] = value
            else:
                nvidia_assets[key] = value

        return AliasGroup(
            pow_assets=pow_assets,
            sim_ready=sim_ready,
            nvidia_assets=nvidia_assets,
        )

    @property
    def has_pow_assets(self) -> bool:
        return bool(self.groups.pow_assets)


# ── Linter engine ─────────────────────────────────────────────────────────────


def scan_directory(path: Path) -> List[Path]:
    """Recursively find all .usda files under the given path."""
    if path.is_file():
        return [path] if path.suffix == ".usda" else []
    return sorted(path.rglob("*.usda"))


def lint_file(file_path: Path, alias_config: AliasConfig | None = None) -> List[LintIssue]:
    """Scan a single .usda file for relative asset path issues.

    Returns a list of LintIssue objects, one per problematic line.
    """
    from .models.pow_config import PowConfig

    issues: List[LintIssue] = []
    text = file_path.read_text(encoding="utf-8")

    # ── Prepare detection patterns ─────────────────────────────────────────
    home_dir = str(Path.home())
    # General rule: any @/home/user/...@ → @user-home/...@
    home_abs_re = re.compile(r"@" + re.escape(home_dir) + r"/([^@]+)@")

    # ROS workspace relative rule: @../../../../simros_ws/...@ → @user-home/simros_ws/...@
    ros_ws_rel_re: re.Pattern | None = None
    ros_ws_home_relative: str | None = None
    try:
        config = PowConfig()
        raw_ros_ws: str = config.get("isaacsim_ros_ws", "~/IsaacSim-ros_workspaces")
        if raw_ros_ws.startswith("~/"):
            ros_ws_home_relative = raw_ros_ws[2:]
        elif raw_ros_ws.startswith("~"):
            ros_ws_home_relative = raw_ros_ws[1:]

        if ros_ws_home_relative:
            escaped_name = re.escape(ros_ws_home_relative)
            ros_ws_rel_re = re.compile(
                r"@(?:\.\./)+(" + escaped_name + r"/[^@]*)@"
            )
    except Exception:
        pass

    # ── Build lint rules ───────────────────────────────────────────────────
    # Each rule is a (compiled_regex, handler) pair.  The handler receives
    # (match, file_path, line_num) and returns a (replacement, message) tuple.
    rules: list[tuple[re.Pattern, callable]] = []

    # Rule 1: relative .pow/assets paths
    def _handle_pow_assets(m, _fp, _ln):
        asset_subpath = m.group(1)
        original = m.group(0)
        # Routing rules (checked in order):
        #   1. simready_content  → sim-ready staging S3 URL
        #   2. Pow in path       → pow-assets alias (custom pow content)
        #   3. everything else   → NVIDIA production S3 URL
        if "simready_content" in asset_subpath:
            replacement = f"@{_SIM_READY_PREFIXES[1]}/{asset_subpath}@"
            message = (
                f"Relative path to sim-ready asset — use sim-ready staging S3 URL: "
                f"{original} → {replacement}"
            )
        elif "Pow" in asset_subpath:
            replacement = f"@pow-assets/{asset_subpath}@"
            message = (
                f"Relative path to pow asset — use pow-assets alias: "
                f"{original} → {replacement}"
            )
        else:
            replacement = f"@{_NVIDIA_PRODUCTION_S3}/{asset_subpath}@"
            message = (
                f"Relative path to NVIDIA asset — use production S3 URL: "
                f"{original} → {replacement}"
            )
        return replacement, message

    rules.append((_RELATIVE_POW_ASSETS_RE, _handle_pow_assets))

    # Rule 2: absolute home-directory paths (general)
    #   @/home/user/anything/...@ → @user-home/anything/...@
    def _handle_home_abs(m, _fp, _ln):
        rest = m.group(1)
        original = m.group(0)
        replacement = f"@user-home/{rest}@"
        message = (
            f"Absolute home path — use user-home alias: "
            f"{original} → {replacement}"
        )
        return replacement, message

    rules.append((home_abs_re, _handle_home_abs))

    # Rule 3: relative ROS workspace paths
    #   @../../../../simros_ws/...@ → @user-home/simros_ws/...@
    if ros_ws_rel_re:
        def _handle_ros_rel(m, _fp, _ln):
            ws_and_rest = m.group(1)
            original = m.group(0)
            replacement = f"@user-home/{ws_and_rest}@"
            message = (
                f"Relative ROS workspace path — use user-home alias: "
                f"{original} → {replacement}"
            )
            return replacement, message

        rules.append((ros_ws_rel_re, _handle_ros_rel))

    # ── Scan lines ────────────────────────────────────────────────────────
    for line_num, line in enumerate(text.splitlines(), start=1):
        for pattern, handler in rules:
            for match in pattern.finditer(line):
                replacement, message = handler(match, file_path, line_num)
                issues.append(
                    LintIssue(
                        file=file_path,
                        line=line_num,
                        original=match.group(0),
                        replacement=replacement,
                        message=message,
                    )
                )

    return issues


def fix_file(file_path: Path, issues: List[LintIssue]) -> None:
    """Apply all lint fixes to a file in-place."""
    if not issues:
        return

    text = file_path.read_text(encoding="utf-8")
    for issue in issues:
        text = text.replace(issue.original, issue.replacement)
    file_path.write_text(text, encoding="utf-8")
