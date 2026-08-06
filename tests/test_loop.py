"""Tests for AgentLoop — explicit state machine (PLAN Tasks 2.2+2.3)."""

import pytest
from decimal import Decimal
from datetime import datetime

from codeguard.loop import AgentLoop
from codeguard.state import AgentState
from codeguard.action import Action, ActionKind, LLMResponse
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.guardrail import GuardrailDecision, GuardrailResult
from codeguard.guardrail.approval import ApprovalStatus, ApprovalResult


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _r(action: Action) -> LLMResponse:
    """Wrap an Action in an LLMResponse for ScriptedMockLLM."""
    return LLMResponse(
        content=action.raw or "",
        next_action=action,
        finish_reason="stop",
        model="mock",
        token_used=0,
        cost_used=Decimal("0"),
        raw_response="",
    )


# ---------------------------------------------------------------------------
# Fake components for state machine testing
# ---------------------------------------------------------------------------

class FakeGuardrail:
    """Scriptable guardrail that returns pre-configured decisions in order."""

    def __init__(self, decisions=None, recoverable=True):
        self._decisions = decisions or ["ALLOW"]
        self._index = 0
        self._recoverable = recoverable

    def evaluate(self, action):
        d = self._decisions[self._index % len(self._decisions)]
        self._index += 1
        from codeguard.action import NormalizedAction
        na = NormalizedAction(
            kind=action.kind,
            tool_name=action.tool_name,
            normalized_parameters=action.parameters,
            action_fingerprint="fp",
            original_raw=action.raw,
            normalized_at=datetime.now(),
        )
        return GuardrailResult(
            decision=getattr(GuardrailDecision, d) if isinstance(d, str) else d,
            rule_ids=[],
            reason_codes=[],
            human_readable_message="",
            recoverable=self._recoverable,
            normalized_action=na,
            action_fingerprint="fp",
        )


class FakeApproval:
    """Scriptable approval manager."""

    def __init__(self, decision=ApprovalStatus.APPROVED):
        self._decision = decision

    def wait_for_approval(self, action):
        return ApprovalResult(
            request_id="r1",
            decision=self._decision,
            validated_at=datetime.now(),
        )

    def create_request(self, action):
        return "r1"


class FakeToolDispatcher:
    """Always-succeed tool dispatcher."""

    def dispatch(self, action):
        from codeguard.tool import ToolResult
        return ToolResult(
            tool_name=action.tool_name or "",
            status="SUCCESS",
            output_summary="",
            diagnostics=[],
            exit_code=0,
            changed_files=[],
            duration=0.1,
            truncated=False,
            error_category=None,
            audit_id="audit-1",
        )


class FakeSensorRunner:
    """Always-pass sensor runner."""

    def run_all(self):
        from codeguard.feedback import FeedbackResult
        return [
            FeedbackResult(
                sensor_id="pytest",
                program="pytest",
                args=["."],
                status="PASSED",
                failure_category=None,
                exit_code=0,
                failure_fingerprint=None,
                validation_type="INTERMEDIATE",
                summary="ok",
                diagnostics=[],
                duration=0.1,
                retryable=False,
                raw_output_truncated="",
            )
        ]


class FakeFeedbackClassifier:
    """Identity classifier (pass-through)."""

    def classify(self, results):
        return results


class FakeObjectiveVerifier:
    """Scriptable objective verifier."""

    def __init__(self, passed=True):
        self._passed = passed

    def verify(self, state):
        return self._passed


from codeguard.stop import StopPolicy, StopDecision


class FakeStopPolicy:
    """Scriptable stop policy. Returns a StopDecision or None to continue."""

    def __init__(self, decision=None):
        self._decision = decision

    def evaluate(self, state):
        if self._decision is None:
            return None
        return StopDecision(True, self._decision, "fake")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_loop_initial_state():
    """AgentLoop starts in INITIALIZING."""
    mock = ScriptedMockLLM(responses=[])
    loop = AgentLoop(session_id="s1", llm=mock)
    assert loop.state.current_state == AgentState.INITIALIZING


