"""Tests for AgentLoop — explicit state machine (PLAN Tasks 2.2+2.3)."""

import pytest
from decimal import Decimal
from datetime import datetime

from codeguard.loop import AgentLoop
from codeguard.state import AgentState
from codeguard.action import Action, ActionKind, LLMResponse
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.guardrail import GuardrailDecision, GuardrailResult
from codeguard.guardrail.approval import ApprovalStatus, ApprovalResult
from codeguard.guardrail.normalizer import ActionNormalizer


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _r(action: Action) -> LLMResponse:
    """Wrap an Action in an LLMResponse for ScriptedMockLLM."""
    return LLMResponse(
        content=action.raw or "",
        next_action=action,
        finish_reason="stop",
        model="mock",
        token_used=0,
        cost_used=Decimal("0"),
        raw_response="",
    )


# ---------------------------------------------------------------------------
# Fake components for state machine testing
# ---------------------------------------------------------------------------

class FakeGuardrail:
    """Scriptable guardrail that returns pre-configured decisions in order."""

    def __init__(self, decisions=None, recoverable=True):
        self._decisions = decisions or ["ALLOW"]
        self._index = 0
        self._recoverable = recoverable

    def evaluate(self, action):
        d = self._decisions[self._index % len(self._decisions)]
        self._index += 1
        from codeguard.action import NormalizedAction
        if isinstance(action, NormalizedAction):
            na = action
        else:
            na = NormalizedAction(
                kind=action.kind,
                tool_name=action.tool_name,
                normalized_parameters=action.parameters,
                action_fingerprint="fp",
                original_raw=action.raw,
                normalized_at=datetime.now(),
            )
        return GuardrailResult(
            decision=getattr(GuardrailDecision, d) if isinstance(d, str) else d,
            rule_ids=[],
            reason_codes=[],
            human_readable_message="",
            recoverable=self._recoverable,
            normalized_action=na,
            action_fingerprint=na.action_fingerprint,
        )


from codeguard.guardrail.approval import ApprovalStatus, ApprovalResult, ApprovalRequest


class FakeApproval:
    """Scriptable approval manager."""

    def __init__(self, decision=ApprovalStatus.APPROVED):
        self._decision = decision
        self._requests: dict[str, ApprovalRequest] = {}

    def create_request(self, session_id, normalized_action,
                       matched_rules=None, risk_summary=""):
        from datetime import datetime, timedelta
        req = ApprovalRequest(
            request_id="r1",
            session_id=session_id,
            normalized_action=normalized_action,
            action_fingerprint=getattr(normalized_action, 'action_fingerprint', 'fp'),
            matched_rules=matched_rules or [],
            risk_summary=risk_summary,
            workspace_snapshot={},
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=300),
        )
        self._requests["r1"] = req
        return req

    def approve(self, request_id, session_id, action_fingerprint):
        return ApprovalResult(
            request_id=request_id,
            decision=ApprovalStatus.APPROVED,
            validated_at=datetime.now(),
        )

    def reject(self, request_id, session_id):
        return ApprovalResult(
            request_id=request_id,
            decision=ApprovalStatus.REJECTED,
            validated_at=datetime.now(),
        )

    def check_timeout(self, req):
        if self._decision == ApprovalStatus.TIMEOUT:
            return ApprovalResult(
                request_id=req.request_id,
                decision=ApprovalStatus.TIMEOUT,
                validated_at=datetime.now(),
            )
        return None

    def get_request(self, request_id):
        return self._requests.get(request_id)

    def check_timeout_for_request(self, request_id):
        req = self._requests.get(request_id)
        if req is None:
            return None
        return self.check_timeout(req)


class FakeToolDispatcher:
    """Always-succeed tool dispatcher."""

    def dispatch(self, action):
        from codeguard.tool import ToolResult
        return ToolResult(
            tool_name=action.tool_name or "",
            status="SUCCESS",
            output_summary="",
            diagnostics=[],
            exit_code=0,
            changed_files=[],
            duration=0.1,
            truncated=False,
            error_category=None,
            audit_id="audit-1",
        )


