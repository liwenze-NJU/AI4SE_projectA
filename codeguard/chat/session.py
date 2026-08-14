"""Interactive chat session coordinator and CLI event rendering.

``ChatSession`` drives the REPL: commands (``/help``, ``/status``,
``/clear``, ``/cancel``, ``/exit``), normal task input, approval prompts
(``[y/N]``), clarification pauses, and Ctrl+C semantics (idle REPL → exit
130, inside a task → cancel and return to the REPL).

``CLIEventSink`` renders harness events with stable prefixes and strictly
bounded payload values, so unbounded or credential-bearing payloads can
never reach the terminal.
"""

from typing import Callable, Protocol
import uuid

from codeguard.chat.history import ChatHistory, TaskSummary
from codeguard.events import HarnessEvent, HarnessEventKind
from codeguard.guardrail import GuardrailDecision
from codeguard.guardrail.approval import ApprovalStatus
from codeguard.loop import AgentLoop
from codeguard.state import AgentState, SessionResult


class InputReader(Protocol):
    def __call__(self, prompt: str) -> str: ...


class OutputWriter(Protocol):
    def __call__(self, text: str) -> None: ...


class CLIEventSink:
    """Renders harness events to the terminal with stable prefixes.

    Every payload value that reaches the terminal is truncated to at most
    500 characters, and only the modeled fields of each event kind are
    rendered — arbitrary payload keys (which may carry credentials or
    unbounded output) are never printed.
    """

    _MAX_VALUE_CHARS = 500
    _TRUNCATION_SUFFIX = "..."

    def __init__(self, write: OutputWriter) -> None:
        self._write = write
        self.assistant_messages: list[str] = []
        self.task_summary: str | None = None

    def emit(self, event: HarnessEvent) -> None:
        kind = event.kind
        payload = event.payload

        if kind == HarnessEventKind.ASSISTANT_MESSAGE:
            message = self._bounded(payload.get("message"))
            if message:
                self.assistant_messages.append(message)
                self._write(f"CodeGuard > {message}")
        elif kind == HarnessEventKind.TOOL_STARTED:
            tool = self._bounded(payload.get("tool"))
            if tool:
                self._write(f"[tool] {tool}")
        elif kind == HarnessEventKind.TOOL_FINISHED:
            tool = self._bounded(payload.get("tool"))
            status = self._bounded(payload.get("status"))
            output = self._bounded(payload.get("output"))
            if tool:
                line = f"[tool] {tool}"
                if status:
                    line += f": {status}"
                if output:
                    line += f" {output}"
                self._write(line)
        elif kind == HarnessEventKind.APPROVAL_REQUESTED:
            tool = self._bounded(payload.get("tool"))
            reason = self._bounded(payload.get("reason"))
            line = "[approval]"
            if tool:
                line += f" {tool}"
            if reason:
                line += f" {reason}"
            self._write(line)
        elif kind == HarnessEventKind.VALIDATION_FINISHED:
            sensor = self._bounded(payload.get("sensor"))
            status = self._bounded(payload.get("status"))
            if sensor:
                line = f"[validation] {sensor}"
                if status:
                    line += f": {status}"
                self._write(line)
        elif kind == HarnessEventKind.TASK_FINISHED:
            outcome = self._bounded(payload.get("outcome"))
            summary = self._bounded(payload.get("summary"))
            if summary:
                # Captured for the completed-task summary (T8-FIX2 P2):
                # cross-task context must carry real content from task 1.
                self.task_summary = summary
            line = "[task]"
            if outcome:
                line += f" {str(outcome).upper()}"
                if summary:
                    line += f": {summary}"
            self._write(line)
        # STATE_CHANGED and USER_INPUT_REQUESTED are handled by the
        # interactive session, not rendered as standalone lines.

    def _bounded(self, value: object) -> str:
        """Render a payload value as text, truncated to the strict bound."""
        if value is None:
            return ""
        text = str(value)
        if len(text) > self._MAX_VALUE_CHARS:
            return text[: self._MAX_VALUE_CHARS] + self._TRUNCATION_SUFFIX
        return text


_HELP_LINES = (
    "/help    Show this command list",
    "/status  Show session status",
    "/clear   Clear chat messages (task summaries are kept)",
    "/cancel  Cancel the active task",
    "/exit    Exit the chat session",
)


def _default_input(prompt: str) -> str:
    """Real terminal input; only reachable in production, never in tests."""
    return input(prompt)


def _default_output(text: str) -> None:
    print(text)