def test_loop_initialize_transition():
    """initialize() transitions INITIALIZING → BUILDING_CONTEXT."""
    mock = ScriptedMockLLM(responses=[])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.initialize()
    assert loop.state.current_state == AgentState.BUILDING_CONTEXT


def test_loop_full_allow_sequence():
    """Full happy path: read_file → COMPLETE_REQUEST."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED
    assert result.steps_total >= 1


def test_loop_block_sequence():
    """Blocked action is skipped; agent recovers with a different action."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="delete_file",
                  parameters={"path": "/outside"}, raw="")),
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "safe"}, raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["BLOCK", "ALLOW"])
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED


def test_loop_approval_approve():
    """Approval granted → execution proceeds."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="write_file",
                  parameters={"path": "output.txt"}, raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["REQUEST_APPROVAL", "ALLOW"])
    loop.approval_manager = FakeApproval(decision=ApprovalStatus.APPROVED)
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED


def test_loop_approval_reject():
    """Approval rejected → CANCELLED."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="write_file",
                  parameters={"path": "output.txt"}, raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["REQUEST_APPROVAL"])
    loop.approval_manager = FakeApproval(decision=ApprovalStatus.REJECTED)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.CANCELLED


def test_loop_approval_timeout():
    """Approval timeout → CANCELLED."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="write_file",
                  parameters={"path": "output.txt"}, raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["REQUEST_APPROVAL"])
    loop.approval_manager = FakeApproval(decision=ApprovalStatus.TIMEOUT)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.CANCELLED


def test_loop_limit_reached():
    """Stop policy returns LIMIT_REACHED."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.stop_policy = FakeStopPolicy(decision=AgentState.LIMIT_REACHED)
    result = loop.run()
    assert result.terminal_state == AgentState.LIMIT_REACHED


def test_loop_failed():
    """Stop policy returns FAILED."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.stop_policy = FakeStopPolicy(decision=AgentState.FAILED)
    result = loop.run()
    assert result.terminal_state == AgentState.FAILED


def test_loop_complete_request_goes_to_final_validation():
    """COMPLETE_REQUEST → FINAL_VALIDATION → COMPLETED."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED


def test_loop_max_steps_limit_reached():
    """Without stop_policy, max_steps limit terminates loop as LIMIT_REACHED."""
    # LLM only returns TOOL_CALL — never COMPLETE_REQUEST
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw=""))
    ] * 10)  # more than max_steps
    loop = AgentLoop(session_id="s1", llm=mock, max_steps=3)
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    # No stop_policy injected — protection comes from max_steps
    result = loop.run()
    assert result.terminal_state == AgentState.LIMIT_REACHED
    assert result.steps_total == 3


def test_loop_stop_policy_completed_ignored():
    """stop_policy 'COMPLETED' does NOT bypass FINAL_VALIDATION."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    # stop_policy returns "COMPLETED" — but this should be ignored;
    # only FINAL_VALIDATION can produce COMPLETED
    loop.stop_policy = FakeStopPolicy(decision=AgentState.COMPLETED)
    result = loop.run()
    # COMPLETED must come from FINAL_VALIDATION, not stop_policy shortcut
    assert result.terminal_state == AgentState.COMPLETED
    # Verify the trace shows FINAL_VALIDATION before COMPLETED
    states = [t["to"] for t in loop._trace]
    final_idx = states.index(AgentState.COMPLETED)
    assert states[final_idx - 1] == AgentState.FINAL_VALIDATION


def test_loop_non_recoverable_block():
    """Non-recoverable BLOCK → FAILED (no retry path)."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="delete_file",
                  parameters={"path": "/etc/passwd"}, raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["BLOCK"], recoverable=False)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.FAILED