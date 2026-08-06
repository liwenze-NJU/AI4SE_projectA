from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid
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


class ApprovalManager:
    """Manages approval requests with timeout, session binding, and fingerprint binding.

    Does NOT auto-approve. The caller must call approve() or reject() explicitly.
    """

    def __init__(self, clock: FakeClock | None = None, approval_timeout: int = 300):
        self._clock = clock or FakeClock()
        self._timeout = approval_timeout
        self._requests: dict[str, ApprovalRequest] = {}

    def create_request(self, session_id: str, normalized_action: NormalizedAction,
                       matched_rules: list[str], risk_summary: str) -> ApprovalRequest:
        req = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            session_id=session_id,
            normalized_action=normalized_action,
            action_fingerprint=normalized_action.action_fingerprint,
            matched_rules=matched_rules,
            risk_summary=risk_summary,
            workspace_snapshot={},
            created_at=self._clock.now,
            expires_at=self._clock.now + timedelta(seconds=self._timeout),
        )
        self._requests[req.request_id] = req
        return req

    def approve(self, request_id: str, session_id: str, action_fingerprint: str) -> ApprovalResult:
        req = self._get_request(request_id)
        if req.session_id != session_id:
            raise ValueError("Session mismatch")
        if self._clock.is_expired(req.expires_at):
            raise ValueError("Request already expired")
        if req.action_fingerprint != action_fingerprint:
            raise ValueError("Action fingerprint mismatch")
        if req.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request already {req.status.value}")
        req.status = ApprovalStatus.APPROVED
        return ApprovalResult(request_id=request_id, decision=ApprovalStatus.APPROVED,
                            validated_at=self._clock.now)

    def reject(self, request_id: str, session_id: str) -> ApprovalResult:
        req = self._get_request(request_id)
        if req.session_id != session_id:
            raise ValueError("Session mismatch")
        if self._clock.is_expired(req.expires_at):
            raise ValueError("Request already expired")
        if req.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request already {req.status.value}")
        req.status = ApprovalStatus.REJECTED
        return ApprovalResult(request_id=request_id, decision=ApprovalStatus.REJECTED,
                            validated_at=self._clock.now)

    def check_timeout(self, req: ApprovalRequest) -> ApprovalResult | None:
        if req.status != ApprovalStatus.PENDING:
            return None
        if self._clock.is_expired(req.expires_at):
            req.status = ApprovalStatus.TIMEOUT
            return ApprovalResult(request_id=req.request_id, decision=ApprovalStatus.TIMEOUT,
                                validated_at=self._clock.now)
        return None

    def _get_request(self, request_id: str) -> ApprovalRequest:
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Unknown request: {request_id}")
        return req