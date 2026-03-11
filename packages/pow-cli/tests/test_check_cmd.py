import pytest
from click.testing import CliRunner

from pow_cli.cli.check import check_cmd


@pytest.mark.cli
class TestCheckCmd:
    @pytest.fixture(autouse=True)
    def setup(self, mocker):
        self.runner = CliRunner()
        self.mock_check = mocker.patch(
            "pow_cli.core.runner.Runner.check_compatibility"
        )

    def _invoke(self):
        return self.runner.invoke(check_cmd, env={"NO_COLOR": "1", "TERM": "dumb"})

    def test_passed_exits_cleanly(self):
        """Passed: checker output was already streamed live; CLI just exits 0."""
        self.mock_check.return_value = {"status": "passed"}
        result = self._invoke()
        assert result.exit_code == 0

    def test_failed_shows_error(self):
        """Failed: CLI must indicate failure."""
        self.mock_check.return_value = {"status": "failed"}
        result = self._invoke()
        assert result.exit_code == 0
        assert "failed" in result.output.lower()

    def test_aborted_shows_message(self):
        """Aborted: CLI must tell the user the check was aborted."""
        self.mock_check.return_value = {"status": "aborted"}
        result = self._invoke()
        assert result.exit_code == 0
        assert "aborted" in result.output.lower()

    def test_not_found_shows_warning(self):
        """Not found: CLI must show the install hint."""
        self.mock_check.return_value = {
            "status": "not_found",
            "message": "isaacsim command not found.",
        }
        result = self._invoke()
        assert result.exit_code == 0
        assert "not found" in result.output.lower()
