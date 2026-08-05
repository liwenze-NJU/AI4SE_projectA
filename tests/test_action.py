import pytest
from datetime import datetime
from decimal import Decimal
from dataclasses import FrozenInstanceError
from codeguard.action import ActionKind, Action, NormalizedAction, LLMResponse, ActionParser


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


# ---------------------------------------------------------------------------
# ActionParser tests (Task 2.4)
# ---------------------------------------------------------------------------

import json


def test_action_parser_tool_call():
    parser = ActionParser()
    raw = json.dumps({"action": "tool_call", "tool": "read_file",
                      "parameters": {"path": "main.py"}})
    action = parser.parse(raw)
    assert action.kind == ActionKind.TOOL_CALL
    assert action.tool_name == "read_file"
    assert action.parameters == {"path": "main.py"}


def test_action_parser_complete_request():
    parser = ActionParser()
    raw = json.dumps({"action": "complete", "summary": "Task finished"})
    action = parser.parse(raw)
    assert action.kind == ActionKind.COMPLETE_REQUEST
    assert action.summary == "Task finished"


def test_action_parser_invalid_json():
    parser = ActionParser()
    with pytest.raises(ValueError, match="Failed to parse action"):
        parser.parse("not json")


def test_action_parser_missing_action_field():
    parser = ActionParser()
    with pytest.raises(ValueError, match="Missing 'action' field"):
        parser.parse(json.dumps({"tool": "read_file"}))


def test_action_parser_unknown_action_type():
    parser = ActionParser()
    with pytest.raises(ValueError, match="Unknown action type"):
        parser.parse(json.dumps({"action": "delete_file", "path": "/x"}))


def test_action_parser_non_dict_json():
    """JSON that parses to a non-dict type must raise ValueError, not crash."""
    parser = ActionParser()
    for bad_input in ['"just a string"', '42', '[]', 'null']:
        with pytest.raises(ValueError, match="Expected a JSON object"):
            parser.parse(bad_input)


def test_action_parser_missing_optional_fields():
    """TOOL_CALL without tool/parameters defaults to None, not empty string/dict."""
    parser = ActionParser()
    raw = json.dumps({"action": "tool_call"})
    action = parser.parse(raw)
    assert action.kind == ActionKind.TOOL_CALL
    assert action.tool_name is None
    assert action.parameters is None


def test_action_parser_complete_without_summary():
    """COMPLETE_REQUEST without summary defaults to None."""
    parser = ActionParser()
    raw = json.dumps({"action": "complete"})
    action = parser.parse(raw)
    assert action.kind == ActionKind.COMPLETE_REQUEST
    assert action.summary is None