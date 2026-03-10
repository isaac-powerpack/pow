import pytest
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner

from pow_cli.common.utils import get_global_dir_name
from pow_cli.cli.init import init_cmd

@pytest.mark.cli
class TestCliInit:
    def test_get_global_dir_name_default(self, mocker):
        mocker.patch("pathlib.Path.exists", return_value=False)
        assert get_global_dir_name() == ".pow"

    def test_get_global_dir_name_from_toml(self, mocker, tmp_path):
        toml_content = b'[tool.pow-cli]\nglobal_dir_name = ".custom_pow"\n'
        mocker.patch("pathlib.Path.cwd", return_value=tmp_path)
        (tmp_path / "pyproject.toml").write_bytes(toml_content)
        
        assert get_global_dir_name() == ".custom_pow"

    def test_get_global_dir_name_empty_in_toml(self, mocker, tmp_path):
        toml_content = b'[tool.pow-cli]\nglobal_dir_name = ""\n'
        mocker.patch("pathlib.Path.cwd", return_value=tmp_path)
        (tmp_path / "pyproject.toml").write_bytes(toml_content)
        
        assert get_global_dir_name() == ".pow"

    def test_init_cmd_step_1_output(self):
        runner = CliRunner()
        # Mock create_global_folder to avoid side effects
        mock_data = {"global_existed": False, "results": []}
        with patch("pow_cli.core.manager.Manager.create_global_folder", return_value=mock_data):
            with patch("pow_cli.core.manager.Manager.download_isaacsim", return_value={"status": "Already installed", "path": "/tmp/isaacsim"}):
                with patch("time.sleep"):
                    result = runner.invoke(init_cmd, input="n\nn\n", env={"NO_COLOR": "1", "TERM": "dumb"}) 
                assert result.exit_code == 0
                assert "[1/8] 🔧 Config:" in result.output
                assert "Using global directory" in result.output

    def test_init_cmd_missing_pyproject_toml(self):
        runner = CliRunner()
        with patch("pathlib.Path.exists", return_value=False):
            result = runner.invoke(init_cmd, env={"NO_COLOR": "1", "TERM": "dumb"})
            assert "pyproject.toml not found" in result.output
            assert result.exit_code == 0

    def test_init_cmd_accepts_existing_global_folder(self):
        runner = CliRunner()
        # Mock create_global_folder to return 'global_existed=True'
        mock_data = {
            "global_existed": True,
            "results": [{"path": ".pow/isaacsim", "status": "Existed"}]
        }
        with patch("pow_cli.core.manager.Manager.create_global_folder", return_value=mock_data):
            with patch("pow_cli.core.manager.Manager.download_isaacsim", return_value={"status": "Already installed", "path": "/tmp/isaacsim"}):
                with patch("time.sleep"):
                    result = runner.invoke(init_cmd, input="n\nn\n", env={"NO_COLOR": "1", "TERM": "dumb"})
                    assert result.exit_code == 0
                assert "already exists" in result.output

    def test_init_cmd_asset_browser_fix_output(self):
        runner = CliRunner()
        mock_global_data = {"global_existed": True, "results": []}
        # Mock fix_asset_browser_cache to return True (fixed)
        with patch("pow_cli.core.manager.Manager.create_global_folder", return_value=mock_global_data):
            with patch("pow_cli.core.manager.Manager.download_isaacsim", return_value={"status": "Already installed", "path": "/tmp/isaacsim"}):
                with patch("pow_cli.core.manager.Manager.fix_asset_browser_cache", return_value=True):
                    with patch("time.sleep"):
                        result = runner.invoke(init_cmd, input="n\nn\n", env={"NO_COLOR": "1", "TERM": "dumb"})
                        assert "Created missing cache file." in result.output

    def test_init_cmd_asset_browser_already_fixed_output(self):
        runner = CliRunner()
        mock_global_data = {"global_existed": True, "results": []}
        # Mock fix_asset_browser_cache to return False (already exists)
        with patch("pow_cli.core.manager.Manager.create_global_folder", return_value=mock_global_data):
            with patch("pow_cli.core.manager.Manager.download_isaacsim", return_value={"status": "Already installed", "path": "/tmp/isaacsim"}):
                with patch("pow_cli.core.manager.Manager.fix_asset_browser_cache", return_value=False):
                    with patch("time.sleep"):
                        result = runner.invoke(init_cmd, input="n\nn\n", env={"NO_COLOR": "1", "TERM": "dumb"})
                        assert "Cache file already exists." in result.output
