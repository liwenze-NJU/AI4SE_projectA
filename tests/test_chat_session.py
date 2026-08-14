"""ChatSession and CLIEventSink tests (interactive CLI plan, Task 5)."""

from decimal import Decimal

import pytest

from codeguard.chat import ChatHistory, ChatSession, CLIEventSink, TaskSummary
from codeguard.events import HarnessEvent, HarnessEventKind
from codeguard.guardrail import GuardrailDecision, GuardrailResult
from codeguard.guardrail.approval import ApprovalStatus
from codeguard.state import AgentState, SessionResult


# ---------------------------------------------------------------------------
# Test helpers and fixtures
# ---------------------------------------------------------------------------

def make_result(state, session_id="sess-1"):
    """Build a SessionResult with the given terminal state."""
    return SessionResult(
        session_id=session_id,
        terminal_state=state,
        steps_total=0,
        llm_calls_total=0,
        token_total=0,
        cost_total=Decimal("0"),
        duration=0.0,
        guardrail_decisions=[],
        feedback_results=[],
        trace=[],
    )


class FakeIO:
    """Scriptable reader (queue of lines) and recording writer."""

    def __init__(self):
        self._queue = []
        self.output = ""
        self.prompts = []

    def queue(self, *lines):
        self._queue.extend(lines)

    def read(self, prompt):
        self.prompts.append(prompt)
        if not self._queue:
            return ""  # empty return is the EOF sentinel
        return self._queue.pop(0)

    def write(self, text):
        self.output += text + "\n"


class FakePendingAction:
    def __init__(self, tool_name, parameters=None, fingerprint="fp-1"):
        self.tool_name = tool_name
        self.normalized_parameters = parameters or {}
        self.action_fingerprint = fingerprint


class FakeState:
    def __init__(self, current_state=AgentState.INITIALIZING, session_id="sess-1"):
        self.current_state = current_state
        self.session_id = session_id
        self.pending_question = None
        self.approval_request_id = None
        self.pending_action = None
        self.guardrail_decision = None
        self.steps_used = 0
        self.llm_calls_used = 0


class FakeLoop:
    """Scriptable recording fake of the AgentLoop surface ChatSession drives.

    Mirrors the real loop contract: start_task / resume_with_user_input /
    cancel return a SessionResult; resume_with_approval records the decision
    and the caller must call run() to continue.  By default it exposes an
    ``event_sink`` attribute like the real loop; pass ``has_event_sink=False``
    to model a loop without one (the session must skip gracefully).
    """

    def __init__(self, has_event_sink=True):
        self.state = FakeState()
        self.calls = []
        self.start_task_results = []
        self.run_results = []
        self.resume_user_results = []
        self.cancel_result = None
        self._start_events = []
        self.event_sink = None
        if not has_event_sink:
            del self.event_sink

    def emit_on_start(self, kind, payload):
        """Queue events to emit (via event_sink) from the next start_task."""
        self._start_events.append((kind, payload))

    def start_task(self, task_id, request, summaries):
        self.calls.append(("start_task", task_id, request, list(summaries)))
        for kind, payload in self._start_events:
            sink = getattr(self, "event_sink", None)
            if sink is not None:
                sink.emit(HarnessEvent(
                    kind=kind,
                    session_id=self.state.session_id,
                    task_id=task_id,
                    payload=payload,
                ))
        result = (
            self.start_task_results.pop(0)
            if self.start_task_results
            else make_result(AgentState.COMPLETED)
        )
        self._apply(result)
        return result

    def run(self):
        self.calls.append(("run",))
        result = (
            self.run_results.pop(0)
            if self.run_results
            else make_result(self.state.current_state)
        )
        self._apply(result)
        return result

    def resume_with_user_input(self, text):
        self.calls.append(("resume_with_user_input", text))
        result = (
            self.resume_user_results.pop(0)
            if self.resume_user_results
            else make_result(AgentState.COMPLETED)
        )
        self._apply(result)
        return result

    def resume_with_approval(self, request_id, session_id, decision,
                             action_fingerprint):
        self.calls.append(("resume_with_approval", request_id, session_id,
                           decision, action_fingerprint))

    def cancel(self):
        self.calls.append(("cancel",))
        result = self.cancel_result or make_result(AgentState.CANCELLED)
        self._apply(result)
        return result

    def _apply(self, result):
        self.state.current_state = result.terminal_state


