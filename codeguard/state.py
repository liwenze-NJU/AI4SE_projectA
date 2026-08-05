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
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LIMIT_REACHED = "limit_reached"