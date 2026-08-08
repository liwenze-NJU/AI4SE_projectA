"""Mock file system for demo scenarios.

Deterministic in-memory store. No real disk I/O, no host paths.
All paths are treated as mock:// URIs.
"""


class MockFileSystem:
    """In-memory files with deterministic content."""

    def __init__(self, initial: dict | None = None):
        self._files: dict[str, str] = dict(initial or {})

    def write_file(self, path: str, content: str) -> dict:
        self._files[path] = content
        return {"status": "ok", "path": path, "mock": True}

    def read_file(self, path: str) -> dict:
        if path in self._files:
            return {"status": "ok", "path": path, "content": self._files[path], "mock": True}
        return {"status": "missing", "path": path, "mock": True}

    def list_directory(self, path: str = "") -> dict:
        prefix = path.rstrip("/")
        names = sorted(p for p in self._files if p.startswith(prefix))
        return {"status": "ok", "path": path, "entries": names, "mock": True}

    @property
    def files(self) -> dict[str, str]:
        return dict(self._files)


mock_fs = MockFileSystem(initial={
    "mock://workspace/src/auth.py": "# auth module (demo)",
    "mock://workspace/src/auth_test.py": "def test_auth():\n    assert True\n",
})
