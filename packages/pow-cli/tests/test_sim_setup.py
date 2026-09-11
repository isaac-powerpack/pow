"""Sim commands repair real filesystem prerequisites before invoking Runner."""

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from pow_cli.cli.sim import sim_group
from pow_cli.core.initializer import Initializer
from pow_cli.core.models.pow_config import PowConfig
from pow_cli.core.runner import Runner


def install_scripts(path):
    path.mkdir(parents=True, exist_ok=True)
    for name in ("isaac-sim.sh", "isaac-sim.compatibility_check.sh"):
        (path / name).write_text("#!/bin/sh\n")


@pytest.fixture
def sim_env(tmp_path, monkeypatch, mocker, reset_config_singleton):
    home = tmp_path / "home"
    work = tmp_path / "work"
    home.mkdir()
    work.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(work)
    mocker.patch.object(Initializer, "_check_platform")
    # Keep the real install orchestration, with no network or Isaac Sim runtime.
    download = mocker.patch.object(Initializer, "_download_isaacsim_zip")
    mocker.patch.object(
        Initializer, "_extract_isaacsim_zip",
        side_effect=lambda zip_path, target, *args: install_scripts(target),
    )
    mocker.patch("pow_cli.cli.init.ask_choice", side_effect=AssertionError("unexpected picker"))
    mocker.patch("pow_cli.cli.init.Confirm.ask", side_effect=AssertionError("unexpected prompt"))
    return home, work, download


@pytest.fixture(params=[[], ["launch"], ["check"]], ids=["bare", "launch", "check"])
def command(request, mocker):
    args = request.param
    check = args == ["check"]

    def verify_prerequisites(**kwargs):
        path = PowConfig.version_dir(kwargs["version"])
        assert Initializer.isaacsim_ready(path, check=check)
        assert Initializer.asset_browser_cache_path(path).is_file()
        base = PowConfig.resolve_global_path()
        assert (base / "system.toml").is_file()
        assert all((base / sub).is_dir() for sub in Initializer.GLOBAL_SUBFOLDERS)

    run = mocker.patch.object(Runner, "run_sim", side_effect=verify_prerequisites)
    checker = mocker.patch.object(Runner, "run_sim_check", side_effect=verify_prerequisites)
    return args, checker if check else run, run if check else checker


def invoke(args):
    return CliRunner().invoke(sim_group, args, env={"NO_COLOR": "1", "TERM": "dumb"})


def prepare_ready(base, version=PowConfig.ISAACSIM_VERSION):
    initializer = Initializer(global_path=base)
    initializer.create_global_folder()
    initializer.create_system_toml()
    install = PowConfig.version_dir(version, base)
    install_scripts(install)
    initializer.fix_asset_browser_cache(install)
    return install


def test_first_use_sets_up_then_runs_and_second_use_is_silent(sim_env, command, mocker):
    home, work, download = sim_env
    args, action, other = command
    result = invoke(args + ["--", "--no-window"])
    assert result.exit_code == 0, result.output
    download.assert_called_once()
    action.assert_called_once()
    assert action.call_args.kwargs["extra_args"] == ["--no-window"]
    other.assert_not_called()
    assert not list(work.iterdir())
    assert PowConfig._instance is None

    for name in ("create_global_folder", "create_system_toml", "download_isaacsim", "fix_asset_browser_cache"):
        mocker.patch.object(Initializer, name, side_effect=AssertionError("unexpected setup write"))
    result = invoke(args)
    assert result.exit_code == 0, result.output
    assert result.output == ""
    assert action.call_count == 2


@pytest.mark.parametrize("missing", ["isaacsim", "modules", "projects", "sim-ros", "system.toml", "cache"])
def test_repairs_individual_missing_prerequisites(sim_env, command, missing):
    home, _, download = sim_env
    args, action, _ = command
    base = home / ".pow"
    install = prepare_ready(base)
    target = Initializer.asset_browser_cache_path(install) if missing == "cache" else base / missing
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    result = invoke(args)
    assert result.exit_code == 0, result.output
    action.assert_called_once()
    assert download.call_count == (1 if missing == "isaacsim" else 0)


def test_custom_global_path_ignores_malformed_project_config(sim_env, command):
    home, work, _ = sim_env
    args, action, _ = command
    (work / "pyproject.toml").write_text('[tool.pow-cli]\nglobal_dir_name = ".custom-pow"\n')
    (work / "pow.toml").write_text("[broken config")
    nested = work / "nested"
    nested.mkdir()
    # Exercise the upward pyproject search too.
    with CliRunner().isolated_filesystem(temp_dir=nested):
        result = invoke(args)
    assert result.exit_code == 0, result.output
    action.assert_called_once()
    assert (home / ".custom-pow" / "system.toml").is_file()
    assert not (home / ".pow").exists()
    assert (work / "pow.toml").read_text() == "[broken config"
    assert PowConfig._instance is None


