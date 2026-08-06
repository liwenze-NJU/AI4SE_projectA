import pytest
from datetime import datetime, timedelta
from codeguard.memory.models import MemoryRecord, MemoryType, MemoryStatus, TrustLevel
from codeguard.memory.store import JSONMemoryStore
from codeguard.memory.retriever import MemoryRetriever


def _make_record(pid="p1", id="m1", type=None, status=None, trust=None,
                 content="test content", tags=None, keywords=None,
                 updated_at=None):
    return MemoryRecord(
        id=id,
        project_id=pid,
        type=type or MemoryType.PROJECT_CONVENTION,
        content=content,
        tags=tags or [],
        keywords=keywords or [],
        source="user",
        trust_level=trust or TrustLevel.USER_APPROVED,
        status=status or MemoryStatus.ACTIVE,
        created_at=datetime.now(),
        updated_at=updated_at or datetime.now(),
        session_id="s1",
    )


class TestRetrieveFiltering:
    def test_retrieve_by_type(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", type=MemoryType.PROJECT_CONVENTION))
        store.save(_make_record(id="m2", type=MemoryType.APPROVED_DECISION))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1", type=MemoryType.PROJECT_CONVENTION)
        assert len(results) == 1
        assert results[0].type == MemoryType.PROJECT_CONVENTION

    def test_retrieve_no_type_filter_returns_all_active(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", type=MemoryType.PROJECT_CONVENTION))
        store.save(_make_record(id="m2", type=MemoryType.APPROVED_DECISION))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1")
        assert len(results) == 2

    def test_retrieve_excludes_pending(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", status=MemoryStatus.PENDING))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1")
        assert len(results) == 0

    def test_retrieve_excludes_rejected(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", status=MemoryStatus.REJECTED))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1")
        assert len(results) == 0

    def test_retrieve_excludes_archived(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", status=MemoryStatus.ARCHIVED))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1")
        assert len(results) == 0

    def test_retrieve_excludes_deleted(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", status=MemoryStatus.DELETED))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1")
        assert len(results) == 0

    def test_retrieve_only_active_passed_through(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", status=MemoryStatus.ACTIVE))
        store.save(_make_record(id="m2", status=MemoryStatus.PENDING))
        store.save(_make_record(id="m3", status=MemoryStatus.REJECTED))
        store.save(_make_record(id="m4", status=MemoryStatus.ARCHIVED))
        store.save(_make_record(id="m5", status=MemoryStatus.DELETED))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1")
        assert len(results) == 1
        assert results[0].id == "m1"

    def test_retrieve_project_isolation(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", pid="p1"))
        store.save(_make_record(id="m2", pid="p2"))
        retriever = MemoryRetriever(store)
        assert len(retriever.retrieve(project_id="p1")) == 1
        assert len(retriever.retrieve(project_id="p2")) == 1

    def test_retrieve_nonexistent_project_returns_empty(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="no_such_project")
        assert results == []


class TestRetrieveTagsKeywords:
    def test_retrieve_tags_exact_match(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", tags=["python", "testing"]))
        store.save(_make_record(id="m2", tags=["javascript"]))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1", tags=["python"])
        assert len(results) == 1
        assert results[0].id == "m1"

    def test_retrieve_tags_any_match(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", tags=["python", "testing"]))
        store.save(_make_record(id="m2", tags=["rust", "systems"]))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1", tags=["python", "rust"])
        assert len(results) == 2

    def test_retrieve_tags_no_match_returns_empty(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", tags=["python"]))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1", tags=["go"])
        assert results == []

    def test_retrieve_keywords_match(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", keywords=["convention", "naming"]))
        store.save(_make_record(id="m2", keywords=["deployment"]))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1", keywords=["convention"])
        assert len(results) == 1
        assert results[0].id == "m1"

    def test_retrieve_keywords_any_match(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", keywords=["convention"]))
        store.save(_make_record(id="m2", keywords=["deployment"]))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1", keywords=["convention", "deployment"])
        assert len(results) == 2

    def test_retrieve_tags_do_not_substitute_for_type(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", type=MemoryType.PROJECT_CONVENTION,
                                tags=["approved_decision"]))
        store.save(_make_record(id="m2", type=MemoryType.APPROVED_DECISION,
                                tags=["project_convention"]))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1", type=MemoryType.PROJECT_CONVENTION)
        assert len(results) == 1
        assert results[0].id == "m1"

    def test_retrieve_tags_and_keywords_combined(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", tags=["python"], keywords=["convention"]))
        store.save(_make_record(id="m2", tags=["python"], keywords=["other"]))
        store.save(_make_record(id="m3", tags=["go"], keywords=["convention"]))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1", tags=["python"], keywords=["convention"])
        assert len(results) == 1
        assert results[0].id == "m1"


class TestRetrieveSorting:
    def test_sort_by_trust_level_descending(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        t = datetime.now()
        store.save(_make_record(id="m1", trust=TrustLevel.LLM_PROPOSED, updated_at=t))
        store.save(_make_record(id="m2", trust=TrustLevel.HARNESS_VERIFIED, updated_at=t))
        store.save(_make_record(id="m3", trust=TrustLevel.USER_APPROVED, updated_at=t))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1")
        assert results[0].trust_level == TrustLevel.USER_APPROVED
        assert results[1].trust_level == TrustLevel.HARNESS_VERIFIED
        assert results[2].trust_level == TrustLevel.LLM_PROPOSED

    def test_sort_by_updated_at_within_same_trust(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        t = datetime.now()
        store.save(_make_record(id="m1", trust=TrustLevel.USER_APPROVED,
                                updated_at=t - timedelta(hours=2)))
        store.save(_make_record(id="m2", trust=TrustLevel.USER_APPROVED,
                                updated_at=t))
        store.save(_make_record(id="m3", trust=TrustLevel.USER_APPROVED,
                                updated_at=t - timedelta(hours=1)))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1")
        assert results[0].id == "m2"
        assert results[1].id == "m3"
        assert results[2].id == "m1"

    def test_sort_stable_by_id_when_same_trust_and_time(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        t = datetime.now()
        store.save(_make_record(id="m3", trust=TrustLevel.USER_APPROVED, updated_at=t))
        store.save(_make_record(id="m1", trust=TrustLevel.USER_APPROVED, updated_at=t))
        store.save(_make_record(id="m2", trust=TrustLevel.USER_APPROVED, updated_at=t))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1")
        ids = [r.id for r in results]
        assert ids == ["m1", "m2", "m3"]


class TestRetrieveTopKAndBudget:
    def test_top_k_limits_results(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        for i in range(5):
            store.save(_make_record(id=f"m{i}"))
        retriever = MemoryRetriever(store, top_k=3)
        results = retriever.retrieve(project_id="p1")
        assert len(results) == 3

    def test_top_k_zero_returns_empty(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1"))
        retriever = MemoryRetriever(store, top_k=0)
        results = retriever.retrieve(project_id="p1")
        assert results == []

    def test_context_budget_truncation(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", content="x" * 500))
        store.save(_make_record(id="m2", content="y" * 500))
        store.save(_make_record(id="m3", content="z" * 500))
        retriever = MemoryRetriever(store, context_budget=1200)
        results = retriever.retrieve(project_id="p1")
        total = sum(len(r.content) for r in results)
        assert total <= 1200
        assert len(results) >= 2

    def test_context_budget_zero_returns_empty(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", content="test"))
        retriever = MemoryRetriever(store, context_budget=0)
        results = retriever.retrieve(project_id="p1")
        assert results == []

    def test_single_record_exceeds_remaining_budget_is_excluded(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", content="x" * 500))
        store.save(_make_record(id="m2", content="y" * 100))
        retriever = MemoryRetriever(store, context_budget=550)
        results = retriever.retrieve(project_id="p1")
        total = sum(len(r.content) for r in results)
        assert total <= 550

    def test_context_budget_never_exceeded(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        for i in range(10):
            store.save(_make_record(id=f"m{i}", content="x" * 200))
        retriever = MemoryRetriever(store, context_budget=999)
        results = retriever.retrieve(project_id="p1")
        total = sum(len(r.content) for r in results)
        assert total <= 999

    def test_does_not_modify_store_records(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        store.save(_make_record(id="m1", content="original"))
        retriever = MemoryRetriever(store)
        results = retriever.retrieve(project_id="p1")
        results[0].content = "modified"
        loaded = store.get("m1", "p1")
        assert loaded.content == "original"

    def test_top_k_applied_before_budget(self, temp_workspace):
        store = JSONMemoryStore(base_dir=str(temp_workspace))
        for i in range(5):
            store.save(_make_record(id=f"m{i}", content="x" * 1000))
        retriever = MemoryRetriever(store, top_k=2, context_budget=3000)
        results = retriever.retrieve(project_id="p1")
        assert len(results) <= 2
        total = sum(len(r.content) for r in results)
        assert total <= 3000