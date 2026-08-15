from enum import Enum


class AgentState(Enum):
    INITIALIZING = "initializing"
    BUILDING_CONTEXT = "building_context"
    DECIDING = "deciding"
    GOVERNING = "governing"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    INTERMEDIATE_VALIDATION = "intermediate_validation"
    FINAL_VALIDATION = "final_validation"
    FEEDING_BACK = "feeding_back"
    AWAITING_USER_INPUT = "awaiting_user_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LIMIT_REACHED = "limit_reached"


from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from codeguard.action import NormalizedAction
from codeguard.guardrail import GuardrailResult


@dataclass
class SessionState:
    session_id: str
    current_state: AgentState
    pending_action: Optional[NormalizedAction] = None
    guardrail_decision: Optional[GuardrailResult] = None
    approval_request_id: Optional[str] = None
    pending_question: Optional[str] = None
    steps_used: int = 0
    llm_calls_used: int = 0
    token_used: int = 0
    cost_used: Decimal = Decimal("0")
    action_fingerprint_history: list[str] = field(default_factory=list)
    failure_fingerprint_history: list[str] = field(default_factory=list)
    # T8-FIX6: fingerprints of tool RESULTS (tool name + params + outcome)
    # so read-only loops like A→B→A→B are detected even when action
    # fingerprints alternate.
    result_fingerprint_history: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)


@dataclass
class SessionResult:
    session_id: str
    terminal_state: AgentState
    steps_total: int
    llm_calls_total: int
    token_total: int
    cost_total: Decimal
    duration: float
    guardrail_decisions: list[GuardrailResult]
    feedback_results: list[Any]
    trace: list[Any]
    error: Optional[str] = None