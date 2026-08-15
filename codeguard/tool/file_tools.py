"""File read tools for the CodeGuard Harness.

Provides read_file, list_directory, find_files, search_text with
workspace boundary enforcement and safety guardrails per SPEC §3.6.

Default safety limits (v1 conservative defaults, documented in AGENT_LOG.md):
  MAX_FILE_SIZE = 1_000_000   # 1 MB
  MAX_LIST_RESULTS = 1000
  list_directory depth = 1 (non-recursive, direct children only)
  EXCLUDED_DIR_NAMES = {".git", ".venv", "node_modules", "__pycache__",
                         "build", "dist", ".tox", ".eggs", ".mypy_cache",
                         ".pytest_cache", ".ruff_cache"}
  SENSITIVE_FILE_NAMES = {".env"}
  SENSITIVE_FILE_SUFFIXES = {".key", ".pem"}
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Safety constants (SPEC §3.6)
# ---------------------------------------------------------------------------

MAX_FILE_SIZE = 1_000_000  # 1 MB
MAX_LIST_RESULTS = 1000
EXCLUDED_DIR_NAMES = {
    ".git", ".venv", "node_modules", "__pycache__",
    "build", "dist", ".tox", ".eggs", ".mypy_cache",
    ".pytest_cache", ".ruff_cache",
}

SENSITIVE_FILE_NAMES = {".env"}
SENSITIVE_FILE_SUFFIXES = {".key", ".pem"}


def _is_excluded_dir(path: Path, workspace_root: str) -> bool:
    """Check if any component of path (relative to workspace) is excluded."""
    root = Path(workspace_root).resolve()
    try:
        rel = path.resolve().relative_to(root)
    except ValueError:
        return False
    return any(part in EXCLUDED_DIR_NAMES for part in rel.parts)


def _is_sensitive_file(path: Path) -> bool:
    """Check if a file is sensitive (.env, *.key, *.pem)."""
    return path.name in SENSITIVE_FILE_NAMES or path.suffix in SENSITIVE_FILE_SUFFIXES


def _is_binary(file_path: Path) -> bool:
    """Detect binary files by checking for null bytes in the first 8KB."""
    with open(file_path, "rb") as f:
        chunk = f.read(8192)
    return b"\x00" in chunk


def _resolve_path(requested: str, workspace_root: str) -> Path:
    """Resolve and validate path is within workspace."""
    root = Path(workspace_root).resolve()
    target = (root / requested).resolve()
    root_str = str(root)
    target_str = str(target)
    if target_str != root_str and not target_str.startswith(root_str + os.sep):
        raise PermissionError(f"Path '{requested}' is outside workspace '{workspace_root}'")
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")
    return target


def read_file(params: dict, workspace_root: str = "") -> dict:
    path = _resolve_path(params["path"], workspace_root)

    # Excluded directory check
    if _is_excluded_dir(path, workspace_root):
        raise PermissionError(
            f"Cannot read file in excluded directory: {path}"
        )

    # Sensitive file check
    if _is_sensitive_file(path):
        raise PermissionError(f"Cannot read sensitive file: {path}")

    # Size limit
    size = path.stat().st_size
    if size > MAX_FILE_SIZE:
        raise ValueError(
            f"File '{path}' exceeds size limit ({size} > {MAX_FILE_SIZE} bytes)"
        )

    # Binary rejection
    if _is_binary(path):
        raise ValueError(f"Cannot read binary file: {path}")

    content = path.read_text(encoding="utf-8")
    return {"status": "SUCCESS", "content": content, "path": str(path)}


def list_directory(params: dict, workspace_root: str = "") -> dict:
    path = _resolve_path(params["path"], workspace_root)
    all_entries = []
    for p in path.iterdir():
        if p.is_dir() and _is_excluded_dir(p, workspace_root):
            continue
        if p.is_file() and _is_sensitive_file(p):
            continue
        all_entries.append(str(p.relative_to(path)))
    truncated = len(all_entries) > MAX_LIST_RESULTS
    if truncated:
        all_entries = all_entries[:MAX_LIST_RESULTS]
    return {"files": all_entries, "path": str(path), "truncated": truncated}


def find_files(params: dict, workspace_root: str = "") -> dict:
    base = _resolve_path(params.get("base_dir", "."), workspace_root)
    pattern = params["pattern"]
    matches = []
    for p in base.glob(pattern):
        if _is_excluded_dir(p, workspace_root):
            continue
        if p.is_file() and _is_sensitive_file(p):
            continue
        matches.append(str(p.relative_to(base)))
    return {"files": matches, "pattern": pattern}


def search_text(params: dict, workspace_root: str = "") -> dict:
    base = _resolve_path(params.get("base_dir", "."), workspace_root)
    pattern = params["pattern"]
    matches = {}
    for p in base.rglob("*"):
        if _is_excluded_dir(p, workspace_root):
            continue
        if p.is_file():
            try:
                if _is_binary(p) or _is_sensitive_file(p):
                    continue
                for i, line in enumerate(
                    p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                ):
                    if pattern in line:
                        matches.setdefault(str(p.relative_to(base)), []).append(i)
            except Exception:
                continue
    return {"matches": matches, "pattern": pattern}


# ---------------------------------------------------------------------------
# Task 4.3: File write tools — write_file, apply_patch, delete_file
# ---------------------------------------------------------------------------

import hashlib
import tempfile


def _resolve_dir(requested: str, workspace_root: str) -> str:
    """Resolve path and validate parent directory is within workspace."""
    root = Path(workspace_root).resolve()
    target = (root / requested).resolve()
    root_str = str(root)
    target_str = str(target)
    if target_str != root_str and not target_str.startswith(root_str + os.sep):
        raise PermissionError(f"Path '{requested}' is outside workspace '{workspace_root}'")
    return str(target)


def write_file(params: dict, workspace_root: str = "") -> dict:
    path = Path(_resolve_dir(params["path"], workspace_root))

    # Safety checks
    if _is_excluded_dir(path, workspace_root):
        raise PermissionError(f"Cannot write to excluded directory: {path}")
    if _is_sensitive_file(path):
        raise PermissionError(f"Cannot write to sensitive file: {path}")

    if path.exists():
        current_content = path.read_bytes()
        current_fp = hashlib.sha256(current_content).hexdigest()
        provided_fp = params.get("sha256_fingerprint")
        if provided_fp and current_fp != provided_fp:
            raise ValueError(f"Fingerprint mismatch: expected {provided_fp}, got {current_fp}")

    content = params["content"]
    # Atomic write: write to temp file, then rename
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise
    return {"status": "SUCCESS", "path": str(path)}


def apply_patch(params: dict, workspace_root: str = "") -> dict:
    path = Path(_resolve_dir(params["path"], workspace_root))

    # Safety checks
    if _is_excluded_dir(path, workspace_root):
        raise PermissionError(f"Cannot patch file in excluded directory: {path}")
    if _is_sensitive_file(path):
        raise PermissionError(f"Cannot patch sensitive file: {path}")

    raw = path.read_bytes()
    had_bom = raw.startswith(b"\xef\xbb\xbf")

    # T8-FIX6: strip the LEADING UTF-8 BOM before matching (the model sees
    # the file without it via read_file's utf-8 decode, so old_string never
    # needs to contain \ufeff); body characters are untouched. The binary
    # write below preserves the original line endings byte-for-byte.
    content = raw.decode("utf-8-sig")
    old = params["old_string"]
    new = params["new_string"]
    if old not in content:
        # Match against the raw-BOM variant too (the model may echo the
        # \ufeff it saw in read_file output as the first character).
        content = raw.decode("utf-8")
        if old not in content:
            raise ValueError(f"old_string not found in {path}")

    patched = content.replace(old, new, 1)
    if had_bom and not patched.startswith("\ufeff"):
        # Re-add the BOM only when the replacement consumed it (matching
        # against the BOM-inclusive variant) — never double it.
        patched = "\ufeff" + patched
    out = patched.encode("utf-8")
    # Atomic write preserving the byte-exact result.
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(out)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise
    return {"status": "SUCCESS", "path": str(path)}


def delete_file(params: dict, workspace_root: str = "") -> dict:
    path = Path(_resolve_dir(params["path"], workspace_root))

    # Safety checks
    if _is_excluded_dir(path, workspace_root):
        raise PermissionError(f"Cannot delete file in excluded directory: {path}")
    if _is_sensitive_file(path):
        raise PermissionError(f"Cannot delete sensitive file: {path}")

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    path.unlink()
    return {"status": "SUCCESS", "path": str(path)}