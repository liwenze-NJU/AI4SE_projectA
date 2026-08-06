import pytest
from pathlib import Path
from codeguard.tool.file_tools import read_file, list_directory, find_files, search_text

@pytest.fixture
def temp_workspace(tmp_path):
    return tmp_path

def test_read_file_success(temp_workspace):
    f = temp_workspace / "test.txt"
    f.write_text("hello world")
    result = read_file({"path": str(f)}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert "hello world" in result["content"]

def test_read_file_outside_workspace(temp_workspace):
    outside = Path("/tmp") / "secret.txt"
    with pytest.raises(PermissionError, match="outside workspace"):
        read_file({"path": str(outside)}, workspace_root=str(temp_workspace))

def test_read_file_not_found(temp_workspace):
    with pytest.raises(FileNotFoundError):
        read_file({"path": str(temp_workspace / "nonexistent.txt")}, workspace_root=str(temp_workspace))

def test_list_directory(temp_workspace):
    (temp_workspace / "a.txt").write_text("a")
    (temp_workspace / "b.txt").write_text("b")
    result = list_directory({"path": str(temp_workspace)}, workspace_root=str(temp_workspace))
    assert "a.txt" in result["files"]
    assert "b.txt" in result["files"]

def test_find_files(temp_workspace):
    (temp_workspace / "test.py").write_text("")
    result = find_files({"pattern": "**/*.py", "base_dir": str(temp_workspace)}, workspace_root=str(temp_workspace))
    assert "test.py" in result["files"]

def test_search_text(temp_workspace):
    (temp_workspace / "main.py").write_text("def hello(): pass")
    result = search_text({"pattern": "hello", "base_dir": str(temp_workspace)}, workspace_root=str(temp_workspace))
    assert "main.py" in result["matches"]


def test_resolve_path_prefix_bypass(tmp_path):
    """Path traversal via prefix collision: workspace vs workspace-extra."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sibling = tmp_path / "workspace-extra"
    sibling.mkdir()
    (sibling / "secret.txt").write_text("secret")
    # Try to access workspace-extra/secret via ../workspace-extra/secret
    with pytest.raises(PermissionError, match="outside workspace"):
        read_file({"path": "../workspace-extra/secret.txt"}, workspace_root=str(workspace))


# ---------------------------------------------------------------------------
# SPEC §3.6 safety boundaries
# ---------------------------------------------------------------------------

def test_read_file_rejects_oversized(temp_workspace):
    """Files exceeding MAX_FILE_SIZE are rejected."""
    f = temp_workspace / "big.txt"
    f.write_text("x" * 2_000_000)  # 2MB > default 1MB limit
    with pytest.raises(ValueError, match="exceeds size limit"):
        read_file({"path": str(f)}, workspace_root=str(temp_workspace))


def test_read_file_rejects_binary(temp_workspace):
    """Binary files are rejected (null bytes detected)."""
    f = temp_workspace / "data.bin"
    f.write_bytes(b"hello\x00world")
    with pytest.raises(ValueError, match="binary file"):
        read_file({"path": str(f)}, workspace_root=str(temp_workspace))


def test_list_directory_excludes_sensitive_dirs(temp_workspace):
    """.git, .venv, node_modules, __pycache__, build, dist are excluded."""
    (temp_workspace / "src").mkdir()
    (temp_workspace / "src" / "main.py").write_text("")
    (temp_workspace / ".git").mkdir()
    (temp_workspace / ".git" / "config").write_text("")
    (temp_workspace / ".venv").mkdir()
    (temp_workspace / "node_modules").mkdir()
    (temp_workspace / "__pycache__").mkdir()
    (temp_workspace / "build").mkdir()
    (temp_workspace / "dist").mkdir()
    result = list_directory({"path": str(temp_workspace)}, workspace_root=str(temp_workspace))
    names = set(result["files"])
    assert "src" in names
    assert ".git" not in names
    assert ".venv" not in names
    assert "node_modules" not in names
    assert "__pycache__" not in names
    assert "build" not in names
    assert "dist" not in names


def test_list_directory_result_limit(temp_workspace):
    """Result count is capped at MAX_LIST_RESULTS with truncated flag."""
    for i in range(1500):
        (temp_workspace / f"file_{i:04d}.txt").write_text("")
    result = list_directory({"path": str(temp_workspace)}, workspace_root=str(temp_workspace))
    assert len(result["files"]) <= 1000
    assert result["truncated"] is True


def test_find_files_excludes_sensitive_dirs(temp_workspace):
    """find_files skips .git, .venv, node_modules, etc."""
    (temp_workspace / "src").mkdir()
    (temp_workspace / "src" / "main.py").write_text("")
    (temp_workspace / ".git").mkdir()
    (temp_workspace / ".git" / "HEAD").write_text("")
    (temp_workspace / "node_modules").mkdir()
    (temp_workspace / "node_modules" / "lib.js").write_text("")
    result = find_files({"pattern": "**/*", "base_dir": str(temp_workspace)},
                        workspace_root=str(temp_workspace))
    names = set(result["files"])
    assert "src/main.py" in names or "src\\main.py" in names
    assert ".git" not in names and ".git/HEAD" not in names and ".git\\HEAD" not in names
    assert "node_modules" not in names and "node_modules/lib.js" not in names and "node_modules\\lib.js" not in names


def test_search_text_excludes_sensitive_dirs(temp_workspace):
    """search_text skips files inside excluded directories."""
    (temp_workspace / "src").mkdir()
    (temp_workspace / "src" / "main.py").write_text("hello")
    (temp_workspace / ".git").mkdir()
    (temp_workspace / ".git" / "log").write_text("hello")
    result = search_text({"pattern": "hello", "base_dir": str(temp_workspace)},
                         workspace_root=str(temp_workspace))
    assert "src/main.py" in result["matches"] or "src\\main.py" in result["matches"]
    assert ".git/log" not in result["matches"] and ".git\\log" not in result["matches"]


import os as _os

@pytest.mark.skipif(
    not hasattr(_os, "symlink"),
    reason="symlink not available on this platform",
)
def test_symlink_outside_workspace_rejected(tmp_path):
    """Symlink pointing outside workspace is rejected."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    link = workspace / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError as e:
        if getattr(e, "winerror", 0) == 1314:
            pytest.skip("symlink requires elevated privileges on this platform")
        raise
    with pytest.raises(PermissionError, match="outside workspace"):
        read_file({"path": "link.txt"}, workspace_root=str(workspace))