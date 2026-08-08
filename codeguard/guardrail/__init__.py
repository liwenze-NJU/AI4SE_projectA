from dataclasses import dataclass
from enum import Enum
from codeguard.action import NormalizedAction


class GuardrailDecision(Enum):
    BLOCK = "BLOCK"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    ALLOW = "ALLOW"


@dataclass
class GuardrailResult:
    decision: GuardrailDecision
    rule_ids: list[str]
    reason_codes: list[str]
    human_readable_message: str
    recoverable: bool
    normalized_action: NormalizedAction
    action_fingerprint: str