class FakeSensorRunner:
    """Always-pass sensor runner."""

    def run_all(self):
        from codeguard.feedback import FeedbackResult
        return [
            FeedbackResult(
                sensor_id="pytest",
                program="pytest",
                args=["."],
                status="PASSED",
                failure_category=None,
                exit_code=0,
                failure_fingerprint=None,
                validation_type="INTERMEDIATE",
                summary="ok",
                diagnostics=[],
                duration=0.1,
                retryable=False,
                raw_output_truncated="",
            )
        ]


class FakeFeedbackClassifier:
    """Identity classifier (pass-through)."""

    def classify(self, results):
        return results


class FakeObjectiveVerifier:
    """Scriptable objective verifier."""

    def __init__(self, passed=True):
        self._passed = passed

    def verify(self, state):
        return self._passed


from codeguard.stop import StopPolicy, StopDecision


class FakeStopPolicy:
    """Scriptable stop policy. Returns a StopDecision or None to continue."""

    def __init__(self, decision=None):
        self._decision = decision

    def evaluate(self, state):
        if self._decision is None:
            return None
        return StopDecision(True, self._decision, "fake")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_loop_initial_state():
    """AgentLoop starts in INITIALIZING."""
    mock = ScriptedMockLLM(responses=[])
    loop = AgentLoop(session_id="s1", llm=mock)
    assert loop.state.current_state == AgentState.INITIALIZING


def test_loop_initialize_transition():
    """initialize() transitions INITIALIZING → BUILDING_CONTEXT."""
    mock = ScriptedMockLLM(responses=[])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.initialize()
    assert loop.state.current_state == AgentState.BUILDING_CONTEXT


def test_loop_full_allow_sequence():
    """Full happy path: read_file → COMPLETE_REQUEST."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.action_normalizer = ActionNormalizer(workspace_root=".")
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED
    assert result.steps_total >= 1


def test_loop_block_sequence():
    """Blocked action is skipped; agent recovers with a different action."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="delete_file",
                  parameters={"path": "/outside"}, raw="")),
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "safe"}, raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.action_normalizer = ActionNormalizer(workspace_root=".")
    loop.rule_engine = FakeGuardrail(decisions=["BLOCK", "ALLOW"])
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED


def test_loop_approval_approve():
    """Approval granted → execution proceeds."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="write_file",
                  parameters={"path": "output.txt"}, raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.action_normalizer = ActionNormalizer(workspace_root=".")
    loop.rule_engine = FakeGuardrail(decisions=["REQUEST_APPROVAL", "ALLOW"])
    loop.approval_manager = FakeApproval(decision=ApprovalStatus.APPROVED)
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    # First run: pauses at AWAITING_APPROVAL
    result = loop.run()
    assert loop.state.current_state == AgentState.AWAITING_APPROVAL
    # Approve and resume
    fp = loop.state.pending_action.action_fingerprint
    loop.resume_with_approval(
        request_id="r1", session_id="s1",
        decision=ApprovalStatus.APPROVED, action_fingerprint=fp,
    )
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED


def test_loop_approval_resume_tool_failure_is_fed_back():
    """An approved tool that FAILS on the resume path must be fed back as a
    failure (not as a neutral result) so the next decision can react."""
    from codeguard.tool import ToolResult

    class FailingDispatcher(FakeToolDispatcher):
        def dispatch(self, action):
            return ToolResult(
                tool_name=action.tool_name or "",
                status="FAILURE",
                output_summary="permission denied writing output.txt",
                diagnostics=[],
                exit_code=1,
                changed_files=[],
                duration=0.1,
                truncated=False,
                error_category="WORKSPACE_VIOLATION",
                audit_id="audit-fail",
            )

    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="write_file",
                  parameters={"path": "output.txt", "content": "x"}, raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.action_normalizer = ActionNormalizer(workspace_root=".")
    loop.rule_engine = FakeGuardrail(decisions=["REQUEST_APPROVAL", "ALLOW"])
    loop.approval_manager = FakeApproval(decision=ApprovalStatus.APPROVED)
    loop.tool_dispatcher = FailingDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    # First run: pauses at AWAITING_APPROVAL
    result = loop.run()
    assert loop.state.current_state == AgentState.AWAITING_APPROVAL
    fp = loop.state.pending_action.action_fingerprint
    loop.resume_with_approval(
        request_id="r1", session_id="s1",
        decision=ApprovalStatus.APPROVED, action_fingerprint=fp,
    )
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED
    # The failure must be visible in the feedback field with a failure marker
    assert "failed" in loop._latest_result.lower()
    assert "permission denied" in loop._latest_result


def test_loop_approval_reject():
    """Approval rejected → CANCELLED."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="write_file",
                  parameters={"path": "output.txt"}, raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.action_normalizer = ActionNormalizer(workspace_root=".")
    loop.rule_engine = FakeGuardrail(decisions=["REQUEST_APPROVAL"])
    loop.approval_manager = FakeApproval(decision=ApprovalStatus.REJECTED)
    loop.stop_policy = FakeStopPolicy()
    # First run: pauses at AWAITING_APPROVAL
    result = loop.run()
    assert loop.state.current_state == AgentState.AWAITING_APPROVAL
    # Reject
    fp = loop.state.pending_action.action_fingerprint
    loop.resume_with_approval(
        request_id="r1", session_id="s1",
        decision=ApprovalStatus.REJECTED, action_fingerprint=fp,
    )
    result = loop.run()
    assert result.terminal_state == AgentState.CANCELLED


