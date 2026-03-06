"""Isaac Powerpack CLI - Root entry point."""

from .cli.main import pow_group

def main():
    """Main entry point for the CLI."""
    pow_group()

if __name__ == "__main__":
    main()