def test_missing_pin_is_installed_and_existing_settings_are_preserved(sim_env, command):
    home, _, download = sim_env
    args, action, _ = command
    base = home / ".pow"
    prepare_ready(base)
    pinned = PowConfig.SUPPORTED_ISAACSIM_VERSIONS[-1]
    config = base / "system.toml"
    content = f'# keep comments\n[sim]\ndefault_version = "{pinned}"\n[custom]\nvalue = 42\n'
    config.write_text(content)

    result = invoke(args)
    assert result.exit_code == 0, result.output
    download.assert_called_once()
    assert action.call_args.kwargs["version"] == pinned
    assert config.read_text() == content


def test_explicit_version_overrides_pin_without_changing_cache(sim_env, command):
    home, _, download = sim_env
    args, action, _ = command
    base = home / ".pow"
    install = prepare_ready(base)
    (base / "system.toml").write_text('[sim]\ndefault_version = "9.9.9"\n')
    cache = Initializer.asset_browser_cache_path(install)
    cache.write_text('{"preserve": true}')

    result = invoke(args + ["-v", PowConfig.ISAACSIM_VERSION])
    assert result.exit_code == 0, result.output
    assert action.call_args.kwargs["version"] == PowConfig.ISAACSIM_VERSION
    assert cache.read_text() == '{"preserve": true}'
    download.assert_not_called()


@pytest.mark.parametrize("installed", [True, False])
def test_unlisted_version_runs_only_if_already_installed(sim_env, command, installed):
    home, _, download = sim_env
    args, action, _ = command
    if installed:
        prepare_ready(home / ".pow", version="9.9.9")
    result = invoke(args + ["-v", "9.9.9"])
    assert result.exit_code == (0 if installed else 1), result.output
    assert action.call_count == int(installed)
    download.assert_not_called()
    if not installed:
        assert "Unsupported Isaac Sim version" in result.output
        assert not (home / ".pow").exists()


@pytest.mark.parametrize("failure", ["create_global_folder", "create_system_toml", "download_isaacsim", "fix_asset_browser_cache", "_check_platform"])
def test_setup_failure_blocks_command(sim_env, command, mocker, failure):
    args, action, other = command
    mocker.patch.object(Initializer, failure, side_effect=RuntimeError("setup failed"))
    result = invoke(args)
    assert result.exit_code == 1
    assert "setup failed" in result.output
    action.assert_not_called()
    other.assert_not_called()


@pytest.mark.parametrize("conflict", ["modules", "system.toml", "cache"])
def test_conflicting_files_are_preserved_and_block_execution(sim_env, command, conflict):
    home, _, download = sim_env
    args, action, _ = command
    base = home / ".pow"
    install = prepare_ready(base)
    path = Initializer.asset_browser_cache_path(install) if conflict == "cache" else base / conflict
    if conflict == "modules":
        path.rmdir()
        path.write_text("user file")
    else:
        path.unlink()
        path.mkdir()
        (path / "user.txt").write_text("user file")

    result = invoke(args)
    assert result.exit_code == 1
    preserved = path if conflict == "modules" else path / "user.txt"
    assert preserved.read_text() == "user file"
    action.assert_not_called()
    download.assert_not_called()


def test_check_repairs_missing_checker_and_keeps_backup(sim_env, mocker):
    home, _, download = sim_env
    base = home / ".pow"
    install = prepare_ready(base)
    (install / "isaac-sim.compatibility_check.sh").unlink()
    (install / "user.txt").write_text("preserve")
    action = mocker.patch.object(Runner, "run_sim_check")

    result = invoke(["check"])
    assert result.exit_code == 0, result.output
    action.assert_called_once()
    download.assert_called_once()
    assert Initializer.isaacsim_ready(install, check=True)
    backups = list((base / "isaacsim-backups").glob("*/*/user.txt"))
    assert len(backups) == 1 and backups[0].read_text() == "preserve"
    assert "Previous installation preserved" in result.output
    assert PowConfig.installed_versions(base) == [PowConfig.ISAACSIM_VERSION]


@pytest.mark.parametrize("args", [["--help"], ["launch", "--help"], ["check", "--help"]])
def test_help_has_no_setup_side_effects(sim_env, args, mocker):
    home, work, download = sim_env
    scan = mocker.patch.object(PowConfig, "resolve_installed_version", side_effect=AssertionError("scan"))
    result = invoke(args)
    assert result.exit_code == 0, result.output
    assert not list(home.iterdir()) and not list(work.iterdir())
    download.assert_not_called()
    scan.assert_not_called()
