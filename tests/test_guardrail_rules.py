import pytest
from datetime import datetime
from pathlib import Path
from codeguard.action import ActionKind, NormalizedAction
from codeguard.guardrail.rules import (
    WorkspaceBoundaryRule,
    CredentialLeakRule,
    UnregisteredToolRule,
    ModeRestrictionRule,
)
from codeguard.tool.registry import ToolRegistry
from codeguard.tool import ToolDefinition


def _make_na(tool_name="read_file", params=None):
    return NormalizedAction(
        kind=ActionKind.TOOL_CALL,
        tool_name=tool_name,
        normalized_parameters=params or {},
        action_fingerprint="fp",
        original_raw="",
        normalized_at=datetime.now(),
    )


def _make_complete():
    return NormalizedAction(
        kind=ActionKind.COMPLETE_REQUEST,
        tool_name=None,
        normalized_parameters={},
        action_fingerprint="COMPLETE_REQUEST",
        original_raw="",
        normalized_at=datetime.now(),
    )


# ── WorkspaceBoundaryRule ────────────────────────────────────────────

class TestWorkspaceBoundaryRule:
    def test_allows_path_inside_workspace(self):
        rule = WorkspaceBoundaryRule(workspace_root="/home/user/project")
        na = _make_na(params={"path": "/home/user/project/src/main.py"})
        assert rule.evaluate(na)["decision"] == "ALLOW"

    def test_blocks_path_outside_workspace(self):
        rule = WorkspaceBoundaryRule(workspace_root="/home/user/project")
        na = _make_na(params={"path": "/etc/passwd"})
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_blocks_dotdot_escape(self):
        rule = WorkspaceBoundaryRule(workspace_root="/home/user/project")
        na = _make_na(params={"path": "/home/user/project/../../etc/passwd"})
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_blocks_name_prefix_bypass(self):
        rule = WorkspaceBoundaryRule(workspace_root="/home/user/project")
        na = _make_na(params={"path": "/home/user/project-evil/secret.txt"})
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_allows_no_path_param(self):
        rule = WorkspaceBoundaryRule(workspace_root="/home/user/project")
        na = _make_na(tool_name="list_directory", params={})
        assert rule.evaluate(na)["decision"] == "ALLOW"

    def test_allows_complete_request(self):
        rule = WorkspaceBoundaryRule(workspace_root="/home/user/project")
        assert rule.evaluate(_make_complete())["decision"] == "ALLOW"

    def test_handles_windows_paths(self):
        rule = WorkspaceBoundaryRule(workspace_root=r"C:\Users\dev\project")
        na = _make_na(params={"path": r"C:\Users\dev\project\src\main.py"})
        assert rule.evaluate(na)["decision"] == "ALLOW"

    def test_blocks_windows_outside_path(self):
        rule = WorkspaceBoundaryRule(workspace_root=r"C:\Users\dev\project")
        na = _make_na(params={"path": r"C:\Windows\System32\config"})
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_blocks_windows_prefix_bypass(self):
        rule = WorkspaceBoundaryRule(workspace_root=r"C:\Users\dev\project")
        na = _make_na(params={"path": r"C:\Users\dev\project-data\secret"})
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_blocks_windows_dotdot_escape(self):
        rule = WorkspaceBoundaryRule(workspace_root=r"C:\Users\dev\project")
        na = _make_na(params={"path": r"C:\Users\dev\project\..\..\Windows\secret"})
        assert rule.evaluate(na)["decision"] == "BLOCK"


# ── CredentialLeakRule ───────────────────────────────────────────────

class TestCredentialLeakRule:
    def test_allows_normal_content(self):
        rule = CredentialLeakRule()
        na = _make_na(tool_name="write_file", params={"path": "out.txt", "content": "hello world"})
        assert rule.evaluate(na)["decision"] == "ALLOW"

    def test_blocks_sk_api_key(self):
        rule = CredentialLeakRule()
        na = _make_na(tool_name="write_file", params={"path": "out.txt", "content": "api_key = sk-1234567890abcdef"})
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_blocks_api_key_assignment(self):
        rule = CredentialLeakRule()
        na = _make_na(tool_name="write_file", params={"path": "out.txt", "content": "api_key=abc123"})
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_blocks_password_in_content(self):
        rule = CredentialLeakRule()
        na = _make_na(tool_name="write_file", params={"path": "out.txt", "content": 'password = "hunter2"'})
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_blocks_secret_in_content(self):
        rule = CredentialLeakRule()
        na = _make_na(tool_name="write_file", params={"path": "out.txt", "content": "secret: abc123"})
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_blocks_token_in_content(self):
        rule = CredentialLeakRule()
        na = _make_na(tool_name="write_file", params={"path": "out.txt", "content": "token=ghp_abc123"})
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_allows_safe_parameters(self):
        rule = CredentialLeakRule()
        na = _make_na(tool_name="read_file", params={"path": "main.py"})
        assert rule.evaluate(na)["decision"] == "ALLOW"

    def test_allows_complete_request(self):
        rule = CredentialLeakRule()
        assert rule.evaluate(_make_complete())["decision"] == "ALLOW"

    def test_checks_all_param_values(self):
        rule = CredentialLeakRule()
        na = _make_na(tool_name="write_file", params={"path": "out.txt", "content": "normal", "header": "api_key: sk-deadbeef"})
        assert rule.evaluate(na)["decision"] == "BLOCK"


# ── UnregisteredToolRule ─────────────────────────────────────────────

class TestUnregisteredToolRule:
    def test_allows_registered_tool(self):
        registry = ToolRegistry()
        td = ToolDefinition(
            name="read_file", description="", parameters_schema={},
            handler=lambda: None, category="FILE", side_effect=False,
            default_risk="ALLOW", supported_modes=["TEST"],
        )
        registry.register(td)
        rule = UnregisteredToolRule(registry)
        na = _make_na(tool_name="read_file")
        assert rule.evaluate(na)["decision"] == "ALLOW"

    def test_blocks_unregistered_tool(self):
        registry = ToolRegistry()
        rule = UnregisteredToolRule(registry)
        na = _make_na(tool_name="unknown_tool")
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_allows_complete_request(self):
        registry = ToolRegistry()
        rule = UnregisteredToolRule(registry)
        assert rule.evaluate(_make_complete())["decision"] == "ALLOW"


# ── ModeRestrictionRule ──────────────────────────────────────────────

class TestModeRestrictionRule:
    def test_allows_read_file_in_demo(self):
        rule = ModeRestrictionRule(mode="demo")
        na = _make_na(tool_name="read_file")
        assert rule.evaluate(na)["decision"] == "ALLOW"

    def test_blocks_run_process_in_demo(self):
        rule = ModeRestrictionRule(mode="demo")
        na = _make_na(tool_name="run_process")
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_blocks_write_file_in_demo(self):
        rule = ModeRestrictionRule(mode="demo")
        na = _make_na(tool_name="write_file")
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_blocks_delete_file_in_demo(self):
        rule = ModeRestrictionRule(mode="demo")
        na = _make_na(tool_name="delete_file")
        assert rule.evaluate(na)["decision"] == "BLOCK"

    def test_allows_all_in_full_mode(self):
        rule = ModeRestrictionRule(mode="full")
        na = _make_na(tool_name="run_process")
        assert rule.evaluate(na)["decision"] == "ALLOW"

    def test_allows_complete_request(self):
        rule = ModeRestrictionRule(mode="demo")
        assert rule.evaluate(_make_complete())["decision"] == "ALLOW"