class RecordingLoopFactory:
    """Records the session ids requested and the loops created."""

    def __init__(self, make_loop):
        self._make_loop = make_loop
        self.requests = []
        self.created_loops = []

    def __call__(self, session_id):
        self.requests.append(session_id)
        loop = self._make_loop()
        self.created_loops.append(loop)
        return loop


@pytest.fixture
def fake_io():
    return FakeIO()


@pytest.fixture
def history():
    return ChatHistory(max_messages=4, max_summaries=2)


@pytest.fixture
def loop_factory():
    return RecordingLoopFactory(FakeLoop)


# ---------------------------------------------------------------------------
# Commands (plan Step 1)
# ---------------------------------------------------------------------------

def test_help_does_not_create_task(fake_io, loop_factory):
    session = ChatSession(loop_factory, fake_io.read, fake_io.write)
    fake_io.queue("/help", "/exit")
    assert session.run() == 0
    assert loop_factory.requests == []
    assert "/status" in fake_io.output


def test_clear_only_clears_messages(fake_io, history, loop_factory):
    history.add_message("user", "old")
    history.add_summary(TaskSummary("t0", "old", "completed", "done"))
    fake_io.queue("/clear", "/exit")
    ChatSession(loop_factory, fake_io.read, fake_io.write, history=history).run()
    assert history.messages == []
    assert len(history.summaries) == 1


def test_status_prints_provider_dict(fake_io, loop_factory):
    session = ChatSession(
        loop_factory, fake_io.read, fake_io.write,
        status_provider=lambda: {"mode": "test", "tasks": 0},
    )
    fake_io.queue("/status", "/exit")
    assert session.run() == 0
    assert "mode: test" in fake_io.output


def test_status_without_provider_prints_safe_message(fake_io, loop_factory):
    session = ChatSession(loop_factory, fake_io.read, fake_io.write)
    fake_io.queue("/status", "/exit")
    assert session.run() == 0
    assert "status" in fake_io.output.lower()


def test_blank_input_is_ignored(fake_io, loop_factory):
    session = ChatSession(loop_factory, fake_io.read, fake_io.write)
    fake_io.queue("   ", "\n", "/exit")
    assert session.run() == 0
    assert loop_factory.requests == []


def test_eof_empty_string_exits_zero(fake_io, loop_factory):
    session = ChatSession(loop_factory, fake_io.read, fake_io.write)
    assert session.run() == 0
    assert loop_factory.requests == []


def test_eof_error_exits_zero(fake_io, loop_factory):
    def read(prompt):
        raise EOFError

    session = ChatSession(loop_factory, read, fake_io.write)
    assert session.run() == 0
    assert loop_factory.requests == []


def test_cancel_with_no_task_does_not_create_task(fake_io, loop_factory):
    session = ChatSession(loop_factory, fake_io.read, fake_io.write)
    fake_io.queue("/cancel", "/exit")
    assert session.run() == 0
    assert "No active task" in fake_io.output
    assert loop_factory.requests == []


def test_exit_returns_zero(fake_io, loop_factory):
    session = ChatSession(loop_factory, fake_io.read, fake_io.write)
    fake_io.queue("/exit")
    assert session.run() == 0
    assert loop_factory.requests == []


# ---------------------------------------------------------------------------
# Normal task flow
# ---------------------------------------------------------------------------

