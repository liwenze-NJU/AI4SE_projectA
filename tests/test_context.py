from codeguard.context import ContextBuilder
from codeguard.memory.models import MemoryRecord, MemoryType, MemoryStatus, TrustLevel
from datetime import datetime


def test_context_builder_builds_with_all_sections():
    builder = ContextBuilder()
    records = [
        MemoryRecord(id="1", project_id="p1", type=MemoryType.PROJECT_CONVENTION, content="Use pytest for testing", tags=[], keywords=[], source="user", trust_level=TrustLevel.USER_APPROVED, status=MemoryStatus.ACTIVE, created_at=datetime.now(), updated_at=datetime.now(), session_id="s1")
    ]
    context = builder.build(
        system_prompt="You are a coding agent.",
        task_description="Fix the bug in main.py",
        memory_records=records,
        tool_descriptions=["read_file(path) -> str", "write_file(path, content) -> None"]
    )
    assert "You are a coding agent." in context
    assert "Fix the bug in main.py" in context
    assert "Use pytest for testing" in context
    assert "read_file" in context


def test_context_builder_empty_records():
    builder = ContextBuilder()
    context = builder.build(
        system_prompt="You are a coding agent.",
        task_description="Fix the bug",
        memory_records=[],
        tool_descriptions=["read_file"]
    )
    assert "You are a coding agent." in context
    assert "Fix the bug" in context
    assert "No relevant memory records" in context


def test_context_builder_no_tool_descriptions():
    builder = ContextBuilder()
    context = builder.build(
        system_prompt="You are a coding agent.",
        task_description="Fix the bug",
        memory_records=[],
        tool_descriptions=[]
    )
    assert "No tools available" in context