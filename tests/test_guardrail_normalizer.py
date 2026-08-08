import pytest
from datetime import datetime
from codeguard.action import Action, ActionKind
from codeguard.guardrail.normalizer import ActionNormalizer, SchemaValidator


def test_normalize_path():
    normalizer = ActionNormalizer(workspace_root="/home/user/project")
    action = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "src/main.py"})
    na = normalizer.normalize(action)
    assert na.action_fingerprint is not None
    assert len(na.action_fingerprint) > 0


def test_normalize_fingerprint_consistent():
    normalizer = ActionNormalizer(workspace_root="/home/user/project")
    a1 = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "src/main.py"})
    a2 = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "src/main.py"})
    fp1 = normalizer.normalize(a1).action_fingerprint
    fp2 = normalizer.normalize(a2).action_fingerprint
    assert fp1 == fp2


def test_normalize_fingerprint_different():
    normalizer = ActionNormalizer(workspace_root="/home/user/project")
    a1 = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "src/main.py"})
    a2 = Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "src/main.py"})
    fp1 = normalizer.normalize(a1).action_fingerprint
    fp2 = normalizer.normalize(a2).action_fingerprint
    assert fp1 != fp2


def test_schema_validator_valid():
    validator = SchemaValidator()
    schema = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    params = {"path": "main.py"}
    validator.validate(params, schema)  # should not raise


def test_schema_validator_invalid():
    validator = SchemaValidator()
    schema = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    params = {}
    with pytest.raises(ValueError, match="Missing required"):
        validator.validate(params, schema)


def test_normalize_complete_request():
    normalizer = ActionNormalizer(workspace_root="/home/user/project")
    action = Action(kind=ActionKind.COMPLETE_REQUEST, summary="done")
    na = normalizer.normalize(action)
    assert na.action_fingerprint == "COMPLETE_REQUEST"