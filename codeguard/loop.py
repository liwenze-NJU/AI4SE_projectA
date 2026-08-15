"""AgentLoop — explicit state machine for the CodeGuard Harness.

Implements the core agent loop driving the full state machine:
  INITIALIZING → BUILDING_CONTEXT → DECIDING → GOVERNING →
  (AWAITING_APPROVAL) → EXECUTING → (INTERMEDIATE_VALIDATION) →
  FEEDING_BACK → DECIDING (loop) → FINAL_VALIDATION → COMPLETED

Governance pipeline (SPEC §3.2):
  Action → ToolRegistry.lookup → SchemaValidator → ActionNormalizer
  → NormalizedAction → RuleEngine → PriorityMerger → GuardrailResult

Components are injected via attributes so that tests can supply
inline test doubles without needing real implementations.
"""

from datetime import datetime
from decimal import Decimal
import hashlib
import json
from codeguard.state import AgentState, SessionState, SessionResult
from codeguard.action import ActionKind
from codeguard.events import HarnessEvent, HarnessEventKind
from codeguard.guardrail import GuardrailDecision
from codeguard.guardrail.approval import ApprovalStatus
from codeguard.guardrail.normalizer import ActionNormalizer


class AgentLoop:
    """Core agent loop driving the state machine.

    Components are injected via attributes after construction:
      tool_registry      — ToolRegistry for tool lookup
      schema_validator   — SchemaValidator for parameter validation
      action_normalizer  — Action → NormalizedAction converter
      rule_engine        — Guardrail evaluator (requires NormalizedAction)
      approval_manager   — Human approval handler
      tool_dispatcher    — Tool execution dispatcher
      sensor_runner      — Sensor / validation runner
      feedback_classifier — Feedback classifier
      objective_verifier — Objective completion verifier
      stop_policy        — Stop condition evaluator
    """

    # Terminal states that must always surface a TASK_FINISHED event so the
    # CLI never silently returns to the prompt (T8-FIX3).
    _TERMINAL_STATES = frozenset({
        AgentState.COMPLETED,
        AgentState.FAILED,
        AgentState.CANCELLED,
        AgentState.LIMIT_REACHED,
    })

    def __init__(self, session_id: str, llm, max_steps: int = 50):
        self.state = SessionState(
            session_id=session_id,
            current_state=AgentState.INITIALIZING,
        )
        self.llm = llm
        self._max_steps = max_steps
        self._trace: list[dict] = []
        self._guardrail_decisions: list = []
        self._feedback_results: list = []
        self._started_at = datetime.now()
        self._iteration = 0
        self._task_finished_emitted = False
        # T8-FIX7: bounded per-task observation history (multi-file tasks
        # need several recent tool results in one context).
        self._observations: list = []
        self._observation_sequence = 0

        # Components to be injected via attributes
        self.tool_registry = None
        self.schema_validator = None
        self.rule_engine = None
        self.action_normalizer: ActionNormalizer | None = None
        self.approval_manager = None
        self.tool_dispatcher = None
        self.sensor_runner = None
        self.feedback_classifier = None
        self.objective_verifier = None
        self.stop_policy = None
        # Event sink for harness events (publishing implemented in Task 4)
        self.event_sink = None

        # Task 4: per-task inputs and carry-forward state
        self.project_id: str | None = None
        self.system_constraints: str | None = None
        self._task_id: str | None = None
        self._task_request: str = ""
        self._conversation_summaries: list[str] = []
        self._transcript: list[str] = []
        self._latest_result: str = ""
        self._cancelled: bool = False

        # Approval resume state
        self._approval_decision: ApprovalStatus | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Transition from INITIALIZING to BUILDING_CONTEXT."""
        self._transition(AgentState.BUILDING_CONTEXT)

    def resume_with_approval(self, request_id: str, session_id: str,
                             decision: ApprovalStatus,
                             action_fingerprint: str) -> None:
        """Resume the loop after an approval decision.

        Called by CLI or WebUI after the user approves or rejects.
        Validates session_id, request_id, and action_fingerprint binding.
        """
        if self.state.current_state != AgentState.AWAITING_APPROVAL:
            raise ValueError(
                f"Cannot resume: not in AWAITING_APPROVAL "
                f"(current: {self.state.current_state.value})"
            )
        if self.approval_manager is None:
            raise ValueError("No approval manager configured")

        if decision == ApprovalStatus.APPROVED:
            self.approval_manager.approve(request_id, session_id, action_fingerprint)
        elif decision == ApprovalStatus.REJECTED:
            self.approval_manager.reject(request_id, session_id)
        self._approval_decision = decision

    # ------------------------------------------------------------------
    # Task 4: per-task API
    # ------------------------------------------------------------------

    _REQUIRED_COMPONENTS = (
        "context_builder", "tool_registry", "action_normalizer", "rule_engine",
        "tool_dispatcher", "sensor_runner", "objective_verifier", "stop_policy",
        "secret_redactor", "event_sink",
    )

    def _validate_production_wiring(self) -> str | None:
        """Return a redacted diagnostic naming missing components, or None."""
        missing = [
            name for name in self._REQUIRED_COMPONENTS
            if getattr(self, name, None) is None
        ]
        if not missing:
            return None
        redactor = self.secret_redactor
        if redactor is not None:
            missing = [redactor.redact(m) for m in missing]
        return f"Missing required components: {', '.join(missing)}"

    def start_task(
        self,
        task_id: str,
        request: str,
        conversation_summaries: list[str],
    ) -> SessionResult:
        """Start a new governed task from a fresh per-task state."""
        diagnostic = self._validate_production_wiring()
        if diagnostic is not None:
            self._transition(AgentState.FAILED)
            self._latest_result = diagnostic
            self._emit_task_finished_once()
            return SessionResult(
                session_id=self.state.session_id,
                terminal_state=AgentState.FAILED,
                steps_total=self.state.steps_used,
                llm_calls_total=self.state.llm_calls_used,
                token_total=self.state.token_used,
                cost_total=self.state.cost_used,
                duration=0.0,
                guardrail_decisions=list(self._guardrail_decisions),
                feedback_results=list(self._feedback_results),
                trace=list(self._trace),
                error=diagnostic,
            )

        # Reset per-task counters and carry-forward state
        self._task_id = task_id
        self._task_request = request
        self._conversation_summaries = list(conversation_summaries)
        self._transcript = []
        self._latest_result = ""
        self._cancelled = False
        self._iteration = 0
        self._trace.clear()
        self._guardrail_decisions.clear()
        self._feedback_results.clear()
        self.state.steps_used = 0
        self.state.llm_calls_used = 0
        self.state.token_used = 0
        self.state.cost_used = Decimal("0")
        self.state.action_fingerprint_history.clear()
        self.state.failure_fingerprint_history.clear()
        self.state.result_fingerprint_history.clear()
        self._observations.clear()
        self._observation_sequence = 0
        # T8-FIX6-FIX: the stop policy's one-shot correction flag is
        # per-task state — reset it so every task's first cycle detection
        # delivers a fresh correction message.
        if self.stop_policy is not None:
            self.stop_policy._result_correction_given = False
            self.stop_policy.pending_correction = None
        self.state.pending_question = None
        self.state.pending_action = None
        self.state.approval_request_id = None
        self.state.guardrail_decision = None
        self._approval_decision = None
        self._task_finished_emitted = False
        self._started_at = datetime.now()
        self.state.current_state = AgentState.INITIALIZING
        return self.run()

    def resume_with_user_input(self, text: str) -> SessionResult:
        """Resume a task paused at AWAITING_USER_INPUT with the user's answer."""
        if self.state.current_state != AgentState.AWAITING_USER_INPUT:
            raise ValueError(
                "Cannot resume with user input: not in AWAITING_USER_INPUT "
                f"(current: {self.state.current_state.value})"
            )
        if not isinstance(text, str) or not text.strip():
            raise ValueError("User input must be a non-empty string")
        answer = text.strip()
        self._latest_result = f"User answer: {answer}"
        self.state.pending_question = None
        self._transition(AgentState.DECIDING)
        return self.run()

    def cancel(self) -> SessionResult:
        """Cancel an active or waiting task; no tool may execute afterward."""
        if self.state.current_state in (
            AgentState.COMPLETED,
            AgentState.FAILED,
            AgentState.CANCELLED,
            AgentState.LIMIT_REACHED,
        ):
            return self._build_result()
        self._cancelled = True
        self._transition(AgentState.CANCELLED)
        self._emit_task_finished_once()
        return self._build_result()

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit_task_finished_once(self) -> None:
        """Emit TASK_FINISHED exactly once when the task reaches a terminal
        state (T8-FIX3). Every terminal path — COMPLETED, FAILED,
        CANCELLED, LIMIT_REACHED — must surface a stable [task] event so
        the CLI never silently returns to the prompt."""
        if self._task_finished_emitted:
            return
        if self.state.current_state not in self._TERMINAL_STATES:
            return
        self._task_finished_emitted = True
        self._emit(HarnessEventKind.TASK_FINISHED, self._task_finished_payload())

    def _task_finished_payload(self) -> dict:
        """Compose the TASK_FINISHED payload with a real bounded summary.

        The summary carries the task transcript (the last assistant
        message, truncated to 500 chars); on failure the redacted error is
        included. The outcome is a SEPARATE field — the summary must never
        repeat the outcome word, so the CLI renders exactly one state word:
        ``[task] COMPLETED: <summary>`` (T8-FIX4).
        """
        assistant_messages = [
            m for m in self._transcript if isinstance(m, str) and m.strip()
        ]
        transcript = assistant_messages[-1] if assistant_messages else ""
        summary = transcript[:500] if transcript else self._latest_result[:500]
        payload: dict = {"outcome": self.state.current_state.value,
                         "summary": summary or self.state.current_state.value}
        if self._cancelled:
            payload["summary"] = "cancelled by user"
        elif self.state.current_state == AgentState.FAILED and self._latest_result:
            payload["summary"] = self._latest_result[:500]
        return payload

    def _emit(self, kind: HarnessEventKind, payload: dict) -> None:
        """Emit a bounded harness event through the injected sink (if any)."""
        if self.event_sink is None:
            return
        self.event_sink.emit(HarnessEvent(
            kind=kind,
            session_id=self.state.session_id,
            task_id=self._task_id or "",
            payload=payload,
        ))

    def run(self) -> SessionResult:
        """Drive the full state machine to a terminal state.

        If the loop enters AWAITING_APPROVAL, it pauses and returns.
        Call resume_with_approval() then run() again to continue.
        """
        if self._cancelled:
            if self.state.current_state != AgentState.CANCELLED:
                self._transition(AgentState.CANCELLED)
            self._emit_task_finished_once()
            return self._build_result()

        if self.state.current_state == AgentState.INITIALIZING:
            self.initialize()

        # Handle resume from AWAITING_APPROVAL
        if self.state.current_state == AgentState.AWAITING_APPROVAL:
            return self._continue_from_approval()

        # BUILDING_CONTEXT → DECIDING
        self._transition(AgentState.DECIDING)

        while self._iteration < self._max_steps:
            if self._cancelled:
                self._transition(AgentState.CANCELLED)
                break
            self._iteration += 1
            # ----- DECIDING: call LLM -----
            context = self._build_context()
            llm_response = self.llm.generate(self.state.session_id, context)
            self.state.llm_calls_used += 1
            self.state.token_used += llm_response.token_used
            self.state.cost_used += llm_response.cost_used

            action = llm_response.next_action

            # COMPLETE_REQUEST → FINAL_VALIDATION (compat path: tasks
            # without an assistant_message terminate through complete)
            if action.kind == ActionKind.COMPLETE_REQUEST:
                if not self._run_final_validation():
                    # FINAL_VALIDATION failed → FEEDING_BACK → retry
                    self._transition(AgentState.FEEDING_BACK)
                    if self._check_stop_policy():
                        break
                    self._transition(AgentState.DECIDING)
                    continue
                self._transition(AgentState.COMPLETED)
                break

            # ----- ASSISTANT_MESSAGE: the task's FINAL user-visible reply -----
            # T8-FIX5 protocol: displayed once, recorded once, then the
            # task immediately enters final validation. There is NO second
            # LLM call asking for complete, no FEEDING_BACK/DECIDING
            # round-trip — termination is guaranteed by the state machine,
            # not by model compliance. Validation failure terminates as
            # FAILED; this path can never reach LIMIT_REACHED.
            if action.kind == ActionKind.ASSISTANT_MESSAGE:
                message = action.message or ""
                self._transcript.append(message)
                self._latest_result = f"Assistant: {message}"
                self._emit(HarnessEventKind.ASSISTANT_MESSAGE,
                           {"message": message})
                if self._run_final_validation():
                    self._transition(AgentState.COMPLETED)
                else:
                    self._transition(AgentState.FAILED)
                break

            if action.kind == ActionKind.REQUEST_USER_INPUT:
                question = action.question or ""
                self.state.pending_question = question
                self._emit(HarnessEventKind.USER_INPUT_REQUESTED, {"question": question})
                # A resumed loop re-enters DECIDING; identical questions
                # repeated consecutively trip the StopPolicy no-progress
                # check (defense against clarification loops).
                self.state.action_fingerprint_history.append(
                    self._conversation_fingerprint(
                        ActionKind.REQUEST_USER_INPUT, question
                    )
                )
                if self._check_stop_policy():
                    break
                self._transition(AgentState.AWAITING_USER_INPUT)
                return self._build_result()

            # ----- TOOL_CALL → GOVERNING -----
            self._transition(AgentState.GOVERNING)

            # Normalize the action before guardrail evaluation
            normalized_action = self._normalize(action)
            if normalized_action is None:
                # Pipeline failure (unknown tool, schema error, no normalizer)
                if self.state.current_state == AgentState.FAILED:
                    break
                if self._check_stop_policy():
                    break
                self._transition(AgentState.DECIDING)
                continue

            if self.rule_engine is not None:
                guardrail_result = self.rule_engine.evaluate(normalized_action)
                self._guardrail_decisions.append(guardrail_result)
                self.state.guardrail_decision = guardrail_result
                self.state.action_fingerprint_history.append(
                    guardrail_result.action_fingerprint
                )

                decision = guardrail_result.decision

                if decision == GuardrailDecision.BLOCK:
                    reason = "; ".join(guardrail_result.reason_codes) or "blocked"
                    self._latest_result = f"Guardrail BLOCK: {reason}"
                    if guardrail_result.recoverable:
                        self._transition(AgentState.FEEDING_BACK)
                        if self._check_stop_policy():
                            break
                        self._transition(AgentState.DECIDING)
                        continue
                    else:
                        self._transition(AgentState.FAILED)
                        break

                elif decision == GuardrailDecision.REQUEST_APPROVAL:
                    self._transition(AgentState.AWAITING_APPROVAL)
                    if self.approval_manager is not None:
                        req = self.approval_manager.create_request(
                            session_id=self.state.session_id,
                            normalized_action=normalized_action,
                            matched_rules=guardrail_result.rule_ids,
                            risk_summary=guardrail_result.human_readable_message,
                        )
                        self.state.pending_action = normalized_action
                        self.state.approval_request_id = req.request_id
                        self._emit(HarnessEventKind.APPROVAL_REQUESTED, {
                            "tool": action.tool_name or "",
                            "reason": guardrail_result.human_readable_message,
                        })
                        return self._build_result()
                    else:
                        self._transition(AgentState.FAILED)
                        break

                elif decision == GuardrailDecision.ALLOW:
                    self._transition(AgentState.EXECUTING)
            else:
                self._transition(AgentState.EXECUTING)

            # ----- EXECUTING -----
            self.state.steps_used += 1

            if self.tool_dispatcher is not None:
                self._dispatch_tool(action)

            if self._is_write_action(action):
                self._transition(AgentState.INTERMEDIATE_VALIDATION)
                self._run_sensors(validation_type="INTERMEDIATE")

            self._transition(AgentState.FEEDING_BACK)

            if self._check_stop_policy():
                break

            self._transition(AgentState.DECIDING)

        # ----- Max steps exhausted -----
        if self.state.current_state not in (
            AgentState.COMPLETED,
            AgentState.FAILED,
            AgentState.CANCELLED,
            AgentState.LIMIT_REACHED,
        ):
            self._transition(AgentState.LIMIT_REACHED)

        # T8-FIX3: every terminal path surfaces one TASK_FINISHED event.
        self._emit_task_finished_once()

        return self._build_result()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    # T8-FIX7: observation-history bounds.
    _MAX_OBSERVATIONS = 10
    _MAX_OBSERVATION_CHARS = 4000
    _OBSERVATION_OUTPUT_CHARS = 800

    def _dispatch_tool(self, action) -> None:
        """Dispatch one governed tool call and record its bounded result.

        Shared by the normal EXECUTING path and the approval-resume path so
        both feed identical success/failure signals into the next decision.
        """
        self._emit(HarnessEventKind.TOOL_STARTED, {"tool": action.tool_name or ""})
        tool_result = self.tool_dispatcher.dispatch(action)
        if tool_result is None:
            return
        self._emit(HarnessEventKind.TOOL_FINISHED, {
            "tool": action.tool_name or "",
            "status": tool_result.status,
            "output": (tool_result.output_summary or "")[:500],
        })
        # T8-FIX6: record the tool RESULT fingerprint so identical
        # read-only loops (same tool, same params, same outcome) trip the
        # StopPolicy result-fingerprint check even when action fingerprints
        # alternate A→B→A→B. A write success is real progress and breaks
        # the cycle naturally because its fingerprint differs.
        params = dict(getattr(action, "parameters", None)
                      or getattr(action, "normalized_parameters", None) or {})
        result_fp = hashlib.sha256(
            f"{action.tool_name}:{sorted(params.items())}:{tool_result.status}"
            .encode("utf-8")
        ).hexdigest()
        self.state.result_fingerprint_history.append(result_fp)
        if tool_result.status in ("FAILURE", "ERROR", "TIMEOUT"):
            self._latest_result = (
                f"Tool {action.tool_name} failed: "
                f"{tool_result.output_summary[:800]}"
            )
        else:
            self._latest_result = (
                f"Tool {action.tool_name} result: "
                f"{tool_result.output_summary[:800]}"
            )
        self._record_observation(action, tool_result, result_fp)

    # ------------------------------------------------------------------
    # T8-FIX7 — bounded per-task observation history
    # ------------------------------------------------------------------

    def _record_observation(self, action, tool_result, result_fp: str) -> None:
        """Append one structured observation (deduped, bounded, redacted).

        Rules:
        - identical tool + identical parameter fingerprint + identical
          result fingerprint updates the existing entry's position instead
          of duplicating (no unbounded repeats);
        - different files are NEVER deduped against each other;
        - a successful write/patch/delete invalidates prior read
          observations for the same target file (stale content);
        - the list is capped by entry count and total characters with
          deterministic oldest-first trimming.
        """
        from codeguard.state import CurrentTaskObservation
        from codeguard.secret import SecretRedactor

        redactor = getattr(self, "secret_redactor", None) or SecretRedactor()
        params = dict(getattr(action, "parameters", None)
                      or getattr(action, "normalized_parameters", None) or {})
        safe_params = redactor.redact(
            ", ".join(f"{k}={v}" for k, v in sorted(params.items())[:8])
        )[:200]
        output = redactor.redact(tool_result.output_summary or "")[
            :self._OBSERVATION_OUTPUT_CHARS
        ]
        tool_name = action.tool_name or ""
        status = tool_result.status

        # Invalidate stale reads for a file that was just written.
        # Compare on NORMALIZED path tails: reads may have been recorded
        # with a relative path (raw Action) while the write resumes with a
        # normalized absolute path (approval path), and vice versa
        # (T8-FIX7-FIX F2). Normalization avoids both the raw/absolute
        # mismatch and substring false-invalidations (F3).
        if status == "SUCCESS" and tool_name in (
            "write_file", "apply_patch", "delete_file"
        ):
            target = str(params.get("path", ""))
            target_norm = self._normalize_path_tail(target)
            if target_norm:
                self._observations = [
                    o for o in self._observations
                    if not (
                        o.tool_name == "read_file"
                        and self._observation_path_tail(o) == target_norm
                    )
                ]

        # Dedup identical (tool, params, result) — move to the end.
        param_fp = hashlib.sha256(
            f"{tool_name}:{sorted(params.items())}".encode("utf-8")
        ).hexdigest()
        self._observations = [
            o for o in self._observations
            if not (
                o.tool_name == tool_name
                and o.parameter_fingerprint == param_fp
                and o.redacted_output == output
            )
        ]
        self._observation_sequence += 1
        self._observations.append(CurrentTaskObservation(
            tool_name=tool_name,
            parameter_fingerprint=param_fp,
            safe_parameter_summary=safe_params,
            status=status,
            redacted_output=output,
            sequence=self._observation_sequence,
        ))
        self._trim_observations()

    def _trim_observations(self) -> None:
        """Enforce entry-count and total-character budgets (oldest first)."""
        while len(self._observations) > self._MAX_OBSERVATIONS:
            self._observations.pop(0)
        total = sum(len(o.redacted_output) + len(o.safe_parameter_summary)
                    for o in self._observations)
        while (self._observations
               and total > self._MAX_OBSERVATION_CHARS):
            dropped = self._observations.pop(0)
            total -= (len(dropped.redacted_output)
                      + len(dropped.safe_parameter_summary))

    @staticmethod
    def _normalize_path_tail(path: str) -> str:
        """Normalize a path to its casefolded tail (file name) for
        comparison across relative/absolute representations."""
        import os as _os
        norm = str(path).replace("\\", "/").rstrip("/")
        tail = norm.rsplit("/", 1)[-1]
        return tail.casefold() if tail else ""

    @staticmethod
    def _observation_path_tail(obs) -> str:
        """Extract the normalized file tail from a read observation's
        parameter summary (form: 'path=...')."""
        summary = str(obs.safe_parameter_summary)
        for part in summary.split(", "):
            if part.startswith("path="):
                return AgentLoop._normalize_path_tail(part[len("path="):])
        return ""

    def _format_observations(self) -> list[str]:
        """Render the current observations as bounded context lines."""
        lines = []
        for o in self._observations:
            head = f"[{o.tool_name}] {o.safe_parameter_summary} -> {o.status}"
            if o.redacted_output:
                lines.append(f"{head}: {o.redacted_output}")
            else:
                lines.append(head)
        return lines

    def _normalize(self, action) -> 'NormalizedAction | None':
        """Run the full governance pipeline (SPEC §3.2, §3.6).

        Action → ToolRegistry.lookup → SchemaValidator
        → ActionNormalizer → NormalizedAction

        Returns NormalizedAction on success, None on failure.
        On failure, transitions to FEEDING_BACK so the LLM can retry.
        """
        from codeguard.action import NormalizedAction

        # Fail closed: no normalizer → cannot proceed
        if self.action_normalizer is None:
            self._transition(AgentState.FAILED)
            return None

        # Step 1: ToolRegistry.lookup
        if self.tool_registry is not None:
            try:
                self.tool_registry.lookup(action.tool_name or "")
            except KeyError:
                # Unknown tool → VALIDATION_ERROR, feed back
                self._latest_result = f"Unknown tool rejected: {action.tool_name}"
                self._transition(AgentState.FEEDING_BACK)
                return None

        # Step 2: SchemaValidator
        if self.schema_validator is not None and self.tool_registry is not None:
            try:
                tool_def = self.tool_registry.lookup(action.tool_name or "")
            except KeyError:
                self._transition(AgentState.FEEDING_BACK)
                return None
            try:
                self.schema_validator.validate(
                    action.parameters or {}, tool_def.parameters_schema
                )
            except ValueError as e:
                # Schema validation failed → VALIDATION_ERROR
                self._latest_result = f"Parameter validation failed: {e}"
                self._transition(AgentState.FEEDING_BACK)
                return None

        # Step 3: ActionNormalizer
        return self.action_normalizer.normalize(action)

    def _run_sensors(self, validation_type: str = "INTERMEDIATE") -> None:
        """Run sensors and classify results; carry the latest result forward."""
        if self.sensor_runner is None:
            return
        sensor_results = self.sensor_runner.run_all()
        for r in sensor_results:
            r.validation_type = validation_type
        if self.feedback_classifier is not None:
            sensor_results = [
                self.feedback_classifier.classify(r)
                for r in sensor_results
            ]
        self._feedback_results.extend(sensor_results)
        if sensor_results:
            latest = sensor_results[-1]
            sensor_feedback = (
                f"Validation {latest.sensor_id}: {latest.status}"
                f" — {latest.summary or ''}"[:800]
            )
            if self._latest_result.startswith("Tool "):
                # Keep the tool outcome visible (a failed tool must not be
                # shadowed by a later sensor run); append validation info.
                self._latest_result = (
                    f"{self._latest_result[:600]} | {sensor_feedback}"
                )
            else:
                self._latest_result = sensor_feedback
            self._emit(HarnessEventKind.VALIDATION_FINISHED, {
                "sensor": latest.sensor_id,
                "status": latest.status,
                "type": validation_type,
            })
            # T8-FIX6: failures feed the existing failure-fingerprint
            # no-progress check (previously never written).
            if latest.failure_fingerprint:
                self.state.failure_fingerprint_history.append(
                    latest.failure_fingerprint
                )

    def _run_final_validation(self) -> bool:
        """Run FINAL_VALIDATION: execute final sensors, classify, verify.

        Returns True if all required sensors pass with FINAL validation_type.
        """
        self._transition(AgentState.FINAL_VALIDATION)
        self._run_sensors(validation_type="FINAL")
        if self.objective_verifier is None:
            return True
        return self.objective_verifier.verify(self._feedback_results)

    def _continue_from_approval(self) -> SessionResult:
        """Continue execution after approval decision."""
        if self._approval_decision is None:
            # Check timeout using public API
            if self.approval_manager is not None and self.state.approval_request_id:
                timeout_result = self.approval_manager.check_timeout_for_request(
                    self.state.approval_request_id
                )
                if timeout_result is not None:
                    self._approval_decision = ApprovalStatus.TIMEOUT

        if self._approval_decision is None:
            return self._build_result()

        if self._approval_decision == ApprovalStatus.APPROVED:
            # Re-validate through governance pipeline before executing
            pending = self.state.pending_action
            if pending is None:
                self._transition(AgentState.FAILED)
                self._emit_task_finished_once()
                return self._build_result()

            # Re-run guardrail check on the NormalizedAction
            if self.rule_engine is not None:
                recheck = self.rule_engine.evaluate(pending)
                if recheck.decision == GuardrailDecision.BLOCK:
                    # Action became BLOCKed after approval — fail
                    self._transition(AgentState.FAILED)
                    self._emit_task_finished_once()
                    return self._build_result()
                # ALLOW or REQUEST_APPROVAL (already approved) → proceed

            self._transition(AgentState.EXECUTING)
            self.state.steps_used += 1
            if self.tool_dispatcher is not None:
                self._dispatch_tool(pending)
            if self._is_write_action(pending):
                self._transition(AgentState.INTERMEDIATE_VALIDATION)
                self._run_sensors(validation_type="INTERMEDIATE")
            self._transition(AgentState.FEEDING_BACK)
            if self._check_stop_policy():
                self._emit_task_finished_once()
                return self._build_result()
            self._transition(AgentState.DECIDING)
            self._approval_decision = None
            return self.run()
        elif self._approval_decision in (ApprovalStatus.REJECTED, ApprovalStatus.TIMEOUT):
            self._latest_result = (
                f"Approval {self._approval_decision.value} — action not executed"
            )
            self._transition(AgentState.CANCELLED)
            self._emit_task_finished_once()
            return self._build_result()

        return self._build_result()

    def _transition(self, new_state: AgentState) -> None:
        """Record a state transition in the trace."""
        self._trace.append({
            "from": self.state.current_state,
            "to": new_state,
            "at": datetime.now(),
        })
        self.state.current_state = new_state

    def _build_context(self) -> str:
        """Build the LLM context for one decision.

        When the runtime pieces are present (Task 4 wiring), use
        ContextBuilder.build_runtime with the current task, summaries,
        memory, tool descriptions, latest result, and budget.  Legacy
        partial wiring (existing unit tests calling run() directly) falls
        back to a minimal context string.
        """
        context_builder = getattr(self, "context_builder", None)
        if context_builder is not None and self._task_request:
            constraints = (
                self.system_constraints
                or "Never escape the workspace; unknown tools are refused; "
                   "writes require approval."
            )
            memory_records = []
            memory_retriever = getattr(self, "memory_retriever", None)
            if memory_retriever is not None and self.project_id:
                try:
                    memory_records = memory_retriever.retrieve(
                        project_id=self.project_id
                    )
                except Exception:
                    memory_records = []
            tool_descriptions = []
            if self.tool_registry is not None:
                for td in self.tool_registry.list_tools():
                    required = td.parameters_schema.get("required", []) \
                        if isinstance(td.parameters_schema, dict) else []
                    tool_descriptions.append(
                        f"{td.name}({', '.join(required)})"
                    )
            budget = (
                f"steps {self.state.steps_used}/{self._max_steps}; "
                f"llm calls {self.state.llm_calls_used}; "
                f"tokens {self.state.token_used}"
            )
            try:
                return context_builder.build_runtime(
                    system_constraints=constraints,
                    task_request=self._task_request,
                    conversation_summaries=self._conversation_summaries,
                    memory_records=memory_records,
                    tool_descriptions=tool_descriptions,
                    latest_result=self._latest_result or "No previous result",
                    budget_summary=budget,
                    observations=self._format_observations(),
                )
            except ValueError:
                # Bounded context impossible (extreme max_chars): fall back
                # to a minimal safe context rather than failing the decision.
                return f"## Task\n{self._task_request}"
        return f"Session {self.state.session_id}, step {self.state.steps_used}"

    def _build_result(self) -> SessionResult:
        """Build a SessionResult from the current state."""
        duration = (datetime.now() - self._started_at).total_seconds()
        return SessionResult(
            session_id=self.state.session_id,
            terminal_state=self.state.current_state,
            steps_total=self.state.steps_used,
            llm_calls_total=self.state.llm_calls_used,
            token_total=self.state.token_used,
            cost_total=self.state.cost_used,
            duration=duration,
            guardrail_decisions=self._guardrail_decisions,
            feedback_results=self._feedback_results,
            trace=self._trace,
        )

    @staticmethod
    def _is_write_action(action) -> bool:
        """Return True if the action has side effects requiring validation."""
        if action is None:
            return False
        write_tools = {
            "write_file", "edit_file", "delete_file", "create_file",
            "run_command", "execute",
        }
        return action.tool_name in write_tools if action.tool_name else False

    @staticmethod
    def _conversation_fingerprint(kind: ActionKind, content: str) -> str:
        """Deterministic fingerprint for clarification pauses (T8-FIX2).

        Reuses the hashing style of ActionNormalizer: sha256 of
        f"{kind}:{content}".  request_user_input never enters governance,
        so the loop itself records the fingerprint for the StopPolicy
        no-progress check (repeated identical questions terminate).
        """
        raw = f"{kind.value}:{content}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _check_stop_policy(self) -> bool:
        """Evaluate the stop policy.  Returns True if the loop should terminate."""
        if self.stop_policy is None:
            return False
        decision = self.stop_policy.evaluate(self.state)
        if decision is None:
            # T8-FIX6: the policy may offer a one-shot correction instead
            # of stopping (first result-cycle detection); carry it into the
            # next decision context.
            correction = getattr(self.stop_policy, "pending_correction", None)
            if correction:
                self.stop_policy.pending_correction = None
                self._latest_result = correction
            return False
        if decision.terminal_state == AgentState.LIMIT_REACHED:
            self._transition(AgentState.LIMIT_REACHED)
            return True
        elif decision.terminal_state == AgentState.FAILED:
            self._transition(AgentState.FAILED)
            return True
        return False