import sys
import pytest
from unittest.mock import MagicMock
from pathlib import Path

# Add the package to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from pow_cli.core.initializer import Initializer

class TestIsaacSimDownload:
    @pytest.fixture(autouse=True)
    def setup_manager(self, mocker):
        self.initializer = Initializer()
        self.mock_distro_id = mocker.patch("distro.id", return_value="ubuntu")
        self.mock_distro_version = mocker.patch("distro.version", return_value="22.04")
        self.mock_distro_name = mocker.patch("distro.name", return_value="Ubuntu")

    def test_architecture_check_failure(self, mocker):
        mocker.patch("platform.machine", return_value="arm64")
        with pytest.raises(RuntimeError, match="Unsupported architecture: arm64"):
            self.initializer.download_isaacsim()

    def test_os_check_failure(self, mocker):
        mocker.patch("platform.machine", return_value="x86_64")
        mocker.patch("platform.system", return_value="Linux")
        
        self.mock_distro_id.return_value = "ubuntu"
        self.mock_distro_version.return_value = "20.04"
        self.mock_distro_name.return_value = "Ubuntu"
        
        expected_msg = "Unsupported OS: Ubuntu 20.04. Isaac Sim requires Ubuntu 22.04 or 24.04."
        with pytest.raises(RuntimeError, match=expected_msg):
            self.initializer.download_isaacsim()

    def test_successful_flow_mocked(self, mocker):
        mocker.patch("platform.machine", return_value="x86_64")
        mocker.patch("platform.system", return_value="Linux")
        
        self.mock_distro_id.return_value = "ubuntu"
        self.mock_distro_version.return_value = "22.04"
        self.mock_distro_name.return_value = "Ubuntu"
        
        mock_urlretrieve = mocker.patch("pow_cli.core.initializer.urllib.request.urlretrieve")
        mock_zip = mocker.patch("pow_cli.core.initializer.zipfile.ZipFile")
        mocker.patch("pow_cli.core.initializer.Path.mkdir")
        mock_exists = mocker.patch("pow_cli.core.initializer.Path.exists")
        mocker.patch("pow_cli.core.initializer.Path.rename")
        mocker.patch("pow_cli.core.initializer.Path.unlink")
        
        # Robust exists side effect using captured arguments
        def exists_side_effect(*args, **kwargs):
            if not args:
                return False
            path_obj = args[0]
            path_str = str(path_obj)
            
            # Check for the target folder: global_path / "isaacsim" / "5.1.0"
            if path_str.endswith("/5.1.0"):
                return False
            
            # Check for the zip file: global_path / "isaacsim" / "isaac-sim-standalone-5.1.0-linux-x86_64.zip"
            if path_str.endswith(".zip"):
                return True
                
            # Check for the extracted folder: global_path / "isaacsim" / "isaac-sim-standalone-5.1.0"
            if "isaac-sim-standalone-5.1.0" in path_str:
                return True
                
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        mock_zip_instance = MagicMock()
        mock_zip_instance.namelist.return_value = ["isaac-sim-standalone-5.1.0/"]
        mock_zip.return_value.__enter__.return_value = mock_zip_instance

        result = self.initializer.download_isaacsim()
        
        assert result["status"] == "Downloaded and installed"
        mock_urlretrieve.assert_called_once()
        mock_zip_instance.extractall.assert_not_called() # It uses .extract() now in a loop
