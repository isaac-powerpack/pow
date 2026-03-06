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
        # Mock time.sleep to speed up tests
        with patch("time.sleep"):
            # We pass 'n' and 'n' to avoid proceeding past conflicts and ROS integration, just to test step 1
            result = runner.invoke(init_cmd, input="n\nn\n", env={"NO_COLOR": "1", "TERM": "dumb"}) 
            assert result.exit_code == 0
            assert "[1/8] 🔧 Config:" in result.output
            assert "Using global directory" in result.output
