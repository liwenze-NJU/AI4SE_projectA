import pytest
from decimal import Decimal
from codeguard.llm.client import LLMClient
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.action import Action, ActionKind, LLMResponse


def test_llm_client_is_protocol():
    """LLMClient is a Protocol — ScriptedMockLLM is usable where LLMClient is expected."""
    mock = ScriptedMockLLM(responses=[])
    assert isinstance(mock, LLMClient)


def test_scripted_mock_llm_returns_scripted_responses():
    action = Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")
    response = LLMResponse(
        content="task complete",
        next_action=action,
        finish_reason="stop",
        model="mock",
        token_used=10,
        cost_used=Decimal(0),
        raw_response=""
    )
    mock = ScriptedMockLLM(responses=[response])
    result = mock.generate("session-1", "context")
    assert result is response
    assert result.finish_reason == "stop"
    assert result.next_action.kind == ActionKind.COMPLETE_REQUEST


def test_scripted_mock_llm_raises_when_empty():
    mock = ScriptedMockLLM(responses=[])
    with pytest.raises(IndexError, match="No more scripted responses"):
        mock.generate("session-1", "context")


def test_scripted_mock_llm_iterates_in_order():
    action1 = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={}, raw="")
    action2 = Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")
    r1 = LLMResponse(content="first", next_action=action1, finish_reason="tool_calls", model="mock", token_used=5, cost_used=Decimal(0), raw_response="")
    r2 = LLMResponse(content="second", next_action=action2, finish_reason="stop", model="mock", token_used=5, cost_used=Decimal(0), raw_response="")
    mock = ScriptedMockLLM(responses=[r1, r2])
    result1 = mock.generate("session-1", "context")
    result2 = mock.generate("session-1", "context")
    assert result1.content == "first"
    assert result2.content == "second"