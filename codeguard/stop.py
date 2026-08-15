from dataclasses import dataclass
from codeguard.state import AgentState, SessionState


@dataclass
class StopDecision:
    should_stop: bool
    terminal_state: AgentState
    reason: str


class StopPolicy:
    """Evaluates session state against stop conditions.

    Per SPEC §3.3: fingerprint checks use CONSECUTIVE repeats (not
    any-occurrence counts). Budgets of None mean no limit.
    Priority: FAILED > CANCELLED > LIMIT_REACHED > COMPLETED.
    """

    def __init__(self, max_steps: int = 50, max_llm_calls: int = 100,
                 token_budget: int | None = None, cost_budget=None,
                 no_progress_threshold: int = 3):
        self._max_steps = max_steps
        self._max_llm_calls = max_llm_calls
        self._token_budget = token_budget
        self._cost_budget = cost_budget
        self._no_progress_threshold = no_progress_threshold
        # T8-FIX6: two-phase result-cycle handling — the first detection
        # yields a correction message (continue), a second consecutive
        # detection terminates.
        self._result_correction_given = False
        self.pending_correction: str | None = None

    def evaluate(self, state: SessionState) -> StopDecision | None:
        if state.steps_used >= self._max_steps:
            return StopDecision(True, AgentState.LIMIT_REACHED,
                               f"Steps {state.steps_used} >= max {self._max_steps}")
        if state.llm_calls_used >= self._max_llm_calls:
            return StopDecision(True, AgentState.LIMIT_REACHED,
                               f"LLM calls {state.llm_calls_used} >= max {self._max_llm_calls}")
        if self._token_budget is not None and state.token_used >= self._token_budget:
            return StopDecision(True, AgentState.LIMIT_REACHED,
                               f"Tokens {state.token_used} >= budget {self._token_budget}")
        if self._cost_budget is not None and state.cost_used >= self._cost_budget:
            return StopDecision(True, AgentState.LIMIT_REACHED,
                               f"Cost {state.cost_used} >= budget {self._cost_budget}")

        if self._no_progress_threshold > 0:
            if self._max_consecutive(state.action_fingerprint_history) >= self._no_progress_threshold:
                return StopDecision(True, AgentState.LIMIT_REACHED,
                                   "Repeated action fingerprint — no progress")
            if self._max_consecutive(state.failure_fingerprint_history) >= self._no_progress_threshold:
                return StopDecision(True, AgentState.LIMIT_REACHED,
                                   "Repeated failure fingerprint — no progress")
            # T8-FIX6: same tool result repeating — including A→B→A→B
            # alternation — is no progress. Tail-cycle detection finds
            # periodic repeats of any block length up to 5. First detection
            # offers one correction; a second consecutive detection stops.
            if self._max_cycle_repeat(
                getattr(state, "result_fingerprint_history", [])
            ) >= self._no_progress_threshold:
                if not self._result_correction_given:
                    self._result_correction_given = True
                    self.pending_correction = (
                        "Your recent tool calls repeat the same results "
                        "without progress. Change parameters, take a "
                        "different action, or complete the task; further "
                        "repetition will terminate the task."
                    )
                    return None
                return StopDecision(True, AgentState.LIMIT_REACHED,
                                   "Repeated tool result fingerprint — no progress")
            else:
                # The cycle broke (real progress happened): arm the
                # correction for any future cycle.
                self._result_correction_given = False

        return None

    @staticmethod
    def _max_cycle_repeat(history: list[str], max_period: int = 5) -> int:
        """Max number of consecutive identical length-L blocks at the tail.

        L=1 is the classic consecutive-repeat run; larger L detects
        A→B→A→B-style alternation cycles.
        """
        if not history:
            return 0
        best = 1
        for length in range(1, min(max_period, len(history) // 2) + 1):
            block = history[-length:]
            run = 1
            idx = len(history) - length
            while idx - length >= 0 and history[idx - length:idx] == block:
                run += 1
                idx -= length
            best = max(best, run)
        return best

    @staticmethod
    def _max_consecutive(history: list[str]) -> int:
        if not history:
            return 0
        max_run = 1
        current_run = 1
        for i in range(1, len(history)):
            if history[i] == history[i - 1]:
                current_run += 1
            else:
                max_run = max(max_run, current_run)
                current_run = 1
        return max(max_run, current_run)