def test_normal_input_starts_one_task_and_appends_history(fake_io, history):
    loop = FakeLoop()
    loop.start_task_results.append(make_result(AgentState.COMPLETED))
    factory = RecordingLoopFactory(lambda: loop)
    session = ChatSession(factory, fake_io.read, fake_io.write, history=history)
    fake_io.queue("fix the bug", "/exit")
    assert session.run() == 0
    # The session creates ONE loop for its whole lifetime and passes the
    # loop factory its own session id.
    assert factory.requests == [session.session_id]
    assert [m.content for m in history.messages] == ["fix the bug"]
    assert len(history.summaries) == 1
    summary = history.summaries[-1]
    assert summary.request == "fix the bug"
    assert summary.outcome == "completed"
    assert summary.task_id == loop.calls[0][1]


def test_start_task_receives_history_summaries(fake_io, history):
    history.add_summary(TaskSummary("t0", "old request", "completed", "old summary"))
    loop = FakeLoop()
    factory = RecordingLoopFactory(lambda: loop)
    session = ChatSession(factory, fake_io.read, fake_io.write, history=history)
    fake_io.queue("new task", "/exit")
    assert session.run() == 0
    kind, task_id, request, summaries = loop.calls[0]
    assert kind == "start_task"
    assert task_id  # generated UUID, non-empty
    assert request == "new task"
    assert summaries == ["old summary"]


# ---------------------------------------------------------------------------
# Approval pause (plan Step 4)
# ---------------------------------------------------------------------------

def test_approval_approve_resumes_same_task_with_binding(fake_io, history):
    loop = FakeLoop()
    loop.state.approval_request_id = "req-1"
    loop.state.pending_action = FakePendingAction(
        "write_file", {"path": "out.txt"}, fingerprint="fp-9",
    )
    loop.start_task_results.append(make_result(AgentState.AWAITING_APPROVAL))
    loop.run_results.append(make_result(AgentState.COMPLETED))
    factory = RecordingLoopFactory(lambda: loop)
    session = ChatSession(factory, fake_io.read, fake_io.write, history=history)
    fake_io.queue("write the file", "y")
    assert session.run() == 0
    # Approval resumed with request/session/fingerprint binding
    assert ("resume_with_approval", "req-1", "sess-1",
            ApprovalStatus.APPROVED, "fp-9") in loop.calls
    # Same loop, same task: no new loop was created for the resume
    assert len(factory.created_loops) == 1
    assert len(history.summaries) == 1
    assert history.summaries[-1].task_id == loop.calls[0][1]
    assert history.summaries[-1].outcome == "completed"
    # Prompt shows action, target, and [y/N]
    joined_prompts = "".join(fake_io.prompts)
    assert "Approve write_file" in joined_prompts
    assert "out.txt" in joined_prompts
    assert "[y/N]" in joined_prompts


@pytest.mark.parametrize("answer,decision", [
    ("y", ApprovalStatus.APPROVED),
    ("yes", ApprovalStatus.APPROVED),
    ("Y", ApprovalStatus.APPROVED),
    ("n", ApprovalStatus.REJECTED),
    ("no", ApprovalStatus.REJECTED),
    ("maybe", ApprovalStatus.REJECTED),
])
def test_approval_accepts_only_explicit_yes(answer, decision, fake_io, history):
    loop = FakeLoop()
    loop.state.approval_request_id = "req-1"
    loop.state.pending_action = FakePendingAction(
        "write_file", {"path": "out.txt"}, "fp-9",
    )
    loop.start_task_results.append(make_result(AgentState.AWAITING_APPROVAL))
    loop.run_results.append(make_result(
        AgentState.COMPLETED if decision == ApprovalStatus.APPROVED
        else AgentState.CANCELLED
    ))
    factory = RecordingLoopFactory(lambda: loop)
    session = ChatSession(factory, fake_io.read, fake_io.write, history=history)
    fake_io.queue("write the file", answer)
    assert session.run() == 0
    assert ("resume_with_approval", "req-1", "sess-1", decision, "fp-9") in loop.calls


