"""Integration tests: Governance-Driven Test Feedback Loop (治理驱动的测试反馈闭环).

Phase 14 — SPEC §3.1, §3.2, §3.3, §3.5, §10.1, §10.2, §10.3.

Each test demonstrates a complete end-to-end scenario using real Harness
components (AgentLoop, RuleEngine, Guardrail, ApprovalManager, FeedbackClassifier,
StopPolicy, ObjectiveVerifier) with ScriptedMockLLM and FakeClock at the
external boundaries.
"""

from decimal import Decimal
from codeguard.composition import CompositionRoot
from codeguard.state import AgentState
from codeguard.action import Action, ActionKind, LLMResponse
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.guardrail.engine import RuleEngine
from codeguard.guardrail.rules import WorkspaceBoundaryRule
from codeguard.guardrail import GuardrailDecision


def _make_response(action: Action, finish_reason: str = "stop") -> LLMResponse:
    """Create an LLMResponse wrapping an Action for ScriptedMockLLM."""
    return LLMResponse(
        content="mock",
        next_action=action,
        finish_reason=finish_reason,
        model="mock",
        token_used=0,
        cost_used=Decimal("0"),
        raw_response="",
    )


def test_scenario_a_block_then_feedback_then_complete():
    """BLOCK -> feedback -> change action -> COMPLETED.

    This is the core governance-driven test feedback loop scenario.
    Phase 1: LLM proposes dangerous action (delete_file outside workspace)
    Phase 2: Guardrail BLOCKs it
    Phase 3: Feedback is injected
    Phase 4: LLM proposes safe action
    Phase 5: Guardrail ALLOWs
    Phase 6: Action executes, COMPLETE_REQUEST -> FINAL_VALIDATION -> COMPLETED
    """
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-a")

    # Replace the default RuleEngine with one that has a real workspace boundary rule
    engine = RuleEngine()
    engine.add_rule(
        "workspace",
        WorkspaceBoundaryRule(workspace_root="/home/user/project").evaluate,
    )
    loop.rule_engine = engine

    # ScriptedMockLLM:
    # 1st call: dangerous action (delete_file outside workspace) -> BLOCKed
    # 2nd call: safe action (read_file inside workspace) -> ALLOWed
    # 3rd call: COMPLETE_REQUEST -> FINAL_VALIDATION -> COMPLETED
    loop.llm = ScriptedMockLLM(responses=[
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="delete_file",
            parameters={"path": "/etc/passwd"},
            raw="",
        )),
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="read_file",
            parameters={"path": "/home/user/project/README.md"},
            raw="",
        )),
        _make_response(Action(
            kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="",
        )),
    ])

    result = loop.run()

    # Verify terminal state
    assert result.terminal_state == AgentState.COMPLETED, (
        f"Expected COMPLETED, got {result.terminal_state}"
    )

    # Verify the BLOCK was recorded
    guardrail_decisions = result.guardrail_decisions
    assert len(guardrail_decisions) >= 2, (
        f"Expected at least 2 guardrail decisions, got {len(guardrail_decisions)}"
    )

    # First decision should be BLOCK
    assert guardrail_decisions[0].decision == GuardrailDecision.BLOCK, (
        f"Expected BLOCK, got {guardrail_decisions[0].decision}"
    )

    # Second decision should be ALLOW
    assert guardrail_decisions[1].decision == GuardrailDecision.ALLOW, (
        f"Expected ALLOW, got {guardrail_decisions[1].decision}"
    )

    # Verify the loop actually made progress (BLOCK didn't count as a step)
    assert result.llm_calls_total == 3, (
        f"Expected 3 LLM calls, got {result.llm_calls_total}"
    )

    # The dangerous action was NOT executed (steps_used only counts executed tools)
    assert result.steps_total == 1, (
        f"Expected 1 executed step (read_file), got {result.steps_total}"
    )


# ---------------------------------------------------------------------------
# Task 14.2: Scenario B — REQUEST_APPROVAL → approve/reject/timeout
# ---------------------------------------------------------------------------

from codeguard.guardrail.approval import ApprovalManager, ApprovalStatus, FakeClock


def _make_approval_rule():
    """Create a rule that always returns REQUEST_APPROVAL for any tool call."""
    def _evaluate(action):
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "approval_rule", "reason_codes": []}
        return {"decision": "REQUEST_APPROVAL", "rule_id": "approval_rule",
                "reason_codes": ["needs_approval"]}
    return _evaluate


