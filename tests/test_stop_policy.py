from decimal import Decimal
from datetime import datetime
from codeguard.stop import StopPolicy, StopDecision
from codeguard.state import AgentState, SessionState


def _make_state(steps=0, llm_calls=0, token=0, cost=Decimal("0"),
                action_fps=None, failure_fps=None, result_fps=None):
    return SessionState(
        session_id="s1", current_state=AgentState.DECIDING,
        pending_action=None, guardrail_decision=None, approval_request_id=None,
        steps_used=steps, llm_calls_used=llm_calls,
        token_used=token, cost_used=cost,
        action_fingerprint_history=action_fps or [],
        failure_fingerprint_history=failure_fps or [],
        result_fingerprint_history=result_fps or [],
        started_at=datetime.now(),
    )


# ── max_steps ────────────────────────────────────────────────────────

class TestMaxSteps:
    def test_steps_at_limit(self):
        policy = StopPolicy(max_steps=5)
        d = policy.evaluate(_make_state(steps=5))
        assert d.should_stop is True
        assert d.terminal_state == AgentState.LIMIT_REACHED

    def test_steps_below_limit(self):
        policy = StopPolicy(max_steps=5)
        assert policy.evaluate(_make_state(steps=4)) is None

    def test_steps_above_limit(self):
        policy = StopPolicy(max_steps=5)
        d = policy.evaluate(_make_state(steps=6))
        assert d.should_stop is True


# ── max_llm_calls ────────────────────────────────────────────────────

class TestMaxLLMCalls:
    def test_llm_calls_at_limit(self):
        policy = StopPolicy(max_llm_calls=10)
        d = policy.evaluate(_make_state(llm_calls=10))
        assert d.should_stop is True

    def test_llm_calls_below_limit(self):
        policy = StopPolicy(max_llm_calls=10)
        assert policy.evaluate(_make_state(llm_calls=9)) is None


# ── token_budget ─────────────────────────────────────────────────────

class TestTokenBudget:
    def test_token_at_budget(self):
        policy = StopPolicy(token_budget=1000)
        d = policy.evaluate(_make_state(token=1000))
        assert d.should_stop is True

    def test_token_below_budget(self):
        policy = StopPolicy(token_budget=1000)
        assert policy.evaluate(_make_state(token=999)) is None

    def test_token_budget_none_means_no_limit(self):
        policy = StopPolicy(token_budget=None)
        assert policy.evaluate(_make_state(token=999999)) is None


# ── cost_budget ──────────────────────────────────────────────────────

class TestCostBudget:
    def test_cost_at_budget(self):
        policy = StopPolicy(cost_budget=Decimal("1.0"))
        d = policy.evaluate(_make_state(cost=Decimal("1.0")))
        assert d.should_stop is True

    def test_cost_below_budget(self):
        policy = StopPolicy(cost_budget=Decimal("1.0"))
        assert policy.evaluate(_make_state(cost=Decimal("0.99"))) is None

    def test_cost_budget_none_means_no_limit(self):
        policy = StopPolicy(cost_budget=None)
        assert policy.evaluate(_make_state(cost=Decimal("999.0"))) is None


# ── Consecutive action fingerprint ───────────────────────────────────

class TestConsecutiveActionFingerprint:
    def test_consecutive_repeats_trigger_stop(self):
        policy = StopPolicy(no_progress_threshold=3)
        d = policy.evaluate(_make_state(action_fps=["fp1", "fp1", "fp1"]))
        assert d.should_stop is True

    def test_non_consecutive_does_not_trigger(self):
        # SPEC: "连续重复" — consecutive only
        policy = StopPolicy(no_progress_threshold=3)
        state = _make_state(action_fps=["fp1", "fp2", "fp1", "fp1"])
        assert policy.evaluate(state) is None

    def test_consecutive_at_boundary(self):
        policy = StopPolicy(no_progress_threshold=3)
        state = _make_state(action_fps=["fp1", "fp1", "fp2", "fp2", "fp2"])
        d = policy.evaluate(state)
        assert d.should_stop is True

    def test_single_fingerprint_no_repeat(self):
        policy = StopPolicy(no_progress_threshold=3)
        assert policy.evaluate(_make_state(action_fps=["fp1"])) is None

    def test_threshold_zero_disables_check(self):
        policy = StopPolicy(no_progress_threshold=0)
        state = _make_state(action_fps=["fp1", "fp1", "fp1", "fp1"])
        assert policy.evaluate(state) is None


# ── Consecutive failure fingerprint ──────────────────────────────────

class TestConsecutiveFailureFingerprint:
    def test_consecutive_failures_trigger_stop(self):
        policy = StopPolicy(no_progress_threshold=3)
        d = policy.evaluate(_make_state(failure_fps=["ff1", "ff1", "ff1"]))
        assert d.should_stop is True

    def test_non_consecutive_failures_do_not_trigger(self):
        policy = StopPolicy(no_progress_threshold=3)
        state = _make_state(failure_fps=["ff1", "ff2", "ff1", "ff1"])
        assert policy.evaluate(state) is None

    def test_action_and_failure_fingerprints_separate(self):
        policy = StopPolicy(no_progress_threshold=3)
        state = _make_state(action_fps=["fp1", "fp1"], failure_fps=["ff1", "ff1", "ff1"])
        d = policy.evaluate(state)
        assert d.should_stop is True  # failure triggers


