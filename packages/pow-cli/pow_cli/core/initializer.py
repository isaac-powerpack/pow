"""Manager core logic."""

import json
import os
import re
import platform
import shutil
import subprocess
import zipfile
import urllib.request
from pathlib import Path

import distro
import tomlkit

from .models.pow_config import PowConfig
from .models.system_config import SystemConfig


class Initializer:
    """Handles the management and initialization process for Isaac Powerpack.
    
    This class is responsible for:
    - Initialize project and global directory.
    - download isaacsim and fix its initial issues
    - setup isaacsim ros workspace
    """

    def __init__(self):
        """Initialize the Manager with default paths."""
        self._config_instance = None

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
            if distro_id != "ubuntu" or distro_version not in PowConfig.SUPPORTED_UBUNTU_VERSIONS:
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
    def _data_path(filename: str) -> Path:
        return Path(__file__).parent.parent / "data" / filename

    # ── Public API ────────────────────────────────────────────────────────────

    def get_config_path(self):
        """Return global configuration information for Step 1."""
        return {
            "global_dir_name": self.config.global_dir_name,
            "global_path": self.config.global_path,
        }

    def get_config(self) -> PowConfig:
        """Get the PowConfig object representing pow.toml."""
        return self.config

    def get_isaacsim_path(self) -> Path | None:
        """Resolve the Isaac Sim installation path.

        Checks the managed .pow/isaacsim/<version> folder first, then falls
        back to importing the ``isaacsim`` Python package. Returns None if
        Isaac Sim cannot be located.
        """
        managed = self.config.global_path / "isaacsim" / PowConfig.ISAACSIM_VERSION
        if managed.is_dir():
            return managed

        try:
            import isaacsim
            pkg_path = Path(isaacsim.__file__).parent
            if pkg_path.is_dir():
                return pkg_path
        except ImportError:
            pass

        return None



    def create_global_folder(self):
        """Create the global directories and return the created paths with status."""
        subfolders = ["isaacsim", "modules", "projects", "sim-ros"]
        global_path = self.config.global_path
        global_dir_name = self.config.global_dir_name

        global_exists = global_path.exists()
        if not global_exists:
            global_path.mkdir(parents=True)

        results = []
        for sub in subfolders:
            sub_path = global_path / sub
            existed = sub_path.exists()

            if global_exists:
                # Skip creation if global folder already exists
                results.append({
                    "path": f"{global_dir_name}/{sub}",
                    "status": "Existed" if existed else "Skipped",
                })
            else:
                # Create sub-folder when global folder is freshly created
                sub_path.mkdir(parents=True, exist_ok=True)
                results.append({
                    "path": f"{global_dir_name}/{sub}",
                    "status": "Created",
                })

        return {"global_existed": global_exists, "results": results}

    def create_system_toml(self) -> dict:
        """Create system.toml in the global folder if it does not already exist."""
        system_toml_path = self.config.global_path / "system.toml"
        if system_toml_path.exists():
            return {"status": "Existed", "path": str(system_toml_path)}

        system_config = SystemConfig.default()
        doc = tomlkit.document()
        for section, values in system_config.to_dict().items():
            table = tomlkit.table()
            for k, v in values.items():
                table.add(k, v)
            doc.add(section, table)
        system_toml_path.write_text(tomlkit.dumps(doc))
        return {"status": "Created", "path": str(system_toml_path)}

    @property
    def config(self) -> PowConfig:
        """Get the PowConfig singleton, instantiating it efficiently."""
        if self._config_instance is None:
            self._config_instance = PowConfig()
        return self._config_instance

    def read_config(self):
        """Read configuration from an existing pow.toml file using the PowConfig singleton."""
        return self.config.data

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

    def download_isaacsim(self, progress_callback=None, status_callback=None, mock=False):
        """Download and install Isaac Sim."""
        self._check_platform()

        dest_dir = self.config.global_path / "isaacsim"
        dest_dir.mkdir(parents=True, exist_ok=True)
        zip_path = dest_dir / PowConfig.ISAACSIM_FILENAME
        target_folder = dest_dir / PowConfig.ISAACSIM_VERSION

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

    def link_managed_isaacsim(self) -> dict:
        """Symlink global managed Isaac Sim to project's _isaacsim."""
        version = PowConfig.ISAACSIM_VERSION
        global_isaacsim = self.config.global_path / "isaacsim" / version

        if not global_isaacsim.is_dir():
            return {"status": "Error", "message": f"Global Isaac Sim {version} not found."}

        target_link = Path("_isaacsim")

        if target_link.exists() or target_link.is_symlink():
            return {"status": "Existed", "path": str(target_link)}

        target_link.symlink_to(global_isaacsim, target_is_directory=True)
        return {"status": "Created", "path": str(target_link)}

    def setup_vscode_configs(self) -> dict:
        """Copy and patch VSCode configs from _isaacsim/.vscode to project."""
        src_vscode = Path("_isaacsim") / ".vscode"
        dest_vscode = Path(".vscode")

        if not src_vscode.is_dir():
            return {"status": "Error", "message": "_isaacsim/.vscode not found."}

        dest_vscode.mkdir(parents=True, exist_ok=True)
        files_to_copy = ["launch.json", "tasks.json", "settings.json", "c_cpp_properties.json"]
        patch_files = {"launch.json", "tasks.json", "settings.json"}
        results = []

        for filename in files_to_copy:
            src_file = src_vscode / filename
            dest_file = dest_vscode / filename

            if not src_file.exists():
                results.append({"file": filename, "status": "Not found in source"})
                continue

            shutil.copy(src_file, dest_file)

            if filename not in patch_files:
                results.append({"file": filename, "status": "Copied"})
                continue

            # Patch: replace ${workspaceFolder} with _isaacsim
            content = dest_file.read_text().replace("${workspaceFolder}", "_isaacsim")

            # Patch settings.json using regex to handle JSONC (comments allowed)
            if filename == "settings.json":
                # Prefix non-prefixed string entries in python.analysis.extraPaths array
                def _prefix_extra_paths(m):
                    # m.group(0) is '"python.analysis.extraPaths": [ ... ]'
                    full_content = m.group(0)
                    key_part, array_part = full_content.split(':', 1)

                    # Match strings inside the array that are not already prefixed
                    patched_array = re.sub(
                        r'([\[,])(\s*)"(?!_isaacsim)([^"]+)"',
                        r'\1\2"_isaacsim/\3"',
                        array_part
                    )
                    return key_part + ':' + patched_array

                content = re.sub(
                    r'"python\.analysis\.extraPaths"\s*:\s*\[[^\]]*\]',
                    _prefix_extra_paths,
                    content,
                    flags=re.DOTALL,
                )

            dest_file.write_text(content)
            results.append({"file": filename, "status": "Copied and patched"})

        return {"status": "Success", "results": results}

    def init_git(self) -> dict:
        """Initialize git repository if it doesn't already exist."""
        git_dir = Path(".git")
        if git_dir.exists():
            return {"status": "Existed"}

        try:
            subprocess.run(["git", "init", "--quiet"], check=True)
            return {"status": "Created"}
        except Exception as e:
            return {"status": "Error", "message": str(e)}

    def create_pow_toml(
        self,
        override: bool = False,
        enable_ros: bool = False,
        isaacsim_ros_ws: str = "~/IsaacSim-ros_workspaces",
    ) -> dict:
        """Copy pow.template.toml to pow.toml and patch settings from user choices."""
        # Initialize git if not already done
        self.init_git()

        pow_toml_path = Path("pow.toml")

        if pow_toml_path.exists() and not override:
            return {"status": "Existed", "path": str(pow_toml_path)}

        template_path = self._data_path("pow.template.toml")
        if not template_path.exists():
            return {"status": "Template not found", "path": str(pow_toml_path)}

        shutil.copy(template_path, pow_toml_path)
        self._patch_pow_toml(
            pow_toml_path,
            enable_ros=enable_ros,
            isaacsim_ros_ws=isaacsim_ros_ws,
        )

        return {"status": "Created", "path": str(pow_toml_path)}

    # ── Private methods ─────────────────────────────────────────────────────────

    @staticmethod
    def _fix_isaacsim_permissions(isaacsim_path: Path):
        """Recursively fix execute permissions lost during zip extraction.

        Makes all .sh files executable and restores execute bits on known
        binary paths (e.g. kit/python/bin/python3).
        """
        # Fix all .sh scripts
        for sh_file in isaacsim_path.rglob("*.sh"):
            if sh_file.is_file() and not os.access(sh_file, os.X_OK):
                sh_file.chmod(sh_file.stat().st_mode | 0o111)

        # Fix known binary directories
        bin_dirs = [
            isaacsim_path / "kit" / "python" / "bin",
            isaacsim_path / "kit",
        ]
        for bin_dir in bin_dirs:
            if not bin_dir.is_dir():
                continue
            for f in bin_dir.iterdir():
                if f.is_file() and not os.access(f, os.X_OK):
                    # Check if it looks like an ELF binary or script
                    try:
                        with open(f, "rb") as fh:
                            header = fh.read(4)
                        if header[:4] == b"\x7fELF" or header[:2] == b"#!":
                            f.chmod(f.stat().st_mode | 0o111)
                    except OSError:
                        pass

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
                urllib.request.urlretrieve(PowConfig.ISAACSIM_URL, zip_path, reporthook)
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
                members = zip_ref.infolist()          # ZipInfo objects carry external_attr
                total_files = len(members)
                target_folder.mkdir(parents=True, exist_ok=True)
                for i, info in enumerate(members):
                    if progress_callback and i % 50 == 0:
                        progress_callback(i, total_files)
                    extracted = target_folder / info.filename
                    zip_ref.extract(info, target_folder)
                    # Restore Unix permissions stored in the zip (upper 16 bits of external_attr)
                    unix_mode = (info.external_attr >> 16) & 0xFFFF
                    if unix_mode and extracted.exists():
                        extracted.chmod(unix_mode)
                if progress_callback:
                    progress_callback(total_files, total_files)
            if status_callback:
                status_callback("Extracted")

            # Run post_install.sh if it exists
            post_install_script = target_folder / "post_install.sh"
            if post_install_script.exists():
                if status_callback:
                    status_callback("Post-Install")
                subprocess.run([str(post_install_script)], cwd=target_folder, check=True)
        except Exception:
            if target_folder.exists():
                shutil.rmtree(target_folder)
            raise
        finally:
            if zip_path.exists():
                zip_path.unlink()

    def _patch_pow_toml(
        self,
        pow_toml_path: Path,
        enable_ros: bool,
        isaacsim_ros_ws: str = "~/IsaacSim-ros_workspaces",
    ):
        """Patch values in pow.toml to reflect user choices made during init."""
        content = pow_toml_path.read_text()
        
        doc = tomlkit.parse(content)
        
        # We ensure the top-level [sim] section is present or patch it.
        # Since the template already has [sim], we just update enable_ros within it.
        if "sim" in doc and isinstance(doc["sim"], dict):
            doc["sim"]["enable_ros"] = enable_ros
            doc["sim"]["isaacsim_ros_ws"] = isaacsim_ros_ws
        else:
            doc["sim"] = {
                "enable_ros": enable_ros,
                "isaacsim_ros_ws": isaacsim_ros_ws,
            }
            
        pow_toml_path.write_text(tomlkit.dumps(doc))
