from datetime import datetime
from codeguard.tracer import Tracer, TraceEvent
from codeguard.state import AgentState
from codeguard.secret import SecretRedactor


# ── Basic event recording ────────────────────────────────────────────

class TestRecordEvents:
    def test_record_state_transition(self):
        tracer = Tracer()
        tracer.record_state_transition(AgentState.INITIALIZING, AgentState.BUILDING_CONTEXT)
        events = tracer.get_events()
        assert len(events) == 1
        assert events[0].event_type == "state_transition"
        assert events[0].data["from"] == "initializing"
        assert events[0].data["to"] == "building_context"

    def test_record_guardrail(self):
        tracer = Tracer()
        tracer.record_guardrail("BLOCK", ["rule1", "rule2"], "Blocked by policy")
        events = tracer.get_events()
        assert len(events) == 1
        assert events[0].event_type == "guardrail"
        assert events[0].data["decision"] == "BLOCK"
        assert "rule1" in events[0].data["rules"]

    def test_record_tool_call(self):
        tracer = Tracer()
        tracer.record_tool_call("read_file", {"path": "main.py"}, "SUCCESS")
        events = tracer.get_events()
        assert len(events) == 1
        assert events[0].event_type == "tool_call"
        assert events[0].data["tool"] == "read_file"
        assert events[0].data["params"]["path"] == "main.py"

    def test_record_feedback(self):
        tracer = Tracer()
        tracer.record_feedback("pytest", "PASSED", None)
        events = tracer.get_events()
        assert len(events) == 1
        assert events[0].event_type == "feedback"
        assert events[0].data["sensor"] == "pytest"
        assert events[0].data["status"] == "PASSED"


# ── Chronological order ──────────────────────────────────────────────

class TestChronologicalOrder:
    def test_events_ordered_by_record_time(self):
        tracer = Tracer()
        tracer.record_state_transition(AgentState.INITIALIZING, AgentState.BUILDING_CONTEXT)
        tracer.record_tool_call("read_file", {}, "SUCCESS")
        tracer.record_state_transition(AgentState.BUILDING_CONTEXT, AgentState.DECIDING)
        events = tracer.get_events()
        assert events[0].event_type == "state_transition"
        assert events[1].event_type == "tool_call"
        assert events[2].event_type == "state_transition"

    def test_multiple_events_all_present(self):
        tracer = Tracer()
        for i in range(5):
            tracer.record_tool_call(f"tool_{i}", {}, "SUCCESS")
        assert len(tracer.get_events()) == 5


# ── Timestamp ────────────────────────────────────────────────────────

class TestTimestamp:
    def test_timestamp_is_set(self):
        tracer = Tracer()
        tracer.record_tool_call("read", {}, "SUCCESS")
        event = tracer.get_events()[0]
        assert event.timestamp is not None
        assert len(event.timestamp) > 0

    def test_timestamp_is_iso_format(self):
        tracer = Tracer()
        tracer.record_tool_call("read", {}, "SUCCESS")
        event = tracer.get_events()[0]
        datetime.fromisoformat(event.timestamp)  # should not raise


# ── SecretRedactor integration ───────────────────────────────────────

class TestRedaction:
    def test_guardrail_message_redacted(self):
        redactor = SecretRedactor()
        tracer = Tracer(secret_redactor=redactor)
        tracer.record_guardrail("BLOCK", ["r1"], "api_key = sk-1234567890abcdef")
        events = tracer.get_events()
        assert "sk-1234567890abcdef" not in events[0].data["message"]

    def test_tool_params_redacted(self):
        redactor = SecretRedactor()
        tracer = Tracer(secret_redactor=redactor)
        tracer.record_tool_call("write_file", {"content": "password = hunter2"}, "SUCCESS")
        events = tracer.get_events()
        content = events[0].data["params"]["content"]
        assert "hunter2" not in content

    def test_nested_dict_redacted(self):
        redactor = SecretRedactor()
        tracer = Tracer(secret_redactor=redactor)
        tracer.record_tool_call("write", {"config": {"auth": {"token": "sk-abc123"}}}, "SUCCESS")
        events = tracer.get_events()
        inner = events[0].data["params"]["config"]["auth"]["token"]
        assert "sk-abc123" not in inner

    def test_nested_list_redacted(self):
        redactor = SecretRedactor()
        tracer = Tracer(secret_redactor=redactor)
        tracer.record_tool_call("batch", {"items": ["api_key=secret1", "normal"]}, "SUCCESS")
        events = tracer.get_events()
        assert "secret1" not in events[0].data["params"]["items"][0]

    def test_normal_data_preserved(self):
        redactor = SecretRedactor()
        tracer = Tracer(secret_redactor=redactor)
        tracer.record_tool_call("read", {"path": "src/main.py", "line": 42}, "SUCCESS")
        events = tracer.get_events()
        params = events[0].data["params"]
        assert params["path"] == "src/main.py"
        assert params["line"] == 42

    def test_default_redactor_applied(self):
        tracer = Tracer()  # no explicit redactor
        tracer.record_tool_call("write", {"content": "api_key = sk-deadbeef"}, "SUCCESS")
        events = tracer.get_events()
        assert "sk-deadbeef" not in events[0].data["params"]["content"]


# ── Defensive copy ───────────────────────────────────────────────────

class TestDefensiveCopy:
    def test_get_events_returns_copy_of_list(self):
        tracer = Tracer()
        tracer.record_tool_call("read", {}, "SUCCESS")
        events = tracer.get_events()
        events.pop()
        assert len(tracer.get_events()) == 1

    def test_modifying_event_data_does_not_affect_internal(self):
        tracer = Tracer()
        tracer.record_tool_call("read", {"path": "main.py"}, "SUCCESS")
        events = tracer.get_events()
        events[0].data["path"] = "modified"
        internal = tracer.get_events()
        assert internal[0].data["params"]["path"] == "main.py"


# ── Empty tracer ─────────────────────────────────────────────────────

class TestEmptyTracer:
    def test_empty_tracer_returns_empty_list(self):
        tracer = Tracer()
        assert tracer.get_events() == []


# ── TraceEvent type ──────────────────────────────────────────────────

class TestTraceEventType:
    def test_trace_event_is_dataclass(self):
        tracer = Tracer()
        tracer.record_tool_call("read", {}, "SUCCESS")
        event = tracer.get_events()[0]
        assert isinstance(event, TraceEvent)
        assert hasattr(event, "event_type")
        assert hasattr(event, "data")
        assert hasattr(event, "timestamp")