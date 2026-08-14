# Interactive Coding-Agent CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn CodeGuard's one-shot local session into an in-process multi-task coding-agent REPL that really reads, edits, and validates the current workspace under the existing Guardrail and approval rules.

**Architecture:** Keep one governed `AgentLoop` per user task and add a `ChatSession` above it for process-local conversation. First replace the production composition root's placeholder handlers with real tools and feedback/context wiring; then extend the action/state protocol and loop; finally add CLI interaction and deterministic end-to-end tests.

**Tech Stack:** Python 3.12, argparse, dataclasses, DeepSeek OpenAI-compatible HTTP API, keyring, pytest 8.3.2, PyInstaller 6.10.0.

## Global Constraints

- Work only on branch `feature/interactive-cli-agent` in `.worktrees/interactive-cli-agent`; never merge it into `main`.
- `main` must remain the course version at `30581f0` / v0.1.1.
- Use Python 3.12 and invoke tests as `python -m pytest`, using the worktree's `.venv\Scripts\python.exe` on Windows.
- Follow strict TDD for every behavior change: run a targeted RED test, implement the minimum, run GREEN, then run the relevant regression group.
- Never use `shell=True`; processes remain structured `program + args` calls inside the workspace.
- Demo and WebUI modes must remain Mock-only and must not import or invoke real DeepSeek, keyring, filesystem mutation, Shell, or network boundaries.
- Local mode must fail closed when credentials, workspace validation, dispatcher, sensors, or required safety components are unavailable.
- Complete chat history is process-local only. `/clear` and process exit must not delete or rewrite structured project memory.
- `ASSISTANT_MESSAGE` never completes a task; only successful final validation may produce `COMPLETED`.
- Tool, sensor, approval, and LLM output must be redacted and bounded before entering model context or persistent Trace.
- Do not implement streaming, `/resume`, model switching, real WebUI chat, multi-agent execution, Git push, or release automation in this plan.
- After each task, run `git diff --check`, update this plan's checkboxes and append an accurate entry to `AGENT_LOG.md`, then commit only that task's files.

## File Structure

### Create

- `codeguard/events.py` — typed Harness events and the event-sink protocol.
- `codeguard/chat/session.py` — process-local REPL/session coordinator; no tool execution logic.
- `codeguard/chat/history.py` — bounded process-local messages and completed-task summaries.
- `codeguard/chat/__init__.py` — exports chat interfaces.
- `codeguard/feedback/composite.py` — adapter that runs an ordered list of `SensorRunner` instances.
- `tests/test_events.py` — event contract tests.
- `tests/test_chat_history.py` — process-local history and clearing tests.
- `tests/test_chat_session.py` — commands, task lifecycle, clarification, approval, and cancellation tests.
- `tests/test_composition_production.py` — direct production-composition wiring tests.
- `tests/test_context_runtime.py` — runtime context and feedback carry-forward tests.
- `tests/test_interactive_cli_e2e.py` — deterministic REPL-to-temporary-workspace tests.

### Modify

- `codeguard/action.py` — add message and user-input actions and parse their required fields.
- `codeguard/state.py` — add `AWAITING_USER_INPUT` and pending-question state.
- `codeguard/loop.py` — accept a task request, use `ContextBuilder`, publish events, carry tool/feedback results, pause/resume for clarification, and fail closed on missing production components.
- `codeguard/context.py` — build bounded runtime context from task, summaries, trusted memory, tools, feedback, and budgets.
- `codeguard/composition.py` — register real handlers and inject dispatcher, sensors, memory, context, and event sink variants.
- `codeguard/guardrail/rules.py` — enforce each registered tool's declared default risk in code.
- `codeguard/tool/dispatcher.py` — dispatch normalized actions consistently and return bounded `ToolResult`.
- `codeguard/feedback/sensor.py` — expose sensor definition metadata needed by the composite runner.
- `codeguard/cli/chat.py` — replace one-shot behavior with interactive `ChatSession` entry point.
- `codeguard/__main__.py` — update chat help and pass the parsed mode/workspace cleanly.
- `codeguard/llm/deepseek.py` — send the action protocol system message and parse all supported action kinds.
- `codeguard/llm/mock.py` — record received contexts for deterministic feedback tests.
- `codeguard/memory/store.py`, `codeguard/memory/retriever.py` — reuse their public APIs from composition; do not change persistence semantics unless a failing composition test proves a defect.
- `tests/test_action.py`, `tests/test_state.py`, `tests/test_loop.py`, `tests/test_context.py`, `tests/test_composition_root.py`, `tests/test_cli.py`, `tests/test_llm_deepseek.py` — extend existing behavior without weakening old assertions.
- `README.md`, `SECURITY.md`, `AGENT_LOG.md` — document the enhanced branch only after functionality passes.

---

### Task 0: Restore a Reproducible Python 3.12 Baseline

