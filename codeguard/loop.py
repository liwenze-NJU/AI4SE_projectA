"""AgentLoop — explicit state machine for the CodeGuard Harness.

Implements the core agent loop driving the full state machine:
  INITIALIZING → BUILDING_CONTEXT → DECIDING → GOVERNING →
  (AWAITING_APPROVAL) → EXECUTING → (INTERMEDIATE_VALIDATION) →
  FEEDING_BACK → DECIDING (loop) → FINAL_VALIDATION → COMPLETED

Components are injected via attributes so that tests can supply
inline test doubles without needing real implementations.
"""

from datetime import datetime
from codeguard.state import AgentState, SessionState, SessionResult
from codeguard.action import ActionKind
from codeguard.guardrail import GuardrailDecision
from codeguard.guardrail.approval import ApprovalStatus


class AgentLoop:
    """Core agent loop driving the state machine.

    Components are injected via attributes after construction:
      rule_engine        — Guardrail evaluator
      approval_manager   — Human approval handler
      tool_dispatcher    — Tool execution dispatcher
      sensor_runner      — Sensor / validation runner
      feedback_classifier — Feedback classifier
      objective_verifier — Objective completion verifier
      stop_policy        — Stop condition evaluator
    """

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

        # Components to be injected via attributes
        self.rule_engine = None
        self.approval_manager = None
        self.tool_dispatcher = None
        self.sensor_runner = None
        self.feedback_classifier = None
        self.objective_verifier = None
        self.stop_policy = None

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

    def run(self) -> SessionResult:
        """Drive the full state machine to a terminal state.

        If the loop enters AWAITING_APPROVAL, it pauses and returns.
        Call resume_with_approval() then run() again to continue.

        Returns
        -------
        SessionResult
            Terminal state (or AWAITING_APPROVAL if paused),
            step counts, trace, and aggregate metrics.
        """
        if self.state.current_state == AgentState.INITIALIZING:
            self.initialize()

        # Handle resume from AWAITING_APPROVAL
        if self.state.current_state == AgentState.AWAITING_APPROVAL:
            return self._continue_from_approval()

        # BUILDING_CONTEXT → DECIDING
        self._transition(AgentState.DECIDING)

        while self._iteration < self._max_steps:
            self._iteration += 1
            # ----- DECIDING: call LLM -----
            context = self._build_context()
            llm_response = self.llm.generate(self.state.session_id, context)
            self.state.llm_calls_used += 1
            self.state.token_used += llm_response.token_used
            self.state.cost_used += llm_response.cost_used

            action = llm_response.next_action

            # COMPLETE_REQUEST → FINAL_VALIDATION
            if action.kind == ActionKind.COMPLETE_REQUEST:
                self._transition(AgentState.FINAL_VALIDATION)
                if self.objective_verifier is None or self.objective_verifier.verify(self._feedback_results):
                    self._transition(AgentState.COMPLETED)
                    break
                else:
                    self._transition(AgentState.FEEDING_BACK)
                    if self._check_stop_policy():
                        break
                    self._transition(AgentState.DECIDING)
                    continue

            # ----- TOOL_CALL → GOVERNING -----
            self._transition(AgentState.GOVERNING)

            if self.rule_engine is not None:
                guardrail_result = self.rule_engine.evaluate(action)
                self._guardrail_decisions.append(guardrail_result)
                self.state.guardrail_decision = guardrail_result
                self.state.action_fingerprint_history.append(
                    guardrail_result.action_fingerprint
                )

                decision = guardrail_result.decision

                if decision == GuardrailDecision.BLOCK:
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
                            normalized_action=action,
                            matched_rules=guardrail_result.rule_ids,
                            risk_summary=guardrail_result.human_readable_message,
                        )
                        self.state.pending_action = action
                        self.state.approval_request_id = req.request_id
                        # Pause — return so caller can approve/reject
                        return self._build_result()
                    else:
                        self._transition(AgentState.FAILED)
                        break

                elif decision == GuardrailDecision.ALLOW:
                    self._transition(AgentState.EXECUTING)
            else:
                # No rule engine — allow by default
                self._transition(AgentState.EXECUTING)

            # ----- EXECUTING -----
            self.state.steps_used += 1

            if self.tool_dispatcher is not None:
                self.tool_dispatcher.dispatch(action)

            if self._is_write_action(action):
                self._transition(AgentState.INTERMEDIATE_VALIDATION)
                if self.sensor_runner is not None:
                    sensor_results = self.sensor_runner.run_all()
                    if self.feedback_classifier is not None:
                        sensor_results = [
                            self.feedback_classifier.classify(r)
                            for r in sensor_results
                        ]
                    self._feedback_results.extend(sensor_results)

            self._transition(AgentState.FEEDING_BACK)

            if self._check_stop_policy():
                break

            # Loop back to DECIDING
            self._transition(AgentState.DECIDING)

        # ----- Max steps exhausted -----
        if self.state.current_state not in (
            AgentState.COMPLETED,
            AgentState.FAILED,
            AgentState.CANCELLED,
            AgentState.LIMIT_REACHED,
        ):
            self._transition(AgentState.LIMIT_REACHED)

        return self._build_result()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _continue_from_approval(self) -> SessionResult:
        """Continue execution after approval decision."""
        if self._approval_decision is None:
            # Check timeout
            if self.approval_manager is not None and self.state.approval_request_id:
                req = self.approval_manager._requests.get(self.state.approval_request_id)
                if req is not None:
                    timeout_result = self.approval_manager.check_timeout(req)
                    if timeout_result is not None:
                        self._approval_decision = ApprovalStatus.TIMEOUT

        if self._approval_decision is None:
            # Still waiting — return current state
            return self._build_result()

        if self._approval_decision == ApprovalStatus.APPROVED:
            self._transition(AgentState.EXECUTING)
            self.state.steps_used += 1
            if self.tool_dispatcher is not None and self.state.pending_action is not None:
                self.tool_dispatcher.dispatch(self.state.pending_action)
            if self._is_write_action(self.state.pending_action):
                self._transition(AgentState.INTERMEDIATE_VALIDATION)
            self._transition(AgentState.FEEDING_BACK)
            if self._check_stop_policy():
                return self._build_result()
            self._transition(AgentState.DECIDING)
            self._approval_decision = None
            # Continue the main loop
            return self.run()
        elif self._approval_decision in (ApprovalStatus.REJECTED, ApprovalStatus.TIMEOUT):
            self._transition(AgentState.CANCELLED)
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
        """Build a context string for the LLM call."""
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

    def _check_stop_policy(self) -> bool:
        """Evaluate the stop policy.  Returns True if the loop should terminate."""
        if self.stop_policy is None:
            return False
        decision = self.stop_policy.evaluate(self.state)
        if decision is None:
            return False
        if decision.terminal_state == AgentState.LIMIT_REACHED:
            self._transition(AgentState.LIMIT_REACHED)
            return True
        elif decision.terminal_state == AgentState.FAILED:
            self._transition(AgentState.FAILED)
            return True
        return False