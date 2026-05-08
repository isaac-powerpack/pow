<p align="center">
    <img src="https://raw.githubusercontent.com/bemunin/isaac-powerpack/main/docs/public/logo.svg" width="400"/>
</p>

Isaac Powerpack or Pow in short is a CLI project management tool to simplify Nvidia Isaac Sim application development. 

Key Features:
- ⚡ Simplify isaac sim workstation installation, setup and launching.
- 📁 Provide organized folder structure, ready to get start.
- 📦 Keep your isaac sim projects isolated from each other.
- 🛠️ Allow setup different Profile for isaac sim runtime settings. e.g. launching with different extension and perfomance configuration.
- 🐢 Simple command to build and launch isaac sim ros docker container to work with ROS2
- 🎨 Local assets management and usda linting tools.

For the full list of commands and options, see the [CLI Reference](docs/cli-reference.md).


🚧 This project is in early development. Features and APIs are still evolving and subject to breaking changes.

## Installation

**💡 Notes**: This tool is currently tested and supported on Ubuntu 22.04 and ROS2 humble.


```bash
# installing uv if you don't have it installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# create your project folder
mkdir sim-projects && cd sim-projects

# create pyproject.toml and initialize uv
uv init --bare

# add pow cli package
uv add "pow-cli==0.1.0"

# Initialize project and install isaac sim, setup ros, create config
uv run pow init

# source your workspace
source .venv/bin/activate
```




### Usage

Run Isaac Sim

```bash

# Run Isaac Sim GUI
pow run

# or Run standalone app
pow python path/to/python_standalone_app.py
```

Run ROS 2

```bash
# Bash into the docker container, you can run this command multiple time
# later command will attach to the running container
pow ros
```

## Profiles

After running `pow init`, a `pow.toml` file is generated in your project root. You can define multiple profiles and switch between them:

```bash
pow run -p perf        # Use the "perf" profile
pow run -p default     # Use the default profile (or just `pow run`)
```

Each profile can `extend` another and override specific settings like `cpu_performance_mode`, `headless`, or add extensions with `exts.add`.

```toml
[sim]
version = "5.1.0"
ext_folders = ["./exts"]
cpu_performance_mode = false
headless = false
enable_ros = false
isaacsim_ros_ws = "~/IsaacSim-ros_workspaces"
exts = ["isaacsim.code_editor.vscode"]
raw_args = ["--/renderer/raytracingMotion/enabled=false"]

[[profiles]]
name = "perf"
extends = "default"
cpu_performance_mode = true
# exts.add = ["your.custom.extension"]
```

### Local Assets

The concept of Local assets is to download predefined assets in advanced from Nvidia Omniverse in your local computer in order to build scene in your Isaac Sim application faster (reduce download bottleneck during creating the scene). 

You can mount the asset directory using `pow asset set` command and download provided collection using `pow asset add`. Currently we only support download isaac sim assets only.

For more detail and feature about Local Assets managemet, see `pow asset` command group in [CLI Reference](docs/cli-reference.md).

## Support

| Platform              | Version / Notes              |
| :-------------------- | :--------------------------- |
| OS                    | Ubuntu 22.04                 |
| ROS                   | humble                       |
| Isaac Sim             | `5.1.0`                      |

<br>

## Contribution

See [Contribution Guide](docs/contributing.md)

## License

[Apache-2.0](LICENSE).
