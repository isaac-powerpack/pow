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
