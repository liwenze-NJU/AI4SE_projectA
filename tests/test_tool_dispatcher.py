import pytest
from pathlib import Path
from codeguard.tool import ToolDefinition, ToolResult
from codeguard.tool.registry import ToolRegistry
from codeguard.tool.dispatcher import ToolDispatcher
from codeguard.action import Action, ActionKind


@pytest.fixture
def temp_workspace(tmp_path):
    return tmp_path


def test_dispatch_read_file(temp_workspace):
    registry = ToolRegistry()
    from codeguard.tool.file_tools import read_file
    td = ToolDefinition(
        name="read_file",
        description="Read file",
        parameters_schema={},
        handler=read_file,
        category="FILE",
        side_effect=False,
        default_risk="ALLOW",
        supported_modes=["TEST"],
    )
    registry.register(td)
    dispatcher = ToolDispatcher(registry, workspace_root=str(temp_workspace))
    f = temp_workspace / "test.txt"
    f.write_text("content")
    action = Action(
        kind=ActionKind.TOOL_CALL,
        tool_name="read_file",
        parameters={"path": str(f)},
    )
    result = dispatcher.dispatch(action)
    assert isinstance(result, ToolResult)
    assert result.status == "SUCCESS"


def test_dispatch_unknown_tool(temp_workspace):
    registry = ToolRegistry()
    dispatcher = ToolDispatcher(registry, workspace_root=str(temp_workspace))
    action = Action(kind=ActionKind.TOOL_CALL, tool_name="nonexistent")
    with pytest.raises(KeyError):
        dispatcher.dispatch(action)


def test_dispatch_applies_secret_redactor(temp_workspace):
    registry = ToolRegistry()
    from codeguard.tool.file_tools import read_file
    td = ToolDefinition(
        name="read_file",
        description="Read file",
        parameters_schema={},
        handler=read_file,
        category="FILE",
        side_effect=False,
        default_risk="ALLOW",
        supported_modes=["TEST"],
    )
    registry.register(td)
    from codeguard.secret import SecretRedactor
    dispatcher = ToolDispatcher(
        registry,
        workspace_root=str(temp_workspace),
        secret_redactor=SecretRedactor(),
    )
    f = temp_workspace / "secret.txt"
    f.write_text("api_key = sk-1234567890abcdef")
    action = Action(
        kind=ActionKind.TOOL_CALL,
        tool_name="read_file",
        parameters={"path": str(f)},
    )
    result = dispatcher.dispatch(action)
    assert "sk-1234567890abcdef" not in result.output_summary


def test_dispatch_handles_permission_error(temp_workspace):
    registry = ToolRegistry()
    from codeguard.tool.file_tools import read_file
    td = ToolDefinition(
        name="read_file",
        description="Read file",
        parameters_schema={},
        handler=read_file,
        category="FILE",
        side_effect=False,
        default_risk="ALLOW",
        supported_modes=["TEST"],
    )
    registry.register(td)
    dispatcher = ToolDispatcher(registry, workspace_root=str(temp_workspace))
    outside = Path("/tmp") / "secret.txt"
    action = Action(
        kind=ActionKind.TOOL_CALL,
        tool_name="read_file",
        parameters={"path": str(outside)},
    )
    result = dispatcher.dispatch(action)
    assert result.status == "FAILURE"
    assert result.error_category == "WORKSPACE_VIOLATION"


def test_dispatch_output_truncated(temp_workspace):
    registry = ToolRegistry()
    from codeguard.tool.file_tools import read_file
    td = ToolDefinition(
        name="read_file",
        description="Read file",
        parameters_schema={},
        handler=read_file,
        category="FILE",
        side_effect=False,
        default_risk="ALLOW",
        supported_modes=["TEST"],
    )
    registry.register(td)
    dispatcher = ToolDispatcher(registry, workspace_root=str(temp_workspace))
    f = temp_workspace / "big.txt"
    f.write_text("x" * 2000)
    action = Action(
        kind=ActionKind.TOOL_CALL,
        tool_name="read_file",
        parameters={"path": str(f)},
    )
    result = dispatcher.dispatch(action)
    assert len(result.output_summary) <= 1000
    assert result.truncated is True