from codeguard.feedback.verifier import ObjectiveVerifier
from codeguard.feedback import FeedbackResult


def _make_fr(sensor_id="pytest", status="PASSED", validation_type="FINAL",
             exit_code=0, failure_category=None, summary="ok"):
    return FeedbackResult(
        sensor_id=sensor_id, program=sensor_id, args=[],
        status=status, failure_category=failure_category,
        exit_code=exit_code, failure_fingerprint=None,
        validation_type=validation_type, summary=summary,
        diagnostics=[], duration=0.1, retryable=False,
        raw_output_truncated="",
    )


# ── Basic scenarios ──────────────────────────────────────────────────

class TestBasic:
    def test_one_required_passed(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [_make_fr("pytest", "PASSED", "FINAL")]
        assert verifier.verify(results) is True

    def test_multiple_required_all_passed(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest", "ruff"])
        results = [
            _make_fr("pytest", "PASSED", "FINAL"),
            _make_fr("ruff", "PASSED", "FINAL"),
        ]
        assert verifier.verify(results) is True

    def test_any_required_failed(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest", "ruff"])
        results = [
            _make_fr("pytest", "PASSED", "FINAL"),
            _make_fr("ruff", "FAILED", "FINAL", exit_code=1, failure_category="LINT_ERROR"),
        ]
        assert verifier.verify(results) is False

    def test_required_sensor_missing(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest", "ruff"])
        results = [_make_fr("pytest", "PASSED", "FINAL")]
        assert verifier.verify(results) is False

    def test_empty_required_sensors(self):
        verifier = ObjectiveVerifier(required_sensors=[])
        assert verifier.verify([]) is True

    def test_empty_results_with_required(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        assert verifier.verify([]) is False


# ── Execution error states ───────────────────────────────────────────

class TestExecutionErrors:
    def test_timeout_not_passed(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [_make_fr("pytest", "TIMEOUT", "FINAL", exit_code=None)]
        assert verifier.verify(results) is False

    def test_unavailable_not_passed(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [_make_fr("pytest", "UNAVAILABLE", "FINAL", exit_code=None)]
        assert verifier.verify(results) is False

    def test_execution_error_not_passed(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [_make_fr("pytest", "EXECUTION_ERROR", "FINAL", exit_code=None)]
        assert verifier.verify(results) is False


# ── FINAL vs INTERMEDIATE ────────────────────────────────────────────

class TestFinalVsIntermediate:
    def test_intermediate_passed_does_not_count(self):
        """INTERMEDIATE_VALIDATION cannot lead to COMPLETED per SPEC."""
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [_make_fr("pytest", "PASSED", "INTERMEDIATE")]
        assert verifier.verify(results) is False

    def test_final_passed_does_count(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [_make_fr("pytest", "PASSED", "FINAL")]
        assert verifier.verify(results) is True

    def test_mixed_validation_types(self):
        """Only FINAL counts; INTERMEDIATE ignored even if PASSED."""
        verifier = ObjectiveVerifier(required_sensors=["pytest", "ruff"])
        results = [
            _make_fr("pytest", "PASSED", "FINAL"),
            _make_fr("ruff", "PASSED", "INTERMEDIATE"),
        ]
        assert verifier.verify(results) is False


# ── Non-required sensors ─────────────────────────────────────────────

class TestNonRequired:
    def test_non_required_failure_does_not_block(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [
            _make_fr("pytest", "PASSED", "FINAL"),
            _make_fr("ruff", "FAILED", "FINAL", exit_code=1, failure_category="LINT_ERROR"),
        ]
        assert verifier.verify(results) is True

    def test_only_non_required_with_empty_required(self):
        verifier = ObjectiveVerifier(required_sensors=[])
        results = [_make_fr("ruff", "FAILED", "FINAL", exit_code=1)]
        assert verifier.verify(results) is True


# ── Same sensor_id multiple results ──────────────────────────────────

class TestDuplicateSensorId:
    def test_last_result_wins(self):
        """Later failure overrides earlier PASSED for the same sensor_id."""
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [
            _make_fr("pytest", "PASSED", "FINAL"),
            _make_fr("pytest", "FAILED", "FINAL", exit_code=1, failure_category="TEST_FAILURE"),
        ]
        assert verifier.verify(results) is False

    def test_last_passed_wins_over_earlier_failure(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [
            _make_fr("pytest", "FAILED", "FINAL", exit_code=1, failure_category="TEST_FAILURE"),
            _make_fr("pytest", "PASSED", "FINAL"),
        ]
        assert verifier.verify(results) is True

    def test_multiple_sensors_last_each(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest", "ruff"])
        results = [
            _make_fr("pytest", "FAILED", "FINAL", exit_code=1),
            _make_fr("ruff", "PASSED", "FINAL"),
            _make_fr("pytest", "PASSED", "FINAL"),
            _make_fr("ruff", "FAILED", "FINAL", exit_code=1),
        ]
        assert verifier.verify(results) is False  # ruff's last is FAILED


# ── No side effects ──────────────────────────────────────────────────

class TestNoSideEffects:
    def test_input_not_modified(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [_make_fr("pytest", "PASSED", "FINAL")]
        original_status = results[0].status
        verifier.verify(results)
        assert results[0].status == original_status

    def test_repeated_call_same_result(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [_make_fr("pytest", "PASSED", "FINAL")]
        assert verifier.verify(results) is True
        assert verifier.verify(results) is True


# ── Edge cases ───────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_results_and_empty_required(self):
        verifier = ObjectiveVerifier(required_sensors=[])
        assert verifier.verify([]) is True

    def test_unknown_sensor_id_ignored(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [
            _make_fr("pytest", "PASSED", "FINAL"),
            _make_fr("unknown_sensor", "FAILED", "FINAL", exit_code=1),
        ]
        assert verifier.verify(results) is True

    def test_result_order_does_not_break_single_sensor(self):
        verifier = ObjectiveVerifier(required_sensors=["pytest", "ruff"])
        results = [
            _make_fr("ruff", "PASSED", "FINAL"),
            _make_fr("pytest", "PASSED", "FINAL"),
        ]
        assert verifier.verify(results) is True