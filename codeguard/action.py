from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


class ActionKind(Enum):
    TOOL_CALL = "tool_call"
    ASSISTANT_MESSAGE = "assistant_message"
    REQUEST_USER_INPUT = "request_user_input"
    COMPLETE_REQUEST = "complete"


import hashlib as _hashlib
import json as _json


@dataclass
class Action:
    kind: ActionKind
    tool_name: Optional[str] = None
    parameters: Optional[dict] = None
    summary: Optional[str] = None
    message: Optional[str] = None
    question: Optional[str] = None
    raw: str = ""

    @property
    def action_fingerprint(self) -> str:
        """Deterministic fingerprint from the action's key fields."""
        data = _json.dumps({
            "kind": self.kind.value,
            "tool_name": self.tool_name or "",
            "parameters": self.parameters or {},
        }, sort_keys=True)
        return _hashlib.sha256(data.encode()).hexdigest()


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

        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object, got {!r}".format(type(data).__name__))

        if "action" not in data:
            raise ValueError("Missing 'action' field in LLM output")

        action_type = data["action"]
        if action_type == "complete":
            summary = data.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                raise ValueError("complete requires a non-empty summary")
            return Action(
                kind=ActionKind.COMPLETE_REQUEST,
                summary=summary,
                raw=raw,
            )
        elif action_type == "tool_call":
            return Action(
                kind=ActionKind.TOOL_CALL,
                tool_name=data.get("tool"),
                parameters=data.get("parameters"),
                raw=raw,
            )
        elif action_type == "assistant_message":
            message = data.get("message")
            if not isinstance(message, str) or not message.strip():
                raise ValueError("assistant_message requires a non-empty message")
            return Action(
                kind=ActionKind.ASSISTANT_MESSAGE,
                message=message,
                raw=raw,
            )
        elif action_type == "request_user_input":
            question = data.get("question")
            if not isinstance(question, str) or not question.strip():
                raise ValueError("request_user_input requires a non-empty question")
            return Action(
                kind=ActionKind.REQUEST_USER_INPUT,
                question=question,
                raw=raw,
            )
        else:
            raise ValueError(f"Unknown action type: {action_type}")