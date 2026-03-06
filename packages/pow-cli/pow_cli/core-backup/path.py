from pathlib import Path


def get_isaacsim_path() -> Path | None:
    """Get the installation path of Isaac Sim."""
    try:
        import isaacsim
        return Path(isaacsim.__file__).parent
    except ImportError:
        return None