def test_scenario_b_approve():
    """REQUEST_APPROVAL → approve → EXECUTING → COMPLETED.

    Approval is bound to session_id, request_id, and action_fingerprint.
    Only the originally requested action is executed after approval.
    """
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-b-approve")

    engine = RuleEngine()
    engine.add_rule("approval_rule", _make_approval_rule())
    loop.rule_engine = engine

    clock = FakeClock()
    loop.approval_manager = ApprovalManager(clock=clock, approval_timeout=60)

    loop.llm = ScriptedMockLLM(responses=[
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "output.txt"},
            raw="",
        )),
        _make_response(Action(
            kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="",
        )),
    ])

    # First run: should pause at AWAITING_APPROVAL
    result = loop.run()
    assert loop.state.current_state == AgentState.AWAITING_APPROVAL, (
        f"Expected AWAITING_APPROVAL, got {loop.state.current_state}"
    )
    assert loop.state.approval_request_id is not None
    assert result.terminal_state == AgentState.AWAITING_APPROVAL

    # Approve the request
    loop.resume_with_approval(
        request_id=loop.state.approval_request_id,
        session_id="scenario-b-approve",
        decision=ApprovalStatus.APPROVED,
        action_fingerprint=loop.state.pending_action.action_fingerprint,
    )

    # Second run: continue from AWAITING_APPROVAL → EXECUTING → ... → COMPLETED
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED, (
        f"Expected COMPLETED, got {result.terminal_state}"
    )
    assert result.steps_total >= 1  # tool was executed


def test_scenario_b_reject():
    """REQUEST_APPROVAL → reject → CANCELLED, zero tool executions."""
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-b-reject")

    engine = RuleEngine()
    engine.add_rule("approval_rule", _make_approval_rule())
    loop.rule_engine = engine

    clock = FakeClock()
    loop.approval_manager = ApprovalManager(clock=clock, approval_timeout=60)

    loop.llm = ScriptedMockLLM(responses=[
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "output.txt"},
            raw="",
        )),
    ])

    # First run: should pause at AWAITING_APPROVAL
    result = loop.run()
    assert loop.state.current_state == AgentState.AWAITING_APPROVAL

    # Reject
    loop.resume_with_approval(
        request_id=loop.state.approval_request_id,
        session_id="scenario-b-reject",
        decision=ApprovalStatus.REJECTED,
        action_fingerprint=loop.state.pending_action.action_fingerprint,
    )

    result = loop.run()
    assert result.terminal_state == AgentState.CANCELLED, (
        f"Expected CANCELLED, got {result.terminal_state}"
    )
    assert result.steps_total == 0  # tool was NOT executed


def test_scenario_b_timeout():
    """REQUEST_APPROVAL → timeout → CANCELLED, zero tool executions.

    Uses FakeClock to advance past the timeout without real waiting.
    """
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-b-timeout")

    engine = RuleEngine()
    engine.add_rule("approval_rule", _make_approval_rule())
    loop.rule_engine = engine

    clock = FakeClock()
    loop.approval_manager = ApprovalManager(clock=clock, approval_timeout=5)

    loop.llm = ScriptedMockLLM(responses=[
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "output.txt"},
            raw="",
        )),
    ])

    # First run: should pause at AWAITING_APPROVAL
    result = loop.run()
    assert loop.state.current_state == AgentState.AWAITING_APPROVAL
    request_id = loop.state.approval_request_id
    assert request_id is not None

    # Advance clock past timeout
    clock.advance(10)

    # Second run: should detect timeout → CANCELLED
    result = loop.run()
    assert result.terminal_state == AgentState.CANCELLED, (
        f"Expected CANCELLED, got {result.terminal_state}"
    )
    assert result.steps_total == 0  # tool was NOT executed


def test_scenario_b_wrong_fingerprint_rejected():
    """Approval with wrong action_fingerprint is rejected."""
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-b-wrong-fp")

    engine = RuleEngine()
    engine.add_rule("approval_rule", _make_approval_rule())
    loop.rule_engine = engine

    clock = FakeClock()
    loop.approval_manager = ApprovalManager(clock=clock, approval_timeout=60)

    loop.llm = ScriptedMockLLM(responses=[
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "output.txt"},
            raw="",
        )),
    ])

    result = loop.run()
    assert loop.state.current_state == AgentState.AWAITING_APPROVAL

    # Try to approve with wrong fingerprint
    import pytest
    with pytest.raises(ValueError, match="fingerprint"):
        loop.resume_with_approval(
            request_id=loop.state.approval_request_id,
            session_id="scenario-b-wrong-fp",
            decision=ApprovalStatus.APPROVED,
            action_fingerprint="wrong-fingerprint",
        )


