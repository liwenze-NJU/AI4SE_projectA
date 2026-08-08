import pytest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from codeguard.state import AgentState


def test_tool_definition():
    from codeguard.tool import ToolDefinition
    td = ToolDefinition(
        name="read_file",
        description="Read file content",
        parameters_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        handler=lambda: None,
        category="FILE",
        side_effect=False,
        default_risk="ALLOW",
        supported_modes=["TEST"]
    )
    assert td.name == "read_file"
    assert td.category == "FILE"


def test_tool_result():
    from codeguard.tool import ToolResult
    tr = ToolResult(
        tool_name="read_file",
        status="SUCCESS",
        output_summary="file content",
        diagnostics=[],
        exit_code=0,
        changed_files=[],
        duration=0.1,
        truncated=False,
        error_category=None,
        audit_id="audit-1"
    )
    assert tr.status == "SUCCESS"
    assert tr.tool_name == "read_file"


def test_feedback_result_passed():
    from codeguard.feedback import FeedbackResult
    fr = FeedbackResult(
        sensor_id="pytest",
        program="pytest",
        args=["."],
        status="PASSED",
        failure_category=None,
        exit_code=0,
        failure_fingerprint=None,
        validation_type="INTERMEDIATE",
        summary="All tests passed",
        diagnostics=[],
        duration=0.5,
        retryable=False,
        raw_output_truncated=""
    )
    assert fr.status == "PASSED"
    assert fr.failure_category is None


def test_feedback_result_failed():
    from codeguard.feedback import FeedbackResult
    fr = FeedbackResult(
        sensor_id="pytest",
        program="pytest",
        args=["."],
        status="FAILED",
        failure_category="TEST_FAILURE",
        exit_code=1,
        failure_fingerprint="fp123",
        validation_type="INTERMEDIATE",
        summary="1 test failed",
        diagnostics=[],
        duration=0.5,
        retryable=True,
        raw_output_truncated="FAILURES..."
    )
    assert fr.status == "FAILED"
    assert fr.failure_fingerprint == "fp123"


def test_sensor_definition():
    from codeguard.feedback import SensorDefinition
    sd = SensorDefinition(
        name="pytest",
        program="pytest",
        args=["."],
        timeout=30,
        parser="pytest",
        required=True,
        allowed_exit_codes={0, 1},
        output_limit=4096
    )
    assert sd.name == "pytest"
    assert sd.required is True


def test_diagnostic():
    from codeguard.feedback import Diagnostic
    d = Diagnostic(file="test.py", line=42, column=5, code="E001", message="syntax error", category="syntax")
    assert d.file == "test.py"
    assert d.line == 42


def test_memory_record():
    from codeguard.memory.models import MemoryRecord, MemoryType, TrustLevel, MemoryStatus
    mr = MemoryRecord(
        id="m1",
        project_id="p1",
        type=MemoryType.PROJECT_CONVENTION,
        content="use pytest for testing",
        tags=["testing"],
        keywords=["pytest"],
        source="user",
        trust_level=TrustLevel.USER_APPROVED,
        status=MemoryStatus.ACTIVE,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        session_id="s1"
    )
    assert mr.type == MemoryType.PROJECT_CONVENTION
    assert mr.status == MemoryStatus.ACTIVE


def test_memory_type_enum():
    from codeguard.memory.models import MemoryType
    assert MemoryType.PROJECT_CONVENTION.value == "project_convention"
    assert MemoryType.APPROVED_DECISION.value == "approved_decision"
    assert MemoryType.TASK_SUMMARY.value == "task_summary"
    assert MemoryType.FAILURE_RESOLUTION.value == "failure_resolution"


def test_trust_level_enum():
    from codeguard.memory.models import TrustLevel
    assert TrustLevel.USER_APPROVED.value == "user_approved"
    assert TrustLevel.HARNESS_VERIFIED.value == "harness_verified"
    assert TrustLevel.LLM_PROPOSED.value == "llm_proposed"


def test_memory_status_enum():
    from codeguard.memory.models import MemoryStatus
    assert MemoryStatus.PENDING.value == "pending"
    assert MemoryStatus.ACTIVE.value == "active"
    assert MemoryStatus.REJECTED.value == "rejected"
    assert MemoryStatus.ARCHIVED.value == "archived"
    assert MemoryStatus.DELETED.value == "deleted"


def test_effective_config():
    from codeguard.config.models import EffectiveConfig, WorkspaceConfig, LLMConfig, LoopConfig, ToolsConfig, SensorsConfig, MemoryConfig, UIConfig, ApprovalConfig
    cfg = EffectiveConfig(
        workspace=WorkspaceConfig(project_root=Path("/root"), additional_protected_paths=[], excluded_paths=[]),
        llm=LLMConfig(provider="deepseek", model="deepseek-v4-flash", max_output_tokens=4096, request_timeout=60, credential_profile="default"),
        loop=LoopConfig(max_steps=50, max_llm_calls=100, max_repair_attempts=3, session_timeout=600, tool_timeout=30, no_progress_threshold=3, token_budget=100000, cost_budget=Decimal("0.5")),
        tools=ToolsConfig(enabled_tools=["read_file"], disabled_tools=[], per_tool_timeouts={}),
        sensors=SensorsConfig(required_sensors=["pytest"], sensor_order=["pytest"], timeout_per_sensor=30, output_limit=4096),
        memory=MemoryConfig(enabled=True, max_records=100, top_k=10, context_budget=2048, allowed_types=["PROJECT_CONVENTION"]),
        ui=UIConfig(web_port=8080, bind_address="127.0.0.1", approval_timeout=15),
        approval=ApprovalConfig(cli_timeout=300),
        mode="test",
        source={}
    )
    assert cfg.mode == "test"
    assert cfg.llm.provider == "deepseek"
    assert cfg.ui.approval_timeout == 15
    assert cfg.approval.cli_timeout == 300


def test_effective_config_immutable():
    """EffectiveConfig is frozen — modifying fields raises FrozenInstanceError."""
    from dataclasses import FrozenInstanceError
    from codeguard.config.models import EffectiveConfig, WorkspaceConfig, LLMConfig, LoopConfig, ToolsConfig, SensorsConfig, MemoryConfig, UIConfig, ApprovalConfig
    cfg = EffectiveConfig(
        workspace=WorkspaceConfig(project_root=Path("/root")),
        llm=LLMConfig(),
        loop=LoopConfig(),
        tools=ToolsConfig(),
        sensors=SensorsConfig(),
        memory=MemoryConfig(),
        ui=UIConfig(),
        approval=ApprovalConfig(),
        mode="test",
        source={}
    )
    with pytest.raises(FrozenInstanceError):
        cfg.mode = "demo"