class ChatSession:
    """Coordinator for one interactive chat session.

    A normal REPL input starts ONE task and waits until it reaches a
    terminal state or an explicit approval/clarification pause.  Only user
    text, assistant messages, and final task summaries are appended to
    ``ChatHistory`` — raw tool output is never appended.

    The injected ``read_input`` contract: an empty string return (or
    ``EOFError``) is end-of-file and acts like ``/exit``; whitespace-only
    lines are blank input and are ignored.
    """

    def __init__(
        self,
        loop_factory: Callable[[str], AgentLoop],
        read_input: Callable[[str], str] | None = None,
        write_output: Callable[[str], None] | None = None,
        history: ChatHistory | None = None,
        status_provider: Callable[[], dict[str, object]] | None = None,
    ) -> None:
        self._loop_factory = loop_factory
        self._read = read_input or _default_input
        self._write = write_output or _default_output
        self._history = history
        self._status_provider = status_provider
        self.session_id = str(uuid.uuid4())
        self._loop: AgentLoop | None = None
        self._task_active = False
        self._current_task_id: str | None = None
        self._current_request: str | None = None

    def run(self) -> int:
        """Run the REPL until /exit, EOF, or Ctrl+C at the idle prompt."""
        while True:
            try:
                raw = self._read("codeguard> ")
            except KeyboardInterrupt:
                # Ctrl+C at the idle REPL exits with the conventional code.
                return 130
            except EOFError:
                return 0

            if raw == "":
                return 0  # empty return is the EOF sentinel

            line = raw.strip() if isinstance(raw, str) else ""
            if line == "":
                continue  # blank input
            if line.startswith("/"):
                if not self._handle_command(line):
                    return 0
                continue

            self._run_task(line)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def _handle_command(self, line: str) -> bool:
        """Handle a slash command; returns False when the session should end."""
        name, _, _ = line.partition(" ")
        if name == "/exit":
            return False
        if name == "/help":
            for text in _HELP_LINES:
                self._write(text)
            return True
        if name == "/status":
            self._print_status()
            return True
        if name == "/clear":
            if self._history is not None:
                self._history.clear_messages()
            self._write("Chat messages cleared (task summaries kept).")
            return True
        if name == "/cancel":
            if self._loop is None or not self._task_active:
                self._write("No active task")
                return True
            result = self._loop.cancel()
            history = self._new_history()
            history.add_summary(TaskSummary(
                task_id=self._current_task_id or "",
                request=self._current_request or "",
                outcome=result.terminal_state.value,
                summary="cancelled by user",
            ))
            self._write(f"Task cancelled ({result.terminal_state.value}).")
            self._end_task()
            return True
        self._write(f"Unknown command: {name} (try /help)")
        return True

    def _print_status(self) -> None:
        if self._status_provider is None:
            self._write("No status provider configured.")
            return
        try:
            status = self._status_provider()
        except Exception:
            self._write("Status unavailable.")
            return
        for key, value in status.items():
            self._write(f"{key}: {value}")

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def _new_history(self) -> ChatHistory:
        return self._history or ChatHistory(max_messages=50, max_summaries=10)

    def _summaries_for(self, history: ChatHistory) -> list[str]:
        """Render task summaries for the next task's LLM context.

        Each line includes the REQUEST so user content always flows into
        the next task's context (T8-FIX2 P2): never just the summary text.
        """
        return [
            f"[{s.request}] ({s.outcome}): {s.summary}"
            for s in history.summaries
        ]

    def _end_task(self) -> None:
        self._task_active = False
        self._current_task_id = None
        self._current_request = None

    def _task_failed(self, message: str) -> None:
        """Surface a task-level error to the terminal and end the task.

        Strict-mode failures (e.g. a malformed LLM action raising a
        redacted ValueError) must not kill the REPL: print one [error]
        line, end the task without a summary, and return to the prompt.
        """
        self._write(f"[error] {message}")
        self._end_task()

    def _run_task(self, line: str) -> None:
        """Start one task and drive it (and its pauses) to completion."""
        history = self._new_history()
        history.add_message("user", line)

        if self._loop is None:
            self._loop = self._loop_factory(self.session_id)
        loop = self._loop
        self._task_active = True
        self._current_task_id = str(uuid.uuid4())
        self._current_request = line
        sink = CLIEventSink(self._write)
        self._sink_task_summary = None
        if hasattr(loop, "event_sink"):
            loop.event_sink = sink

        try:
            result = loop.start_task(
                self._current_task_id, line, self._summaries_for(history)
            )
        except KeyboardInterrupt:
            # Ctrl+C while the task was starting: cancel it and return to
            # the REPL rather than aborting the session.
            try:
                result = loop.cancel()
            except Exception:
                self._end_task()
                return
        except ValueError as e:
            # Strict-mode failures (e.g. malformed LLM action) end the
            # task and return to the REPL instead of crashing the session.
            self._task_failed(str(e))
            return

        while True:
            state = result.terminal_state

            if state == AgentState.AWAITING_APPROVAL:
                try:
                    result = self._handle_approval(loop, history)
                except ValueError as e:
                    self._task_failed(str(e))
                    return
                if result is None:
                    self._end_task()
                    return
                continue

            if state == AgentState.AWAITING_USER_INPUT:
                try:
                    result = self._handle_user_input(loop, history, line)
                except ValueError as e:
                    self._task_failed(str(e))
                    return
                if result is None:
                    self._end_task()
                    return
                continue

            # Terminal state: record assistant text and the final summary.
            self._sink_task_summary = sink.task_summary
            for message in sink.assistant_messages:
                history.add_message("assistant", message)
            history.add_summary(TaskSummary(
                task_id=self._current_task_id or "",
                request=line,
                outcome=state.value,
                summary=self._task_summary_text(state, result),
            ))
            if state == AgentState.FAILED and loop.state.guardrail_decision:
                decision = loop.state.guardrail_decision
                if decision.decision == GuardrailDecision.BLOCK:
                    reason = "; ".join(decision.reason_codes) or "blocked"
                    self._write(f"[guardrail] BLOCK: {reason}")
            break

        self._end_task()

    def _task_summary_text(self, state: AgentState, result: SessionResult) -> str:
        """Build a meaningful TaskSummary text, never empty on completion.

        The TASK_FINISHED summary emitted by the loop (a bounded transcript
        excerpt) is preferred; a redacted error for failures, or a fixed
        fallback per outcome, otherwise (T8-FIX2 P2).
        """
        if result.error:
            return str(result.error)
        if self._sink_task_summary:
            return self._sink_task_summary
        if state == AgentState.COMPLETED:
            return "completed"
        if state == AgentState.CANCELLED:
            return "cancelled by user"
        return state.value

    # ------------------------------------------------------------------
    # Pauses
    # ------------------------------------------------------------------

    def _handle_approval(self, loop, history) -> SessionResult | None:
        """Prompt for an approval decision; empty input defaults to REJECT."""
        state = loop.state
        request_id = state.approval_request_id or ""
        pending = state.pending_action
        session_id = state.session_id

        tool_name = (pending.tool_name or "action") if pending else "action"
        target = ""
        if pending and pending.normalized_parameters:
            target = str(
                pending.normalized_parameters.get("path")
                or pending.normalized_parameters.get("pattern")
                or pending.normalized_parameters.get("program")
                or ""
            )
        reason = ""
        if state.guardrail_decision is not None:
            reason = state.guardrail_decision.human_readable_message

        parts = [f"Approve {tool_name}?"]
        if target:
            parts.append(f"target: {target}")
        if reason:
            parts.append(f"reason: {reason}")
        prompt = " ".join(parts) + " [y/N]: "

        try:
            raw = self._read(prompt)
        except KeyboardInterrupt:
            # Ctrl+C at an approval prompt is a rejection.
            answer = ""
        else:
            answer = raw.strip().lower()

        if answer in ("y", "yes"):
            decision = ApprovalStatus.APPROVED
        else:
            decision = ApprovalStatus.REJECTED

        try:
            loop.resume_with_approval(
                request_id, session_id, decision, pending.action_fingerprint,
            )
            return loop.run()
        except Exception:
            try:
                return loop.cancel()
            except Exception:
                return None

    def _handle_user_input(self, loop, history, request) -> SessionResult | None:
        """Collect the answer for a clarification pause.

        Normal text resumes the task, /cancel cancels it, and Ctrl+C
        (KeyboardInterrupt) cancels it and returns to the REPL.
        """
        prompt = loop.state.pending_question or "Input required"
        self._write(f"CodeGuard asks: {prompt}")
        try:
            raw = self._read("codeguard> ")
        except KeyboardInterrupt:
            return self._cancel_current(loop)

        text = raw.strip() if isinstance(raw, str) else ""
        if text == "" or text.startswith("/cancel"):
            return self._cancel_current(loop)

        try:
            return loop.resume_with_user_input(text)
        except ValueError:
            # The loop refused the answer (e.g. empty after strip) or a
            # strict-mode failure surfaced from the resumed loop: treat
            # it as a cancellation rather than crashing the REPL.
            return self._cancel_current(loop)

    def _cancel_current(self, loop) -> SessionResult | None:
        """Cancel the active task; the terminal-state recorder in
        ``_run_task`` appends the final summary."""
        try:
            return loop.cancel()
        except Exception:
            return None
