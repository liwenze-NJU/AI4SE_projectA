import os
import glob
from pathlib import Path

def _resolve_path(requested: str, workspace_root: str) -> Path:
    """Resolve and validate path is within workspace."""
    root = Path(workspace_root).resolve()
    target = (root / requested).resolve()
    if not str(target).startswith(str(root)):
        raise PermissionError(f"Path '{requested}' is outside workspace '{workspace_root}'")
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")
    return target

def read_file(params: dict, workspace_root: str = "") -> dict:
    path = _resolve_path(params["path"], workspace_root)
    content = path.read_text(encoding="utf-8")
    return {"status": "SUCCESS", "content": content, "path": str(path)}

def list_directory(params: dict, workspace_root: str = "") -> dict:
    path = _resolve_path(params["path"], workspace_root)
    files = [str(p.relative_to(path)) for p in path.iterdir()]
    return {"files": files, "path": str(path)}

def find_files(params: dict, workspace_root: str = "") -> dict:
    base = _resolve_path(params.get("base_dir", "."), workspace_root)
    pattern = params["pattern"]
    matches = [str(p.relative_to(base)) for p in base.glob(pattern)]
    return {"files": matches, "pattern": pattern}

def search_text(params: dict, workspace_root: str = "") -> dict:
    base = _resolve_path(params.get("base_dir", "."), workspace_root)
    pattern = params["pattern"]
    matches = {}
    for p in base.rglob("*"):
        if p.is_file():
            try:
                for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if pattern in line:
                        matches.setdefault(str(p.relative_to(base)), []).append(i)
            except Exception:
                continue
    return {"matches": matches, "pattern": pattern}