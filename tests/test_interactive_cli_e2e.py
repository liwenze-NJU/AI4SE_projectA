"""Deterministic end-to-end interactive coding tests (interactive CLI plan, Task 7).

These tests drive the REAL production composition — the ChatSession REPL over
a ``CompositionRoot(mode="test")`` loop with real tools, real guardrail /
approval, and the real pytest sensor — with ScriptedMockLLM at the LLM
boundary and queued CLI input at the reader boundary.  A temporary project is
safely modified and verified across multiple LLM decisions and two REPL
tasks.

Integration decisions (documented per the task instructions):

1. Scripted responses are written to the loop's expectations: the loop
   consumes ``llm_response.next_action`` (Action objects), never raw JSON,
   so parse errors cannot occur here.  For the approval flow, write_file
   hits ToolRiskRule REQUEST_APPROVAL and the session consumes ONE input
   line at the ``[y/N]`` prompt, so ``y`` is queued at that point.
2. The test-mode pytest sensor runs ``<sys.executable> -m pytest -q`` with
   cwd=the temporary project (required=False).  Every project under test
   keeps one tiny test file that PASSES after the scripted fix, so the
   real subprocess run stays small and the output shows
   ``[validation] pytest: PASSED``.
3. "Repeated invalid LLM JSON reaches LIMIT_REACHED" is implemented through
   the closest production-honest path: ScriptedMockLLM never parses JSON,
   so we script Actions that the governance pipeline rejects identically
   3+ consecutive times (a workspace-escape write, BLOCK + recoverable) and
   assert the real StopPolicy no-progress state machine terminates with
   LIMIT_REACHED.
4. "A failing required final sensor prevents COMPLETED" is configured by
   test-level wiring of the production verifier:
   ``loop.objective_verifier.required_sensors = ["pytest"]`` — the same
   class of test-level override as the write-risk ALLOW overrides in
   test_integration_guardrail_feedback.py — with a genuinely failing pytest
   suite in the temporary project.
5. The demo-isolation case uses ``CompositionRoot(mode="demo")`` whose loop
   has no dispatcher/sensor surface: ``start_task`` fails closed with FAILED
   and a redacted diagnostic BEFORE any LLM call, so a scripted write_file
   never reaches a handler.
6. ``/clear`` is asserted against ChatHistory only: a MemoryRecord saved
   into the composition-injected memory_store (via the loop's own
   project_id) must still be retrieved after chat messages are cleared.
"""

from decimal import Decimal
from pathlib import Path

