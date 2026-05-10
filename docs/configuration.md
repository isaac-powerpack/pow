# Configuration

After running `pow init`, a `pow.toml` file is generated in your project root. This file controls how Isaac Sim is launched, which extensions are loaded, and how profiles customize runtime behavior.

## Default Configuration

The `[sim]` section defines the base (default) settings used by `pow run`:

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
```

### Settings Reference

| Key                    | Type       | Default                              | Description |
|:-----------------------|:-----------|:-------------------------------------|:------------|
| `version`              | `string`   | `"5.1.0"`                            | Isaac Sim version to use. |
| `ext_folders`          | `string[]` | `["./exts"]`                         | Directories to search for custom extensions. |
| `cpu_performance_mode` | `bool`     | `false`                              | Enable CPU performance governor via `cpupower` (requires `sudo`). |
| `headless`             | `bool`     | `false`                              | Run Isaac Sim without the GUI window. |
| `enable_ros`           | `bool`     | `false`                              | Source the ROS 2 workspace environment before launching. |
| `isaacsim_ros_ws`      | `string`   | `"~/IsaacSim-ros_workspaces"`        | Path to the cloned IsaacSim-ros_workspaces directory. |
| `exts`                 | `string[]` | `["isaacsim.code_editor.vscode"]`    | Extensions to enable on launch. |
| `raw_args`             | `string[]` | `["--/renderer/raytracingMotion/enabled=false"]` | Extra CLI arguments passed directly to Isaac Sim. |

---

## Profiles

Profiles let you define named sets of overrides that you can switch between at runtime:

```bash
pow run                  # Uses the default [sim] settings
pow run -p perf          # Uses the "perf" profile
pow run -p my_profile    # Uses a custom profile you defined
```

### Defining a Profile

Add a `[[profiles]]` entry in `pow.toml`. Each profile requires a `name` and can optionally `extends` another profile:

```toml
[[profiles]]
name = "perf"
extends = "default"
cpu_performance_mode = true
headless = false
```

- **`name`** — The identifier you pass to `pow run -p <name>`.
- **`extends`** — Which profile to inherit settings from. Use `"default"` (or omit) to inherit from `[sim]`. You can also point to another profile name for multi-level inheritance.

### Override vs Append

There are two ways a profile can modify list values from its base:

#### Override (replace the entire list)

Assigning a key directly **replaces** the base value completely:

```toml
[[profiles]]
name = "minimal"
extends = "default"
# This REPLACES the default exts list entirely
exts = ["your.custom.extension"]
```

#### Append (extend the base list)

Using the `.add` suffix **appends** items to the inherited list:

```toml
[[profiles]]
name = "perf"
extends = "default"
# This APPENDS to the default raw_args list
raw_args.add = [
    "--/rtx-transient/dlssg/enabled=true",
    "--/rtx/reflections/enabled=false",
]
```

The `.add` keyword works with any list-type setting (`exts`, `raw_args`, `ext_folders`, etc.).

> [!NOTE]
> The `.add` suffix only works with list values. Using it on a non-list setting (e.g., `headless.add`) will produce an error.

### Profile Inheritance Chain

Profiles can extend other profiles, not just `"default"`:

```toml
[sim]
exts = ["isaacsim.code_editor.vscode"]
raw_args = ["--/renderer/raytracingMotion/enabled=false"]

[[profiles]]
name = "perf"
extends = "default"
cpu_performance_mode = true

[[profiles]]
name = "perf-headless"
extends = "perf"
headless = true
```

In this example:
- `pow run -p perf` → inherits `[sim]` + enables `cpu_performance_mode`
- `pow run -p perf-headless` → inherits `perf` (which inherits `[sim]`) + enables `headless`

> [!WARNING]
> Circular inheritance (e.g., profile A extends B, B extends A) is detected and will produce an error.

---

## Full Example

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
# Override exts entirely
exts = ["your.custom.extension"]
# Append additional raw_args
raw_args.add = [
    # Enable framegen 2x
    "--/rtx-transient/dlssg/enabled=true",
    "--/rtx-transient/internal/dlssg/interpolatedFrameCount=1",
    # Disable rtx features for performance
    "--/rtx/reflections/enabled=false",
    "--/rtx/translucency/enabled=false",
]

[[profiles]]
name = "headless"
extends = "default"
headless = true
```