**Files:**
- Verify: `requirements/dev.txt`
- Verify: `requirements/runtime.txt`
- Do not modify source code.

**Interfaces:**
- Consumes: Windows Python 3.12 installation or an explicitly approved Python 3.12 executable.
- Produces: `.venv\Scripts\python.exe` with the pinned development dependencies and a fresh baseline test result.

- [ ] **Step 1: Confirm the isolated branch and broken baseline interpreter**

Run:

```powershell
git branch --show-current
git status --short --branch
py -0p
Test-Path .\.venv\Scripts\python.exe
```

Expected: branch is `feature/interactive-cli-agent`; worktree is clean; the existing environment is absent or unusable. Do not treat the missing interpreter as a product test failure.

- [ ] **Step 2: Install or select Python 3.12 with user approval**

If `py -3.12` is unavailable, stop and obtain approval before installing Python. Do not download or install an interpreter silently. After Python is available, run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements\dev.txt
```

Expected: all commands exit 0 and `.venv\Scripts\python.exe --version` reports Python 3.12.x.

- [ ] **Step 3: Run the full baseline suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs
```

Expected: the existing suite passes with only the documented Windows symlink skip. Record the fresh count in `AGENT_LOG.md`. If any test fails, stop feature work and use `superpowers:systematic-debugging` to determine whether the branch baseline or environment is responsible.

- [ ] **Step 4: Verify no environment files are tracked**

Run:

```powershell
git status --short
git check-ignore -v .venv
```

Expected: `.venv` is ignored and the source worktree remains clean. Task 0 creates no commit unless documentation must record a necessary environment correction.

---

### Task 1: Define Conversation Actions and Harness Events

**Files:**
- Create: `codeguard/events.py`
- Create: `tests/test_events.py`
- Modify: `codeguard/action.py`
- Modify: `codeguard/state.py`
- Modify: `tests/test_action.py`
- Modify: `tests/test_state.py`

**Interfaces:**
- Consumes: existing `Action`, `ActionKind`, `ActionParser`, `AgentState`.
- Produces: `ActionKind.ASSISTANT_MESSAGE`, `ActionKind.REQUEST_USER_INPUT`, `AgentState.AWAITING_USER_INPUT`, `HarnessEventKind`, `HarnessEvent`, and `EventSink.emit(event: HarnessEvent) -> None`.

- [x] **Step 1: Write failing action and state tests**

Add these focused tests:

```python
def test_parser_accepts_assistant_message():
    action = ActionParser().parse(
        '{"action":"assistant_message","message":"I will inspect the tests."}'
    )
    assert action.kind is ActionKind.ASSISTANT_MESSAGE
    assert action.message == "I will inspect the tests."


def test_parser_rejects_empty_assistant_message():
    with pytest.raises(ValueError, match="message"):
        ActionParser().parse('{"action":"assistant_message","message":""}')


def test_parser_accepts_user_input_request():
    action = ActionParser().parse(
        '{"action":"request_user_input","question":"Which file should change?"}'
    )
    assert action.kind is ActionKind.REQUEST_USER_INPUT
    assert action.question == "Which file should change?"


def test_agent_state_has_awaiting_user_input():
    assert AgentState.AWAITING_USER_INPUT.value == "awaiting_user_input"
```

- [x] **Step 2: Run the targeted tests to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_action.py tests\test_state.py -q
```

Expected: FAIL because the enum values and fields do not exist.

- [x] **Step 3: Add the minimal action and state model**

Use these exact fields:

```python
class ActionKind(Enum):
    TOOL_CALL = "tool_call"
    ASSISTANT_MESSAGE = "assistant_message"
    REQUEST_USER_INPUT = "request_user_input"
    COMPLETE_REQUEST = "complete"


@dataclass
class Action:
    kind: ActionKind
    tool_name: Optional[str] = None
    parameters: Optional[dict] = None
    summary: Optional[str] = None
    message: Optional[str] = None
    question: Optional[str] = None
    raw: str = ""
```

Add `AWAITING_USER_INPUT = "awaiting_user_input"` to `AgentState`, plus `pending_question: Optional[str] = None` to `SessionState`. `ActionParser` must require a non-empty string for `message`, `question`, and the existing completion `summary`; unknown actions remain errors.

- [x] **Step 4: Write failing event-contract tests**

```python
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
```

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_events.py -q
```

Expected: collection ERROR because `codeguard.events` does not exist.

- [x] **Step 5: Implement the event protocol**

Create:

```python
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
```

Also implement `NullEventSink` and `CollectingEventSink`; the latter is a deterministic test utility with `events: list[HarnessEvent]`.