def test_approval_empty_input_defaults_to_rejection(fake_io, history):
    loop = FakeLoop()
    loop.state.approval_request_id = "req-1"
    loop.state.pending_action = FakePendingAction(
        "write_file", {"path": "out.txt"}, "fp-9",
    )
    loop.start_task_results.append(make_result(AgentState.AWAITING_APPROVAL))
    loop.run_results.append(make_result(AgentState.CANCELLED))
    factory = RecordingLoopFactory(lambda: loop)
    session = ChatSession(factory, fake_io.read, fake_io.write, history=history)
    fake_io.queue("write the file", "")
    assert session.run() == 0
    assert ("resume_with_approval", "req-1", "sess-1",
            ApprovalStatus.REJECTED, "fp-9") in loop.calls
    assert history.summaries[-1].outcome == "cancelled"


# ---------------------------------------------------------------------------
# Clarification pause (plan Step 4)
# ---------------------------------------------------------------------------

def test_user_input_pause_resumes_with_text(fake_io, history):
    loop = FakeLoop()
    loop.state.pending_question = "Which file?"
    loop.start_task_results.append(make_result(AgentState.AWAITING_USER_INPUT))
    loop.resume_user_results.append(make_result(AgentState.COMPLETED))
    factory = RecordingLoopFactory(lambda: loop)
    session = ChatSession(factory, fake_io.read, fake_io.write, history=history)
    fake_io.queue("edit the config", "src/config.py")
    assert session.run() == 0
    assert ("resume_with_user_input", "src/config.py") in loop.calls
    assert len(factory.created_loops) == 1
    assert "Which file?" in fake_io.output
    assert history.summaries[-1].outcome == "completed"


def test_user_input_pause_cancel_command_cancels(fake_io, history):
    loop = FakeLoop()
    loop.state.pending_question = "Which file?"
    loop.start_task_results.append(make_result(AgentState.AWAITING_USER_INPUT))
    factory = RecordingLoopFactory(lambda: loop)
    session = ChatSession(factory, fake_io.read, fake_io.write, history=history)
    fake_io.queue("edit the config", "/cancel")
    assert session.run() == 0
    assert ("cancel",) in loop.calls
    assert history.summaries[-1].outcome == "cancelled"


def test_user_input_pause_ctrl_c_cancels_and_returns_to_repl(fake_io, history):
    loop = FakeLoop()
    loop.state.pending_question = "Which file?"
    loop.start_task_results.append(make_result(AgentState.AWAITING_USER_INPUT))
    factory = RecordingLoopFactory(lambda: loop)
    reads = {"n": 0}

    def read(prompt):
        reads["n"] += 1
        if reads["n"] == 1:
            return "edit the config"
        if reads["n"] == 2:
            raise KeyboardInterrupt  # Ctrl+C at the clarification prompt
        return "/exit"

    session = ChatSession(factory, read, fake_io.write, history=history)
    assert session.run() == 0
    assert ("cancel",) in loop.calls
    assert history.summaries[-1].outcome == "cancelled"


# ---------------------------------------------------------------------------
# Ctrl+C semantics
# ---------------------------------------------------------------------------

def test_ctrl_c_at_idle_repl_exits_130(fake_io, loop_factory):
    def read(prompt):
        raise KeyboardInterrupt

    session = ChatSession(loop_factory, read, fake_io.write)
    assert session.run() == 130
    assert loop_factory.requests == []


def test_ctrl_c_during_task_start_cancels_and_returns_to_repl(fake_io, history):
    class RaisingLoop(FakeLoop):
        def start_task(self, task_id, request, summaries):
            self.calls.append(("start_task", task_id, request, list(summaries)))
            raise KeyboardInterrupt

    loop = RaisingLoop()
    factory = RecordingLoopFactory(lambda: loop)
    reads = {"n": 0}

    def read(prompt):
        reads["n"] += 1
        if reads["n"] == 1:
            return "do work"
        return "/exit"

    session = ChatSession(factory, read, fake_io.write, history=history)
    assert session.run() == 0
    assert ("cancel",) in loop.calls
    assert history.summaries[-1].outcome == "cancelled"


# ---------------------------------------------------------------------------
# ValueError from the loop (e.g. strict DeepSeek protocol errors)
# ---------------------------------------------------------------------------

