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
        with patch("pow_cli.core.manager.Manager.create_global_folder", return_value=[]):
            with patch("time.sleep"):
                result = runner.invoke(init_cmd, input="n\nn\n", env={"NO_COLOR": "1", "TERM": "dumb"}) 
                assert result.exit_code == 0
                assert "[1/8] 🔧 Config:" in result.output
                assert "Using global directory" in result.output

    def test_init_cmd_rejects_existing_global_folder(self):
        runner = CliRunner()
        # Mock create_global_folder to raise FileExistsError
        with patch("pow_cli.core.manager.Manager.create_global_folder", 
                   side_effect=FileExistsError("Global directory '/mock/path' already exists.")):
            result = runner.invoke(init_cmd, env={"NO_COLOR": "1", "TERM": "dumb"})
            assert "Error: Global directory" in result.output
            assert "already exists" in result.output
            assert "Initialization aborted" in result.output