- [x] **Step 6: Run GREEN and regressions**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_action.py tests\test_state.py tests\test_events.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_loop.py tests\test_llm_mock.py tests\test_llm_deepseek.py -q
git diff --check
```

Expected: all targeted and related tests pass.

- [x] **Step 7: Log and commit**

```powershell
git add codeguard\action.py codeguard\state.py codeguard\events.py tests\test_action.py tests\test_state.py tests\test_events.py AGENT_LOG.md docs\superpowers\plans\2026-08-13-interactive-cli-agent.md
git commit -m "feat: add conversational action and event contracts"
```

---

### Task 2: Build Bounded Runtime Context and Process-Local History

**Files:**
- Create: `codeguard/chat/__init__.py`
- Create: `codeguard/chat/history.py`
- Create: `tests/test_chat_history.py`
- Create: `tests/test_context_runtime.py`
- Modify: `codeguard/context.py`
- Modify: `tests/test_context.py`

**Interfaces:**
- Consumes: `MemoryRecord`, `ToolDefinition`, `ToolResult`, `FeedbackResult`, `SecretRedactor`.
- Produces: `ChatMessage(role: str, content: str)`, `TaskSummary(task_id: str, request: str, outcome: str, summary: str)`, `ChatHistory`, and `ContextBuilder.build_runtime(...) -> str`.

- [x] **Step 1: Write failing process-local history tests**

```python
def test_clear_removes_messages_but_keeps_task_summaries():
    history = ChatHistory(max_messages=4, max_summaries=2)
    history.add_message("user", "fix auth")
    history.add_summary(TaskSummary("t1", "fix auth", "completed", "tests pass"))
    history.clear_messages()
    assert history.messages == []
    assert [s.task_id for s in history.summaries] == ["t1"]


def test_history_evicts_oldest_message_deterministically():
    history = ChatHistory(max_messages=2, max_summaries=2)
    history.add_message("user", "one")
    history.add_message("assistant", "two")
    history.add_message("user", "three")
    assert [m.content for m in history.messages] == ["two", "three"]
```

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_history.py -q
```

Expected: collection ERROR because the history module does not exist.

- [x] **Step 2: Implement bounded history**

Use frozen dataclasses and list copies from read-only properties. Reject roles outside `{"user", "assistant"}` and empty content. `clear_messages()` must not call the persistent memory store and must not remove task summaries.

- [x] **Step 3: Write failing runtime-context tests**

```python
def test_runtime_context_priority_and_feedback():
    context = ContextBuilder(max_chars=4000, redactor=SecretRedactor()).build_runtime(
        system_constraints="Never escape workspace",
        task_request="Fix failing parser test",
        conversation_summaries=["Earlier: use pytest"],
        memory_records=[],
        tool_descriptions=["read_file(path)", "run_tests()"],
        latest_result="pytest failed at tests/test_parser.py:12",
        budget_summary="steps 1/20; tokens 100/10000",
    )
    assert context.index("Never escape workspace") < context.index("Fix failing parser test")
    assert "tests/test_parser.py:12" in context
    assert "read_file(path)" in context


def test_runtime_context_never_truncates_task_or_latest_error():
    context = ContextBuilder(max_chars=240, redactor=SecretRedactor()).build_runtime(
        system_constraints="SAFE",
        task_request="CURRENT-TASK",
        conversation_summaries=["old-" * 100],
        memory_records=[],
        tool_descriptions=["read_file(path)"],
        latest_result="LATEST-ERROR",
        budget_summary="steps 1/2",
    )
    assert "CURRENT-TASK" in context
    assert "LATEST-ERROR" in context
    assert len(context) <= 240
```

- [x] **Step 4: Run runtime-context tests to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_context_runtime.py -q
```

Expected: FAIL because `ContextBuilder` does not accept these arguments or implement priority truncation.

- [x] **Step 5: Implement `build_runtime` without breaking legacy `build`**

Add:

```python
def build_runtime(
    self,
    system_constraints: str,
    task_request: str,
    conversation_summaries: list[str],
    memory_records: list[MemoryRecord],
    tool_descriptions: list[str],
    latest_result: str,
    budget_summary: str,
) -> str:
```

Build named sections in the specified priority. Redact every external string. When over `max_chars`, drop oldest conversation summaries first, then memory records, then shorten tool descriptions. Reserve space for system constraints, current task, latest result, and budget; if these mandatory fields alone exceed the limit, truncate the system constraints first but retain the complete current task and latest result or raise `ValueError` when that is mathematically impossible.

- [x] **Step 6: Run GREEN and regressions**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_history.py tests\test_context_runtime.py tests\test_context.py -q
git diff --check
```

Expected: all pass; the legacy context tests remain unchanged.

- [x] **Step 7: Log and commit**

```powershell
git add codeguard\chat codeguard\context.py tests\test_chat_history.py tests\test_context_runtime.py tests\test_context.py AGENT_LOG.md docs\superpowers\plans\2026-08-13-interactive-cli-agent.md
git commit -m "feat: add bounded chat history and runtime context"
```

---

### Task 3: Wire Real Tools, Dispatcher, and Sensors in the Composition Root

