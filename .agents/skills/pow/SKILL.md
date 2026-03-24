---
name: pow
description: Information about the pow CLI architecture and features
---

# Pow CLI Overview

`pow` is the Isaac Powerpack CLI, a tool that manages project initialization and Isaac Sim workflows.

## Architecture

- **Click Framework**: The CLI is built on Click and the commands reside under `packages/pow-cli/pow_cli/cli/`.
- **Core Manager**: The heavy lifting (like Docker inspection, git clones, status callbacks) is handled by the `Manager` class inside `packages/pow-cli/pow_cli/core/manager.py`.
- **Rich UI**: Almost everything in the CLI interface is styled using the `rich` library (progress bars, spinners, colored panels).
- **Target OS**: The CLI is mainly support Ubuntu 22.04 and 24.04

## Implementation Note
- If I specify .pow. It means global folder directory in general that is read by global_dir_name property from `PowConfig` class in `packages/pow-cli/pow_cli/core/models/pow_config.py`
- Use tomllib to read and tomlkit to edit .toml file in python code. do not patch it with regex.
- Always Obtain isaacsim version from PowConfig if any concrete isaacsim version for example 5.1.0 or 5.1 is given.

## Testing

- Run tests against the CLI logic with:
    ```bash
    uv run pytest packages/pow-cli/tests/
    ```
- Do not make test case too tighly couple. Only test for important logics.
