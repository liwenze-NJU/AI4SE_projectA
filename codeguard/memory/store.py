import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

from codeguard.memory.models import MemoryRecord, MemoryType, MemoryStatus, TrustLevel


class JSONMemoryStore:
    """Project-scoped JSON file memory store with atomic writes.

    Stores records per project in base_dir/projects/<project_id>/memory.json.
    Uses tempfile + os.replace() for atomic writes.
    """

    SCHEMA_VERSION = 1

    def __init__(self, base_dir: str, max_records: int = 100, max_content_size: int = 100_000):
        self._base = Path(base_dir)
        self._max_records = max_records
        self._max_content_size = max_content_size

    def _project_path(self, project_id: str) -> Path:
        p = self._base / "projects" / project_id
        p.mkdir(parents=True, exist_ok=True)
        return p / "memory.json"

    def _load(self, project_id: str) -> dict:
        path = self._project_path(project_id)
        if not path.exists():
            return {"schema_version": self.SCHEMA_VERSION, "records": []}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._backup_corrupted(path)
            raise ValueError(
                f"Memory file for project {project_id} is corrupted. "
                f"Original backed up, starting with empty store."
            )

    def _backup_corrupted(self, path: Path) -> None:
        backup = path.with_name(f"memory.json.backup.{int(time.time())}")
        path.rename(backup)

    def _save_atomically(self, project_id: str, data: dict) -> None:
        path = self._project_path(project_id)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp, str(path))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _record_to_dict(self, record: MemoryRecord) -> dict:
        d = record.__dict__.copy()
        d["type"] = record.type.value
        d["trust_level"] = record.trust_level.value
        d["status"] = record.status.value
        d["created_at"] = record.created_at.isoformat()
        d["updated_at"] = record.updated_at.isoformat()
        return d

    def _dict_to_record(self, d: dict) -> MemoryRecord:
        d = d.copy()
        d["type"] = MemoryType(d["type"])
        d["trust_level"] = TrustLevel(d["trust_level"])
        d["status"] = MemoryStatus(d["status"])
        d["created_at"] = datetime.fromisoformat(d["created_at"])
        d["updated_at"] = datetime.fromisoformat(d["updated_at"])
        return MemoryRecord(**d)

    def save(self, record: MemoryRecord) -> None:
        if len(record.content) > self._max_content_size:
            raise ValueError(
                f"Record content ({len(record.content)} chars) exceeds "
                f"max_content_size ({self._max_content_size})"
            )
        data = self._load(record.project_id)
        record_dict = self._record_to_dict(record)
        existing_idx = None
        for i, r in enumerate(data["records"]):
            if r["id"] == record.id:
                existing_idx = i
                break
        if existing_idx is not None:
            data["records"][existing_idx] = record_dict
        else:
            if len(data["records"]) >= self._max_records:
                raise ValueError(
                    f"Max records ({self._max_records}) reached for project {record.project_id}"
                )
            data["records"].append(record_dict)
        self._save_atomically(record.project_id, data)

    def get(self, record_id: str, project_id: str) -> MemoryRecord | None:
        data = self._load(project_id)
        for r in data["records"]:
            if r["id"] == record_id:
                return self._dict_to_record(r)
        return None

    def list(self, project_id: str, type: MemoryType | None = None) -> list[MemoryRecord]:
        data = self._load(project_id)
        records = [self._dict_to_record(r) for r in data["records"]]
        if type is not None:
            records = [r for r in records if r.type == type]
        return records