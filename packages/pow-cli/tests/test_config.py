import pytest
try:
    import tomllib
except ImportError:
    import tomli as tomllib
from pathlib import Path
from pow_cli.core.models.pow_config import PowConfig

@pytest.fixture
def reset_config_singleton():
    """Reset the PowConfig singleton before and after tests."""
    PowConfig._instance = None
    yield
    PowConfig._instance = None

def test_singleton(tmp_path, monkeypatch, reset_config_singleton):
    """Test that PowConfig is a singleton."""
    root = tmp_path / "project"
    root.mkdir()
    pow_toml = root / "pow.toml"
    pow_toml.write_text("[sim]\nversion='5.1.0'")
    monkeypatch.chdir(root)
    
    c1 = PowConfig()
    c2 = PowConfig()
    assert c1 is c2

def test_find_project_root(tmp_path, monkeypatch, reset_config_singleton):
    """Test finding the project root with pow.toml using template structure."""
    root = tmp_path / "project"
    root.mkdir()
    pow_toml = root / "pow.toml"
    
    # Matching pow.template.toml structure
    content = """
[sim]
version = "5.1.0"
ext_folders = ["./exts"]
"""
    pow_toml.write_text(content)
    
    subdir = root / "subdir"
    subdir.mkdir()
    
    monkeypatch.chdir(subdir)
    
    config = PowConfig()
    assert config.project_root == root
    assert config.get("version") == "5.1.0"
    assert config.get("ext_folders") == ["./exts"]

def test_config_profile_merging(tmp_path, monkeypatch, reset_config_singleton):
    """Test the profile merging logic."""
    root = tmp_path / "project"
    root.mkdir()
    pow_toml = root / "pow.toml"
    
    # Data by pow.template.toml
    content = """
[sim]
version = "5.1.0"
headless = false
enable_ros = false

[[profiles]]
name = "perf"
headless = true
custom_val = "perf_mode"
"""
    pow_toml.write_text(content)
    monkeypatch.chdir(root)
    
    config = PowConfig()
    
    # 1. Base default profile (maps to 'sim')
    assert config.get("version") == "5.1.0"
    assert config.get("headless") is False
    assert config.get("enable_ros") is False 
    
    # 2. 'perf' profile merges [sim] + 'perf' profile
    # - headless: from 'perf' (True) overrides [sim] (False)
    # - version: from [sim] (5.1.0)
    perf_profile = config.get_profile("perf")
    assert perf_profile["headless"] is True
    assert perf_profile["enable_ros"] is False
    assert perf_profile["version"] == "5.1.0"
    assert perf_profile["custom_val"] == "perf_mode"
    
    # Test through get() helper
    assert config.get("headless", profile="perf") is True
    assert config.get("enable_ros", profile="perf") is False

def test_no_config_found(tmp_path, monkeypatch, reset_config_singleton):
    """Test behavior when no pow.toml is found."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)
    
    config = PowConfig()
    # instantiation should succeed to allow access to global paths
    assert config.global_dir_name == ".pow"

    # but accessing project data should raise the error
    with pytest.raises(RuntimeError, match="Project not initialized: pow.toml not found"):
        _ = config.data

def test_global_dir_name_default(tmp_path, monkeypatch, reset_config_singleton):
    """Test global_dir_name defaults to .pow when no pyproject.toml exists."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)
    config = PowConfig()
    assert config.global_dir_name == ".pow"

def test_global_dir_name_custom(tmp_path, monkeypatch, reset_config_singleton):
    """Test global_dir_name reads from pyproject.toml."""
    root = tmp_path / "project"
    root.mkdir()
    pyproject = root / "pyproject.toml"
    pyproject.write_text('[tool.pow-cli]\nglobal_dir_name = ".custom_pow"')
    monkeypatch.chdir(root)
    config = PowConfig()
    assert config.global_dir_name == ".custom_pow"
