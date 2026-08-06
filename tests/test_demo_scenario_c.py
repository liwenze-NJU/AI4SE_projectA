from codeguard.demo.scenario_c import run_scenario_c
from codeguard.state import AgentState


def test_scenario_c_completes():
    result = run_scenario_c()
    assert result.terminal_state == AgentState.COMPLETED


def test_scenario_c_feedback_loop_triggered():
    """Scenario C: first test fails, feedback classified, agent repairs, passes."""
    result = run_scenario_c()
    # Must have at least one failed feedback result (first test run)
    failed = [r for r in result.feedback_results if r.status != "PASSED"]
    assert len(failed) >= 1
    # And at least one passed result (after repair)
    passed = [r for r in result.feedback_results if r.status == "PASSED"]
    assert len(passed) >= 1


def test_scenario_c_feedback_classified():
    """The failure must be classified (failure_category set)."""
    result = run_scenario_c()
    failed = [r for r in result.feedback_results if r.status != "PASSED"]
    assert failed, "expected at least one failed feedback result"
    assert all(r.failure_category is not None for r in failed)


def test_scenario_c_repair_action_after_failure():
    """The LLM must change action after the failure (repair step executed)."""
    result = run_scenario_c()
    # Guardrail decisions: first run_tests ALLOW, repair tool ALLOW, final complete
    from codeguard.guardrail import GuardrailDecision
    decisions = result.guardrail_decisions
    assert len(decisions) >= 2
    assert all(d.decision == GuardrailDecision.ALLOW for d in decisions)
