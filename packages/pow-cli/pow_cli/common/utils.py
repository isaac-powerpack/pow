"""Common utilities and shared objects."""

import shutil
from rich.console import Console

console = Console(width=70)
# console.clear()


def get_terminal_width(max_width=80) -> int:
    """Get the current terminal width."""
    if max_width:
        return min(shutil.get_terminal_size(fallback=(80, 24)).columns, max_width)
        
    return shutil.get_terminal_size(fallback=(80, 24)).columns