# ── No condition met ─────────────────────────────────────────────────

class TestNoCondition:
    def test_no_condition_returns_none(self):
        policy = StopPolicy(max_steps=50, max_llm_calls=100, no_progress_threshold=3)
        state = _make_state(steps=1, llm_calls=1)
        assert policy.evaluate(state) is None

    def test_below_all_limits(self):
        policy = StopPolicy(max_steps=10, max_llm_calls=10, token_budget=100, cost_budget=Decimal("1.0"))
        state = _make_state(steps=5, llm_calls=5, token=50, cost=Decimal("0.5"))
        assert policy.evaluate(state) is None


# ── T8-FIX6: result-fingerprint no-progress (read A→B→A→B loops) ────

def _state_with_result_fps(result_fps, **kw):
    kw["result_fps"] = result_fps
    return _make_state(steps=5, llm_calls=6, **kw)


class TestResultFingerprintNoProgress:
    def test_alternating_reads_first_detection_offers_correction(self):
        """A→B→A→B read-only alternation: the FIRST detection offers one
        correction (no stop); the SECOND consecutive detection stops."""
        policy = StopPolicy(no_progress_threshold=3)
        fps = ["r:a", "r:b", "r:a", "r:b", "r:a", "r:b"]
        state = _state_with_result_fps(fps)
        d = policy.evaluate(state)
        assert d is None
        assert policy.pending_correction is not None
        # A second identical evaluation (same state = still stuck) stops.
        d = policy.evaluate(state)
        assert d is not None
        assert d.terminal_state == AgentState.LIMIT_REACHED

    def test_write_success_resets_result_progress(self):
        """A successful write is real progress: the result-fingerprint run
        must not trip when a distinct result intervenes."""
        policy = StopPolicy(no_progress_threshold=3)
        state = _state_with_result_fps(
            ["r:a", "r:b", "w:1", "r:a", "r:b"],
        )
        assert policy.evaluate(state) is None

    def test_patch_fail_then_correct_once_allowed(self):
        """patch FAILURE → one corrective read/patch with new content →
        success is the normal loop; it must NOT be stopped."""
        policy = StopPolicy(no_progress_threshold=3)
        state = _state_with_result_fps(
            ["f:patch", "r:a", "s:patch"],
        )
        assert policy.evaluate(state) is None

    def test_repeated_identical_reads_stop_after_correction(self):
        """Same read tool + same params + same result: correction first,
        then stop on the next detection."""
        policy = StopPolicy(no_progress_threshold=3)
        state = _state_with_result_fps(["r:a", "r:a", "r:a"])
        assert policy.evaluate(state) is None
        assert policy.pending_correction is not None
        d = policy.evaluate(state)
        assert d is not None
        assert d.terminal_state == AgentState.LIMIT_REACHED

    def test_correction_rearms_after_cycle_breaks(self):
        """Once the cycle breaks (new result), a FUTURE cycle gets a fresh
        correction before stopping — the one-shot flag must rearm."""
        policy = StopPolicy(no_progress_threshold=3)
        stuck = ["r:a", "r:b", "r:a", "r:b", "r:a", "r:b"]
        assert policy.evaluate(_state_with_result_fps(stuck)) is None
        assert policy.pending_correction is not None
        # progress happened (distinct result appended), then a NEW cycle
        assert policy.evaluate(_state_with_result_fps(stuck + ["w:9"])) is None
        new_cycle = stuck + ["w:9", "r:c", "r:d", "r:c", "r:d", "r:c", "r:d"]
        assert policy.evaluate(_state_with_result_fps(new_cycle)) is None
        assert policy.pending_correction is not None
        d = policy.evaluate(_state_with_result_fps(new_cycle))
        assert d is not None

    def test_missing_history_means_no_trigger(self):
        """Old state without the new field never trips the new check."""
        policy = StopPolicy(no_progress_threshold=3)
        assert policy.evaluate(_make_state(steps=1)) is None


# ── StopDecision structure ───────────────────────────────────────────

class TestStopDecisionStructure:
    def test_has_should_stop(self):
        policy = StopPolicy(max_steps=1)
        d = policy.evaluate(_make_state(steps=1))
        assert d.should_stop is True

    def test_has_terminal_state(self):
        policy = StopPolicy(max_steps=1)
        d = policy.evaluate(_make_state(steps=1))
        assert d.terminal_state == AgentState.LIMIT_REACHED

    def test_has_reason(self):
        policy = StopPolicy(max_steps=1)
        d = policy.evaluate(_make_state(steps=1))
        assert len(d.reason) > 0