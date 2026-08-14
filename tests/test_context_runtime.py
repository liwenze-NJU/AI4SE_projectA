"""Bounded runtime context tests (interactive CLI plan, Task 2)."""

import pytest

from codeguard.context import ContextBuilder
from codeguard.secret import SecretRedactor


def test_runtime_context_priority_and_feedback():
    context = ContextBuilder(max_chars=4000, redactor=SecretRedactor()).build_runtime(
        system_constraints="Never escape workspace",
        task_request="Fix failing parser test",
        conversation_summaries=["Earlier: use pytest"],
        memory_records=[],
        tool_descriptions=["read_file(path)", "run_tests()"],
        latest_result="pytest failed at tests/test_parser.py:12",
        budget_summary="steps 1/20; tokens 100/10000",
    )
    assert context.index("Never escape workspace") < context.index("Fix failing parser test")
    assert "tests/test_parser.py:12" in context
    assert "read_file(path)" in context


def test_runtime_context_never_truncates_task_or_latest_error():
    context = ContextBuilder(max_chars=240, redactor=SecretRedactor()).build_runtime(
        system_constraints="SAFE",
        task_request="CURRENT-TASK",
        conversation_summaries=["old-" * 100],
        memory_records=[],
        tool_descriptions=["read_file(path)"],
        latest_result="LATEST-ERROR",
        budget_summary="steps 1/2",
    )
    assert "CURRENT-TASK" in context
    assert "LATEST-ERROR" in context
    assert len(context) <= 240


def test_runtime_context_redacts_external_strings():
    context = ContextBuilder(max_chars=4000, redactor=SecretRedactor()).build_runtime(
        system_constraints="Keep sk-secret-key safe",
        task_request="Fix auth using token=t0ken",
        conversation_summaries=["seen password=pw"],
        memory_records=[],
        tool_descriptions=["run_test(secret=sk-abc)"],
        latest_result="api_key=sk-other",
        budget_summary="steps 1/2",
    )
    assert "sk-secret-key" not in context
    assert "sk-abc" not in context
    assert "sk-other" not in context
    assert "t0ken" not in context
    assert "pw" not in context


def test_runtime_context_raises_when_mandatory_exceeds_limit_with_tools():
    """Tool truncation must terminate even when mandatory fields alone
    exceed max_chars (regression: previously infinite loop)."""
    builder = ContextBuilder(max_chars=60, redactor=SecretRedactor())
    with pytest.raises(ValueError, match="Cannot fit mandatory runtime context"):
        builder.build_runtime(
            system_constraints="S",
            task_request="T",
            conversation_summaries=[],
            memory_records=[],
            tool_descriptions=["x" * 100],
            latest_result="L",
            budget_summary="B",
        )


def test_runtime_context_drops_tool_section_when_description_halved_to_empty():
    """A tool description halved to empty is removed entirely; the
    assembly must not leave a dangling '## Available Tools' header."""
    builder = ContextBuilder(max_chars=70, redactor=SecretRedactor())
    context = builder.build_runtime(
        system_constraints="S",
        task_request="T",
        conversation_summaries=[],
        memory_records=[],
        tool_descriptions=["x" * 100],
        latest_result="L",
        budget_summary="B",
    )
    assert "## Available Tools" not in context
    assert len(context) <= 70


# ---------------------------------------------------------------------------
# Task 4 — loop integration: tool results carried into the next LLM context
# ---------------------------------------------------------------------------

from decimal import Decimal

from codeguard.loop import AgentLoop
from codeguard.state import AgentState
from codeguard.action import Action, ActionKind, LLMResponse
from codeguard.llm.mock import ScriptedMockLLM


def _response_for(action: Action) -> LLMResponse:
    return LLMResponse(
        content=action.raw or "",
        next_action=action,
        finish_reason="stop",
        model="mock",
        token_used=0,
        cost_used=Decimal("0"),
        raw_response="",
    )


def make_wired_test_loop(tmp_path, llm):
    """Fully-wired test loop: real context builder, registry, normalizer,
    rule engine, dispatcher, sensors, verifier, stop policy, redactor,
    and event sink.  Workspace root is the pytest tmp_path."""
    from codeguard.composition import CompositionRoot

    root = CompositionRoot(mode="test", workspace_root=str(tmp_path))
    loop = root.create_loop(session_id="ctx-t1")
    loop.llm = llm
    # write_file requires approval by default; keep every action ALLOW so
    # the scripted TOOL_CALLs reach the dispatcher boundary directly.
    loop.tool_registry.lookup("write_file").default_risk = "ALLOW"
    return loop


def test_tool_result_is_in_next_llm_context(tmp_path):
    llm = ScriptedMockLLM([
        _response_for(Action(
            kind=ActionKind.TOOL_CALL, tool_name="read_file",
            parameters={"path": "a.txt"}, raw="",
        )),
        _response_for(Action(
            kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="",
        )),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    (tmp_path / "a.txt").write_text("needle", encoding="utf-8")
    result = loop.start_task("t1", "Inspect a.txt", [])
    assert result.terminal_state is AgentState.COMPLETED
    assert "needle" in llm.received_contexts[1]


def test_first_context_contains_request_and_tool_descriptions(tmp_path):
    llm = ScriptedMockLLM([
        _response_for(Action(
            kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="",
        )),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    result = loop.start_task("t1", "Inspect a.txt", ["Earlier: use pytest"])
    assert result.terminal_state is AgentState.COMPLETED
    first = llm.received_contexts[0]
    assert "Inspect a.txt" in first
    assert "read_file(path)" in first
    assert "Earlier: use pytest" in first