def test_loop_value_error_prints_error_and_session_continues(fake_io, history):
    """A strict-mode ValueError (e.g. malformed LLM action) must not kill
    the REPL: print [error] ..., end the task, continue to the next input."""
    class RaisingOnceLoop(FakeLoop):
        def __init__(self):
            super().__init__()
            self._raised = False

        def start_task(self, task_id, request, summaries):
            self.calls.append(("start_task", task_id, request, list(summaries)))
            if not self._raised:
                self._raised = True
                raise ValueError("Invalid action response from DeepSeek: sk-***")
            # Mirror FakeLoop.start_task without appending to calls again.
            result = (
                self.start_task_results.pop(0)
                if self.start_task_results
                else make_result(AgentState.COMPLETED)
            )
            self._apply(result)
            return result

    loop = RaisingOnceLoop()
    factory = RecordingLoopFactory(lambda: loop)
    session = ChatSession(factory, fake_io.read, fake_io.write, history=history)
    fake_io.queue("fix the bug", "do another task", "/exit")
    assert session.run() == 0
    assert "[error] Invalid action response from DeepSeek: sk-***" in fake_io.output
    # The next queued inputs were still processed: the REPL survived and
    # started a fresh task afterwards.
    assert ("start_task",) == tuple(c[0] for c in loop.calls[:1])
    assert len([c for c in loop.calls if c[0] == "start_task"]) == 2
    # The failed task left no summary; the second task completed normally.
    assert len(history.summaries) == 1
    assert history.summaries[-1].request == "do another task"
    assert history.summaries[-1].outcome == "completed"
    assert session._task_active is False


# ---------------------------------------------------------------------------
# Event sink wiring
# ---------------------------------------------------------------------------

def test_session_replaces_loop_event_sink_and_records_assistant_messages(
        fake_io, history):
    loop = FakeLoop()
    loop.emit_on_start(HarnessEventKind.ASSISTANT_MESSAGE,
                       {"message": "I will fix it"})
    loop.start_task_results.append(make_result(AgentState.COMPLETED))
    factory = RecordingLoopFactory(lambda: loop)
    session = ChatSession(factory, fake_io.read, fake_io.write, history=history)
    fake_io.queue("fix the bug", "/exit")
    assert session.run() == 0
    assert isinstance(loop.event_sink, CLIEventSink)
    assert "CodeGuard > I will fix it" in fake_io.output
    assert [m.content for m in history.messages] == ["fix the bug", "I will fix it"]


def test_session_skips_sink_when_loop_has_no_event_sink(fake_io, history):
    loop = FakeLoop(has_event_sink=False)
    loop.start_task_results.append(make_result(AgentState.COMPLETED))
    factory = RecordingLoopFactory(lambda: loop)
    session = ChatSession(factory, fake_io.read, fake_io.write, history=history)
    fake_io.queue("do work", "/exit")
    assert session.run() == 0
    assert not hasattr(loop, "event_sink")
    assert [m.content for m in history.messages] == ["do work"]


def test_guardrail_block_line_uses_final_decision(fake_io, history):
    loop = FakeLoop()
    loop.state.guardrail_decision = GuardrailResult(
        decision=GuardrailDecision.BLOCK,
        rule_ids=["workspace"],
        reason_codes=["workspace-escape"],
        human_readable_message="path escapes workspace",
        recoverable=False,
        normalized_action=None,
        action_fingerprint="fp-x",
    )
    # The guardrail decision is set on the loop state BEFORE the task
    # starts (as the real loop leaves it after a terminal BLOCK); the
    # session renders it once the FAILED result comes back.
    loop.start_task_results.append(make_result(AgentState.FAILED))
    factory = RecordingLoopFactory(lambda: loop)
    session = ChatSession(factory, fake_io.read, fake_io.write, history=history)
    fake_io.queue("write outside", "/exit")
    assert session.run() == 0
    assert "[guardrail] BLOCK: workspace-escape" in fake_io.output


