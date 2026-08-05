from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


class ActionKind(Enum):
    TOOL_CALL = "tool_call"
    COMPLETE_REQUEST = "complete"


@dataclass
class Action:
    kind: ActionKind
    tool_name: Optional[str] = None
    parameters: Optional[dict] = None
    summary: Optional[str] = None
    raw: str = ""


@dataclass(frozen=True)
class NormalizedAction:
    kind: ActionKind
    tool_name: Optional[str]
    normalized_parameters: Optional[dict]
    action_fingerprint: str
    original_raw: str
    normalized_at: datetime


@dataclass
class LLMResponse:
    content: str
    next_action: Action
    finish_reason: str
    model: str
    token_used: int
    cost_used: Decimal
    raw_response: str


# ---------------------------------------------------------------------------
# ActionParser
# ---------------------------------------------------------------------------

import json as _json


class ActionParser:
    """Parses LLM output string into Action."""

    def parse(self, raw: str) -> Action:
        try:
            data = _json.loads(raw)
        except _json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse action: {e}")

        if "action" not in data:
            raise ValueError("Missing 'action' field in LLM output")

        action_type = data["action"]
        if action_type == "complete":
            return Action(
                kind=ActionKind.COMPLETE_REQUEST,
                summary=data.get("summary", ""),
                raw=raw,
            )
        elif action_type == "tool_call":
            return Action(
                kind=ActionKind.TOOL_CALL,
                tool_name=data.get("tool", ""),
                parameters=data.get("parameters", {}),
                raw=raw,
            )
        else:
            raise ValueError(f"Unknown action type: {action_type}")