import os
import subprocess
from pathlib import Path

# Shell metacharacters that are never allowed in args
_SHELL_METACHARS = set(";&|`$")


def _validate_args(args: list[str]):
    for i, arg in enumerate(args):
        for char in arg:
            if char in _SHELL_METACHARS:
                raise ValueError(f"Shell metacharacter '{char}' in args[{i}]: {arg[:50]}")


def _validate_cwd(cwd: str, workspace_root: str):
    """Validate cwd is within workspace_root."""
    root = Path(workspace_root).resolve()
    target = Path(cwd).resolve()
    root_str = str(root)
    target_str = str(target)
    if target_str != root_str and not target_str.startswith(root_str + os.sep):
        raise PermissionError(f"cwd '{cwd}' is outside workspace '{workspace_root}'")


def run_process(params: dict, workspace_root: str = "") -> dict:
    program = params["program"]
    args = params.get("args", [])
    timeout = params.get("timeout", 30)
    cwd = params.get("cwd", workspace_root)

    _validate_args(args)
    _validate_cwd(cwd, workspace_root)

    try:
        result = subprocess.run(
            [program] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            shell=False,
        )
        return {
            "status": "SUCCESS",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Process '{program}' timed out after {timeout}s")