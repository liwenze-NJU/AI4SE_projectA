from datetime import datetime
from decimal import Decimal
from codeguard.state import AgentState
from codeguard.action import ActionKind, NormalizedAction
from codeguard.guardrail import GuardrailDecision
from codeguard.guardrail.approval import ApprovalStatus


def test_session_state_creation():
    from codeguard.state import SessionState
    na = NormalizedAction(kind=ActionKind.TOOL_CALL, tool_name="read_file", normalized_parameters={}, action_fingerprint="fp", original_raw="", normalized_at=datetime.now())
    ss = SessionState(
        session_id="s1",
        current_state=AgentState.INITIALIZING,
        pending_action=na,
        guardrail_decision=None,
        approval_request_id=None,
        steps_used=0,
        llm_calls_used=0,
        token_used=0,
        cost_used=Decimal("0"),
        action_fingerprint_history=[],
        failure_fingerprint_history=[],
        started_at=datetime.now()
    )
    assert ss.session_id == "s1"
    assert ss.current_state == AgentState.INITIALIZING
    assert ss.steps_used == 0
    assert ss.cost_used == Decimal("0")


def test_session_result_creation():
    from codeguard.state import SessionResult
    sr = SessionResult(
        session_id="s1",
        terminal_state=AgentState.COMPLETED,
        steps_total=5,
        llm_calls_total=3,
        token_total=100,
        cost_total=Decimal("0.01"),
        duration=10.0,
        guardrail_decisions=[],
        feedback_results=[],
        trace=[],
        error=None
    )
    assert sr.terminal_state == AgentState.COMPLETED
    assert sr.steps_total == 5
    assert sr.error is None


def test_guardrail_result_with_enum():
    from codeguard.guardrail import GuardrailResult
    na = NormalizedAction(kind=ActionKind.TOOL_CALL, tool_name="read_file", normalized_parameters={}, action_fingerprint="fp", original_raw="", normalized_at=datetime.now())
    gr = GuardrailResult(
        decision=GuardrailDecision.BLOCK,
        rule_ids=["R1"],
        reason_codes=["out_of_bounds"],
        human_readable_message="Blocked: path outside workspace",
        recoverable=False,
        normalized_action=na,
        action_fingerprint="fp"
    )
    assert gr.decision == GuardrailDecision.BLOCK
    assert "out_of_bounds" in gr.reason_codes


def test_approval_request_with_enum():
    from codeguard.guardrail.approval import ApprovalRequest
    na = NormalizedAction(kind=ActionKind.TOOL_CALL, tool_name="write_file", normalized_parameters={}, action_fingerprint="fp", original_raw="", normalized_at=datetime.now())
    ar = ApprovalRequest(
        request_id="r1",
        session_id="s1",
        normalized_action=na,
        action_fingerprint="fp",
        matched_rules=["R2"],
        risk_summary="Writing to system directory",
        workspace_snapshot={},
        created_at=datetime.now(),
        expires_at=datetime.now()
    )
    assert ar.request_id == "r1"
    assert ar.status == ApprovalStatus.PENDING


def test_approval_result_with_enum():
    from codeguard.guardrail.approval import ApprovalResult, ApprovalStatus
    ar = ApprovalResult(request_id="r1", decision=ApprovalStatus.APPROVED, validated_at=datetime.now())
    assert ar.decision == ApprovalStatus.APPROVED