from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MemoryType(Enum):
    PROJECT_CONVENTION = "project_convention"
    APPROVED_DECISION = "approved_decision"
    TASK_SUMMARY = "task_summary"
    FAILURE_RESOLUTION = "failure_resolution"


class TrustLevel(Enum):
    USER_APPROVED = "user_approved"
    HARNESS_VERIFIED = "harness_verified"
    LLM_PROPOSED = "llm_proposed"


class MemoryStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass
class MemoryRecord:
    id: str
    project_id: str
    type: MemoryType
    content: str
    tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    source: str = ""
    trust_level: TrustLevel = TrustLevel.LLM_PROPOSED
    status: MemoryStatus = MemoryStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    session_id: str = ""