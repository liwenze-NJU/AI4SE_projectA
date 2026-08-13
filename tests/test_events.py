import pytest
from dataclasses import FrozenInstanceError
from codeguard.events import (
    HarnessEvent,
    HarnessEventKind,
    EventSink,
    NullEventSink,
    CollectingEventSink,
)


def test_collecting_sink_receives_typed_event():
    sink = CollectingEventSink()
    event = HarnessEvent(
        kind=HarnessEventKind.ASSISTANT_MESSAGE,
        session_id="chat-1",
        task_id="task-1",
        payload={"message": "Inspecting tests"},
    )
    sink.emit(event)
    assert sink.events == [event]


def test_null_sink_is_noop():
    sink = NullEventSink()
    event = HarnessEvent(
        kind=HarnessEventKind.STATE_CHANGED,
        session_id="s",
        task_id="t",
        payload={"state": "deciding"},
    )
    # Must not raise; nothing is recorded.
    sink.emit(event)


def test_harness_event_is_frozen():
    event = HarnessEvent(
        kind=HarnessEventKind.TOOL_STARTED,
        session_id="s",
        task_id="t",
        payload={"tool": "read_file"},
    )
    with pytest.raises(FrozenInstanceError):
        event.payload = {"tool": "write_file"}


def test_harness_event_kind_values():
    expected = [
        "state_changed",
        "assistant_message",
        "user_input_requested",
        "tool_started",
        "tool_finished",
        "approval_requested",
        "validation_finished",
        "task_finished",
    ]
    assert [k.value for k in HarnessEventKind] == expected


def test_event_sink_is_protocol():
    """EventSink must be a Protocol, not a concrete base class."""
    assert hasattr(EventSink, "_is_protocol")
