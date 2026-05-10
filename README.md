<p align="center">
    <img src="https://raw.githubusercontent.com/bemunin/isaac-powerpack/main/docs/public/logo.svg" width="400"/>
</p>

Isaac Powerpack (or Pow) is a project management tool to simplify Nvidia Isaac Sim application development.

Key Features:
- ⚡ CLI to Simplify isaac sim workstation installation, setup and launching.
- 📁 Provide organized folder structure, ready to get start.
- 📦 Keep your isaac sim projects isolated from each other.
- 🛠️ Allow setup different Profile for isaac sim runtime settings. e.g. launching with different extension and perfomance configuration.
- 🐢 Simple command to build and launch isaac sim ros docker container to work with ROS2
- 🎨 Local assets management and usda linting tools.

For the full list of ready-to-use commands and options, see the [CLI Reference](docs/cli-reference.md).

> [!IMPORTANT]
> This project is in early development. Features and APIs are still evolving and subject to breaking changes. Some features may not be fully implemented yet. Please check the [changelog](packages/pow-cli/CHANGELOG.md) for the latest updates.

## Installation

Pow CLI required `uv` python package manager and `docker` to run ros container. Follow this installation guide to get them installed.
- [uv Installation Guide](https://docs.astral.sh/uv/)
- [Docker Installation Guide](https://docs.docker.com/get-docker/)

Setup your project

```bash
# create your project folder
mkdir sim-project && cd sim-project

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

Run ROS 2 container

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

Each profile can extend another and override specific settings like `cpu_performance_mode`, `headless`, or use `add` keyword to extends the list e.g. `exts.add`. 


In example below, you can define a "perf" profile that enables CPU performance mode and use `raw_args.add` to extends raw_args. Setting key without `.add` will override the value such as `exts` in this case.

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
exts = ["your.custom.extension"]
raw_args.add=[ 
    # Enable framegen 2x
    "--/rtx-transient/dlssg/enabled=true",
    "--/rtx-transient/internal/dlssg/interpolatedFrameCount=1",
    # Disable rtx features for performance
    "--/rtx/reflections/enabled=false",
    "--/rtx/translucency/enabled=false"
]
```

For the full settings reference, profile inheritance, and examples, see the [Configuration Guide](docs/configuration.md).

### Local Assets

The concept of Local assets is to download predefined assets in advanced from Nvidia Omniverse in your local computer in order to build scene in your Isaac Sim application faster (reduce download bottleneck during creating the scene). 

You can mount the asset directory using `pow asset set` command and download provided collection using `pow asset add`. Currently we only support download isaac sim assets only.

For more detail and feature about Local Assets managemet, see `pow asset` command group in [CLI Reference](docs/cli-reference.md).

### Folder Structure

After running `pow init`, your project will have the following structure:

```
sim-project/
├── .vscode/              # VSCode configuration (launch.json, settings.json, etc.)
├── .modules/             # 3rd party module that use in your project e.g. pegasus sim
├── .assets/              # 3D assets or any assets you use only in your project
├── exts/                 # Your custom Isaac Sim extensions
├── scripts/              # Isaacsim Helper scripts to execute via vscode
├── standalone/           # Standalone Python applications
├── usda/                 # USD scene description files
├── _isaacsim/            # Symlink → ~/.pow/isaacsim/5.1.0 for intellisense and autocomplete
├── .gitignore            # Pre-configured gitignore for Isaac Sim projects
├── pow.toml              # Project configuration (sim settings, profiles)
└── pyproject.toml        # Python project manifest
```

`pow init` also creates a **global directory** at `~/.pow` (shared across all projects):

```
~/.pow/
├── isaacsim/             # Downloaded Isaac Sim installations
│   └── 5.1.0/            # Isaac Sim 5.1.0 app files
├── modules/              # Shared modules
├── assets/               # mounting folder for local assets
└── system.toml           # Global system configuration
```


## Support

| Platform              | Version / Notes              |
| :-------------------- | :--------------------------- |
| OS                    | Ubuntu 22.04 / 24.04         |
| ROS2                  | Humble / Jazzy               |
| Isaac Sim             | `5.1.0`                      |

> [!NOTE]
> Pow is mainly developed and tested on Ubuntu 22.04 and ROS2 Humble environment.  

<br>    

## Contribution

See [Contribution Guide](docs/contributing.md)

## License

[Apache-2.0](LICENSE).
