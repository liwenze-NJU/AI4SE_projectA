from codeguard.demo.scenario_b import (
    run_scenario_b_approve,
    run_scenario_b_reject,
    run_scenario_b_timeout,
)
from codeguard.state import AgentState


def test_scenario_b_approve():
    """REQUEST_APPROVAL → approve → execute → COMPLETED."""
    result = run_scenario_b_approve()
    assert result.terminal_state == AgentState.COMPLETED
    assert result.steps_total >= 1  # tool executed after approval


def test_scenario_b_reject():
    """REQUEST_APPROVAL → reject → CANCELLED, zero tool executions."""
    result = run_scenario_b_reject()
    assert result.terminal_state == AgentState.CANCELLED
    assert result.steps_total == 0


def test_scenario_b_timeout():
    """REQUEST_APPROVAL → timeout → CANCELLED, zero tool executions."""
    result = run_scenario_b_timeout()
    assert result.terminal_state == AgentState.CANCELLED
    assert result.steps_total == 0


def test_scenario_b_approval_was_requested():
    """The pending action must have gone through REQUEST_APPROVAL first."""
    from codeguard.guardrail import GuardrailDecision
    result = run_scenario_b_approve()
    decisions = result.guardrail_decisions
    assert len(decisions) >= 1
    assert decisions[0].decision == GuardrailDecision.REQUEST_APPROVAL
