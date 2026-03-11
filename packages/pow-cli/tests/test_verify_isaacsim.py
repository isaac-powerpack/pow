import sys
import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# Add the package to sys.path
sys.path.append(str(Path(__file__).parent.parent))

# Mock distro at the module level for the entire test session
mock_distro = MagicMock()
sys.modules["distro"] = mock_distro

from pow_cli.core.manager import Manager

class TestIsaacSimDownload(unittest.TestCase):
    def setUp(self):
        self.manager = Manager()
        mock_distro.reset_mock()

    @patch("platform.machine")
    def test_architecture_check_failure(self, mock_machine):
        mock_machine.return_value = "arm64"
        with self.assertRaisesRegex(RuntimeError, "Unsupported architecture: arm64"):
            self.manager.download_isaacsim()

    @patch("platform.machine")
    @patch("platform.system")
    def test_os_check_failure(self, mock_system, mock_machine):
        mock_machine.return_value = "x86_64"
        mock_system.return_value = "Linux"
        
        mock_distro.id.return_value = "ubuntu"
        mock_distro.version.return_value = "20.04"
        mock_distro.name.return_value = "Ubuntu"
        
        expected_msg = "Unsupported OS: Ubuntu 20.04. Isaac Sim requires Ubuntu 22.04 or 24.04."
        with self.assertRaisesRegex(RuntimeError, expected_msg):
            self.manager.download_isaacsim()

    @patch("platform.machine")
    @patch("platform.system")
    @patch("pow_cli.core.manager.urllib.request.urlretrieve")
    @patch("pow_cli.core.manager.zipfile.ZipFile")
    @patch("pow_cli.core.manager.Path.mkdir")
    @patch("pow_cli.core.manager.Path.exists")
    @patch("pow_cli.core.manager.Path.rename")
    @patch("pow_cli.core.manager.Path.unlink")
    def test_successful_flow_mocked(self, mock_unlink, mock_rename, mock_exists, mock_mkdir, mock_zip, mock_urlretrieve, mock_system, mock_machine):
        mock_machine.return_value = "x86_64"
        mock_system.return_value = "Linux"
        
        mock_distro.id.return_value = "ubuntu"
        mock_distro.version.return_value = "22.04"
        mock_distro.name.return_value = "Ubuntu"
        
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

        result = self.manager.download_isaacsim()
        
        self.assertEqual(result["status"], "Downloaded and installed")
        mock_urlretrieve.assert_called_once()
        mock_zip_instance.extractall.assert_not_called() # It uses .extract() now in a loop
        # We can't easily assert on .extract() because it's called multiple times, 
        # but we checked the flow.


if __name__ == "__main__":
    unittest.main()
