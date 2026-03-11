"""Runner core logic."""

import shutil
import subprocess


class Runner:
    """Handles execution of Isaac Sim and related tools."""

    @staticmethod
    def check_compatibility() -> dict:
        """Run the Isaac Sim built-in compatibility check.

        Uses the ``isaacsim`` CLI entry point installed via pip.
        Streams output to the terminal, waits for the process to finish,
        then reports passed/failed based on ``System checking result:``.

        Returns a dict with keys:
            status  – "passed" | "failed" | "aborted" | "not_found"
        """
        isaacsim_cmd = shutil.which("isaacsim")
        if isaacsim_cmd is None:
            return {
                "status": "not_found",
                "message": (
                    "The `isaacsim` command was not found. "
                    'Install it with: uv add "isaacsim[compatibility-check]" --index https://pypi.nvidia.com'
                ),
            }

        try:
            process = subprocess.Popen(
                [isaacsim_cmd, "isaacsim.exp.compatibility_check"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError as e:
            return {"status": "failed", "message": f"Failed to launch compatibility check: {e}"}

        output_lines: list[str] = []
        try:
            for line in process.stdout:
                print(line, end="", flush=True)
                output_lines.append(line)
            process.wait()
        except KeyboardInterrupt:
            process.kill()
            process.wait()
            return {"status": "aborted"}

        full_output = "".join(output_lines)
        if "System checking result: PASSED" in full_output:
            return {"status": "passed"}
        return {"status": "failed"}
