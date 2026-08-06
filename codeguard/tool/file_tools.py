"""File read tools for the CodeGuard Harness.

Provides read_file, list_directory, find_files, search_text with
workspace boundary enforcement and safety guardrails per SPEC §3.6.

Default safety limits (v1 conservative defaults, documented in AGENT_LOG.md):
  MAX_FILE_SIZE = 1_000_000   # 1 MB
  MAX_LIST_RESULTS = 1000
  EXCLUDED_DIR_NAMES = {".git", ".venv", "node_modules", "__pycache__",
                         "build", "dist", ".tox", ".eggs", ".mypy_cache",
                         ".pytest_cache", ".ruff_cache"}
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


def _is_excluded_dir(path: Path, workspace_root: str) -> bool:
    """Check if any component of path (relative to workspace) is excluded."""
    root = Path(workspace_root).resolve()
    try:
        rel = path.resolve().relative_to(root)
    except ValueError:
        return False
    return any(part in EXCLUDED_DIR_NAMES for part in rel.parts)


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
                if _is_binary(p):
                    continue
                for i, line in enumerate(
                    p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                ):
                    if pattern in line:
                        matches.setdefault(str(p.relative_to(base)), []).append(i)
            except Exception:
                continue
    return {"matches": matches, "pattern": pattern}