from codeguard.action import Action, ActionKind, LLMResponse
from codeguard.chat import ChatHistory, ChatSession
from codeguard.composition import CompositionRoot
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.memory.models import (
    MemoryRecord,
    MemoryStatus,
    MemoryType,
    TrustLevel,
)
from codeguard.state import AgentState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resp(action: Action) -> LLMResponse:
    """Wrap an Action in an LLMResponse for ScriptedMockLLM."""
    return LLMResponse(
        content=action.raw or "mock",
        next_action=action,
        finish_reason="stop",
        model="mock",
        token_used=0,
        cost_used=Decimal("0"),
        raw_response="",
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


class InterruptOnReadN(FakeIO):
    """Raises KeyboardInterrupt (Ctrl+C) on the Nth read call."""

    def __init__(self, n):
        super().__init__()
        self._n = n
        self._reads = 0

    def read(self, prompt):
        self._reads += 1
        self.prompts.append(prompt)
        if self._reads == self._n:
            raise KeyboardInterrupt
        if not self._queue:
            return ""
        return self._queue.pop(0)


def _make_session(tmp_path: Path, responses, *, history=None):
    """Build a real CompositionRoot(mode="test") session over tmp_path.

    Returns (root, [loop], io, session); the created loop is kept in the
    list so tests can inspect the REAL loop after the REPL has run.
    """
    root = CompositionRoot(mode="test", workspace_root=str(tmp_path))
    loops = []

    def factory(session_id):
        loop = root.create_loop(session_id)
        loop.llm = ScriptedMockLLM(responses=list(responses))
        loops.append(loop)
        return loop

    io = FakeIO()
    session = ChatSession(factory, io.read, io.write, history=history)
    return root, loops, io, session


def _write_value_project(tmp_path: Path, value: str = "VALUE = 1\n") -> None:
    """Create the tiny fixture project.

    The test must be a real ``test_*`` function: a bare module-level assert
    is NOT collected by pytest, so the sensor would report "no tests ran"
    (exit 5) and never validate the change.
    """
    (tmp_path / "value.py").write_text(value, encoding="utf-8")
    (tmp_path / "test_value.py").write_text(
        "from value import VALUE\n"
        "def test_value():\n"
        "    assert VALUE == 2\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Happy path (plan Step 1)
# ---------------------------------------------------------------------------

def test_interactive_agent_edits_validates_and_accepts_second_task(tmp_path):
    """REPL → governed loop → real tools → approval → sensors → validation,
    then a second task starts in the same session."""
    _write_value_project(tmp_path)
    responses = [
        _resp(Action(ActionKind.ASSISTANT_MESSAGE,
                     message="Inspecting value.py", raw="")),
        _resp(Action(ActionKind.TOOL_CALL, tool_name="read_file",
                     parameters={"path": "value.py"}, raw="")),
        _resp(Action(ActionKind.TOOL_CALL, tool_name="write_file",
                     parameters={"path": "value.py", "content": "VALUE = 2\n"},
                     raw="")),
        _resp(Action(ActionKind.TOOL_CALL, tool_name="run_tests",
                     parameters={}, raw="")),
        _resp(Action(ActionKind.COMPLETE_REQUEST, summary="value.py updated",
                     raw="")),
        # second REPL task: harmless inspection
        _resp(Action(ActionKind.TOOL_CALL, tool_name="read_file",
                     parameters={"path": "value.py"}, raw="")),
        _resp(Action(ActionKind.COMPLETE_REQUEST, summary="inspected", raw="")),
    ]
    history = ChatHistory(max_messages=50, max_summaries=10)
    _root, loops, io, session = _make_session(tmp_path, responses, history=history)
    io.queue("fix value.py so the test passes", "y",
             "inspect the project", "/exit")
    assert session.run() == 0

    loop = loops[0]

    # The temporary project was really modified through the real handler.
    assert (tmp_path / "value.py").read_text(encoding="utf-8") == "VALUE = 2\n"

    # The approval pause consumed exactly one explicit `y` at a [y/N] prompt
    # naming the tool and target.
    joined_prompts = "".join(io.prompts)
    assert "Approve write_file" in joined_prompts
    assert "value.py" in joined_prompts
    assert "[y/N]" in joined_prompts

    # Validation is recorded as passed (intermediate after the write).
    assert "[validation] pytest: PASSED" in io.output
    assert any(r.status == "PASSED" for r in loop._feedback_results)

    # Both tasks reached COMPLETED and left summaries.
    assert io.output.count("[task] COMPLETED") == 2
    assert len(history.summaries) == 2
    assert history.summaries[0].request == "fix value.py so the test passes"
    assert history.summaries[0].outcome == "completed"
    assert history.summaries[1].request == "inspect the project"
    assert history.summaries[1].outcome == "completed"

    # The output carries assistant/tool/approval/validation/task events.
    assert "CodeGuard > Inspecting value.py" in io.output
    assert "[tool] read_file" in io.output
    assert "[tool] run_tests" in io.output
    assert "[approval] write_file" in io.output

    # One loop served both tasks and consumed every scripted decision.
    assert len(loop.llm.received_contexts) == 7


# ---------------------------------------------------------------------------
# Negative cases (plan Step 4)
# ---------------------------------------------------------------------------

def test_empty_approval_rejects_and_leaves_file_unchanged(tmp_path):
    _write_value_project(tmp_path)
    responses = [
        _resp(Action(ActionKind.TOOL_CALL, tool_name="write_file",
                     parameters={"path": "value.py", "content": "VALUE = 2\n"},
                     raw="")),
    ]
    history = ChatHistory(max_messages=50, max_summaries=10)
    _root, loops, io, session = _make_session(tmp_path, responses, history=history)
    io.queue("bump the value", "", "/exit")  # empty approval answer
    assert session.run() == 0

    assert (tmp_path / "value.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert history.summaries[-1].outcome == "cancelled"
    assert "[approval] write_file" in io.output
    # The loop paused at the approval and never made another decision.
    assert len(loops[0].llm.received_contexts) == 1


def test_workspace_escape_is_blocked_and_no_handler_runs(tmp_path):
    responses = [
        _resp(Action(ActionKind.TOOL_CALL, tool_name="write_file",
                     parameters={"path": "../escape.txt", "content": "boom"},
                     raw="")),
        _resp(Action(ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ]
    history = ChatHistory(max_messages=50, max_summaries=10)
    _root, loops, io, session = _make_session(tmp_path, responses, history=history)
    io.queue("write outside", "/exit")
    assert session.run() == 0

    loop = loops[0]
    # No handler ran: the escaped file does not exist and no tool started.
    assert not (tmp_path.parent / "escape.txt").exists()
    assert "[tool] write_file" not in io.output
    # The escape reached governance (fingerprint recorded) and the BLOCK
    # was fed back into the next decision.
    assert len(loop.state.action_fingerprint_history) == 1
    assert "Guardrail BLOCK" in loop.llm.received_contexts[1]
    assert history.summaries[-1].outcome == "completed"


def test_request_user_input_resumes_with_user_answer(tmp_path):
    (tmp_path / "config.py").write_text("PORT = 1\n", encoding="utf-8")
    responses = [
        _resp(Action(ActionKind.REQUEST_USER_INPUT, question="Which file?",
                     raw="")),
        _resp(Action(ActionKind.TOOL_CALL, tool_name="read_file",
                     parameters={"path": "config.py"}, raw="")),
        _resp(Action(ActionKind.COMPLETE_REQUEST, summary="ok", raw="")),
    ]
    history = ChatHistory(max_messages=50, max_summaries=10)
    _root, loops, io, session = _make_session(tmp_path, responses, history=history)
    io.queue("read the config", "config.py", "/exit")
    assert session.run() == 0

    loop = loops[0]
    assert "CodeGuard asks: Which file?" in io.output
    # The user's answer reached the next LLM decision.
    assert "User answer: config.py" in loop.llm.received_contexts[1]
    assert history.summaries[-1].outcome == "completed"


def test_cancel_command_prevents_later_tool_execution(tmp_path):
    """/cancel at a clarification pause cancels the task; the scripted
    write_file that would have come next never executes."""
    responses = [
        _resp(Action(ActionKind.REQUEST_USER_INPUT, question="Which file?",
                     raw="")),
        _resp(Action(ActionKind.TOOL_CALL, tool_name="write_file",
                     parameters={"path": "value.py", "content": "VALUE = 2\n"},
                     raw="")),
    ]
    history = ChatHistory(max_messages=50, max_summaries=10)
    _root, loops, io, session = _make_session(tmp_path, responses, history=history)
    io.queue("edit something", "/cancel", "/exit")
    assert session.run() == 0

    loop = loops[0]
    assert loop.state.current_state == AgentState.CANCELLED
    assert history.summaries[-1].outcome == "cancelled"
    assert "[task] CANCELLED" in io.output
    # Only the first decision was made; the write action never ran.
    assert len(loop.llm.received_contexts) == 1
    assert not (tmp_path / "value.py").exists()


def test_ctrl_c_at_approval_prompt_prevents_later_tool_execution(tmp_path):
    """Ctrl+C at the approval prompt is a rejection: the write is not
    executed and no further decision is taken."""
    _write_value_project(tmp_path)
    responses = [
        _resp(Action(ActionKind.TOOL_CALL, tool_name="write_file",
                     parameters={"path": "value.py", "content": "VALUE = 2\n"},
                     raw="")),
    ]
    history = ChatHistory(max_messages=50, max_summaries=10)
    root = CompositionRoot(mode="test", workspace_root=str(tmp_path))
    loop = root.create_loop("ctrl-c-session")
    loop.llm = ScriptedMockLLM(responses=list(responses))
    io = InterruptOnReadN(n=2)  # read 1 = task input, read 2 = approval prompt
    io.queue("bump the value", "/exit")
    session = ChatSession(lambda sid: loop, io.read, io.write, history=history)
    assert session.run() == 0

    assert (tmp_path / "value.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert history.summaries[-1].outcome == "cancelled"
    assert len(loop.llm.received_contexts) == 1


def test_repeated_invalid_actions_reach_limit_reached(tmp_path):
    """Repeated governance-rejected actions (identical fingerprints) drive
    the real StopPolicy no-progress state machine to LIMIT_REACHED
    (integration decision 3)."""
    responses = [
        _resp(Action(ActionKind.TOOL_CALL, tool_name="write_file",
                     parameters={"path": "..", "content": "escape"}, raw="")),
    ] * 4
    history = ChatHistory(max_messages=50, max_summaries=10)
    _root, loops, io, session = _make_session(tmp_path, responses, history=history)
    io.queue("write outside", "/exit")
    assert session.run() == 0

    loop = loops[0]
    assert history.summaries[-1].outcome == "limit_reached"
    assert len(loop.state.action_fingerprint_history) >= 3
    assert "[task] COMPLETED" not in io.output


def test_failing_required_final_sensor_prevents_completed(tmp_path):
    """With the production verifier required on pytest (test-level wiring,
    integration decision 4), a failing suite keeps the terminal state away
    from COMPLETED and the failure is fed back into the next decision."""
    _write_value_project(tmp_path)
    write = _resp(Action(ActionKind.TOOL_CALL, tool_name="write_file",
                         parameters={"path": "value.py", "content": "VALUE = 1\n"},
                         raw=""))
    complete = _resp(Action(ActionKind.COMPLETE_REQUEST, summary="done", raw=""))
    history = ChatHistory(max_messages=50, max_summaries=10)
    root = CompositionRoot(mode="test", workspace_root=str(tmp_path))
    loop = root.create_loop("required-sensor-session")
    loop.llm = ScriptedMockLLM(
        responses=[write, complete, write, complete, write, complete]
    )
    # Test-level wiring of the production verifier: this is the same class
    # of override as the write-risk ALLOW overrides in
    # test_integration_guardrail_feedback.py.
    loop.objective_verifier.required_sensors = ["pytest"]
    io = FakeIO()
    session = ChatSession(lambda sid: loop, io.read, io.write, history=history)
    io.queue("make it pass", "y", "y", "y", "/exit")
    assert session.run() == 0

    assert history.summaries[-1].outcome != "completed"
    assert history.summaries[-1].outcome == "limit_reached"
    assert "[validation] pytest: FAILED" in io.output
    # The failure was fed back into the next LLM decision.
    assert any("Validation pytest: FAILED" in c
               for c in loop.llm.received_contexts)
    assert any(r.status == "FAILED" for r in loop._feedback_results)


def test_clear_removes_messages_but_keeps_structured_memory(tmp_path):
    """/clear removes chat messages only; structured memory records for the
    project survive (integration decision 6)."""
    _write_value_project(tmp_path)
    root = CompositionRoot(mode="test", workspace_root=str(tmp_path))
    loop = root.create_loop("clear-session")
    loop.llm = ScriptedMockLLM(responses=[
        _resp(Action(ActionKind.TOOL_CALL, tool_name="read_file",
                     parameters={"path": "value.py"}, raw="")),
        _resp(Action(ActionKind.COMPLETE_REQUEST, summary="ok", raw="")),
    ])
    history = ChatHistory(max_messages=50, max_summaries=10)
    io = FakeIO()
    session = ChatSession(lambda sid: loop, io.read, io.write, history=history)

    # A structured memory record for THIS project, saved BEFORE /clear runs
    # through the composition-injected store with the loop's own project id.
    loop.memory_store.save(MemoryRecord(
        id="m7",
        project_id=loop.project_id,
        type=MemoryType.TASK_SUMMARY,
        content="value.py holds VALUE = 1",
        tags=["value"],
        keywords=["value"],
        source="e2e",
        trust_level=TrustLevel.USER_APPROVED,
        status=MemoryStatus.ACTIVE,
    ))

    io.queue("inspect", "/clear", "/exit")
    assert session.run() == 0

    assert history.messages == []
    assert len(history.summaries) == 1  # task summaries are kept
    assert "Chat messages cleared" in io.output
    retrieved = loop.memory_retriever.retrieve(project_id=loop.project_id)
    assert [r.id for r in retrieved] == ["m7"]


def test_demo_composition_cannot_modify_the_project(tmp_path):
    """Demo mode has no dispatcher/sensor surface: start_task fails closed
    with FAILED and a redacted diagnostic before any LLM call, so even a
    scripted write_file never reaches a handler (integration decision 5)."""
    root = CompositionRoot(mode="demo", workspace_root=str(tmp_path))
    loop = root.create_loop("demo-session")
    loop.llm = ScriptedMockLLM(responses=[
        _resp(Action(ActionKind.TOOL_CALL, tool_name="write_file",
                     parameters={"path": "value.py", "content": "VALUE = 2\n"},
                     raw="")),
    ])
    history = ChatHistory(max_messages=50, max_summaries=10)
    io = FakeIO()
    session = ChatSession(lambda sid: loop, io.read, io.write, history=history)
    io.queue("change value.py", "/exit")
    assert session.run() == 0

    assert not (tmp_path / "value.py").exists()
    assert loop.llm.received_contexts == []
    assert history.summaries[-1].outcome == "failed"
    summary = history.summaries[-1].summary
    assert "tool_dispatcher" in summary
    assert "sensor_runner" in summary
