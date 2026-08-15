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


def test_read_file_rejects_excluded_dir(temp_workspace):
    """read_file rejects files inside excluded directories (.git etc.)."""
    (temp_workspace / ".git").mkdir()
    (temp_workspace / ".git" / "config").write_text("repo config")
    with pytest.raises(PermissionError, match="excluded directory"):
        read_file({"path": ".git/config"}, workspace_root=str(temp_workspace))


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


# ---------------------------------------------------------------------------
# Sensitive file blocking (.env, *.key, *.pem)
# ---------------------------------------------------------------------------

def test_read_file_rejects_sensitive_file(temp_workspace):
    """read_file rejects .env, *.key, *.pem files."""
    for name in [".env", "secret.key", "cert.pem"]:
        f = temp_workspace / name
        f.write_text("sensitive content")
        with pytest.raises(PermissionError, match="sensitive file"):
            read_file({"path": name}, workspace_root=str(temp_workspace))


def test_list_directory_hides_sensitive_files(temp_workspace):
    """list_directory does not expose .env, *.key, *.pem."""
    (temp_workspace / "main.py").write_text("ok")
    (temp_workspace / ".env").write_text("SECRET=1")
    (temp_workspace / "db.key").write_text("keydata")
    (temp_workspace / "cert.pem").write_text("certdata")
    result = list_directory({"path": str(temp_workspace)}, workspace_root=str(temp_workspace))
    names = set(result["files"])
    assert "main.py" in names
    assert ".env" not in names
    assert "db.key" not in names
    assert "cert.pem" not in names


def test_find_files_hides_sensitive_files(temp_workspace):
    """find_files does not expose .env, *.key, *.pem."""
    (temp_workspace / "main.py").write_text("ok")
    (temp_workspace / ".env").write_text("SECRET=1")
    result = find_files({"pattern": "**/*", "base_dir": str(temp_workspace)},
                        workspace_root=str(temp_workspace))
    names = set(result["files"])
    assert "main.py" in names
    assert ".env" not in names


def test_search_text_hides_sensitive_files(temp_workspace):
    """search_text does not expose matches in .env, *.key, *.pem."""
    (temp_workspace / "main.py").write_text("hello")
    (temp_workspace / ".env").write_text("hello")
    result = search_text({"pattern": "hello", "base_dir": str(temp_workspace)},
                         workspace_root=str(temp_workspace))
    assert "main.py" in result["matches"]
    assert ".env" not in result["matches"]


# ---------------------------------------------------------------------------
# Task 4.3: File write tools — write_file, apply_patch, delete_file
# ---------------------------------------------------------------------------

import hashlib