**Files:**
- Create: `codeguard/feedback/composite.py`
- Create: `tests/test_composition_production.py`
- Modify: `codeguard/composition.py`
- Modify: `codeguard/tool/dispatcher.py`
- Modify: `codeguard/feedback/sensor.py`
- Modify: `codeguard/guardrail/rules.py`
- Modify: `tests/test_composition_root.py`
- Modify: `tests/test_tool_dispatcher.py`
- Modify: `tests/test_guardrail_rules.py`
- Modify: `tests/test_memory_retriever.py`

**Interfaces:**
- Consumes: real handlers in `codeguard.tool.file_tools`, `run_process`, `ToolRegistry`, `ToolDispatcher`, `SensorRunner`, config dataclasses.
- Produces: `CompositeSensorRunner.run_all() -> list[FeedbackResult]`, `ToolRiskRule`, and a fully wired `CompositionRoot(mode, workspace_root=None, event_sink=None)` with project-scoped memory retrieval.

- [x] **Step 1: Write failing composition tests that expose placeholder wiring**

```python
def test_test_composition_has_dispatcher_and_sensors(tmp_path):
    loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
    assert isinstance(loop.tool_dispatcher, ToolDispatcher)
    assert loop.sensor_runner is not None


def test_read_file_handler_reads_temporary_workspace(tmp_path):
    (tmp_path / "hello.txt").write_text("hello", encoding="utf-8")
    loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
    action = Action(ActionKind.TOOL_CALL, "read_file", {"path": "hello.txt"})
    result = loop.tool_dispatcher.dispatch(action)
    assert result.status == "SUCCESS"
    assert "hello" in result.output_summary


def test_required_sensors_are_not_an_empty_success_in_local_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(KeyringCredentialStore, "get", lambda self, provider: "sk-test")
    loop = CompositionRoot(mode="local", workspace_root=tmp_path).create_loop("s1")
    assert loop.sensor_runner is not None
    assert loop.objective_verifier.required_sensors


def test_write_file_declared_risk_requests_approval(tmp_path):
    loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
    action = loop.action_normalizer.normalize(
        Action(ActionKind.TOOL_CALL, "write_file", {"path": "a.py", "content": "x = 1"})
    )
    result = loop.rule_engine.evaluate(action)
    assert result.decision is GuardrailDecision.REQUEST_APPROVAL
```

- [x] **Step 2: Run the composition tests to verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_composition_production.py -q
```

Expected: FAIL because dispatcher/sensors are `None`, handlers return `None`, and final validation accepts an empty required-sensor list.

- [x] **Step 3: Implement `CompositeSensorRunner`**

```python
class CompositeSensorRunner:
    def __init__(self, runners: list[SensorRunner]):
        if not runners:
            raise ValueError("At least one sensor runner is required")
        self._runners = list(runners)

    def run_all(self) -> list[FeedbackResult]:
        return [runner.run() for runner in self._runners]
```

Expose a read-only `definition` property from `SensorRunner` so composition can derive required sensor names without reaching into private fields.

- [x] **Step 4: Register the exact real handlers**

Map:

```python
"read_file" -> file_tools.read_file
"list_directory" -> file_tools.list_directory
"find_files" -> file_tools.find_files
"search_text" -> file_tools.search_text
"write_file" -> file_tools.write_file
"apply_patch" -> file_tools.apply_patch
"delete_file" -> file_tools.delete_file
"run_process" -> process_tool.run_process
```

Register `run_tests`, `run_lint`, and `run_typecheck` as structured wrappers around trusted, configuration-owned `SensorDefinition` objects. Do not accept user-supplied program strings for these trusted validation tools.

Use complete schemas matching the actual handlers: `write_file` requires `path` and `content`; `apply_patch` requires `path`, `old_string`, and `new_string`; `run_process` requires `program` and accepts `args`, `cwd`, and bounded `timeout`. Do not preserve the current incomplete schemas merely to keep old tests green.

- [x] **Step 5: Make the dispatcher accept `Action | NormalizedAction` safely**

Normalize parameter extraction in one private helper and call registered handlers as `handler(params, workspace_root=str(self._workspace_root))`. A missing dispatcher or unknown tool must fail closed. Return redacted `ToolResult`; never coerce an exception into success.

- [x] **Step 6: Wire each mode explicitly**

Use constructor:

```python
def __init__(
    self,
    mode: str = "test",
    workspace_root: str | Path | None = None,
    event_sink: EventSink | None = None,
):
```

Resolve the root once. In `test`, require a caller-provided temporary root for any test that executes real handlers and use deterministic configured sensors. In `local`, use the current/project root, real dispatcher, DeepSeek, persistent memory, and at least pytest as a required sensor. Define pytest with `program=sys.executable`, `args=["-m", "pytest", "-q"]`, `cwd=workspace_root`; it is configuration-owned rather than model-controlled. In `demo`, retain the existing Mock composition and explicitly avoid real dispatcher/sensors.

Compute `project_id` as SHA-256 of the normalized, case-normalized absolute workspace path. In local mode store structured memory below `%LOCALAPPDATA%\CodeGuard\memory` (raise a clear fail-closed error if the location is unavailable); in tests use a caller-provided temporary memory base. Inject `JSONMemoryStore` and `MemoryRetriever(top_k=10, context_budget=2048)` into the loop. Retrieval must still return ACTIVE records only and preserve the existing trust ordering.

- [x] **Step 7: Enforce registered tool risk through Guardrail code**

Add `ToolRiskRule(registry: ToolRegistry)`. For `TOOL_CALL`, look up `ToolDefinition.default_risk` and return exactly `ALLOW`, `REQUEST_APPROVAL`, or `BLOCK`; unknown risk strings fail closed as BLOCK. Non-tool conversation actions are never sent through the tool governance pipeline. Register rules in the composition root so the engine includes workspace boundary, credential leak, unregistered tool, mode restriction, and tool risk. Set ordinary write/patch tools to `REQUEST_APPROVAL`, destructive deletion to `REQUEST_APPROVAL` or `BLOCK` according to the existing declared definition, and trusted read/test tools to `ALLOW`.

- [x] **Step 8: Run composition, dispatcher, memory, Guardrail, and demo-safety regressions**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_composition_production.py tests\test_composition_root.py tests\test_tool_dispatcher.py tests\test_guardrail_rules.py tests\test_memory_retriever.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_demo_scenario_a.py tests\test_demo_scenario_b.py tests\test_demo_scenario_c.py tests\test_web_mock_security.py -q
git diff --check
```

