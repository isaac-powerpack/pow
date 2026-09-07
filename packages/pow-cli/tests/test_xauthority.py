import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import click
import pytest

from pow_cli.core.ros_manager import RosManager


def authority_path(args):
    return Path(args[1].split("src=", 1)[1].split(",dst=", 1)[0])


@pytest.mark.parametrize("fail", [False, True])
def test_credentials_private_and_cleaned(monkeypatch, mocker, fail):
    monkeypatch.setenv("DISPLAY", ":0")
    run = mocker.patch("subprocess.run", return_value=MagicMock(stdout="0100 0000 cookie\n"))
    try:
        with RosManager._x11_args() as args:
            authority = authority_path(args)
            assert authority.stat().st_mode & 0o777 == 0o600
            assert authority.parent.stat().st_mode & 0o777 == 0o700
            assert "readonly" in args[1]
            assert "XAUTHORITY=/run/pow.Xauthority" in args
            assert any("/tmp/.X11-unix" in arg for arg in args)
            assert run.call_args.kwargs["input"].startswith("ffff")
            if fail:
                raise RuntimeError("docker failed")
    except RuntimeError:
        assert fail
    assert not authority.parent.exists()
    assert all(call.args[0][0] == "xauth" for call in run.call_args_list)


@pytest.mark.parametrize("failure", ["empty", "missing", "failed"])
def test_authentication_failure_blocks_launch(monkeypatch, mocker, failure):
    monkeypatch.setenv("DISPLAY", ":0")
    run = mocker.patch("subprocess.run", return_value=MagicMock(stdout=""))
    if failure == "missing":
        run.side_effect = FileNotFoundError()
    elif failure == "failed":
        run.side_effect = subprocess.CalledProcessError(1, ["xauth"])
    cfg = MagicMock()
    cfg.ros_ws_path = Path("/example/ros")
    cfg.project_root = None
    with pytest.raises(click.ClickException, match="DISPLAY"):
        RosManager._start_new_container(cfg, "image")
    assert all(call.args[0][0] == "xauth" for call in run.call_args_list)


def test_headless_requires_no_credentials(monkeypatch, mocker):
    monkeypatch.delenv("DISPLAY", raising=False)
    run = mocker.patch("subprocess.run")
    with RosManager._x11_args() as args:
        assert args == []
    run.assert_not_called()


def test_attachment_reuses_mount(mocker):
    cfg = MagicMock()
    mocker.patch.object(RosManager, "_load_and_validate_config", return_value=(cfg, "image"))
    mocker.patch.object(RosManager, "_is_container_running", return_value=True)
    attach = mocker.patch.object(RosManager, "_attach_to_container")
    xauth = mocker.patch.object(RosManager, "_x11_args")
    RosManager.run_simros_container()
    attach.assert_called_once()
    xauth.assert_not_called()


def test_launch_mounts_authority_before_image(monkeypatch, mocker):
    monkeypatch.setenv("DISPLAY", ":0")
    cfg = MagicMock()
    cfg.ros_ws_path = Path("/example/ros")
    cfg.project_root = None
    run = mocker.patch("subprocess.run", return_value=MagicMock(stdout="0100 0000 cookie\n"))
    RosManager._start_new_container(cfg, "example-image", ["bash"])
    cmd = run.call_args.args[0]
    assert cmd[:2] == ["docker", "run"]
    assert cmd.index("XAUTHORITY=/run/pow.Xauthority") < cmd.index("example-image")
    assert cmd[-1] == "bash"
    assert not any(call.args[0][0] == "xhost" for call in run.call_args_list)


@pytest.mark.skipif(shutil.which("xauth") is None, reason="host xauth unavailable")
def test_real_xauth_selects_only_current_display(tmp_path, monkeypatch):
    """Exercise xauth against synthetic credentials, never the desktop cookie."""
    source = tmp_path / ".Xauthority"
    source.touch(mode=0o600)
    for display, cookie in [(":91", "11" * 16), (":92", "22" * 16)]:
        subprocess.run(["xauth", "-f", str(source), "add", display,
                        "MIT-MAGIC-COOKIE-1", cookie], check=True, capture_output=True)
    original = source.read_bytes()
    monkeypatch.setenv("XAUTHORITY", str(source))
    monkeypatch.setenv("DISPLAY", ":91")
    with RosManager._x11_args() as args:
        authority = authority_path(args)
        records = subprocess.run(["xauth", "-f", str(authority), "nlist"],
                                 check=True, capture_output=True, text=True).stdout
        assert "11" * 16 in records
        assert "22" * 16 not in records
        assert records.startswith("ffff")
    assert not authority.exists()
    assert source.read_bytes() == original