def test_scenario_b_wrong_session_rejected():
    """Approval with wrong session_id is rejected."""
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-b-wrong-session")

    engine = RuleEngine()
    engine.add_rule("approval_rule", _make_approval_rule())
    loop.rule_engine = engine

    clock = FakeClock()
    loop.approval_manager = ApprovalManager(clock=clock, approval_timeout=60)

    loop.llm = ScriptedMockLLM(responses=[
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "output.txt"},
            raw="",
        )),
    ])

    result = loop.run()
    assert loop.state.current_state == AgentState.AWAITING_APPROVAL

    import pytest
    with pytest.raises(ValueError, match="Session"):
        loop.resume_with_approval(
            request_id=loop.state.approval_request_id,
            session_id="wrong-session",
            decision=ApprovalStatus.APPROVED,
            action_fingerprint=loop.state.pending_action.action_fingerprint,
        )


# ---------------------------------------------------------------------------
# Task 14.3: Scenario C — fail → classify → repair → COMPLETED
# ---------------------------------------------------------------------------

from codeguard.feedback import FeedbackResult


class ScriptedSensorRunner:
    """Returns pre-scripted FeedbackResult lists in order."""

    def __init__(self, responses: list[list[FeedbackResult]]):
        self._responses = responses
        self._call_count = 0

    def run_all(self) -> list[FeedbackResult]:
        if self._call_count >= len(self._responses):
            return []
        result = self._responses[self._call_count]
        self._call_count += 1
        return result


def test_scenario_c_fail_repair_cycle():
    """fail → classify → repair → COMPLETED.

    Demonstrates the feedback loop:
    Phase 1: LLM writes buggy code → sensor FAILED
    Phase 2: FeedbackClassifier categorizes → feedback injected
    Phase 3: LLM writes fixed code → sensor PASSED
    Phase 4: COMPLETE_REQUEST → FINAL_VALIDATION → COMPLETED
    """
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-c")

    # Scripted sensor runner: first call returns FAILED, second returns PASSED
    fail_result = FeedbackResult(
        sensor_id="pytest",
        program="python",
        args=["-m", "pytest"],
        status="FAILED",
        failure_category="TEST_ASSERTION_FAILURE",
        exit_code=1,
        failure_fingerprint="abc123",
        validation_type="INTERMEDIATE",
        summary="1 test failed: test_add",
        diagnostics=[
            {"file": "test_math.py", "line": 10, "message": "assert 1 == 2"}
        ],
        duration=0.5,
        retryable=True,
        raw_output_truncated="FAILED test_add - assert 1 == 2",
    )
    pass_result = FeedbackResult(
        sensor_id="pytest",
        program="python",
        args=["-m", "pytest"],
        status="PASSED",
        failure_category=None,
        exit_code=0,
        failure_fingerprint=None,
        validation_type="INTERMEDIATE",
        summary="All tests passed",
        diagnostics=[],
        duration=0.3,
        retryable=False,
        raw_output_truncated="1 passed",
    )

    loop.sensor_runner = ScriptedSensorRunner(
        responses=[[fail_result], [pass_result]]
    )

    # ScriptedMockLLM:
    # 1st call: write buggy code → fails test
    # 2nd call: write fixed code → passes test
    # 3rd call: COMPLETE_REQUEST → FINAL_VALIDATION → COMPLETED
    loop.llm = ScriptedMockLLM(responses=[
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "buggy.py", "content": "def add(a, b): return a - b"},
            raw="",
        )),
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "fixed.py", "content": "def add(a, b): return a + b"},
            raw="",
        )),
        _make_response(Action(
            kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="",
        )),
    ])

    result = loop.run()

    # Verify terminal state
    assert result.terminal_state == AgentState.COMPLETED, (
        f"Expected COMPLETED, got {result.terminal_state}"
    )

    # Verify feedback was collected
    assert len(result.feedback_results) >= 2, (
        f"Expected at least 2 feedback results, got {len(result.feedback_results)}"
    )

    # First feedback should be FAILED
    assert result.feedback_results[0].status == "FAILED", (
        f"Expected FAILED, got {result.feedback_results[0].status}"
    )
    assert result.feedback_results[0].failure_category == "TEST_FAILURE"

    # Second feedback should be PASSED
    assert result.feedback_results[1].status == "PASSED", (
        f"Expected PASSED, got {result.feedback_results[1].status}"
    )

    # Verify LLM calls: 3 (two write_file + one COMPLETE_REQUEST)
    assert result.llm_calls_total == 3, (
        f"Expected 3 LLM calls, got {result.llm_calls_total}"
    )

    # Verify steps: 2 (two write_file executions)
    assert result.steps_total == 2, (
        f"Expected 2 executed steps, got {result.steps_total}"
    )