def test_loop_approval_timeout():
    """Approval timeout → CANCELLED."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="write_file",
                  parameters={"path": "output.txt"}, raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.action_normalizer = ActionNormalizer(workspace_root=".")
    loop.rule_engine = FakeGuardrail(decisions=["REQUEST_APPROVAL"])
    loop.approval_manager = FakeApproval(decision=ApprovalStatus.TIMEOUT)
    loop.stop_policy = FakeStopPolicy()
    # First run: pauses at AWAITING_APPROVAL
    result = loop.run()
    assert loop.state.current_state == AgentState.AWAITING_APPROVAL
    # Resume — FakeApproval returns TIMEOUT from check_timeout
    result = loop.run()
    assert result.terminal_state == AgentState.CANCELLED


def test_loop_limit_reached():
    """Stop policy returns LIMIT_REACHED."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.action_normalizer = ActionNormalizer(workspace_root=".")
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.stop_policy = FakeStopPolicy(decision=AgentState.LIMIT_REACHED)
    result = loop.run()
    assert result.terminal_state == AgentState.LIMIT_REACHED


def test_loop_failed():
    """Stop policy returns FAILED."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.action_normalizer = ActionNormalizer(workspace_root=".")
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.stop_policy = FakeStopPolicy(decision=AgentState.FAILED)
    result = loop.run()
    assert result.terminal_state == AgentState.FAILED


def test_loop_complete_request_goes_to_final_validation():
    """COMPLETE_REQUEST → FINAL_VALIDATION → COMPLETED."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED


def test_loop_max_steps_limit_reached():
    """Without stop_policy, max_steps limit terminates loop as LIMIT_REACHED."""
    # LLM only returns TOOL_CALL — never COMPLETE_REQUEST
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw=""))
    ] * 10)  # more than max_steps
    loop = AgentLoop(session_id="s1", llm=mock, max_steps=3)
    loop.action_normalizer = ActionNormalizer(workspace_root=".")
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    # No stop_policy injected — protection comes from max_steps
    result = loop.run()
    assert result.terminal_state == AgentState.LIMIT_REACHED
    assert result.steps_total == 3


