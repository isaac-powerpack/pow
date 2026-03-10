import sys
import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# Add the package to sys.path
sys.path.append("/home/bemunin/Projects/pow/packages/pow-cli")

# Mock lsb_release at the module level for the entire test session
mock_lsb = MagicMock()
sys.modules["lsb_release"] = mock_lsb

from pow_cli.core.manager import Manager

class TestIsaacSimDownload(unittest.TestCase):
    def setUp(self):
        self.manager = Manager()
        mock_lsb.reset_mock()

    @patch("platform.machine")
    def test_architecture_check_failure(self, mock_machine):
        mock_machine.return_value = "arm64"
        with self.assertRaisesRegex(RuntimeError, "Unsupported architecture: arm64"):
            self.manager.download_isaacsim()

    @patch("platform.machine")
    @patch("builtins.open", new_callable=mock_open, read_data='ID=ubuntu\nVERSION_ID="20.04"\n')
    def test_os_check_failure(self, mock_file, mock_machine):
        mock_machine.return_value = "x86_64"
        # Force lsb_release to fail so it falls back to /etc/os-release
        mock_lsb.get_distro_information.side_effect = Exception("lsb_release failed")
        
        with self.assertRaisesRegex(RuntimeError, "Unsupported OS: ubuntu 20.04"):
            self.manager.download_isaacsim()

    @patch("platform.machine")
    @patch("pow_cli.core.manager.urllib.request.urlretrieve")
    @patch("pow_cli.core.manager.zipfile.ZipFile")
    @patch("pow_cli.core.manager.Path.mkdir")
    @patch("pow_cli.core.manager.Path.exists")
    @patch("pow_cli.core.manager.Path.rename")
    @patch("pow_cli.core.manager.Path.unlink")
    def test_successful_flow_mocked(self, mock_unlink, mock_rename, mock_exists, mock_mkdir, mock_zip, mock_urlretrieve, mock_machine):
        mock_machine.return_value = "x86_64"
        mock_lsb.get_distro_information.side_effect = None
        mock_lsb.get_distro_information.return_value = {"ID": "Ubuntu", "RELEASE": "22.04"}
        
        # Robust exists side effect using captured arguments
        def exists_side_effect(*args, **kwargs):
            if not args:
                return False
            path_obj = args[0]
            path_str = str(path_obj)
            print(f"DEBUG: Checking exists for {path_str}")
            
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
        mock_zip_instance.extractall.assert_called_once()
        mock_rename.assert_called_once()

if __name__ == "__main__":
    unittest.main()