Expected: all pass. Demo safety tests must still prove zero real boundaries.

- [ ] **Step 9: Log and commit**

```powershell
git add codeguard\composition.py codeguard\tool\dispatcher.py codeguard\feedback\sensor.py codeguard\feedback\composite.py codeguard\guardrail\rules.py tests\test_composition_production.py tests\test_composition_root.py tests\test_tool_dispatcher.py tests\test_guardrail_rules.py tests\test_memory_retriever.py AGENT_LOG.md docs\superpowers\plans\2026-08-13-interactive-cli-agent.md
git commit -m "fix: wire production tools and validation sensors"
```

---

### Task 4: Feed Tasks, Tool Results, and Validation Back into AgentLoop

**Files:**
- Modify: `codeguard/loop.py`
- Modify: `codeguard/context.py`
- Modify: `codeguard/llm/mock.py`
- Modify: `tests/test_loop.py`
- Modify: `tests/test_integration_guardrail_feedback.py`
- Modify: `tests/test_phase14_spec_compliance.py`
- Modify: `tests/test_context_runtime.py`

**Interfaces:**
- Consumes: `ContextBuilder.build_runtime`, `EventSink`, dispatcher, sensor runner, memory retriever, `Action` conversation kinds.
- Produces: `AgentLoop.start_task(task_id: str, request: str, conversation_summaries: list[str]) -> SessionResult`, `resume_with_user_input(text: str) -> SessionResult`, and `cancel() -> SessionResult`.

- [x] **Step 1: Write failing context carry-forward test**

```python
def test_tool_result_is_in_next_llm_context(tmp_path):
    llm = RecordingScriptedMockLLM([
        response_for(tool_call("read_file", {"path": "a.txt"})),
        response_for(complete("done")),
    ])
    loop = make_wired_test_loop(tmp_path, llm)
    (tmp_path / "a.txt").write_text("needle", encoding="utf-8")
    result = loop.start_task("t1", "Inspect a.txt", [])
    assert result.terminal_state is AgentState.COMPLETED
    assert "needle" in llm.received_contexts[1]
```

Also write a test proving the first context contains the current request and available tool descriptions.

- [x] **Step 2: Run targeted tests to verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_context_runtime.py tests\test_loop.py -q
```

Expected: FAIL because `start_task`, recorded contexts, and runtime context integration do not exist.

- [x] **Step 3: Record contexts in the Mock LLM**

Add `received_contexts: list[str]`, append the exact context at the start of every `generate`, and preserve all existing scripted-response behavior.

- [x] **Step 4: Add explicit per-task inputs and result carry-forward**

`start_task` must initialize task ID, request, summaries, reset per-task counters/results, and call the governed loop. Replace `_build_context()` with `ContextBuilder.build_runtime(...)`. Save the latest redacted `ToolResult`, `FeedbackResult`, Guardrail BLOCK, approval rejection, or parser error in a bounded feedback field used by the next decision.

The dispatcher result must be appended to Trace/events and checked. `FAILURE`, `ERROR`, or `TIMEOUT` transitions to `FEEDING_BACK`; it must never be treated as a successful execution.

- [x] **Step 5: Implement message and clarification behavior**

- `ASSISTANT_MESSAGE`: emit an event, save the message in the task transcript, transition through `FEEDING_BACK` to `DECIDING`, and consume an LLM call but not a tool step.
- `REQUEST_USER_INPUT`: set `pending_question`, emit an event, transition to `AWAITING_USER_INPUT`, and return a non-terminal `SessionResult`.
- `resume_with_user_input(text)`: require the awaiting state and non-empty text, add the answer to the latest context, clear the pending question, transition to `DECIDING`, and continue.
- `cancel()`: transition an active or waiting task to `CANCELLED`; no tool may execute afterward.

- [x] **Step 6: Fail closed on incomplete production wiring**

At task start, validate that context builder, registry, normalizer, rule engine, dispatcher, sensor runner, objective verifier, stop policy, redactor, and event sink exist. Return `FAILED` with a redacted diagnostic when any required component is missing. Demo scenario helpers may keep their dedicated Mock assembly, but normal test/local task execution cannot silently skip a component.

- [x] **Step 7: Run loop and integration regressions**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_loop.py tests\test_context_runtime.py tests\test_integration_guardrail_feedback.py tests\test_phase14_spec_compliance.py -q
git diff --check
```

