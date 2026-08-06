import copy
from dataclasses import dataclass, field
from datetime import datetime
from codeguard.state import AgentState
from codeguard.secret import SecretRedactor


@dataclass
class TraceEvent:
    event_type: str
    data: dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class Tracer:
    """Records chronological trace of agent execution.

    Applies SecretRedactor to all string values in event data before
    storing — including nested dicts, lists, and tuples. get_events()
    returns deep copies so callers cannot mutate internal state.
    """

    def __init__(self, secret_redactor: SecretRedactor | None = None):
        self._events: list[TraceEvent] = []
        self._redactor = secret_redactor or SecretRedactor()

    def record_state_transition(self, old: AgentState, new: AgentState):
        data = {"from": old.value, "to": new.value}
        self._events.append(TraceEvent("state_transition", data))

    def record_guardrail(self, decision: str, rule_ids: list[str], message: str):
        data = {
            "decision": decision,
            "rules": list(rule_ids),
            "message": self._redactor.redact(message),
        }
        self._events.append(TraceEvent("guardrail", data))

    def record_tool_call(self, tool: str, params: dict, status: str):
        safe_params = self._redact_nested(params)
        data = {"tool": tool, "params": safe_params, "status": status}
        self._events.append(TraceEvent("tool_call", data))

    def record_feedback(self, sensor: str, status: str, category: str | None):
        data = {"sensor": sensor, "status": status}
        if category is not None:
            data["category"] = category
        self._events.append(TraceEvent("feedback", data))

    def get_events(self) -> list[TraceEvent]:
        return copy.deepcopy(self._events)

    def _redact_nested(self, obj):
        if isinstance(obj, str):
            return self._redactor.redact(obj)
        if isinstance(obj, dict):
            return {k: self._redact_nested(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._redact_nested(v) for v in obj]
        if isinstance(obj, tuple):
            return tuple(self._redact_nested(v) for v in obj)
        return obj