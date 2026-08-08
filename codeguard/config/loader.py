import tomllib
from pathlib import Path

_KNOWN_SECTIONS = {
    "workspace", "llm", "loop", "tools", "sensors",
    "memory", "ui", "approval", "mode",
}


class ConfigLoader:
    """Loads TOML config files with section-level validation.

    Uses Python 3.12 built-in tomllib. No include, command substitution,
    or environment variable interpolation support.
    """

    def load_file(self, path: str) -> dict:
        p = Path(path)
        if not p.exists():
            return {}
        raw = p.read_text(encoding="utf-8")
        if not raw.strip():
            return {}
        try:
            data = tomllib.loads(raw)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML in {path}: {e}") from e

        for key in data:
            if key not in _KNOWN_SECTIONS:
                raise ValueError(
                    f"Unknown config section '{key}' in {path}"
                )

        return data