"""ROS-related core logic.

Centralises ROS workspace setup, Docker image building, environment
sourcing, and container launching that was previously spread across
Initializer and Runner.
"""

import os
import shlex
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

import click
from rich.console import Console

from .models.pow_config import PowConfig

console = Console()


class RosManager:
    """Manages all ROS-related operations for Isaac Powerpack."""

    def __init__(self, config: PowConfig | None = None):
        self._config = config or PowConfig()

    @property
    def config(self) -> PowConfig:
        return self._config

    # ── Environment preparation ──────────────────────────────────────────────

    @staticmethod
    def isaacsim_bridge_env(config: PowConfig, profile: str = "default") -> dict[str, str]:
        """Env for launching Isaac Sim with its internal ROS2 bridge libs.

        Clears host ROS environment that conflicts with Isaac Sim's bundled
        Python, then points ``LD_LIBRARY_PATH`` at the prebuilt bridge libs
        shipped in ``exts/isaacsim.ros2.core|bridge/<distro>/lib``. The bridge
        distro is read from ``ros_bridge`` in pow.toml (default
        ``jazzy``), resolved for the given *profile*.

        ``RMW_IMPLEMENTATION`` is inherited from the host environment when set,
        falling back to ``rmw_fastrtps_cpp`` so the RMW picked here matches the
        one used by ROS 2 nodes running outside Isaac Sim.
        """
        isaacsim_version = config.get("version", PowConfig.ISAACSIM_VERSION)
        isaacsim_dir = PowConfig.version_dir(isaacsim_version, config.global_path)
        bridge_distro = config.get_ros_bridge(profile)
        return RosManager.bridge_env(isaacsim_dir, bridge_distro)

    #: Extensions that ship the prebuilt ROS 2 libraries, newest naming first.
    #: Isaac Sim 6.0 renamed ``isaacsim.ros2.bridge`` to ``isaacsim.ros2.core``;
    #: probing both keeps a single code path working across releases.
    _ROS2_LIB_EXTS = ("isaacsim.ros2.core", "isaacsim.ros2.bridge")

    @staticmethod
    def _find_bridge_lib(isaacsim_dir: Path, bridge_distro: str) -> Path:
        """Locate the bundled ROS 2 library directory for *bridge_distro*."""
        candidates = [
            isaacsim_dir / "exts" / ext / bridge_distro / "lib"
            for ext in RosManager._ROS2_LIB_EXTS
        ]
        for candidate in candidates:
            if candidate.is_dir():
                return candidate

        listed = "\n".join(f"  - {c}" for c in candidates)
        raise click.ClickException(
            f"Isaac Sim ROS2 libs for '{bridge_distro}' not found. Looked in:\n"
            f"{listed}\n"
            "Run `pow init` to install Isaac Sim first."
        )

    @staticmethod
    def bridge_env(isaacsim_dir: Path, bridge_distro: str) -> dict[str, str]:
        """Config-free variant of :meth:`isaacsim_bridge_env`.

        Takes the resolved Isaac Sim install directory and bridge distro
        directly, so callers that must not read pow.toml (``pow sim``) can build
        the same environment.
        """
        env = os.environ.copy()

        for var in (
            "ROS_VERSION",
            "ROS_PYTHON_VERSION",
            "ROS_DISTRO",
            "AMENT_PREFIX_PATH",
            "COLCON_PREFIX_PATH",
            "PYTHONPATH",
            "CMAKE_PREFIX_PATH",
        ):
            env.pop(var, None)

        # Strip system ROS installs from LD_LIBRARY_PATH
        ld_parts = [
            p for p in env.get("LD_LIBRARY_PATH", "").split(":")
            if p and not p.startswith("/opt/ros/")
        ]

        bridge_lib = RosManager._find_bridge_lib(isaacsim_dir, bridge_distro)

        ld_parts.append(str(bridge_lib))
        env["LD_LIBRARY_PATH"] = ":".join(ld_parts)
        env["ROS_DISTRO"] = bridge_distro
        # Inherit the host's RMW when set; default to Fast DDS otherwise.
        env.setdefault("RMW_IMPLEMENTATION", "rmw_fastrtps_cpp")
        return env

    # ── Workspace setup (from Initializer) ───────────────────────────────────

    def setup_ros_workspace(
        self,
        status_callback=None,
        ws_path: "Path | None" = None,
        sim_version: str | None = None,
    ) -> dict:
        """Setup ROS workspace for Isaac Sim project.

        Args:
            ws_path: Explicit workspace path override.  When ``None`` the
                     path is read from ``self.config.ros_ws_path`` (i.e.
                     the ``isaacsim_ros_ws`` key in pow.toml).
            sim_version: Isaac Sim version whose matching workspace ref should
                     be cloned.  ``pow init`` passes this explicitly because
                     pow.toml may not exist yet.
        """
        ros_distro = self.config.ros_distro
        ubuntu_version = self.config.ubuntu_version
        clone_path = ws_path or self.config.ros_ws_path
        if sim_version is None:
            try:
                sim_version = self.config.get("version", PowConfig.ISAACSIM_VERSION)
            except RuntimeError:  # no pow.toml yet
                sim_version = PowConfig.ISAACSIM_VERSION
        ws_ref = PowConfig.release(sim_version)["ros_ws_ref"]

        # Clone workspace if not already cloned
        if not (clone_path / ".git").exists():
            if status_callback:
                status_callback("cloning")
            subprocess.run(
                [
                    "git", "clone", "-b", ws_ref, "--quiet",
                    "https://github.com/isaac-sim/IsaacSim-ros_workspaces.git",
                    str(clone_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            if status_callback:
                status_callback("existed")

        return {
            "status": "success",
            "ros_distro": ros_distro,
            "ubuntu_version": ubuntu_version,
            "path": str(clone_path),
            "ws_ref": ws_ref,
        }

    @staticmethod
    def _detect_cuda_version() -> str | None:
        """Detect the host CUDA version from nvidia-smi.

        Returns the version string (e.g. ``"12.8"``) or ``None`` if
        ``nvidia-smi`` is not available or the version cannot be parsed.
        """
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "CUDA Version" in line:
                        # Line looks like: "| ... CUDA Version: 12.8  |"
                        parts = line.split("CUDA Version:")
                        if len(parts) > 1:
                            return parts[1].strip().rstrip("|").strip()
        except FileNotFoundError:
            pass
        return None

    def build_simros_image(self, status_callback=None, ws_path: "Path | None" = None) -> dict:
        """Build pow_simros_<distro> Docker image using Dockerfile.simros_<distro>.

        Skips the build if the image already exists locally.

        Args:
            ws_path: Explicit workspace path override.  When ``None`` the
                     path is read from ``self.config.ros_ws_path``.
        """
        ros_ws = ws_path or self.config.ros_ws_path
        ros_distro = self.config.ros_distro
        docker_image = f"pow_simros_{ros_distro}"
        distro_ws = ros_ws / f"{ros_distro}_ws"
        dockerfile_path = Path(__file__).parent.parent / "docker" / f"Dockerfile.simros_{ros_distro}"

        # Check if image already exists
        if RosManager.image_exists(docker_image):
            if status_callback:
                status_callback("simros_built")
            return {"status": "existed", "image": docker_image}

        if status_callback:
            status_callback("simros_building")

        # Detect host CUDA version for PyTorch wheel selection
        # Fix CUDA version to 12.1 for pytorch compatibility both ubuntu 22.04 and 24.04 nvidia drivers
        cuda_version = "12.1" 
        console.print(f"[dim]Using  CUDA version:[/dim] [cyan]{cuda_version or 'None'}[/cyan]")

        build_cmd = [
            "docker", "build",
            "-f", str(dockerfile_path),
            "-t", docker_image,
            "--build-context", f"ros_ws={distro_ws}",
        ]

        if cuda_version:
            build_cmd.extend(["--build-arg", f"CUDA_VERSION={cuda_version}"])
            if status_callback:
                status_callback(f"simros_building:Using host CUDA {cuda_version} for PyTorch")

        build_cmd.append(".")

        process = subprocess.Popen(
            build_cmd,
            cwd=str(ros_ws),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        output_lines: list[str] = []
        for line in process.stdout:
            stripped = line.strip()
            if stripped:
                output_lines.append(stripped)
                if status_callback:
                    status_callback(f"simros_building:{stripped}")
        process.wait()

        if process.returncode != 0:
            tail = "\n".join(output_lines[-30:])
            raise RuntimeError(
                f"Docker build for {docker_image} failed with exit code {process.returncode}\n"
                f"--- Last lines of build output ---\n{tail}"
            )

        return {"status": "built", "image": docker_image}

    def build_custom_ros_image(self, status_callback=None, no_cache: bool = False) -> dict:
        """Build a custom ROS image layered on top of ``pow_simros_<distro>``.

        Builds the Dockerfile referenced by ``ros_dockerfile`` in pow.toml,
        tagging the result with ``ros_docker_image``.  The custom Dockerfile is
        expected to start with ``FROM pow_simros_<distro>`` so it inherits the
        base image's WORKDIR and entrypoint.

        Returns ``{"status": "skipped"}`` when ``ros_dockerfile`` is empty.
        The build always runs (Docker layer caching keeps unchanged builds fast)
        so edits to the custom Dockerfile take effect on rebuild.  Pass
        ``no_cache=True`` to bypass the layer cache entirely.
        """
        ros_dockerfile = self.config.ros_dockerfile
        if not ros_dockerfile:
            return {"status": "skipped"}

        project_root = self.config.project_root
        if project_root is None:
            raise RuntimeError("Not initialized: pow.toml not found.")

        dockerfile_path = project_root / ros_dockerfile
        if not dockerfile_path.exists():
            raise RuntimeError(
                f"Custom ROS Dockerfile not found: {dockerfile_path}\n"
                f"Check the 'ros_dockerfile' path in pow.toml."
            )

        image = self.config.ros_docker_image

        if status_callback:
            status_callback("custom_building")

        build_cmd = [
            "docker", "build",
            "-f", str(dockerfile_path),
            "-t", image,
        ]
        if no_cache:
            build_cmd.append("--no-cache")
        build_cmd.append(str(project_root))

        process = subprocess.Popen(
            build_cmd,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        output_lines: list[str] = []
        for line in process.stdout:
            stripped = line.strip()
            if stripped:
                output_lines.append(stripped)
                if status_callback:
                    status_callback(f"custom_building:{stripped}")
        process.wait()

        if process.returncode != 0:
            tail = "\n".join(output_lines[-30:])
            raise RuntimeError(
                f"Docker build for custom image '{image}' failed with exit code "
                f"{process.returncode}\n"
                f"--- Last lines of build output ---\n{tail}"
            )

        return {"status": "built", "image": image}

    @staticmethod
    def image_exists(image: str) -> bool:
        """Check whether a docker image exists locally.

        Appends ``:latest`` only when the reference carries no explicit tag.
        """
        ref = image if ":" in image.rsplit("/", 1)[-1] else f"{image}:latest"
        result = subprocess.run(
            ["docker", "image", "inspect", ref],
            capture_output=True,
        )
        return result.returncode == 0

    # ── Container launching (from Runner) ────────────────────────────────────

    @staticmethod
    def _load_and_validate_config() -> tuple[PowConfig, str]:
        """Load config and return (config, docker_image) or raise."""
        config = PowConfig()
        if config.project_root is None:
            raise click.ClickException("Not initialized. Run `pow init` first.")

        enable_ros = config.get("enable_ros", False)
        if not enable_ros:
            raise click.ClickException(
                "ROS integration is disabled in pow.toml.\n"
                "Set 'enable_ros = true' under [sim] and re-run 'pow init' to enable it."
            )

        docker_image = config.ros_image_name

        if not RosManager.image_exists(docker_image):
            raise click.ClickException(
                f"Docker image '{docker_image}' not found.\n"
                "Run 'pow ros build' (or 'pow init') to build it."
            )

        return config, docker_image

    @staticmethod
    @contextmanager
    def _x11_args():
        """Share the current display cookie without changing host access control.

        xauth honors the host XAUTHORITY (or ~/.Xauthority). Only the selected
        display's records are copied, and the private copy is mounted read-only.
        Docker retains its bind mount if the client detaches before container exit.
        """
        display = os.environ.get("DISPLAY")
        if not display:
            yield []
            return
        with tempfile.TemporaryDirectory(prefix="pow-xauth-") as directory:
            authority = Path(directory) / ".Xauthority"
            authority.touch(mode=0o600)
            try:
                result = subprocess.run(
                    ["xauth", "nlist", display], check=True, capture_output=True, text=True,
                )
                records = result.stdout.splitlines()
                if not records or any(len(row) < 4 for row in records):
                    raise click.ClickException(
                        "No X11 credentials for DISPLAY. Run from your desktop session "
                        "with a valid XAUTHORITY, or unset DISPLAY for a headless launch."
                    )
                # FamilyWild makes the selected cookie usable with the container hostname.
                data = "\n".join("ffff" + row[4:] for row in records) + "\n"
                subprocess.run(
                    ["xauth", "-f", str(authority), "nmerge", "-"],
                    input=data, text=True, check=True, capture_output=True,
                )
            except (FileNotFoundError, subprocess.CalledProcessError):
                raise click.ClickException(
                    "Could not prepare X11 authentication. Install xauth and check "
                    "DISPLAY/XAUTHORITY, or unset DISPLAY for a headless launch."
                ) from None
            authority.chmod(0o600)
            args = [
                "--mount", f"type=bind,src={authority},dst=/run/pow.Xauthority,readonly",
                "--env", "XAUTHORITY=/run/pow.Xauthority",
            ]
            if display.startswith((":", "unix:")):
                args.extend([
                    "--mount", "type=bind,src=/tmp/.X11-unix,dst=/tmp/.X11-unix,readonly",
                ])
            yield args

    @staticmethod
    def _is_container_running(container_name: str) -> bool:
        """Return True if the named container is currently running."""
        result = subprocess.run(
            ["docker", "container", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    @staticmethod
    def _attach_to_container(
        container_name: str,
        docker_image: str,
        extra_args: list[str] | None = None,
        verbose: bool = False,
    ) -> None:
        """Attach to an already-running container via ``docker exec``."""
        exec_cmd: list[str] = ["docker", "exec", "-it", container_name]
        exec_cmd.extend(["/ros_config/entrypoint.sh"] + (extra_args or ["/bin/bash"]))

        console.print(f"[dim]Starting container from image:[/dim] [cyan]{docker_image}[/cyan]")
        console.print(f"[green]Container '{container_name}' is already running. Attaching...[/green]")
        
        if verbose:
            console.print(f"[blue]Running: {' '.join(shlex.quote(c) for c in exec_cmd)}[/blue]")

        try:
            subprocess.run(exec_cmd, check=True, env=os.environ)
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"Docker exec exited with code {e.returncode}")
        except KeyboardInterrupt:
            if verbose:
                console.print("[yellow]Detached from container.[/yellow]")

    @staticmethod
    def _start_new_container(
        config: PowConfig,
        docker_image: str,
        extra_args: list[str] | None = None,
        verbose: bool = False,
    ) -> None:
        """Create and start a new ``pow_simros`` container."""
        ros_distro = config.ros_distro
        ros_ws_path = config.ros_ws_path
        distro_ws = ros_ws_path / f"{ros_distro}_ws"
        container_name = config.ros_container_name

        uid = os.getuid()
        gid = os.getgid()

        host_home = os.path.expanduser("~")
        ros_config_dir = os.path.join(host_home, ".ros")

        cmd = [
            "docker", "run", "-it", "--rm", "--net=host",
            "--env", f"HOST_UID={uid}",
            "--env", f"HOST_GID={gid}",
            "--env", "DISPLAY",
            "--env", "ROS_DOMAIN_ID",
            "-v", f"{distro_ws}:/{ros_distro}_ws",
        ]

        if os.path.exists(ros_config_dir):
            cmd.extend(["-v", f"{ros_config_dir}:/home/hostuser/.ros"])

        # Mount project scripts folder into the container
        if config.project_root:
            scripts_dir = config.project_root / "scripts"
            if scripts_dir.exists():
                cmd.extend(["-v", f"{scripts_dir}:/home/hostuser/scripts"])

        cmd.extend(["--name", container_name, docker_image])
        cmd.extend(extra_args or ["/bin/bash"])

        console.print(f"[dim]Starting container from image:[/dim] [cyan]{docker_image}[/cyan]")
        if verbose:
            console.print(f"[blue]Running: {' '.join(shlex.quote(c) for c in cmd)}[/blue]")

        try:
            with RosManager._x11_args() as x11_args:
                # Authenticate before modifying an existing container.
                subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
                subprocess.run(cmd[:2] + x11_args + cmd[2:], check=True, env=os.environ)
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"Docker container exited with code {e.returncode}")
        except KeyboardInterrupt:
            if verbose:
                console.print("[yellow]Container stopped by user.[/yellow]")

    @staticmethod
    def run_simros_container(
        extra_args: list[str] | None = None,
        verbose: bool = False,
    ) -> None:
        """Launch the pow_simros Docker container.

        Reads ``enable_ros`` and ``ros_distro`` from pow.toml.
        If ROS is disabled the user is told how to enable it.

        Args:
            extra_args: Additional arguments forwarded to the container command.
            verbose: When True, print status feedback to the console.
        """
        config, docker_image = RosManager._load_and_validate_config()

        container_name = config.ros_container_name

        if RosManager._is_container_running(container_name):
            RosManager._attach_to_container(container_name, docker_image, extra_args, verbose=verbose)
        else:
            RosManager._start_new_container(config, docker_image, extra_args, verbose=verbose)
