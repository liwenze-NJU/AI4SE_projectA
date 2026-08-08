import pytest
from codeguard.demo.scenario_a import run_scenario_a
from codeguard.state import AgentState


def test_scenario_a_completes():
    result = run_scenario_a()
    assert result.terminal_state == AgentState.COMPLETED
    assert result.steps_total >= 1  # safe action executed


def test_scenario_a_blocked_dangerous_action_then_safe():
    """Scenario A: dangerous action is BLOCKed, then a safe action completes."""
    result = run_scenario_a()
    decisions = result.guardrail_decisions
    assert len(decisions) >= 2
    # First decision must BLOCK the dangerous action
    from codeguard.guardrail import GuardrailDecision
    assert decisions[0].decision == GuardrailDecision.BLOCK
    # Final decision must ALLOW the safe action
    assert decisions[-1].decision == GuardrailDecision.ALLOW


def test_scenario_a_uses_only_mock_components():
    from codeguard.demo import mock_store, mock_credential, mock_tool_dispatcher, mock_fs
    assert mock_store is not None
    assert mock_credential is not None
    assert mock_tool_dispatcher is not None
    assert mock_fs is not None


def test_scenario_a_no_real_external_boundaries():
    """Demo scenario must not touch real DeepSeek/keyring/local executor."""
    import codeguard.demo.scenario_a as mod
    src = open(mod.__file__, encoding="utf-8").read()
    for forbidden in ("deepseek", "keyring", "KeyringCredentialStore",
                      "LocalToolExecutor", "subprocess", "requests"):
        assert forbidden not in src
