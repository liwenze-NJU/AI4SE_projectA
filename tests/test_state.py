from codeguard.state import AgentState


def test_agent_state_has_13_values():
    """SPEC: 13 observable states. FINALIZING is a lifecycle cleanup, not counted."""
    values = [s.value for s in AgentState]
    assert len(values) == 13
    assert "initializing" in values
    assert "building_context" in values
    assert "deciding" in values
    assert "governing" in values
    assert "awaiting_approval" in values
    assert "executing" in values
    assert "intermediate_validation" in values
    assert "final_validation" in values
    assert "feeding_back" in values
    assert "completed" in values
    assert "failed" in values
    assert "cancelled" in values
    assert "limit_reached" in values


def test_agent_state_terminal():
    assert AgentState.COMPLETED.value == "completed"
    assert AgentState.FAILED.value == "failed"
    assert AgentState.CANCELLED.value == "cancelled"
    assert AgentState.LIMIT_REACHED.value == "limit_reached"


def test_agent_state_running():
    assert AgentState.INITIALIZING.value == "initializing"
    assert AgentState.BUILDING_CONTEXT.value == "building_context"
    assert AgentState.DECIDING.value == "deciding"
    assert AgentState.GOVERNING.value == "governing"
    assert AgentState.AWAITING_APPROVAL.value == "awaiting_approval"
    assert AgentState.EXECUTING.value == "executing"
    assert AgentState.INTERMEDIATE_VALIDATION.value == "intermediate_validation"
    assert AgentState.FINAL_VALIDATION.value == "final_validation"
    assert AgentState.FEEDING_BACK.value == "feeding_back"