# ---------------------------------------------------------------------------
# Task 14.4: No-progress detection → LIMIT_REACHED
# ---------------------------------------------------------------------------

from codeguard.stop import StopPolicy


def test_no_progress_repeated_action():
    """Repeated action_fingerprint → no_progress_threshold → LIMIT_REACHED.

    When the same action is proposed 3+ consecutive times, the
    StopPolicy detects no progress and terminates the loop.
    """
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="no-progress-action")

    # StopPolicy with no_progress_threshold=3
    loop.stop_policy = StopPolicy(
        max_steps=50, max_llm_calls=100, no_progress_threshold=3,
    )

    # Same action repeated 4 times
    same_action = _make_response(Action(
        kind=ActionKind.TOOL_CALL,
        tool_name="read_file",
        parameters={"path": "same.txt"},
        raw="",
    ))
    loop.llm = ScriptedMockLLM(responses=[same_action] * 5)

    result = loop.run()

    assert result.terminal_state == AgentState.LIMIT_REACHED, (
        f"Expected LIMIT_REACHED, got {result.terminal_state}"
    )
    # The loop should stop after 3+ consecutive same fingerprints
    # (GOVERNING appends fingerprint, StopPolicy checks after FEEDING_BACK)
    assert result.llm_calls_total >= 3, (
        f"Expected at least 3 LLM calls before stopping, got {result.llm_calls_total}"
    )


def test_no_progress_repeated_failure():
    """Repeated failure_fingerprint → no_progress_threshold → LIMIT_REACHED.

    When the same failure fingerprint appears 3+ consecutive times,
    the StopPolicy detects no progress and terminates the loop.
    """
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="no-progress-failure")

    loop.stop_policy = StopPolicy(
        max_steps=50, max_llm_calls=100, no_progress_threshold=3,
    )

    # Sensor that always returns FAILED with the same fingerprint
    fail_result = FeedbackResult(
        sensor_id="pytest",
        program="python",
        args=["-m", "pytest"],
        status="FAILED",
        failure_category="TEST_FAILURE",
        exit_code=1,
        failure_fingerprint="same_failure_fp",
        validation_type="INTERMEDIATE",
        summary="Always fails",
        diagnostics=[],
        duration=0.1,
        retryable=True,
        raw_output_truncated="FAILED",
    )
    loop.sensor_runner = ScriptedSensorRunner(
        responses=[[fail_result]] * 10
    )

    # LLM keeps proposing the same write action
    write_action = _make_response(Action(
        kind=ActionKind.TOOL_CALL,
        tool_name="write_file",
        parameters={"path": "buggy.py", "content": "bad"},
        raw="",
    ))
    loop.llm = ScriptedMockLLM(responses=[write_action] * 10)

    result = loop.run()

    assert result.terminal_state == AgentState.LIMIT_REACHED, (
        f"Expected LIMIT_REACHED, got {result.terminal_state}"
    )


def test_no_progress_non_consecutive_does_not_trigger():
    """Non-consecutive repeated fingerprints do NOT trigger LIMIT_REACHED.

    If the agent proposes different actions between repeats, the
    consecutive-run counter resets and the loop continues normally.
    """
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="no-progress-nonconsecutive")

    loop.stop_policy = StopPolicy(
        max_steps=50, max_llm_calls=100, no_progress_threshold=3,
    )

    # Alternating actions: A, B, A, B, A, COMPLETE
    # Fingerprint A appears 3 times but NOT consecutively
    loop.llm = ScriptedMockLLM(responses=[
        _make_response(Action(
            kind=ActionKind.TOOL_CALL, tool_name="read_file",
            parameters={"path": "a.txt"}, raw="",
        )),
        _make_response(Action(
            kind=ActionKind.TOOL_CALL, tool_name="read_file",
            parameters={"path": "b.txt"}, raw="",
        )),
        _make_response(Action(
            kind=ActionKind.TOOL_CALL, tool_name="read_file",
            parameters={"path": "a.txt"}, raw="",
        )),
        _make_response(Action(
            kind=ActionKind.TOOL_CALL, tool_name="read_file",
            parameters={"path": "b.txt"}, raw="",
        )),
        _make_response(Action(
            kind=ActionKind.TOOL_CALL, tool_name="read_file",
            parameters={"path": "a.txt"}, raw="",
        )),
        _make_response(Action(
            kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="",
        )),
    ])

    result = loop.run()

    # Should complete normally — non-consecutive repeats don't trigger
    assert result.terminal_state == AgentState.COMPLETED, (
        f"Expected COMPLETED, got {result.terminal_state}"
    )