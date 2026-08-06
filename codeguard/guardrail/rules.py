import re
from pathlib import Path
from codeguard.action import ActionKind, NormalizedAction
from codeguard.tool.registry import ToolRegistry


class WorkspaceBoundaryRule:
    """Blocks actions that access paths outside the workspace.

    Uses pathlib.Path.resolve() for safe parent-child checks that handle
    .. escapes, name prefix bypass (workspace vs workspace-evil), and
    symlink resolution. Works correctly on both POSIX and Windows.
    """

    def __init__(self, workspace_root: str):
        self._root = Path(workspace_root).resolve()

    def evaluate(self, action: NormalizedAction) -> dict:
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "workspace_boundary", "reason_codes": []}
        path = action.normalized_parameters.get("path", "")
        if not path:
            return {"decision": "ALLOW", "rule_id": "workspace_boundary", "reason_codes": []}
        if not self._is_within_workspace(path):
            return {"decision": "BLOCK", "rule_id": "workspace_boundary", "reason_codes": ["out_of_bounds"]}
        return {"decision": "ALLOW", "rule_id": "workspace_boundary", "reason_codes": []}

    def _is_within_workspace(self, path_str: str) -> bool:
        try:
            resolved = Path(path_str).resolve()
            resolved.relative_to(self._root)
            return True
        except (ValueError, OSError):
            return False


class CredentialLeakRule:
    """Blocks actions that write credential patterns to output.

    Patterns align with SecretRedactor: sk- API keys, and
    api_key/password/secret/token assignments. All parameter values
    are checked, not just "content".
    """

    _CREDENTIAL_FIELDS = ['api_key', 'password', 'secret', 'token']

    def __init__(self):
        self._sk_pattern = re.compile(r'\bsk-\w+')
        self._field_patterns = [
            re.compile(rf'{field}\s*[=:]\s*\S+') for field in self._CREDENTIAL_FIELDS
        ]

    def evaluate(self, action: NormalizedAction) -> dict:
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "credential_leak", "reason_codes": []}
        for value in action.normalized_parameters.values():
            if not isinstance(value, str):
                continue
            if self._sk_pattern.search(value):
                return {"decision": "BLOCK", "rule_id": "credential_leak", "reason_codes": ["credential_detected"]}
            for p in self._field_patterns:
                if p.search(value):
                    return {"decision": "BLOCK", "rule_id": "credential_leak", "reason_codes": ["credential_detected"]}
        return {"decision": "ALLOW", "rule_id": "credential_leak", "reason_codes": []}


class UnregisteredToolRule:
    """Blocks actions that reference unregistered tools."""

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def evaluate(self, action: NormalizedAction) -> dict:
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "unregistered_tool", "reason_codes": []}
        try:
            self._registry.lookup(action.tool_name or "")
            return {"decision": "ALLOW", "rule_id": "unregistered_tool", "reason_codes": []}
        except KeyError:
            return {"decision": "BLOCK", "rule_id": "unregistered_tool", "reason_codes": ["unknown_tool"]}


class ModeRestrictionRule:
    """Blocks actions not allowed in the current mode.

    Demo mode: read-only tools only (blocks run_process, write_file,
    delete_file, apply_patch). Full mode: all actions allowed.
    COMPLETE_REQUEST is always allowed.
    """

    _DEMO_BLOCKED_TOOLS = frozenset({"run_process", "write_file", "delete_file", "apply_patch"})

    def __init__(self, mode: str):
        self._mode = mode

    def evaluate(self, action: NormalizedAction) -> dict:
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "mode_restriction", "reason_codes": []}
        if self._mode == "demo" and action.tool_name in self._DEMO_BLOCKED_TOOLS:
            return {"decision": "BLOCK", "rule_id": "mode_restriction", "reason_codes": ["blocked_in_demo"]}
        return {"decision": "ALLOW", "rule_id": "mode_restriction", "reason_codes": []}