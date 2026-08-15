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


# ---------------------------------------------------------------------------
# T8-FIX7 — bounded current-task observation history
# ---------------------------------------------------------------------------

def test_two_file_reads_both_visible_in_next_context(tmp_path):
    """T8-FIX7 core: after reading file_a then file_b, the NEXT context
    contains BOTH files' latest content — the single-_latest_result
    overwrite bug is gone."""
    (tmp_path / "a.txt").write_text("CONTENT-A", encoding="utf-8")
    (tmp_path / "b.txt").write_text("CONTENT-B", encoding="utf-8")
    llm = ScriptedMockLLM([
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "a.txt"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "b.txt"}, raw="")),
        _response_for(Action(ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    result = loop.start_task("t1", "Read both files", [])
    assert result.terminal_state is AgentState.COMPLETED
    ctx = llm.received_contexts[2]
    assert "CONTENT-A" in ctx
    assert "CONTENT-B" in ctx


def test_read_a_b_a_keeps_both_observations(tmp_path):
    """T8-FIX7: read A→B→A keeps BOTH observations (no single-result
    overwrite), and A's newest read does not drop B."""
    (tmp_path / "a.txt").write_text("CONTENT-A", encoding="utf-8")
    (tmp_path / "b.txt").write_text("CONTENT-B", encoding="utf-8")
    llm = ScriptedMockLLM([
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "a.txt"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "b.txt"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "a.txt"}, raw="")),
        _response_for(Action(ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    result = loop.start_task("t1", "Read both files", [])
    assert result.terminal_state is AgentState.COMPLETED
    ctx = llm.received_contexts[3]
    assert "CONTENT-A" in ctx
    assert "CONTENT-B" in ctx


def test_observation_history_resets_per_task(tmp_path):
    """T8-FIX7: a NEW task starts with an empty observation history."""
    (tmp_path / "a.txt").write_text("CONTENT-A", encoding="utf-8")
    llm = ScriptedMockLLM([
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "a.txt"}, raw="")),
        _response_for(Action(ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
        _response_for(Action(ActionKind.COMPLETE_REQUEST, summary="done2", raw="")),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    loop.start_task("t1", "Read a.txt", [])
    result = loop.start_task("t2", "Second task", [])
    assert result.terminal_state is AgentState.COMPLETED
    assert "CONTENT-A" not in llm.received_contexts[2]


def test_observation_history_survives_approval_and_resume(tmp_path):
    """T8-FIX7: observations survive an approval pause + resume."""
    (tmp_path / "a.txt").write_text("CONTENT-A", encoding="utf-8")
    llm = ScriptedMockLLM([
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "a.txt"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "write_file",
                             {"path": "out.txt", "content": "x"}, raw="")),
        _response_for(Action(ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    loop.tool_registry.lookup("write_file").default_risk = "REQUEST_APPROVAL"
    result = loop.start_task("t1", "Read then write", [])
    assert result.terminal_state is AgentState.AWAITING_APPROVAL
    from codeguard.guardrail.approval import ApprovalStatus
    fp = loop.state.pending_action.action_fingerprint
    loop.resume_with_approval(
        request_id=loop.state.approval_request_id,
        session_id=loop.state.session_id,
        decision=ApprovalStatus.APPROVED,
        action_fingerprint=fp,
    )
    result = loop.run()
    assert result.terminal_state is AgentState.COMPLETED
    # The final decision's context still carries the pre-approval read.
    assert "CONTENT-A" in llm.received_contexts[-1]


def test_write_invalidates_stale_read_observation(tmp_path):
    """T8-FIX7: after a successful write to a file, the OLD read content
    for that file must no longer be offered to the model."""
    (tmp_path / "a.txt").write_text("OLD-CONTENT", encoding="utf-8")
    llm = ScriptedMockLLM([
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "a.txt"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "write_file",
                             {"path": "a.txt", "content": "NEW-CONTENT"}, raw="")),
        _response_for(Action(ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    loop.tool_registry.lookup("write_file").default_risk = "ALLOW"
    result = loop.start_task("t1", "Update a.txt", [])
    assert result.terminal_state is AgentState.COMPLETED
    ctx = llm.received_contexts[2]
    assert "OLD-CONTENT" not in ctx


def test_multi_file_real_flow_completes(tmp_path):
    """T8-FIX7 requirement 14: read value.py → read test_value.py →
    apply_patch value.py → apply_patch test_value.py → validation →
    COMPLETED — the full multi-file workflow."""
    (tmp_path / "value.py").write_text("VALUE: int = 2\n", encoding="utf-8")
    (tmp_path / "test_value.py").write_text(
        "from value import VALUE\n\ndef test_value():\n    assert VALUE == 2\n",
        encoding="utf-8")
    llm = ScriptedMockLLM([
        _response_for(Action(ActionKind.TOOL_CALL, "read_file",
                             {"path": "value.py"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "read_file",
                             {"path": "test_value.py"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "apply_patch",
                             {"path": "value.py", "old_string": "VALUE: int = 2",
                              "new_string": "VALUE: int = 3"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "apply_patch",
                             {"path": "test_value.py",
                              "old_string": "assert VALUE == 2",
                              "new_string": "assert VALUE == 3"}, raw="")),
        _response_for(Action(ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    loop.tool_registry.lookup("apply_patch").default_risk = "ALLOW"
    result = loop.start_task("t1", "Update both files to 3", [])
    assert result.terminal_state is AgentState.COMPLETED
    assert "VALUE: int = 3" in (tmp_path / "value.py").read_text(encoding="utf-8")
    assert "assert VALUE == 3" in (tmp_path / "test_value.py").read_text(encoding="utf-8")


def test_normal_multi_file_reads_not_falsely_stopped(tmp_path):
    """T8-FIX7 requirement 16: normal multi-file reading must NOT be
    misjudged as no-progress by the StopPolicy."""
    (tmp_path / "a.txt").write_text("CONTENT-A", encoding="utf-8")
    (tmp_path / "b.txt").write_text("CONTENT-B", encoding="utf-8")
    llm = ScriptedMockLLM([
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "a.txt"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "b.txt"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "a.txt"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "b.txt"}, raw="")),
        _response_for(Action(ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    result = loop.start_task("t1", "Read both files twice", [])
    assert result.terminal_state is AgentState.COMPLETED


def test_tool_failure_and_prior_observation_coexist(tmp_path):
    """T8-FIX7 requirement 9: a tool failure's message and the prior
    relevant file observation both appear in the next context."""
    (tmp_path / "a.txt").write_text("CONTENT-A", encoding="utf-8")
    llm = ScriptedMockLLM([
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "a.txt"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "missing.txt"}, raw="")),
        _response_for(Action(ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    result = loop.start_task("t1", "Read files", [])
    assert result.terminal_state is AgentState.COMPLETED
    ctx = llm.received_contexts[2]
    assert "CONTENT-A" in ctx          # prior observation survives
    assert "missing.txt" in ctx        # failure info present too


def test_observations_redact_secrets(tmp_path):
    """T8-FIX7 requirements 12/13: observation content passes through
    SecretRedactor before entering the context — credentials never leak."""
    (tmp_path / "secrets.txt").write_text(
        "api_key = sk-1111222233334444\npassword = hunter2\n", encoding="utf-8")
    llm = ScriptedMockLLM([
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "secrets.txt"}, raw="")),
        _response_for(Action(ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    result = loop.start_task("t1", "Read secrets.txt", [])
    assert result.terminal_state is AgentState.COMPLETED
    ctx = llm.received_contexts[1]
    assert "sk-1111222233334444" not in ctx
    assert "hunter2" not in ctx


def test_observation_budget_trims_deterministically(tmp_path):
    """T8-FIX7 requirement 10: entry and character budgets trim the
    OLDEST observations first; the newest ones survive."""
    llm = ScriptedMockLLM([])
    loop = make_wired_test_loop(tmp_path, llm)
    # Directly exercise the trim helper with synthetic observations.
    from codeguard.state import CurrentTaskObservation
    import hashlib
    for i in range(15):
        loop._observation_sequence += 1
        loop._observations.append(CurrentTaskObservation(
            tool_name="read_file",
            parameter_fingerprint=hashlib.sha256(f"f{i}".encode()).hexdigest(),
            safe_parameter_summary=f"path=f{i}.txt",
            status="SUCCESS",
            redacted_output="x" * 500,
            sequence=loop._observation_sequence,
        ))
    loop._trim_observations()
    # Both budgets hold: entry cap AND character cap (the character cap
    # is the binding constraint here — 15 × ~510 chars > 4000).
    assert len(loop._observations) <= loop._MAX_OBSERVATIONS
    total = sum(len(o.redacted_output) + len(o.safe_parameter_summary)
                for o in loop._observations)
    assert total <= loop._MAX_OBSERVATION_CHARS
    # Deterministic oldest-first trimming: the kept entries are the
    # NEWEST contiguous tail, in order.
    seqs = [o.sequence for o in loop._observations]
    assert seqs == sorted(seqs)
    assert seqs[-1] == 15          # newest observation always kept
    assert seqs[0] > 1             # oldest ones were trimmed
    assert len(seqs) < 15


def test_approval_resume_write_invalidates_stale_read(tmp_path):
    """T8-FIX7-FIX F2: the production default path — write_file at
    REQUEST_APPROVAL risk — must invalidate the stale read observation
    after approval resume (raw relative path vs normalized absolute
    path must both match)."""
    (tmp_path / "b.txt").write_text("OLD-CONTENT", encoding="utf-8")
    llm = ScriptedMockLLM([
        _response_for(Action(ActionKind.TOOL_CALL, "read_file", {"path": "b.txt"}, raw="")),
        _response_for(Action(ActionKind.TOOL_CALL, "write_file",
                             {"path": "b.txt", "content": "NEW-CONTENT"}, raw="")),
        _response_for(Action(ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    # The helper sets ALLOW; restore the PRODUCTION default so the write
    # genuinely pauses for approval.
    loop.tool_registry.lookup("write_file").default_risk = "REQUEST_APPROVAL"
    result = loop.start_task("t1", "Update b.txt", [])
    assert result.terminal_state is AgentState.AWAITING_APPROVAL
    from codeguard.guardrail.approval import ApprovalStatus
    fp = loop.state.pending_action.action_fingerprint
    loop.resume_with_approval(
        request_id=loop.state.approval_request_id,
        session_id=loop.state.session_id,
        decision=ApprovalStatus.APPROVED,
        action_fingerprint=fp,
    )
    result = loop.run()
    assert result.terminal_state is AgentState.COMPLETED
    ctx = llm.received_contexts[-1]
    assert "OLD-CONTENT" not in ctx
    assert "NEW-CONTENT" in ctx
