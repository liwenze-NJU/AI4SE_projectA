import pytest
from datetime import datetime
from decimal import Decimal
from dataclasses import FrozenInstanceError
from codeguard.action import ActionKind, Action, NormalizedAction, LLMResponse


def test_action_kind_enum():
    assert ActionKind.TOOL_CALL.value == "tool_call"
    assert ActionKind.COMPLETE_REQUEST.value == "complete"


def test_action_creation():
    action = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "x"}, raw="")
    assert action.tool_name == "read_file"
    assert action.parameters == {"path": "x"}
    assert action.kind == ActionKind.TOOL_CALL


def test_action_complete_request():
    action = Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")
    assert action.kind == ActionKind.COMPLETE_REQUEST
    assert action.tool_name is None


def test_normalized_action_immutable():
    na = NormalizedAction(
        kind=ActionKind.TOOL_CALL,
        tool_name="read_file",
        normalized_parameters={"path": "/abs/x"},
        action_fingerprint="abc123",
        original_raw="",
        normalized_at=datetime.now()
    )
    assert na.action_fingerprint == "abc123"
    with pytest.raises(FrozenInstanceError):
        na.action_fingerprint = "new_fp"


def test_llm_response_creation():
    action = Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")
    response = LLMResponse(
        content="",
        next_action=action,
        finish_reason="stop",
        model="mock",
        token_used=0,
        cost_used=Decimal("0"),
        raw_response=""
    )
    assert response.finish_reason == "stop"
    assert response.next_action.kind == ActionKind.COMPLETE_REQUEST