def test_loop_stop_policy_completed_ignored():
    """stop_policy 'COMPLETED' does NOT bypass FINAL_VALIDATION."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.action_normalizer = ActionNormalizer(workspace_root=".")
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    # stop_policy returns "COMPLETED" — but this should be ignored;
    # only FINAL_VALIDATION can produce COMPLETED
    loop.stop_policy = FakeStopPolicy(decision=AgentState.COMPLETED)
    result = loop.run()
    # COMPLETED must come from FINAL_VALIDATION, not stop_policy shortcut
    assert result.terminal_state == AgentState.COMPLETED
    # Verify the trace shows FINAL_VALIDATION before COMPLETED
    states = [t["to"] for t in loop._trace]
    final_idx = states.index(AgentState.COMPLETED)
    assert states[final_idx - 1] == AgentState.FINAL_VALIDATION


def test_loop_non_recoverable_block():
    """Non-recoverable BLOCK → FAILED (no retry path)."""
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="delete_file",
                  parameters={"path": "/etc/passwd"}, raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["BLOCK"], recoverable=False)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.FAILED


# ---------------------------------------------------------------------------
# Task 4 — per-task inputs, assistant messages, user input, and cancel
# ---------------------------------------------------------------------------

from codeguard.events import CollectingEventSink, HarnessEventKind


class FakeTaskToolDispatcher:
    """FakeToolDispatcher that also records the dispatched actions."""

    def __init__(self):
        self.dispatched: list = []
        self._inner = FakeToolDispatcher()

    def dispatch(self, action):
        self.dispatched.append(action)
        return self._inner.dispatch(action)


def _make_task_loop(task_id="t1", request="Do the work",
                    summaries=None, responses=None, event_sink=None):
    """Fully-wired loop for start_task scenarios (real components)."""
    from codeguard.composition import CompositionRoot
    import tempfile

    root = CompositionRoot(
        mode="test",
        workspace_root=tempfile.mkdtemp(prefix="codeguard-loop-test-"),
        event_sink=event_sink,
    )
    loop = root.create_loop(session_id="s-task")
    if responses is not None:
        loop.llm = ScriptedMockLLM(responses=responses)
    return loop


def test_start_task_resets_counters_and_runs():
    """start_task drives a governed run and returns the result."""
    responses = [
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ]
    loop = _make_task_loop(responses=responses)
    result = loop.start_task("t1", "Do the work", [])
    assert result.terminal_state == AgentState.COMPLETED
    assert result.steps_total == 1
    assert result.llm_calls_total == 2


def test_assistant_message_is_final_reply_and_completes():
    """T8-FIX5: ASSISTANT_MESSAGE is the FINAL user-visible reply. It is
    emitted once, recorded once, triggers final validation once, and the
    task terminates — exactly one LLM call, no DECIDING round-trip, no
    LIMIT_REACHED."""
    sink = CollectingEventSink()
    responses = [
        _r(Action(kind=ActionKind.ASSISTANT_MESSAGE, message="Hello there", raw="")),
    ]
    loop = _make_task_loop(responses=responses, event_sink=sink)
    result = loop.start_task("t1", "Do the work", [])
    assert result.terminal_state == AgentState.COMPLETED
    assert result.steps_total == 0
    # Exactly ONE LLM call: no second call to ask for complete.
    assert result.llm_calls_total == 1
    assert loop._transcript == ["Hello there"]
    assistant_events = [
        e for e in sink.events
        if e.kind == HarnessEventKind.ASSISTANT_MESSAGE
    ]
    assert [e.payload["message"] for e in assistant_events] == ["Hello there"]
    # Final validation ran once (FINAL-typed results exist, exactly one run).
    final_runs = [r for r in loop._feedback_results
                  if r.validation_type == "FINAL"]
    assert len(final_runs) >= 1
    # One TASK_FINISHED with COMPLETED; never LIMIT_REACHED.
    finished = [
        e for e in sink.events if e.kind == HarnessEventKind.TASK_FINISHED
    ]
    assert len(finished) == 1
    assert finished[0].payload["outcome"] == "completed"
    # No DECIDING round-trip after the message: the trace's last states are
    # FINAL_VALIDATION → COMPLETED.
    states = [t["to"] for t in loop._trace]
    assert states[-2:] == [AgentState.FINAL_VALIDATION, AgentState.COMPLETED]


def test_request_user_input_pauses_and_resume_continues():
    """REQUEST_USER_INPUT → AWAITING_USER_INPUT; resume_with_user_input
    feeds the answer into the next context and completes."""
    responses = [
        _r(Action(kind=ActionKind.REQUEST_USER_INPUT, question="Which file?", raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ]
    loop = _make_task_loop(responses=responses)
    result = loop.start_task("t1", "Do the work", [])
    assert result.terminal_state == AgentState.AWAITING_USER_INPUT
    assert loop.state.pending_question == "Which file?"
    # The awaiting state must not have consumed any steps
    assert result.steps_total == 0

    result = loop.resume_with_user_input("src/main.py")
    assert result.terminal_state == AgentState.COMPLETED
    assert "src/main.py" in loop.llm.received_contexts[1]
    assert loop.state.pending_question is None


def test_resume_with_user_input_requires_awaiting_state():
    """resume_with_user_input outside AWAITING_USER_INPUT raises ValueError."""
    loop = _make_task_loop(
        responses=[_r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""))]
    )
    with pytest.raises(ValueError, match="AWAITING_USER_INPUT"):
        loop.resume_with_user_input("text")


def test_resume_with_user_input_requires_nonempty_text():
    """resume_with_user_input with empty text raises ValueError."""
    responses = [
        _r(Action(kind=ActionKind.REQUEST_USER_INPUT, question="Which file?", raw="")),
    ]
    loop = _make_task_loop(responses=responses)
    loop.start_task("t1", "Do the work", [])
    assert loop.state.current_state == AgentState.AWAITING_USER_INPUT
    with pytest.raises(ValueError, match="empty"):
        loop.resume_with_user_input("   ")


def test_cancel_prevents_further_tool_execution():
    """cancel() transitions an active task to CANCELLED and no tool may
    execute afterward."""
    responses = [
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ]
    loop = _make_task_loop(responses=responses)
    loop.tool_dispatcher = FakeTaskToolDispatcher()
    result = loop.cancel()
    assert result.terminal_state == AgentState.CANCELLED
    assert loop.state.current_state == AgentState.CANCELLED
    # A resumed run must not dispatch any tool
    result = loop.run()
    assert result.terminal_state == AgentState.CANCELLED
    assert loop.tool_dispatcher.dispatched == []


def test_start_task_fails_closed_when_components_missing():
    """start_task must FAILED with a redacted diagnostic when required
    components are missing; run() keeps legacy partial-wiring behavior."""
    loop = _make_task_loop(
        responses=[_r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""))]
    )
    loop.tool_registry = None
    result = loop.start_task("t1", "Do the work", [])
    assert result.terminal_state == AgentState.FAILED
    assert "tool_registry" in result.error



# ---------------------------------------------------------------------------
# T8-FIX5 — assistant_message is the task's FINAL reply (protocol change)
# ---------------------------------------------------------------------------

def test_assistant_message_is_final_reply_and_completes():
    """T8-FIX5: ASSISTANT_MESSAGE is the FINAL user-visible reply. It is
    emitted once, recorded once, triggers final validation once, and the
    task terminates — exactly one LLM call, no second call to ask for
    complete, no LIMIT_REACHED."""
    sink = CollectingEventSink()
    responses = [
        _r(Action(kind=ActionKind.ASSISTANT_MESSAGE, message="Hello there", raw="")),
    ]
    loop = _make_task_loop(responses=responses, event_sink=sink)
    result = loop.start_task("t1", "Do the work", [])
    assert result.terminal_state == AgentState.COMPLETED
    assert result.steps_total == 0
    # Exactly ONE LLM call: no second call to ask for complete.
    assert result.llm_calls_total == 1
    assert loop._transcript == ["Hello there"]
    assistant_events = [
        e for e in sink.events
        if e.kind == HarnessEventKind.ASSISTANT_MESSAGE
    ]
    assert [e.payload["message"] for e in assistant_events] == ["Hello there"]
    # Final validation ran (FINAL-typed results exist).
    final_runs = [r for r in loop._feedback_results
                  if r.validation_type == "FINAL"]
    assert len(final_runs) >= 1
    # Exactly one TASK_FINISHED with COMPLETED; never LIMIT_REACHED.
    finished = [
        e for e in sink.events if e.kind == HarnessEventKind.TASK_FINISHED
    ]
    assert len(finished) == 1
    assert finished[0].payload["outcome"] == "completed"
    # Trace ends FINAL_VALIDATION -> COMPLETED; no DECIDING round-trip.
    states = [t["to"] for t in loop._trace]
    assert states[-2:] == [AgentState.FINAL_VALIDATION, AgentState.COMPLETED]
    # The reply is the terminal summary (single state word, no repeat).
    assert "completed:" not in finished[0].payload["summary"]
    assert "Hello there" in finished[0].payload["summary"]


def test_assistant_message_validation_failure_terminates_failed():
    """T8-FIX5: when final validation fails after the final reply, the
    task terminates FAILED — displayed once, ONE terminal event, no
    COMPLETED, no LIMIT_REACHED, no further LLM call."""
    from codeguard.feedback import FeedbackResult

    class FailingFinalSensorRunner(FakeSensorRunner):
        def run_all(self):
            return [
                FeedbackResult(
                    sensor_id="pytest", program="pytest", args=["."],
                    status="FAILED", failure_category="TEST_FAILURE",
                    exit_code=1, failure_fingerprint="fp-x",
                    validation_type="INTERMEDIATE", summary="boom",
                    diagnostics=[], duration=0.1, retryable=True,
                    raw_output_truncated="boom",
                )
            ]

    sink = CollectingEventSink()
    responses = [
        _r(Action(kind=ActionKind.ASSISTANT_MESSAGE, message="Answer", raw="")),
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw="")),
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ]
    loop = _make_task_loop(responses=responses, event_sink=sink)
    loop.sensor_runner = FailingFinalSensorRunner()
    loop.objective_verifier = FakeObjectiveVerifier(passed=False)
    result = loop.start_task("t1", "Do the work", [])
    assert result.terminal_state == AgentState.FAILED
    # The reply was displayed exactly once and never re-requested.
    assistant_events = [
        e for e in sink.events
        if e.kind == HarnessEventKind.ASSISTANT_MESSAGE
    ]
    assert [e.payload["message"] for e in assistant_events] == ["Answer"]
    assert result.llm_calls_total == 1
    finished = [
        e for e in sink.events if e.kind == HarnessEventKind.TASK_FINISHED
    ]
    assert len(finished) == 1
    assert finished[0].payload["outcome"] == "failed"


def test_tool_then_assistant_message_completes_with_tool_progress():
    """T8-FIX5: tool_call -> tool_result feeds the next context -> the final
    assistant_message is displayed once -> validation -> COMPLETED. Progress
    is expressed by tool/validation events, not intermediate messages."""
    sink = CollectingEventSink()
    responses = [
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="read_file",
                  parameters={"path": "x"}, raw="")),
        _r(Action(kind=ActionKind.ASSISTANT_MESSAGE, message="check done", raw="")),
    ]
    loop = _make_task_loop(responses=responses, event_sink=sink)
    result = loop.start_task("t1", "Do the work", [])
    assert result.terminal_state == AgentState.COMPLETED
    assert result.llm_calls_total == 2
    assistant_events = [
        e for e in sink.events
        if e.kind == HarnessEventKind.ASSISTANT_MESSAGE
    ]
    assert [e.payload["message"] for e in assistant_events] == ["check done"]
    finished = [
        e for e in sink.events if e.kind == HarnessEventKind.TASK_FINISHED
    ]
    assert len(finished) == 1
    assert finished[0].payload["outcome"] == "completed"


def test_request_user_input_then_assistant_message_terminates():
    """T8-FIX5: request_user_input pauses; after the user's answer the
    final assistant_message ends the task correctly."""
    sink = CollectingEventSink()
    responses = [
        _r(Action(kind=ActionKind.REQUEST_USER_INPUT, question="Which file?", raw="")),
        _r(Action(kind=ActionKind.ASSISTANT_MESSAGE, message="Got it", raw="")),
    ]
    loop = _make_task_loop(responses=responses, event_sink=sink)
    result = loop.start_task("t1", "Do the work", [])
    assert result.terminal_state == AgentState.AWAITING_USER_INPUT
    result = loop.resume_with_user_input("config.py")
    assert result.terminal_state == AgentState.COMPLETED
    assistant_events = [
        e for e in sink.events
        if e.kind == HarnessEventKind.ASSISTANT_MESSAGE
    ]
    assert [e.payload["message"] for e in assistant_events] == ["Got it"]
    finished = [
        e for e in sink.events if e.kind == HarnessEventKind.TASK_FINISHED
    ]
    assert len(finished) == 1
    assert finished[0].payload["outcome"] == "completed"


def test_complete_without_assistant_message_still_terminates():
    """T8-FIX5 compat path: a task that never emits assistant_message can
    still terminate via complete — exactly one terminal event."""
    sink = CollectingEventSink()
    responses = [
        _r(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ]
    loop = _make_task_loop(responses=responses, event_sink=sink)
    result = loop.start_task("t1", "Do the work", [])
    assert result.terminal_state == AgentState.COMPLETED
    finished = [
        e for e in sink.events if e.kind == HarnessEventKind.TASK_FINISHED
    ]
    assert len(finished) == 1
    assert finished[0].payload["outcome"] == "completed"


def test_repeated_questions_reach_limit_and_emit_task_finished():
    """LIMIT_REACHED must emit a TASK_FINISHED event with the terminal
    outcome — no silent return to the REPL. Repeated identical
    clarification questions trip the StopPolicy no-progress check."""
    sink = CollectingEventSink()
    responses = [
        _r(Action(kind=ActionKind.REQUEST_USER_INPUT, question="Q?", raw="")),
    ] * 6
    loop = _make_task_loop(responses=responses, event_sink=sink)
    result = loop.start_task("t1", "Do the work", [])
    assert result.terminal_state == AgentState.AWAITING_USER_INPUT
    for _ in range(6):
        result = loop.resume_with_user_input("answer")
        if result.terminal_state != AgentState.AWAITING_USER_INPUT:
            break
    assert result.terminal_state == AgentState.LIMIT_REACHED
    finished = [
        e for e in sink.events if e.kind == HarnessEventKind.TASK_FINISHED
    ]
    assert len(finished) == 1
    assert finished[0].payload["outcome"] == "limit_reached"


def test_failed_emits_task_finished_event():
    """FAILED (non-recoverable BLOCK) must emit TASK_FINISHED too."""
    sink = CollectingEventSink()
    mock = ScriptedMockLLM(responses=[
        _r(Action(kind=ActionKind.TOOL_CALL, tool_name="delete_file",
                  parameters={"path": "/etc/passwd"}, raw="")),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["BLOCK"], recoverable=False)
    loop.stop_policy = FakeStopPolicy()
    loop.event_sink = sink
    result = loop.run()
    assert result.terminal_state == AgentState.FAILED
    finished = [
        e for e in sink.events if e.kind == HarnessEventKind.TASK_FINISHED
    ]
    assert len(finished) == 1
    assert finished[0].payload["outcome"] == "failed"


def test_task_finished_summary_has_no_duplicate_state_word():
    """The TASK_FINISHED payload summary must not repeat the outcome word:
    '[task] COMPLETED: completed: ...' is forbidden."""
    sink = CollectingEventSink()
    responses = [
        _r(Action(kind=ActionKind.ASSISTANT_MESSAGE,
                  message="session code is BLUE-731.", raw="")),
    ]
    loop = _make_task_loop(responses=responses, event_sink=sink)
    result = loop.start_task("t1", "Do the work", [])
    assert result.terminal_state == AgentState.COMPLETED
    finished = [
        e for e in sink.events if e.kind == HarnessEventKind.TASK_FINISHED
    ]
    assert len(finished) == 1
    payload = finished[0].payload
    assert payload["outcome"] == "completed"
    summary = payload["summary"]
    assert "completed:" not in summary
    assert "session code is BLUE-731." in summary
