"""Manager core logic."""

import platform
import shutil
import zipfile
import urllib.request
from pathlib import Path
from ..common.utils import get_global_dir_name

class Manager:
    """Handles the management and initialization process for Isaac Powerpack."""

    def __init__(self):
        """Initialize the Manager with default paths."""
        self.global_dir_name = get_global_dir_name()
        self.home = Path.home()
        self.global_path = self.home / self.global_dir_name

    def get_config_info(self):
        """Return global configuration information for Step 1."""
        return {
            "global_dir_name": self.global_dir_name,
            "global_path": self.global_path
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
                    "status": "Existed" if existed else "Skipped"
                })
            else:
                # Create if global folder is new
                sub_path.mkdir(parents=True, exist_ok=True)
                results.append({
                    "path": f"{self.global_dir_name}/{sub}",
                    "status": "Created"
                })
            
        return {
            "global_existed": global_exists,
            "results": results
        }

    def read_config(self):
        """Read configuration from an existing pow.toml file."""
        import tomllib
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
        import json
        isaacsim_path = Path(isaacsim_path)
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

    def setup_ros_workspace(self, status_callback=None) -> dict:
        """Setup ROS workspace for Isaac Sim project in .pow/sim-ros."""
        import distro
        import subprocess
        
        ros_workspace_path = self.global_path / "sim-ros"
        clone_path = ros_workspace_path / "IsaacSim-ros_workspaces"
        
        # Determine Ubuntu version and corresponding ROS distro
        try:
            distro_version = distro.version()
        except Exception:
            distro_version = "22.04" # Default fallback
            
        if distro_version == "24.04":
            ros_distro = "jazzy"
            ubuntu_version = "24.04"
        else:
            ros_distro = "humble"
            ubuntu_version = "22.04"

        # Clone workspace if not already cloned (check .git to distinguish from empty dir)
        if not (clone_path / ".git").exists():
            if status_callback:
                status_callback("cloning")
            subprocess.run(
                [
                    "git", "clone", "-b", "IsaacSim-5.1.0", "--quiet", 
                    "https://github.com/isaac-sim/IsaacSim-ros_workspaces.git", 
                    str(clone_path)
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            if status_callback:
                status_callback("existed")

        # Build ROS workspace (skip if Docker image already exists)
        ubuntu_major = ubuntu_version.split(".")[0]  # "22.04" -> "22"
        docker_image = f"isaac_sim_ros:ubuntu_{ubuntu_major}_{ros_distro}"
        
        # Check if Docker image already exists
        image_exists = subprocess.run(
            ["docker", "image", "inspect", docker_image],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0

        if image_exists:
            if status_callback:
                status_callback("built")
        else:
            # Run Docker build (quiet, but stream output lines for progress)
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
            "path": str(clone_path)
        }

    def download_isaacsim(self, progress_callback=None, status_callback=None, mock=False):
        """Download and install Isaac Sim 5.1.0."""
        # 1. Architecture Check
        if platform.machine() != "x86_64":
            raise RuntimeError(f"Unsupported architecture: {platform.machine()}. Isaac Sim requires x86_64.")

        # 2. OS Check
        system = platform.system()
        if system == "Windows":
            raise RuntimeError("Unsupported OS: Windows. Pow only support Isaac Sim on Ubuntu 22.04 or 24.04.")
        elif system == "Darwin":
            raise RuntimeError("Unsupported OS: macOS. Pow only support Isaac Sim on Ubuntu 22.04 or 24.04.")
        elif system != "Linux":
            raise RuntimeError(f"Unsupported OS: {system}. Pow only support Isaac Sim on Ubuntu 22.04 or 24.04.")

        import distro
        try:
            distro_id = distro.id()
            distro_version = distro.version()
            
            if distro_id != "ubuntu" or distro_version not in ["22.04", "24.04"]:
                distro_name = distro.name() if hasattr(distro, 'name') else distro_id
                raise RuntimeError(f"Unsupported OS: {distro_name} {distro_version}. Isaac Sim requires Ubuntu 22.04 or 24.04.")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Could not verify OS version using distro package: {e}")

        # 3. Preparation
        url = "https://download.isaacsim.omniverse.nvidia.com/isaac-sim-standalone-5.1.0-linux-x86_64.zip"
        dest_dir = self.global_path / "isaacsim"
        dest_dir.mkdir(parents=True, exist_ok=True)
        zip_path = dest_dir / "isaac-sim-standalone-5.1.0-linux-x86_64.zip"
        target_folder = dest_dir / "5.1.0"

        if not mock and target_folder.exists():
            return {"status": "Already installed", "path": str(target_folder)}

        # 4. Download (skip if zip already exists)
        if not mock and zip_path.exists():
            if status_callback:
                status_callback("Skipped download")
        else:
            if status_callback:
                status_callback("Downloading")

            if mock:
                import time
                total_size = 100 * 1024 * 1024 # Mock 100MB
                for i in range(101):
                    if progress_callback:
                        progress_callback(i * 1024 * 1024, total_size)
                    time.sleep(0.02)
            else:
                def reporthook(blocknum, blocksize, totalsize):
                    if progress_callback:
                        progress_callback(blocknum * blocksize, totalsize)

                try:
                    urllib.request.urlretrieve(url, zip_path, reporthook)
                except Exception as e:
                    if zip_path.exists():
                        zip_path.unlink()
                    raise RuntimeError(f"Download failed: {e}")

        # 5. Extraction
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
        else:
            if status_callback:
                status_callback("Extracting")

            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    namelist = zip_ref.namelist()
                    total_files = len(namelist)
                    
                    # Equivalent to: unzip file.zip -d 5.1.0
                    target_folder.mkdir(parents=True, exist_ok=True)
                    
                    for i, member in enumerate(namelist):
                        if progress_callback and i % 50 == 0:
                            progress_callback(i, total_files)
                        zip_ref.extract(member, target_folder)
                    
                    # Final 100% update
                    if progress_callback:
                        progress_callback(total_files, total_files)
                
                if status_callback:
                    status_callback("Extracted")
            except Exception:
                # Clean up partial extraction on failure
                if target_folder.exists():
                    shutil.rmtree(target_folder)
                raise
            finally:
                if zip_path.exists():
                    zip_path.unlink()

        return {"status": "Downloaded and installed", "path": str(target_folder)}

    def setup_project_structure(self, local_folders: list) -> dict:
        """Create project folders and .gitignore from template."""
        results = []
        
        # 1. Create folders
        for folder in local_folders:
            path = Path(folder)
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                results.append({"path": folder, "status": "Created"})
            else:
                results.append({"path": folder, "status": "Existed"})

        # 2. Copy .gitignore
        template_path = Path(__file__).parent.parent / "data" / "gitignore.template"
        gitignore_path = Path(".gitignore")
        
        if gitignore_path.exists():
            results.append({"path": ".gitignore", "status": "Existed"})
        elif template_path.exists():
            shutil.copy(template_path, gitignore_path)
            results.append({"path": ".gitignore", "status": "Created from template"})
        else:
            results.append({"path": ".gitignore", "status": "Template not found"})

        return {"results": results}
