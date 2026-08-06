import pytest
from pathlib import Path
from codeguard.tool.process_tool import run_process


@pytest.fixture
def temp_workspace(tmp_path):
    return tmp_path


def test_run_process_echo(temp_workspace):
    result = run_process({"program": "echo", "args": ["hello"]}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert "hello" in result["stdout"]


def test_run_process_rejects_shell_metacharacters(temp_workspace):
    with pytest.raises(ValueError, match="Shell metacharacter"):
        run_process({"program": "echo", "args": ["hello| rm -rf /"]}, workspace_root=str(temp_workspace))


def test_run_process_timeout(temp_workspace):
    with pytest.raises(TimeoutError):
        run_process({"program": "python", "args": ["-c", "import time\ntime.sleep(10)"], "timeout": 1}, workspace_root=str(temp_workspace))


def test_run_process_cwd(temp_workspace):
    result = run_process({"program": "python", "args": ["-c", "import os\nprint(os.getcwd())"], "cwd": str(temp_workspace)}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert str(temp_workspace) in result["stdout"]


def test_run_process_captures_stderr(temp_workspace):
    result = run_process({"program": "python", "args": ["-c", "import sys\nsys.stderr.write('error')"]}, workspace_root=str(temp_workspace))
    assert "error" in result["stderr"]


def test_run_process_rejects_cwd_outside_workspace(temp_workspace):
    """cwd must be within workspace_root."""
    with pytest.raises(PermissionError, match="outside workspace"):
        run_process({"program": "echo", "args": ["hello"], "cwd": "/tmp"}, workspace_root=str(temp_workspace))


def test_run_process_rejects_semicolon_in_args(temp_workspace):
    """Semicolon is a shell metacharacter and must be rejected."""
    with pytest.raises(ValueError, match="Shell metacharacter"):
        run_process({"program": "echo", "args": ["hello; rm -rf /"]}, workspace_root=str(temp_workspace))