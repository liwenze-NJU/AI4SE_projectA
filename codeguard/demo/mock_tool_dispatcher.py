"""Mock tool dispatcher for demo scenarios.

Records dispatched actions in memory; never executes real commands
or touches the host file system.
"""

from codeguard.action import Action, ActionKind
from codeguard.tool import ToolResult
from codeguard.demo.mock_fs import mock_fs


class MockToolDispatcher:
    """Deterministic dispatcher that records calls and returns mock results."""

    def __init__(self):
        self.calls: list[Action] = []

    def dispatch(self, action: Action) -> ToolResult:
        self.calls.append(action)
        params = action.parameters or {}
        path = params.get("path", "")
        status = "SUCCESS"
        if action.tool_name == "read_file":
            info = mock_fs.read_file(path)
            if info["status"] == "missing":
                status = "FAILURE"
            output = f"mock read of {path}"
        elif action.tool_name in ("write_file", "apply_patch"):
            content = params.get("content", "")
            mock_fs.write_file(path, content)
            output = f"mock write of {path}"
        elif action.tool_name == "run_tests":
            output = "mock tests: 0 passed, 0 failed"
        else:
            output = f"mock {action.tool_name}"
        return ToolResult(
            tool_name=action.tool_name or "",
            status=status,
            output_summary=output,
            diagnostics=[],
            exit_code=0 if status == "SUCCESS" else 1,
            changed_files=[path] if status == "SUCCESS" else [],
            duration=0.0,
            truncated=False,
            error_category=None,
            audit_id="mock",
        )


mock_tool_dispatcher = MockToolDispatcher()