Expected: all pass, including the old BLOCK/approval/feedback scenarios.

- [x] **Step 8: Log and commit**

```powershell
git add codeguard\loop.py codeguard\context.py codeguard\llm\mock.py tests\test_loop.py tests\test_context_runtime.py tests\test_integration_guardrail_feedback.py tests\test_phase14_spec_compliance.py AGENT_LOG.md docs\superpowers\plans\2026-08-13-interactive-cli-agent.md
git commit -m "feat: feed runtime results through the governed agent loop"
```

---

### Task 5: Implement ChatSession and CLI Event Rendering

**Files:**
- Create: `codeguard/chat/session.py`
- Create: `tests/test_chat_session.py`
- Modify: `codeguard/chat/__init__.py`
- Modify: `codeguard/cli/chat.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `CompositionRoot`, `ChatHistory`, `AgentLoop.start_task`, clarification/approval resume methods, Harness events.
- Produces: `ChatSession.run() -> int`, `CLIEventSink`, and injectable `InputReader`/`OutputWriter` callables.

- [ ] **Step 1: Write failing command tests**

```python
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
```

Add tests for `/status`, blank input, EOF, `/cancel` with no task, and `/exit`.

- [ ] **Step 2: Run command tests to verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_session.py -q
```

Expected: collection ERROR because `ChatSession` does not exist.

- [ ] **Step 3: Implement the minimal session coordinator**

Use constructor:

```python
class ChatSession:
    def __init__(
        self,
        loop_factory: Callable[[str], AgentLoop],
        read_input: Callable[[str], str],
        write_output: Callable[[str], None],
        history: ChatHistory | None = None,
        status_provider: Callable[[], dict[str, object]] | None = None,
    ): ...

    def run(self) -> int: ...
```

Generate UUID chat/task IDs. A normal REPL input starts one task and waits until it reaches a terminal state or an explicit approval/clarification pause. Append only user text, assistant messages, and final task summaries to `ChatHistory`; do not append raw tool output.

- [ ] **Step 4: Write failing approval and clarification tests**

Test that an approval prompt defaults to rejection on empty input, accepts only explicit `y`/`yes`, calls `resume_with_approval` with request/session/fingerprint binding, and returns to the same task. Test that `REQUEST_USER_INPUT` accepts normal text, `/cancel`, and `Ctrl+C` distinctly.

- [ ] **Step 5: Implement `CLIEventSink` and pause handling**

Render stable prefixes:

```text
CodeGuard > <assistant message>
[tool] read_file
[guardrail] BLOCK: <reason>
[approval] write_file <target>
[validation] pytest: PASSED
[task] COMPLETED: <summary>
```

Never print raw credentials or complete unbounded tool output. Approval prompt must show action, target, reason, and `[y/N]`. Catch the first `KeyboardInterrupt` inside a task as cancellation and return to the REPL; a `KeyboardInterrupt` at the idle REPL exits with code 130.

- [ ] **Step 6: Replace the one-shot CLI command**

`chat_command(args)` must parse `--mode`, construct `CompositionRoot(mode=mode, workspace_root=Path.cwd())`, create a `ChatSession`, and exit with the integer returned by `run()`. A missing local key prints the existing safe error and exits 1. Test/demo inputs remain injectable; no real `input()` or keyring is used in unit tests.

