from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from codeguard.action import NormalizedAction


class ApprovalStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"


@dataclass
class ApprovalRequest:
    request_id: str
    session_id: str
    normalized_action: NormalizedAction
    action_fingerprint: str
    matched_rules: list[str]
    risk_summary: str
    workspace_snapshot: dict
    created_at: datetime
    expires_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING


@dataclass
class ApprovalResult:
    request_id: str
    decision: ApprovalStatus
    validated_at: datetime
    validator_notes: str = ""


class FakeClock:
    """Injectable clock for deterministic timeout testing."""

    def __init__(self, now: datetime | None = None):
        self._now = now or datetime.now()

    @property
    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float):
        self._now += timedelta(seconds=seconds)

    def is_expired(self, deadline: datetime) -> bool:
        return self._now >= deadline