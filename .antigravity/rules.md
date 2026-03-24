# Isaac Powerpack Development Rules

1. **Package Manager**: Use `uv` for all Python dependency management and script running.
2. **Testing**: Run tests with `uv run pytest`. Tests are in `packages/pow-cli/tests/`.
3. **CLI Structure**:
   - `packages/pow-cli/pow_cli/cli/`: Contains click commands.
   - `packages/pow-cli/pow_cli/core/`: Contains core business logic (e.g., `Manager`).
4. **Dependencies**: Custom PyPI indexes (like NVIDIA's) are configured in `pyproject.toml`.
5. **Formatting/Linting**: Use `ruff` for linting and code formatting.