# ---------------------------------------------------------------------------
# CLIEventSink rendering (plan Step 5)
# ---------------------------------------------------------------------------

class CollectingWrite:
    def __init__(self):
        self.lines = []

    def __call__(self, text):
        self.lines.append(text)


@pytest.fixture
def write_lines():
    return CollectingWrite()


def test_sink_renders_stable_prefixes(write_lines):
    sink = CLIEventSink(write_lines)
    sink.emit(HarnessEvent(HarnessEventKind.ASSISTANT_MESSAGE, "s1", "t1",
                           {"message": "Hello"}))
    sink.emit(HarnessEvent(HarnessEventKind.TOOL_STARTED, "s1", "t1",
                           {"tool": "read_file"}))
    sink.emit(HarnessEvent(HarnessEventKind.TOOL_FINISHED, "s1", "t1",
                           {"tool": "read_file", "status": "SUCCESS",
                            "output": "line 1"}))
    sink.emit(HarnessEvent(HarnessEventKind.APPROVAL_REQUESTED, "s1", "t1",
                           {"tool": "write_file", "reason": "risky write"}))
    sink.emit(HarnessEvent(HarnessEventKind.VALIDATION_FINISHED, "s1", "t1",
                           {"sensor": "pytest", "status": "PASSED",
                            "type": "FINAL"}))
    sink.emit(HarnessEvent(HarnessEventKind.TASK_FINISHED, "s1", "t1",
                           {"outcome": "completed", "summary": "all done"}))
    assert write_lines.lines == [
        "CodeGuard > Hello",
        "[tool] read_file",
        "[tool] read_file: SUCCESS line 1",
        "[approval] write_file risky write",
        "[validation] pytest: PASSED",
        "[task] COMPLETED: all done",
    ]


def test_sink_truncates_unbounded_assistant_message(write_lines):
    sink = CLIEventSink(write_lines)
    sink.emit(HarnessEvent(HarnessEventKind.ASSISTANT_MESSAGE, "s", "t",
                           {"message": "x" * 1200}))
    line = write_lines.lines[-1]
    assert line.startswith("CodeGuard > ")
    assert line.endswith("...")
    assert len(line) == len("CodeGuard > ") + 500 + 3


def test_sink_truncates_tool_output(write_lines):
    sink = CLIEventSink(write_lines)
    sink.emit(HarnessEvent(HarnessEventKind.TOOL_FINISHED, "s", "t",
                           {"tool": "run_tests", "status": "SUCCESS",
                            "output": "o" * 900}))
    line = write_lines.lines[-1]
    assert line.endswith("...")
    assert len(line) < len("[tool] run_tests: SUCCESS ") + 600


def test_sink_never_prints_unmodeled_payload_values(write_lines):
    sink = CLIEventSink(write_lines)
    sink.emit(HarnessEvent(HarnessEventKind.TOOL_FINISHED, "s", "t",
                           {"tool": "read_file", "status": "SUCCESS",
                            "output": "ok", "secret": "sk-123456"}))
    joined = "\n".join(write_lines.lines)
    assert "sk-123456" not in joined


def test_sink_ignores_state_changes_and_input_requests(write_lines):
    sink = CLIEventSink(write_lines)
    sink.emit(HarnessEvent(HarnessEventKind.STATE_CHANGED, "s", "t",
                           {"state": "deciding"}))
    sink.emit(HarnessEvent(HarnessEventKind.USER_INPUT_REQUESTED, "s", "t",
                           {"question": "Which file?"}))
    assert write_lines.lines == []


def test_sink_records_assistant_messages(write_lines):
    sink = CLIEventSink(write_lines)
    sink.emit(HarnessEvent(HarnessEventKind.ASSISTANT_MESSAGE, "s", "t",
                           {"message": "m1"}))
    sink.emit(HarnessEvent(HarnessEventKind.ASSISTANT_MESSAGE, "s", "t",
                           {"message": "m2"}))
    assert sink.assistant_messages == ["m1", "m2"]