def test_write_file_new(temp_workspace):
    from codeguard.tool.file_tools import write_file
    path = temp_workspace / "new.txt"
    result = write_file({"path": str(path), "content": "hello"}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert path.read_text() == "hello"

def test_write_file_with_fingerprint(temp_workspace):
    from codeguard.tool.file_tools import write_file
    path = temp_workspace / "existing.txt"
    path.write_text("original")
    content_before = path.read_bytes()
    fp = hashlib.sha256(content_before).hexdigest()
    result = write_file({"path": str(path), "content": "modified", "sha256_fingerprint": fp}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert path.read_text() == "modified"

def test_write_file_fingerprint_mismatch(temp_workspace):
    from codeguard.tool.file_tools import write_file
    import pytest
    path = temp_workspace / "existing.txt"
    path.write_text("original")
    with pytest.raises(ValueError, match="Fingerprint mismatch"):
        write_file({"path": str(path), "content": "modified", "sha256_fingerprint": "wrong"}, workspace_root=str(temp_workspace))

def test_write_file_outside_workspace(temp_workspace):
    from codeguard.tool.file_tools import write_file
    import pytest
    outside = Path("/tmp") / "malicious.txt"
    with pytest.raises(PermissionError):
        write_file({"path": str(outside), "content": "x"}, workspace_root=str(temp_workspace))

def test_write_file_rejects_excluded_dir(temp_workspace):
    from codeguard.tool.file_tools import write_file
    import pytest
    (temp_workspace / ".git").mkdir()
    with pytest.raises(PermissionError, match="excluded"):
        write_file({"path": str(temp_workspace / ".git" / "config"), "content": "x"}, workspace_root=str(temp_workspace))

def test_apply_patch(temp_workspace):
    from codeguard.tool.file_tools import apply_patch
    path = temp_workspace / "main.py"
    path.write_text("def foo():\n    pass\n")
    result = apply_patch({"path": str(path), "old_string": "    pass", "new_string": "    return 42"}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert "return 42" in path.read_text()


def test_apply_patch_bom_file_first_line(temp_workspace):
    """T8-FIX6: a UTF-8 BOM file's first line matches an old_string WITHOUT
    ﻿; the BOM is preserved on write-back (no double BOM)."""
    from codeguard.tool.file_tools import apply_patch
    path = temp_workspace / "value.py"
    path.write_bytes(b"\xef\xbb\xbf" + "VALUE: int = 2\n".encode("utf-8"))
    result = apply_patch({"path": str(path),
                          "old_string": "VALUE: int = 2",
                          "new_string": "VALUE: int = 3"},
                         workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")            # BOM preserved
    assert not raw.startswith(b"\xef\xbb\xbf\xef\xbb\xbf")  # no double BOM
    text = path.read_text(encoding="utf-8-sig")
    assert "VALUE: int = 3" in text


def test_apply_patch_no_bom_file_stays_no_bom(temp_workspace):
    """T8-FIX6: a non-BOM file gains NO BOM after a successful patch."""
    from codeguard.tool.file_tools import apply_patch
    path = temp_workspace / "plain.py"
    path.write_bytes("VALUE = 1\n".encode("utf-8"))
    result = apply_patch({"path": str(path),
                          "old_string": "VALUE = 1",
                          "new_string": "VALUE = 2"},
                         workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_apply_patch_bom_mismatch_preserves_bytes(temp_workspace):
    """T8-FIX6: a failed patch leaves the original bytes completely
    unchanged (BOM included)."""
    from codeguard.tool.file_tools import apply_patch
    import pytest
    path = temp_workspace / "value.py"
    original = b"\xef\xbb\xbf" + "VALUE: int = 2\n".encode("utf-8")
    path.write_bytes(original)
    with pytest.raises(ValueError, match="not found"):
        apply_patch({"path": str(path),
                     "old_string": "NOT PRESENT",
                     "new_string": "x"},
                    workspace_root=str(temp_workspace))
    assert path.read_bytes() == original


def test_apply_patch_bom_crlf_preserved(temp_workspace):
    """T8-FIX6: CRLF line endings survive a patch on a BOM file."""
    from codeguard.tool.file_tools import apply_patch
    path = temp_workspace / "crlf.py"
    path.write_bytes(b"\xef\xbb\xbf" + "VALUE = 1\r\nNEXT = 2\r\n".encode("utf-8"))
    result = apply_patch({"path": str(path),
                          "old_string": "VALUE = 1",
                          "new_string": "VALUE = 9"},
                         workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    raw = path.read_bytes()
    assert b"\xef\xbb\xbf" in raw
    assert b"VALUE = 9\r\n" in raw
    assert raw.count(b"\r\n") == 2  # both lines keep CRLF


def test_apply_patch_bom_body_preserved(temp_workspace):
    """T8-FIX6: ﻿ characters in the BODY are NOT stripped (only the
    leading BOM is handled); legal content survives."""
    from codeguard.tool.file_tools import apply_patch
    path = temp_workspace / "body.py"
    body = 'TEXT = "﻿keep"\nTAIL = 1\n'
    path.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))
    result = apply_patch({"path": str(path),
                          "old_string": "TAIL = 1",
                          "new_string": "TAIL = 2"},
                         workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    text = path.read_text(encoding="utf-8-sig")
    assert "﻿keep" in text


def test_apply_patch_bom_crlf_old_string_with_newline(temp_workspace):
    """T8-FIX6 acceptance scenario: BOM + CRLF file, old_string WITHOUT BOM
    but WITH the CRLF newline must match the first line."""
    from codeguard.tool.file_tools import apply_patch
    path = temp_workspace / "value.py"
    path.write_bytes(b"\xef\xbb\xbf" + "VALUE: int = 2\r\n".encode("utf-8"))
    result = apply_patch({"path": str(path),
                          "old_string": "VALUE: int = 2\r\n",
                          "new_string": "VALUE: int = 3\r\n"},
                         workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    raw = path.read_bytes()
    assert raw == b"\xef\xbb\xbf" + "VALUE: int = 3\r\n".encode("utf-8")


def test_apply_patch_bom_old_string_with_bom_prefix(temp_workspace):
    """T8-FIX6: an old_string that echoes the BOM character the model saw
    in read_file output still matches, and the BOM survives the write."""
    from codeguard.tool.file_tools import apply_patch
    path = temp_workspace / "value.py"
    path.write_bytes(b"\xef\xbb\xbf" + "VALUE: int = 2\n".encode("utf-8"))
    result = apply_patch({"path": str(path),
                          "old_string": "﻿VALUE: int = 2",
                          "new_string": "VALUE: int = 3"},
                         workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    raw = path.read_bytes()
    assert raw == b"\xef\xbb\xbf" + "VALUE: int = 3\n".encode("utf-8")


def test_apply_patch_no_bom_lf_line_endings_preserved(temp_workspace):
    """T8-FIX6: LF-only files stay LF-only after a patch (no CRLF
    conversion on Windows)."""
    from codeguard.tool.file_tools import apply_patch
    path = temp_workspace / "lf.py"
    path.write_bytes("VALUE = 1\nTAIL = 2\n".encode("utf-8"))
    result = apply_patch({"path": str(path),
                          "old_string": "VALUE = 1",
                          "new_string": "VALUE = 9"},
                         workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    raw = path.read_bytes()
    assert raw == "VALUE = 9\nTAIL = 2\n".encode("utf-8")

def test_apply_patch_context_mismatch(temp_workspace):
    from codeguard.tool.file_tools import apply_patch
    import pytest
    path = temp_workspace / "main.py"
    path.write_text("def foo():\n    pass\n")
    with pytest.raises(ValueError, match="not found"):
        apply_patch({"path": str(path), "old_string": "not found", "new_string": "x"}, workspace_root=str(temp_workspace))

def test_delete_file(temp_workspace):
    from codeguard.tool.file_tools import delete_file
    path = temp_workspace / "temp.txt"
    path.write_text("delete me")
    result = delete_file({"path": str(path)}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert not path.exists()