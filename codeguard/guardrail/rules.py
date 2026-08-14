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
        if not isinstance(action, NormalizedAction):
            raise TypeError(
                f"WorkspaceBoundaryRule requires NormalizedAction, "
                f"got {type(action).__name__}"
            )
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "workspace_boundary", "reason_codes": []}
        path = action.normalized_parameters.get("path", "")
        if not path:
            return {"decision": "ALLOW", "rule_id": "workspace_boundary", "reason_codes": []}
        if not self._is_within_workspace(path):
            return {"decision": "BLOCK", "rule_id": "workspace_boundary",
                    "reason_codes": ["out_of_bounds"], "recoverable": True}
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
        if not isinstance(action, NormalizedAction):
            raise TypeError(
                f"CredentialLeakRule requires NormalizedAction, "
                f"got {type(action).__name__}"
            )
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "credential_leak", "reason_codes": []}
        for value in action.normalized_parameters.values():
            if not isinstance(value, str):
                continue
            if self._sk_pattern.search(value):
                return {"decision": "BLOCK", "rule_id": "credential_leak",
                        "reason_codes": ["credential_detected"], "recoverable": True}
            for p in self._field_patterns:
                if p.search(value):
                    return {"decision": "BLOCK", "rule_id": "credential_leak",
                            "reason_codes": ["credential_detected"], "recoverable": True}
        return {"decision": "ALLOW", "rule_id": "credential_leak", "reason_codes": []}


class UnregisteredToolRule:
    """Blocks actions that reference unregistered tools."""

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def evaluate(self, action: NormalizedAction) -> dict:
        if not isinstance(action, NormalizedAction):
            raise TypeError(
                f"UnregisteredToolRule requires NormalizedAction, "
                f"got {type(action).__name__}"
            )
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "unregistered_tool", "reason_codes": []}
        try:
            self._registry.lookup(action.tool_name or "")
            return {"decision": "ALLOW", "rule_id": "unregistered_tool", "reason_codes": []}
        except KeyError:
            return {"decision": "BLOCK", "rule_id": "unregistered_tool",
                    "reason_codes": ["unknown_tool"], "recoverable": True}


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
        if not isinstance(action, NormalizedAction):
            raise TypeError(
                f"ModeRestrictionRule requires NormalizedAction, "
                f"got {type(action).__name__}"
            )
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "mode_restriction", "reason_codes": []}
        if self._mode == "demo" and action.tool_name in self._DEMO_BLOCKED_TOOLS:
            return {"decision": "BLOCK", "rule_id": "mode_restriction",
                    "reason_codes": ["blocked_in_demo"], "recoverable": True}
        return {"decision": "ALLOW", "rule_id": "mode_restriction", "reason_codes": []}


class ToolRiskRule:
    """Enforces each registered tool's declared default risk in code.

    For TOOL_CALL actions the rule looks up ``ToolDefinition.default_risk``
    and returns exactly ALLOW, REQUEST_APPROVAL, or BLOCK.  Unknown risk
    strings fail closed as BLOCK.  Non-tool conversation actions are never
    sent through the tool governance pipeline.
    """

    _VALID_DECISIONS = frozenset({"ALLOW", "REQUEST_APPROVAL", "BLOCK"})

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def evaluate(self, action: NormalizedAction) -> dict:
        if not isinstance(action, NormalizedAction):
            raise TypeError(
                f"ToolRiskRule requires NormalizedAction, "
                f"got {type(action).__name__}"
            )
        if action.kind != ActionKind.TOOL_CALL:
            # Conversation and completion actions are not governed by tool risk
            return {"decision": "ALLOW", "rule_id": "tool_risk", "reason_codes": []}
        try:
            definition = self._registry.lookup(action.tool_name or "")
        except KeyError:
            return {"decision": "BLOCK", "rule_id": "tool_risk",
                    "reason_codes": ["unknown_tool"], "recoverable": True}
        risk = definition.default_risk
        if risk not in self._VALID_DECISIONS:
            return {"decision": "BLOCK", "rule_id": "tool_risk",
                    "reason_codes": ["invalid_default_risk"], "recoverable": False}
        return {"decision": risk, "rule_id": "tool_risk", "reason_codes": []}