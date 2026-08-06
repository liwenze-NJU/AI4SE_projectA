import json
import pytest
from datetime import datetime
from codeguard.memory.models import MemoryRecord, MemoryType, MemoryStatus, TrustLevel
from codeguard.memory.store import JSONMemoryStore


def _make_record(project_id="p1", id="m1", type=None, status=None, trust_level=None,
                 content="test content", tags=None, keywords=None):
    return MemoryRecord(
        id=id,
        project_id=project_id,
        type=type or MemoryType.PROJECT_CONVENTION,
        content=content,
        tags=tags or [],
        keywords=keywords or [],
        source="user",
        trust_level=trust_level or TrustLevel.USER_APPROVED,
        status=status or MemoryStatus.ACTIVE,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        session_id="s1",
    )


class TestJSONMemoryStoreCreate:
    def test_save_and_get(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        record = _make_record()
        store.save(record)
        loaded = store.get("m1", "p1")
        assert loaded is not None
        assert loaded.id == "m1"
        assert loaded.content == "test content"

    def test_get_nonexistent_returns_none(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        assert store.get("nonexistent", "p1") is None

    def test_list_by_project(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", project_id="p1"))
        store.save(_make_record(id="m2", project_id="p1"))
        records = store.list(project_id="p1")
        assert len(records) == 2

    def test_list_by_project_and_type(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", project_id="p1", type=MemoryType.PROJECT_CONVENTION))
        store.save(_make_record(id="m2", project_id="p1", type=MemoryType.APPROVED_DECISION))
        records = store.list(project_id="p1", type=MemoryType.PROJECT_CONVENTION)
        assert len(records) == 1
        assert records[0].type == MemoryType.PROJECT_CONVENTION

    def test_list_empty_project(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        records = store.list(project_id="empty_project")
        assert records == []

    def test_max_records_enforcement(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace), max_records=2)
        store.save(_make_record(id="m1", project_id="p1"))
        store.save(_make_record(id="m2", project_id="p1"))
        with pytest.raises(ValueError, match="Max records"):
            store.save(_make_record(id="m3", project_id="p1"))

    def test_atomic_write_produces_valid_json(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        record = _make_record()
        store.save(record)
        file_path = temp_workspace / "projects" / "p1" / "memory.json"
        assert file_path.exists()
        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert "schema_version" in data
        assert len(data["records"]) == 1

    def test_schema_version_in_file(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record())
        file_path = temp_workspace / "projects" / "p1" / "memory.json"
        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert data["schema_version"] == 1

    def test_projects_isolated(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", project_id="p1"))
        store.save(_make_record(id="m2", project_id="p2"))
        assert len(store.list(project_id="p1")) == 1
        assert len(store.list(project_id="p2")) == 1

    def test_save_updates_existing_record(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        record = _make_record(id="m1", content="original")
        store.save(record)
        record.content = "updated"
        store.save(record)
        loaded = store.get("m1", "p1")
        assert loaded.content == "updated"

    def test_corrupted_file_backup_and_error(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1"))
        file_path = temp_workspace / "projects" / "p1" / "memory.json"
        file_path.write_text("not valid json{{", encoding="utf-8")
        with pytest.raises(ValueError, match="corrupted"):
            store.get("m1", "p1")
        backup_files = list(file_path.parent.glob("memory.json.backup.*"))
        assert len(backup_files) == 1

    def test_content_size_limit(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace), max_content_size=100)
        record = _make_record(content="x" * 101)
        with pytest.raises(ValueError, match="content.*exceeds"):
            store.save(record)