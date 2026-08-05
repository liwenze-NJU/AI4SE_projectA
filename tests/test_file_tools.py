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