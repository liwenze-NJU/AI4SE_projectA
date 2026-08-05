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