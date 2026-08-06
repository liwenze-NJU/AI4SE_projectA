import subprocess

# Shell metacharacters that are never allowed in args
_SHELL_METACHARS = set("&|`$\n\r")

def _validate_args(args: list[str]):
    for i, arg in enumerate(args):
        for char in arg:
            if char in _SHELL_METACHARS:
                raise ValueError(f"Shell metacharacter '{char}' in args[{i}]: {arg[:50]}")

def run_process(params: dict, workspace_root: str = "") -> dict:
    program = params["program"]
    args = params.get("args", [])
    timeout = params.get("timeout", 30)
    cwd = params.get("cwd", workspace_root)

    _validate_args(args)

    try:
        result = subprocess.run(
            [program] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            shell=False
        )
        return {
            "status": "SUCCESS",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Process '{program}' timed out after {timeout}s")