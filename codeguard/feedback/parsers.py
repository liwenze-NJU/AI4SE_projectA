import hashlib
import re

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _compute_fingerprint(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


class PytestParser:
    """Parses pytest output for test failures."""

    _FAILED_RE = re.compile(r'^FAILED\s+(.+?)(?:::\S+)?\s*(?:-.*)?$')

    def parse(self, output: str) -> dict:
        clean = _strip_ansi(output)
        if not clean:
            return {"failure_category": None, "diagnostics": [], "fingerprint": None}

        has_failure = bool(re.search(r'\bFAILED\b', clean) or "FAILURES" in clean)
        if not has_failure:
            return {"failure_category": None, "diagnostics": [], "fingerprint": None}

        diagnostics = []
        for line in clean.splitlines():
            m = self._FAILED_RE.match(line.strip())
            if m:
                path = m.group(1).strip()
                parts = path.rsplit(":", 1) if ":" in path else (path, None)
                file = parts[0].strip()
                line_num = None
                if len(parts) == 2 and parts[1] and parts[1].strip().isdigit():
                    line_num = int(parts[1].strip())
                diagnostics.append({
                    "file": file,
                    "line": line_num,
                    "column": None,
                    "code": None,
                    "message": line.strip(),
                    "category": "test_failure",
                })

        if not diagnostics:
            return {"failure_category": None, "diagnostics": [], "fingerprint": None}

        fp = _compute_fingerprint(*(f"{d['file']}:{d['line']}" for d in diagnostics))
        return {"failure_category": "TEST_FAILURE", "diagnostics": diagnostics, "fingerprint": fp}


class RuffParser:
    """Parses ruff linter output."""

    _RUFF_RE = re.compile(
        r'^(.+?):(\d+):(\d+):\s+(\S+)\s+(.*)$'
    )

    def parse(self, output: str) -> dict:
        clean = _strip_ansi(output)
        if not clean:
            return {"failure_category": None, "diagnostics": [], "fingerprint": None}

        diagnostics = []
        for line in clean.splitlines():
            m = self._RUFF_RE.match(line.strip())
            if m:
                diagnostics.append({
                    "file": m.group(1),
                    "line": int(m.group(2)),
                    "column": int(m.group(3)),
                    "code": m.group(4),
                    "message": m.group(5).strip(),
                    "category": "lint",
                })

        if not diagnostics:
            return {"failure_category": None, "diagnostics": [], "fingerprint": None}

        fp = _compute_fingerprint(*(f"{d['file']}:{d['line']}:{d['column']}:{d['code']}" for d in diagnostics))
        return {"failure_category": "LINT_ERROR", "diagnostics": diagnostics, "fingerprint": fp}


class MypyParser:
    """Parses mypy type-checker output."""

    _MYPY_RE = re.compile(
        r'^(.+?):(\d+)(?::(\d+))?:\s+(error|warning):\s+(.+?)(?:\s+\[(\S+)\])?\s*$'
    )

    def parse(self, output: str) -> dict:
        clean = _strip_ansi(output)
        if not clean:
            return {"failure_category": None, "diagnostics": [], "fingerprint": None}

        diagnostics = []
        for line in clean.splitlines():
            m = self._MYPY_RE.match(line.strip())
            if m:
                diagnostics.append({
                    "file": m.group(1),
                    "line": int(m.group(2)),
                    "column": int(m.group(3)) if m.group(3) else None,
                    "code": m.group(6) if m.group(6) else None,
                    "message": m.group(5).strip(),
                    "category": "type_error",
                })

        if not diagnostics:
            return {"failure_category": None, "diagnostics": [], "fingerprint": None}

        fp = _compute_fingerprint(*(f"{d['file']}:{d['line']}" for d in diagnostics))
        return {"failure_category": "TYPE_ERROR", "diagnostics": diagnostics, "fingerprint": fp}


class GenericParser:
    """Fallback parser for unrecognized failure output."""

    def parse(self, output: str) -> dict:
        clean = _strip_ansi(output)
        fp = _compute_fingerprint(clean) if clean else _compute_fingerprint("empty")
        return {"failure_category": "UNKNOWN_FAILURE", "diagnostics": [], "fingerprint": fp}