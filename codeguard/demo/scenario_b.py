"""Demo Scenario B — REQUEST_APPROVAL → approve / reject / timeout.

Flow (SPEC §3.9 demo scenario 2):
  LLM proposes a side-effect action → REQUEST_APPROVAL → AWAITING_APPROVAL
  → approve: execute → COMPLETED
  → reject: CANCELLED (zero executions)
  → timeout: CANCELLED (zero executions, FakeClock, no real waiting).

Uses only ScriptedMockLLM + mock boundaries.
"""

from decimal import Decimal
from codeguard.composition import CompositionRoot
from codeguard.loop import AgentLoop
from codeguard.action import Action, ActionKind, LLMResponse
from codeguard.state import AgentState
from codeguard.guardrail.engine import RuleEngine
from codeguard.guardrail.approval import ApprovalManager, ApprovalStatus, FakeClock
from codeguard.demo.mock_tool_dispatcher import mock_tool_dispatcher


def _make_response(action: Action) -> LLMResponse:
    return LLMResponse(
        content="mock",
        next_action=action,
        finish_reason="stop",
        model="mock",
        token_used=0,
        cost_used=Decimal("0"),
        raw_response="",
    )


def _make_approval_rule():
    """Rule that requests approval for any tool call (side-effect action)."""
    def _evaluate(action):
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "approval_rule", "reason_codes": []}
        return {"decision": "REQUEST_APPROVAL", "rule_id": "approval_rule",
                "reason_codes": ["needs_approval"]}
    return _evaluate


def _build_loop(session_id: str, approve: bool, timeout: bool) -> AgentLoop:
    root = CompositionRoot(mode="demo")
    loop: AgentLoop = root.create_loop(session_id=session_id)
    loop.llm._responses = [
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "src/auth.py", "content": "patch"},
            raw="",
        )),
    ]
    if approve:
        loop.llm._responses.append(
            _make_response(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""))
        )

    engine = RuleEngine()
    engine.add_rule("approval", _make_approval_rule())
    loop.rule_engine = engine

    clock = FakeClock()
    loop.approval_manager = ApprovalManager(clock=clock, approval_timeout=5)
    loop.tool_dispatcher = mock_tool_dispatcher

    # Record the clock so the caller can advance it for timeout tests
    loop._demo_clock = clock
    loop._demo_approve = approve
    loop._demo_timeout = timeout
    return loop


def _run_b(session_id: str, approve: bool, timeout: bool):
    loop = _build_loop(session_id, approve=approve, timeout=timeout)
    # First run: pause at AWAITING_APPROVAL
    result = loop.run()
    assert loop.state.current_state == AgentState.AWAITING_APPROVAL
    request_id = loop.state.approval_request_id
    pending = loop.state.pending_action
    assert request_id is not None
    assert pending is not None

    if timeout:
        loop._demo_clock.advance(10)
        # resume via run(): loop detects expiry through check_timeout_for_request
        return loop.run()

    if approve:
        loop.resume_with_approval(
            request_id=request_id,
            session_id=session_id,
            decision=ApprovalStatus.APPROVED,
            action_fingerprint=pending.action_fingerprint,
        )
    else:
        loop.resume_with_approval(
            request_id=request_id,
            session_id=session_id,
            decision=ApprovalStatus.REJECTED,
            action_fingerprint=pending.action_fingerprint,
        )
    return loop.run()


def run_scenario_b_approve():
    return _run_b("demo-b-approve", approve=True, timeout=False)


def run_scenario_b_reject():
    return _run_b("demo-b-reject", approve=False, timeout=False)


def run_scenario_b_timeout():
    return _run_b("demo-b-timeout", approve=False, timeout=True)
