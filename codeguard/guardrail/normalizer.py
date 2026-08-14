import hashlib
import json
from datetime import datetime
from codeguard.action import Action, ActionKind, NormalizedAction


class SchemaValidator:
    """Validates tool parameters against JSON Schema.

    Supports required fields, string typing, integer typing with
    minimum/maximum bounds, and array typing with string items.
    Unlisted parameter keys are ignored (extras allowed).
    """

    def validate(self, params: dict, schema: dict):
        required = schema.get("required", [])
        for field in required:
            if field not in params:
                raise ValueError(f"Missing required parameter: {field}")
        properties = schema.get("properties", {})
        for key, value in params.items():
            if key not in properties:
                continue
            expected_type = properties[key].get("type")
            if expected_type == "string":
                if not isinstance(value, str):
                    raise ValueError(
                        f"Parameter '{key}' should be string, got {type(value).__name__}"
                    )
            elif expected_type == "integer":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(
                        f"Parameter '{key}' should be integer, got {type(value).__name__}"
                    )
                minimum = properties[key].get("minimum")
                maximum = properties[key].get("maximum")
                if minimum is not None and value < minimum:
                    raise ValueError(
                        f"Parameter '{key}' must be >= {minimum}, got {value}"
                    )
                if maximum is not None and value > maximum:
                    raise ValueError(
                        f"Parameter '{key}' must be <= {maximum}, got {value}"
                    )
            elif expected_type == "array":
                if not isinstance(value, list):
                    raise ValueError(
                        f"Parameter '{key}' should be array, got {type(value).__name__}"
                    )
                items_type = (properties[key].get("items") or {}).get("type")
                if items_type == "string":
                    for i, item in enumerate(value):
                        if not isinstance(item, str):
                            raise ValueError(
                                f"Parameter '{key}[{i}]' should be string, "
                                f"got {type(item).__name__}"
                            )


class ActionNormalizer:
    """Normalizes actions for consistent guardrail evaluation."""

    def __init__(self, workspace_root: str = ""):
        self._workspace_root = workspace_root

    def normalize(self, action: Action) -> NormalizedAction:
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return NormalizedAction(
                kind=action.kind,
                tool_name=None,
                normalized_parameters={},
                action_fingerprint="COMPLETE_REQUEST",
                original_raw=action.raw,
                normalized_at=datetime.now()
            )

        normalized_params = dict(action.parameters or {})
        if "path" in normalized_params and self._workspace_root:
            normalized_params["path"] = self._resolve_path(normalized_params["path"])

        fp = self._compute_fingerprint(action.tool_name or "", normalized_params)
        return NormalizedAction(
            kind=action.kind,
            tool_name=action.tool_name,
            normalized_parameters=normalized_params,
            action_fingerprint=fp,
            original_raw=action.raw,
            normalized_at=datetime.now()
        )

    def _resolve_path(self, path: str) -> str:
        from pathlib import Path
        root = Path(self._workspace_root).resolve()
        target = (root / path).resolve()
        return str(target)

    def _compute_fingerprint(self, tool_name: str, params: dict) -> str:
        raw = f"{tool_name}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(raw.encode()).hexdigest()