- [ ] **Step 7: Run chat and CLI tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_session.py tests\test_cli.py tests\test_events.py tests\test_chat_history.py -q
git diff --check
```

Expected: all pass.

- [ ] **Step 8: Log and commit**

```powershell
git add codeguard\chat codeguard\cli\chat.py tests\test_chat_session.py tests\test_cli.py AGENT_LOG.md docs\superpowers\plans\2026-08-13-interactive-cli-agent.md
git commit -m "feat: add interactive chat session and CLI rendering"
```

---

### Task 6: Update DeepSeek Protocol and CLI Metadata

**Files:**
- Modify: `codeguard/llm/deepseek.py`
- Modify: `codeguard/llm/client.py`
- Modify: `codeguard/__main__.py`
- Modify: `tests/test_llm_deepseek.py`
- Modify: `tests/test_scaffold.py`

**Interfaces:**
- Consumes: all `ActionKind` values and runtime context.
- Produces: a strict provider prompt/response schema and CLI help describing an interactive session.

- [ ] **Step 1: Write failing provider-protocol tests**

Assert that the HTTP request contains a system message which lists exactly `tool_call`, `assistant_message`, `request_user_input`, and `complete`; assert each response shape parses to the correct action. Add malformed/empty-message tests that raise a redacted `ValueError` instead of treating arbitrary text as completion.

- [ ] **Step 2: Run provider tests to verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_llm_deepseek.py -q
```

Expected: FAIL because the current adapter sends only one user message and converts invalid JSON to completion.

- [ ] **Step 3: Implement the strict DeepSeek action protocol**

Send:

```python
messages = [
    {"role": "system", "content": ACTION_PROTOCOL_PROMPT},
    {"role": "user", "content": context},
]
```

The prompt must state that only one JSON object is permitted, show the required fields for all four action kinds, prohibit prose outside JSON, and explain that `complete` requires a summary and still undergoes final validation. Delegate parsing to the shared `ActionParser`; do not retain the permissive invalid-JSON-to-complete fallback.

- [ ] **Step 4: Update CLI help and version only after behavior is implemented**

Change chat help to `Start an interactive governed coding-agent session`. Keep package version `0.1.1` during development; version bump to `0.2.0-interactive` belongs to the final release task, not this task.

- [ ] **Step 5: Run provider and CLI regressions**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_llm_deepseek.py tests\test_cli.py tests\test_scaffold.py -q
git diff --check
```

Expected: all pass and no test performs network access.

- [ ] **Step 6: Log and commit**

```powershell
git add codeguard\llm\deepseek.py codeguard\llm\client.py codeguard\__main__.py tests\test_llm_deepseek.py tests\test_scaffold.py AGENT_LOG.md docs\superpowers\plans\2026-08-13-interactive-cli-agent.md
git commit -m "feat: enforce interactive DeepSeek action protocol"
```

---

### Task 7: Deterministic End-to-End Interactive Coding Test

**Files:**
- Create: `tests/test_interactive_cli_e2e.py`
- Modify: test helpers only when required; do not add production shortcuts.

**Interfaces:**
- Consumes: complete `ChatSession`, wired `CompositionRoot(mode="test")`, ScriptedMockLLM, Guardrail, approval, tools, sensor runner.
- Produces: reproducible proof that a temporary project is safely modified and verified across multiple LLM decisions and two REPL tasks.

- [ ] **Step 1: Write the failing happy-path E2E test**

Create a temporary project with `value.py` containing `VALUE = 1` and a small test expecting `VALUE == 2`. Script responses in this order:

1. `assistant_message` explaining inspection;
2. `read_file` for `value.py`;
3. `write_file` setting `VALUE = 2`;
4. `run_tests`;
5. `complete` with a summary.

Queue CLI inputs: the task, explicit approval `y`, a second harmless inspection task, and `/exit`. Assert the file changes, validation is recorded as passed, first task is `COMPLETED`, second task can start, and the output contains assistant/tool/approval/validation/task events.

- [ ] **Step 2: Run the E2E test to verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_interactive_cli_e2e.py::test_interactive_agent_edits_validates_and_accepts_second_task -v
```

Expected: FAIL at the first missing or inconsistent integration behavior. Record the exact failure rather than weakening the assertion.

- [ ] **Step 3: Make only integration fixes required by the test**

Do not add E2E-only flags or bypass Guardrail. Fix the production boundary responsible for the failure, rerun the targeted test, and keep each fix protected by the closest lower-level regression test when practical.

- [ ] **Step 4: Add negative E2E cases**

Add deterministic tests for:

- empty approval rejects and leaves the file unchanged;
- workspace escape is BLOCKed and no handler runs;
- `REQUEST_USER_INPUT` resumes with the user's answer;
- `/cancel` and `Ctrl+C` prevent later tool execution;
- repeated invalid LLM JSON reaches `LIMIT_REACHED`;
- a failing required final sensor prevents `COMPLETED`;
- `/clear` removes chat messages but not structure-memory records;
- demo composition cannot modify the temporary project even if scripted with `write_file`.

