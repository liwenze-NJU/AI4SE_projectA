from enum import Enum
from dataclasses import dataclass
from typing import Protocol


class HarnessEventKind(Enum):
    STATE_CHANGED = "state_changed"
    ASSISTANT_MESSAGE = "assistant_message"
    USER_INPUT_REQUESTED = "user_input_requested"
    TOOL_STARTED = "tool_started"
    TOOL_FINISHED = "tool_finished"
    APPROVAL_REQUESTED = "approval_requested"
    VALIDATION_FINISHED = "validation_finished"
    TASK_FINISHED = "task_finished"


@dataclass(frozen=True)
class HarnessEvent:
    kind: HarnessEventKind
    session_id: str
    task_id: str
    payload: dict[str, object]


class EventSink(Protocol):
    def emit(self, event: HarnessEvent) -> None: ...


class NullEventSink:
    """Discards every event; useful as a default for non-observing callers."""

    def emit(self, event: HarnessEvent) -> None:
        pass


class CollectingEventSink:
    """Deterministic test utility that records every emitted event in order."""

    def __init__(self) -> None:
        self.events: list[HarnessEvent] = []

    def emit(self, event: HarnessEvent) -> None:
        self.events.append(event)
