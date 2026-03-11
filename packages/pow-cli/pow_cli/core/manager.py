"""Manager core logic."""

import json
import platform
import re
import shutil
import subprocess
import tomllib
import zipfile
import urllib.request
from pathlib import Path

import distro

from ..common.utils import get_global_dir_name


_ISAACSIM_VERSION = "5.1.0"
_ISAACSIM_FILENAME = f"isaac-sim-standalone-{_ISAACSIM_VERSION}-linux-x86_64.zip"
_ISAACSIM_URL = f"https://download.isaacsim.omniverse.nvidia.com/{_ISAACSIM_FILENAME}"
_SUPPORTED_UBUNTU_VERSIONS = ["22.04", "24.04"]
_ROS_DISTRO_MAP = {"24.04": "jazzy", "22.04": "humble"}


class Manager:
    """Handles the management and initialization process for Isaac Powerpack."""

    def __init__(self):
        """Initialize the Manager with default paths."""
        self.global_dir_name = get_global_dir_name()
        self.home = Path.home()
        self.global_path = self.home / self.global_dir_name

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _check_platform(self):
        """Raise RuntimeError when the current platform cannot run Isaac Sim."""
        if platform.machine() != "x86_64":
            raise RuntimeError(
                f"Unsupported architecture: {platform.machine()}. Isaac Sim requires x86_64."
            )

        system = platform.system()
        if system in ("Windows", "Darwin"):
            label = "Windows" if system == "Windows" else "macOS"
            raise RuntimeError(
                f"Unsupported OS: {label}. Pow only support Isaac Sim on Ubuntu 22.04 or 24.04."
            )
        if system != "Linux":
            raise RuntimeError(
                f"Unsupported OS: {system}. Pow only support Isaac Sim on Ubuntu 22.04 or 24.04."
            )

        try:
            distro_id = distro.id()
            distro_version = distro.version()
            if distro_id != "ubuntu" or distro_version not in _SUPPORTED_UBUNTU_VERSIONS:
                distro_name = distro.name()
                raise RuntimeError(
                    f"Unsupported OS: {distro_name} {distro_version}. "
                    f"Isaac Sim requires Ubuntu 22.04 or 24.04."
                )
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Could not verify OS version using distro package: {e}")

    @staticmethod
    def _detect_ros_distro() -> tuple[str, str]:
        """Return (ros_distro, ubuntu_version) based on current OS."""
        try:
            ubuntu_version = distro.version()
        except Exception:
            ubuntu_version = "22.04"  # safe fallback

        if ubuntu_version not in _ROS_DISTRO_MAP:
            ubuntu_version = "22.04"

        return _ROS_DISTRO_MAP[ubuntu_version], ubuntu_version

    @staticmethod
    def _data_path(filename: str) -> Path:
        return Path(__file__).parent.parent / "data" / filename

    # ── Public API ────────────────────────────────────────────────────────────

    def get_config_info(self):
        """Return global configuration information for Step 1."""
        return {
            "global_dir_name": self.global_dir_name,
            "global_path": self.global_path,
        }

    def create_global_folder(self):
        """Create the global directories and return the created paths with status."""
        subfolders = ["isaacsim", "modules", "projects", "sim-ros"]

        global_exists = self.global_path.exists()
        if not global_exists:
            self.global_path.mkdir(parents=True)

        results = []
        for sub in subfolders:
            sub_path = self.global_path / sub
            existed = sub_path.exists()

            if global_exists:
                # Skip creation if global folder already exists
                results.append({
                    "path": f"{self.global_dir_name}/{sub}",
                    "status": "Existed" if existed else "Skipped",
                })
            else:
                # Create sub-folder when global folder is freshly created
                sub_path.mkdir(parents=True, exist_ok=True)
                results.append({
                    "path": f"{self.global_dir_name}/{sub}",
                    "status": "Created",
                })

        return {"global_existed": global_exists, "results": results}

    def read_config(self):
        """Read configuration from an existing pow.toml file."""
        pow_toml_path = Path("pow.toml")
        if pow_toml_path.exists():
            with open(pow_toml_path, "rb") as f:
                try:
                    self.config = tomllib.load(f)
                    return self.config
                except Exception as e:
                    print(f"Error reading pow.toml: {e}")
        return {}

    def fix_asset_browser_cache(self, isaacsim_path) -> bool:
        """Fix the Isaac Sim asset browser cache issue."""
        cache_path = (
            Path(isaacsim_path)
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

    def setup_ros_workspace(self, status_callback=None) -> dict:
        """Setup ROS workspace for Isaac Sim project in .pow/sim-ros."""
        ros_distro, ubuntu_version = self._detect_ros_distro()

        clone_path = self.global_path / "sim-ros" / "IsaacSim-ros_workspaces"

        # Clone workspace if not already cloned
        if not (clone_path / ".git").exists():
            if status_callback:
                status_callback("cloning")
            subprocess.run(
                [
                    "git", "clone", "-b", "IsaacSim-5.1.0", "--quiet",
                    "https://github.com/isaac-sim/IsaacSim-ros_workspaces.git",
                    str(clone_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            if status_callback:
                status_callback("existed")

        # Build ROS workspace (skip if Docker image already exists)
        ubuntu_major = ubuntu_version.split(".")[0]
        docker_image = f"isaac_sim_ros:ubuntu_{ubuntu_major}_{ros_distro}"

        image_exists = subprocess.run(
            ["docker", "image", "inspect", docker_image],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0

        if image_exists:
            if status_callback:
                status_callback("built")
        else:
            if status_callback:
                status_callback("building")
            process = subprocess.Popen(
                ["./build_ros.sh", "-d", ros_distro, "-v", ubuntu_version],
                cwd=clone_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in process.stdout:
                stripped = line.strip()
                if stripped and status_callback:
                    status_callback(f"building:{stripped}")
            process.wait()
            if process.returncode != 0:
                raise RuntimeError(f"ROS build failed with exit code {process.returncode}")

        return {
            "status": "success",
            "ros_distro": ros_distro,
            "ubuntu_version": ubuntu_version,
            "path": str(clone_path),
        }

    def download_isaacsim(self, progress_callback=None, status_callback=None, mock=False):
        """Download and install Isaac Sim."""
        self._check_platform()

        dest_dir = self.global_path / "isaacsim"
        dest_dir.mkdir(parents=True, exist_ok=True)
        zip_path = dest_dir / _ISAACSIM_FILENAME
        target_folder = dest_dir / _ISAACSIM_VERSION

        if not mock and target_folder.exists():
            return {"status": "Already installed", "path": str(target_folder)}

        self._download_isaacsim_zip(zip_path, progress_callback, status_callback, mock)
        self._extract_isaacsim_zip(zip_path, target_folder, progress_callback, status_callback, mock)

        return {"status": "Downloaded and installed", "path": str(target_folder)}

    def setup_project_structure(self, local_folders: list) -> dict:
        """Create project folders and .gitignore from template."""
        results = []

        for folder in local_folders:
            path = Path(folder)
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                results.append({"path": folder, "status": "Created"})
            else:
                results.append({"path": folder, "status": "Existed"})

        gitignore_path = Path(".gitignore")
        template_path = self._data_path("gitignore.template")

        if gitignore_path.exists():
            results.append({"path": ".gitignore", "status": "Existed"})
        elif template_path.exists():
            shutil.copy(template_path, gitignore_path)
            results.append({"path": ".gitignore", "status": "Created from template"})
        else:
            results.append({"path": ".gitignore", "status": "Template not found"})

        return {"results": results}

    def create_pow_toml(self, override: bool = False, enable_ros: bool = False) -> dict:
        """Copy pow.template.toml to pow.toml and patch settings from user choices."""
        pow_toml_path = Path("pow.toml")

        if pow_toml_path.exists() and not override:
            return {"status": "Existed", "path": str(pow_toml_path)}

        template_path = self._data_path("pow.template.toml")
        if not template_path.exists():
            return {"status": "Template not found", "path": str(pow_toml_path)}

        shutil.copy(template_path, pow_toml_path)
        self._patch_pow_toml(pow_toml_path, enable_ros=enable_ros)

        return {"status": "Created", "path": str(pow_toml_path)}

    # ── Private methods ─────────────────────────────────────────────────────────
    def _download_isaacsim_zip(self, zip_path, progress_callback, status_callback, mock):
        """Download the Isaac Sim zip archive."""
        if not mock and zip_path.exists():
            if status_callback:
                status_callback("Skipped download")
            return

        if status_callback:
            status_callback("Downloading")

        if mock:
            import time
            total_size = 100 * 1024 * 1024  # 100 MB mock
            for i in range(101):
                if progress_callback:
                    progress_callback(i * 1024 * 1024, total_size)
                time.sleep(0.02)
        else:
            def reporthook(blocknum, blocksize, totalsize):
                if progress_callback:
                    progress_callback(blocknum * blocksize, totalsize)

            try:
                urllib.request.urlretrieve(_ISAACSIM_URL, zip_path, reporthook)
            except Exception as e:
                if zip_path.exists():
                    zip_path.unlink()
                raise RuntimeError(f"Download failed: {e}")

    def _extract_isaacsim_zip(self, zip_path, target_folder, progress_callback, status_callback, mock):
        """Extract the Isaac Sim zip archive."""
        if mock:
            import time
            total_mock_files = 100
            if status_callback:
                status_callback("Extracting")
            for i in range(total_mock_files + 1):
                if progress_callback:
                    progress_callback(i, total_mock_files)
                time.sleep(0.02)
            if status_callback:
                status_callback("Extracted")
            return

        if status_callback:
            status_callback("Extracting")

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                namelist = zip_ref.namelist()
                total_files = len(namelist)
                target_folder.mkdir(parents=True, exist_ok=True)
                for i, member in enumerate(namelist):
                    if progress_callback and i % 50 == 0:
                        progress_callback(i, total_files)
                    zip_ref.extract(member, target_folder)
                if progress_callback:
                    progress_callback(total_files, total_files)
            if status_callback:
                status_callback("Extracted")
        except Exception:
            if target_folder.exists():
                shutil.rmtree(target_folder)
            raise
        finally:
            if zip_path.exists():
                zip_path.unlink()

    def _patch_pow_toml(self, pow_toml_path: Path, enable_ros: bool):
        """Patch values in pow.toml to reflect user choices made during init."""
        content = pow_toml_path.read_text()
        ros_value = "true" if enable_ros else "false"
        content = re.sub(
            r"^enable_ros\s*=\s*(true|false)",
            f"enable_ros = {ros_value}",
            content,
            flags=re.MULTILINE,
        )
        pow_toml_path.write_text(content)