- [ ] **Step 5: Run all E2E and safety tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_interactive_cli_e2e.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_guardrail_engine.py tests\test_guardrail_rules.py tests\test_approval_manager.py tests\test_web_mock_security.py -q
git diff --check
```

Expected: all pass.

- [ ] **Step 6: Log and commit**

```powershell
git add tests\test_interactive_cli_e2e.py codeguard AGENT_LOG.md docs\superpowers\plans\2026-08-13-interactive-cli-agent.md
git commit -m "test: cover interactive coding-agent workflow end to end"
```

---

### Task 8: Documentation, Full Verification, and Enhanced Release Candidate

**Files:**
- Modify: `README.md`
- Modify: `SECURITY.md`
- Modify: `AGENT_LOG.md`
- Modify: `codeguard/__init__.py`
- Modify: `codeguard/__main__.py`
- Modify: `docs/superpowers/plans/2026-08-13-interactive-cli-agent.md`
- Verify: `codeguard.spec`
- Verify: `.github/workflows/ci.yml`
- Verify: `.gitlab-ci.yml`

**Interfaces:**
- Consumes: all completed implementation tasks.
- Produces: documented `0.2.0-interactive` release candidate on the enhanced branch only.

- [ ] **Step 1: Update user documentation accurately**

Document:

- how to obtain the course version (`main` / v0.1.1) and enhanced version (`feature/interactive-cli-agent`);
- `codeguard chat --mode local` behavior and commands;
- automatic safe reads/tests and Guardrail-controlled writes;
- process-local history and lack of `/resume`;
- DeepSeek key setup and cost warning;
- known limitations from the design;
- explicit statement that the enhanced branch is not merged into `main`.

Update `SECURITY.md` with clarification input, approval binding, bounded context, trusted sensor definitions, cancellation, and the prohibition on push/release tools.

- [ ] **Step 2: Run the complete test suite freshly**

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs
```

Expected: 0 failures. Record the exact pass/skip count and runtime in `AGENT_LOG.md`; do not copy the old 626 count.

- [ ] **Step 3: Run offline CLI and Demo smoke tests**

```powershell
.\.venv\Scripts\python.exe -m codeguard --help
.\.venv\Scripts\python.exe -m codeguard demo a
.\.venv\Scripts\python.exe -m codeguard demo b
.\.venv\Scripts\python.exe -m codeguard demo c
```

For interactive test mode, pipe only deterministic scripted input supported by the test composition; never call local mode in CI or without explicit cost approval.

- [ ] **Step 4: Run security and repository checks**

```powershell
git grep -n -E "sk-[A-Za-z0-9_-]{12,}|api_key[[:space:]]*=" -- ':!tests/*'
git diff --check
git status --short --branch
git rev-parse --short main
git branch --show-current
```

Expected: no real credential matches; no whitespace errors; branch is `feature/interactive-cli-agent`; `main` is still `30581f0`.

- [ ] **Step 5: Build and smoke-test the Windows executable**

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm codeguard.spec
.\dist\codeguard.exe --help
.\dist\codeguard.exe demo a
```

Start `codeguard.exe web` on an unused local port, verify `/health`, and stop it. Verify interactive test mode manually with Mock inputs. Do not configure or expose a real key during the build verification.

- [ ] **Step 6: Set enhanced version metadata**

After all verification succeeds, set both reported version locations to `0.2.0-interactive`. Add or update a test asserting the version output. Rerun that test and `codeguard --version`.

- [ ] **Step 7: Request two-stage review**

Use `superpowers:requesting-code-review`: first verify every design acceptance criterion and branch-separation rule, then review code quality and security. Fix all Critical and Major findings with TDD and repeat the relevant verification.

- [ ] **Step 8: Final commit without merging**

```powershell
git add README.md SECURITY.md AGENT_LOG.md codeguard\__init__.py codeguard\__main__.py docs\superpowers\plans\2026-08-13-interactive-cli-agent.md
git commit -m "docs: prepare interactive CLI release candidate"
```

Push `feature/interactive-cli-agent` to the selected remote only with explicit user approval. An optional Draft PR may be created for CI/review, but it must remain unmerged. Create tag/Release `v0.2.0-interactive` only after remote CI passes and the user authorizes publishing.

---

## Final Acceptance Checklist

- [ ] `main` remains at course version v0.1.1 and contains none of the enhanced commits.
- [ ] The enhanced branch creates and completes more than one task in one CLI process.
- [ ] Production composition uses real tool handlers, dispatcher, sensors, runtime context, and feedback.
- [ ] Safe reads and trusted tests execute automatically.
- [ ] Writes and dangerous actions use existing Guardrail and action-bound approval.
- [ ] Tool and validation results appear in the next LLM context.
- [ ] `ASSISTANT_MESSAGE` continues automatically; `REQUEST_USER_INPUT` pauses and resumes explicitly.
- [ ] `/clear` removes process-local messages only; `/exit` leaves no full chat-history file.
- [ ] Final sensor failure prevents `COMPLETED`.
- [ ] Demo and Mock WebUI remain isolated from real side effects.
- [ ] Full pytest, offline smoke, credential scan, PyInstaller build, and executable smoke tests have fresh passing evidence.
- [ ] Enhanced version is available from `feature/interactive-cli-agent` or `v0.2.0-interactive` without merging into `main`.
