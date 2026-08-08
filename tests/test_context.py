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
    assert "No relevant memory records" in context
    assert "No tools available" in context


def test_context_builder_multiple_records():
    """Multiple memory records appear in order with correct format."""
    builder = ContextBuilder()
    records = [
        MemoryRecord(id="1", project_id="p1", type=MemoryType.PROJECT_CONVENTION,
                     content="First convention", tags=[], keywords=[], source="user",
                     trust_level=TrustLevel.USER_APPROVED, status=MemoryStatus.ACTIVE,
                     created_at=datetime.now(), updated_at=datetime.now(), session_id="s1"),
        MemoryRecord(id="2", project_id="p1", type=MemoryType.APPROVED_DECISION,
                     content="Second decision", tags=[], keywords=[], source="user",
                     trust_level=TrustLevel.USER_APPROVED, status=MemoryStatus.ACTIVE,
                     created_at=datetime.now(), updated_at=datetime.now(), session_id="s1"),
        MemoryRecord(id="3", project_id="p1", type=MemoryType.FAILURE_RESOLUTION,
                     content="Third resolution", tags=[], keywords=[], source="user",
                     trust_level=TrustLevel.USER_APPROVED, status=MemoryStatus.ACTIVE,
                     created_at=datetime.now(), updated_at=datetime.now(), session_id="s1"),
    ]
    context = builder.build(
        system_prompt="Sys",
        task_description="Task",
        memory_records=records,
        tool_descriptions=["tool_a", "tool_b", "tool_c"],
    )
    # Verify order and format
    lines = context.split("\n")
    mem_start = lines.index("## Memory")
    assert lines[mem_start + 1] == "- [project_convention] First convention"
    assert lines[mem_start + 2] == "- [approved_decision] Second decision"
    assert lines[mem_start + 3] == "- [failure_resolution] Third resolution"
    # Verify tools appear in order
    tools_start = lines.index("## Available Tools")
    assert lines[tools_start + 1] == "- tool_a"
    assert lines[tools_start + 2] == "- tool_b"
    assert lines[tools_start + 3] == "- tool_c"


def test_context_builder_none_inputs():
    """None for memory_records or tool_descriptions is treated as empty."""
    builder = ContextBuilder()
    context = builder.build(
        system_prompt="You are a coding agent.",
        task_description="Fix the bug",
        memory_records=None,
        tool_descriptions=None,
    )
    assert "No relevant memory records" in context
    assert "No tools available" in context