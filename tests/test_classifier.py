from codeguard.feedback.classifier import FeedbackClassifier
from codeguard.feedback import FeedbackResult


def _make_fr(sensor_id="pytest", status="FAILED", exit_code=1, raw_output="",
             failure_category=None, diagnostics=None, duration=0.1, summary=""):
    return FeedbackResult(
        sensor_id=sensor_id,
        program=sensor_id,
        args=[],
        status=status,
        failure_category=failure_category,
        exit_code=exit_code,
        failure_fingerprint=None,
        validation_type="INTERMEDIATE",
        summary=summary,
        diagnostics=diagnostics or [],
        duration=duration,
        retryable=(status != "PASSED"),
        raw_output_truncated=raw_output,
    )


# ── PASSED ───────────────────────────────────────────────────────────

class TestPassed:
    def test_passed_unchanged(self):
        classifier = FeedbackClassifier()
        result = _make_fr(status="PASSED", exit_code=0, summary="1 passed")
        classified = classifier.classify(result)
        assert classified.status == "PASSED"
        assert classified.failure_category is None
        assert classified.failure_fingerprint is None

    def test_passed_preserves_duration(self):
        classifier = FeedbackClassifier()
        result = _make_fr(status="PASSED", exit_code=0, duration=0.5)
        classified = classifier.classify(result)
        assert classified.duration == 0.5


# ── Execution-level errors ───────────────────────────────────────────

class TestExecutionErrors:
    def test_timeout_preserved(self):
        classifier = FeedbackClassifier()
        result = _make_fr(status="TIMEOUT", exit_code=None, summary="Timed out")
        classified = classifier.classify(result)
        assert classified.status == "TIMEOUT"
        assert classified.failure_category == "TIMEOUT"

    def test_unavailable_preserved(self):
        classifier = FeedbackClassifier()
        result = _make_fr(status="UNAVAILABLE", exit_code=None)
        classified = classifier.classify(result)
        assert classified.status == "UNAVAILABLE"
        assert classified.failure_category == "UNAVAILABLE"

    def test_execution_error_preserved(self):
        classifier = FeedbackClassifier()
        result = _make_fr(status="EXECUTION_ERROR", exit_code=None)
        classified = classifier.classify(result)
        assert classified.status == "EXECUTION_ERROR"
        assert classified.failure_category == "EXECUTION_ERROR"


# ── FAILED with parsers ──────────────────────────────────────────────

class TestFailedWithParsers:
    def test_pytest_failed_uses_pytest_parser(self):
        classifier = FeedbackClassifier()
        output = "FAILED test_main.py:3::test_hello - assert 1 == 2"
        result = _make_fr(sensor_id="pytest", status="FAILED", exit_code=1, raw_output=output)
        classified = classifier.classify(result)
        assert classified.failure_category == "TEST_FAILURE"
        assert len(classified.diagnostics) >= 1

    def test_ruff_failed_uses_ruff_parser(self):
        classifier = FeedbackClassifier()
        output = "main.py:1:1: F401 `os` imported but unused"
        result = _make_fr(sensor_id="ruff", status="FAILED", exit_code=1, raw_output=output)
        classified = classifier.classify(result)
        assert classified.failure_category == "LINT_ERROR"
        assert len(classified.diagnostics) >= 1

    def test_mypy_failed_uses_mypy_parser(self):
        classifier = FeedbackClassifier()
        output = 'main.py:10: error: Incompatible return value type (got "int", expected "str")'
        result = _make_fr(sensor_id="mypy", status="FAILED", exit_code=1, raw_output=output)
        classified = classifier.classify(result)
        assert classified.failure_category == "TYPE_ERROR"
        assert len(classified.diagnostics) >= 1

    def test_unknown_sensor_uses_generic_parser(self):
        classifier = FeedbackClassifier()
        result = _make_fr(sensor_id="eslint", status="FAILED", exit_code=1, raw_output="some error")
        classified = classifier.classify(result)
        assert classified.failure_category == "UNKNOWN_FAILURE"


# ── Empty / malformed output ─────────────────────────────────────────

class TestMalformedOutput:
    def test_empty_failed_output_unknown_failure(self):
        classifier = FeedbackClassifier()
        result = _make_fr(sensor_id="pytest", status="FAILED", exit_code=1, raw_output="")
        classified = classifier.classify(result)
        # PytestParser returns None for empty output → UNKNOWN_FAILURE
        assert classified.failure_category is not None

    def test_malformed_failed_output_unknown_failure(self):
        classifier = FeedbackClassifier()
        result = _make_fr(sensor_id="pytest", status="FAILED", exit_code=1,
                          raw_output="garbage that no parser understands")
        classified = classifier.classify(result)
        assert classified.failure_category is not None


# ── Parser exception fail-safe ───────────────────────────────────────

class TestParserExceptionSafe:
    def test_parser_exception_does_not_crash(self):
        classifier = FeedbackClassifier()
        # Abuse a sensor_id that maps to a parser which will choke on None
        # But the classifier itself should never crash
        result = _make_fr(sensor_id="nonexistent_xyz", status="FAILED", exit_code=1,
                          raw_output="anything")
        classified = classifier.classify(result)
        assert classified.status == "FAILED"
        assert classified.failure_category is not None


# ── Fingerprint ──────────────────────────────────────────────────────

class TestFingerprint:
    def test_fingerprint_set_on_failure(self):
        classifier = FeedbackClassifier()
        output = "FAILED test_main.py:3::test_hello"
        result = _make_fr(sensor_id="pytest", status="FAILED", exit_code=1, raw_output=output)
        classified = classifier.classify(result)
        assert classified.failure_fingerprint is not None
        assert len(classified.failure_fingerprint) == 64

    def test_same_failure_same_fingerprint(self):
        classifier = FeedbackClassifier()
        output = "FAILED test_main.py:3::test_hello"
        r1 = classifier.classify(
            _make_fr(sensor_id="pytest", status="FAILED", exit_code=1, raw_output=output))
        r2 = classifier.classify(
            _make_fr(sensor_id="pytest", status="FAILED", exit_code=1, raw_output=output))
        assert r1.failure_fingerprint == r2.failure_fingerprint

    def test_different_failure_different_fingerprint(self):
        classifier = FeedbackClassifier()
        r1 = classifier.classify(
            _make_fr(sensor_id="pytest", status="FAILED", exit_code=1,
                     raw_output="FAILED test_a.py:1::test_x"))
        r2 = classifier.classify(
            _make_fr(sensor_id="pytest", status="FAILED", exit_code=1,
                     raw_output="FAILED test_b.py:2::test_y"))
        assert r1.failure_fingerprint != r2.failure_fingerprint

    def test_fingerprint_differs_by_category(self):
        classifier = FeedbackClassifier()
        r1 = classifier.classify(
            _make_fr(sensor_id="pytest", status="FAILED", exit_code=1,
                     raw_output="FAILED test_a.py:1::test_x"))
        r2 = classifier.classify(
            _make_fr(sensor_id="ruff", status="FAILED", exit_code=1,
                     raw_output="test_a.py:1:1: F401 unused"))
        assert r1.failure_fingerprint != r2.failure_fingerprint


# ── Evidence preservation ────────────────────────────────────────────

class TestEvidencePreservation:
    def test_preserves_exit_code(self):
        classifier = FeedbackClassifier()
        result = _make_fr(sensor_id="pytest", status="FAILED", exit_code=2,
                          raw_output="FAILED test.py::t")
        classified = classifier.classify(result)
        assert classified.exit_code == 2

    def test_preserves_duration(self):
        classifier = FeedbackClassifier()
        result = _make_fr(sensor_id="pytest", status="FAILED", exit_code=1, duration=1.5,
                          raw_output="FAILED test.py::t")
        classified = classifier.classify(result)
        assert classified.duration == 1.5

    def test_preserves_raw_output(self):
        classifier = FeedbackClassifier()
        raw = "FAILED test.py::t"
        result = _make_fr(sensor_id="pytest", status="FAILED", exit_code=1, raw_output=raw)
        classified = classifier.classify(result)
        assert classified.raw_output_truncated == raw

    def test_preserves_summary(self):
        classifier = FeedbackClassifier()
        result = _make_fr(sensor_id="pytest", status="FAILED", exit_code=1,
                          summary="Exit code: 1", raw_output="FAILED test.py::t")
        classified = classifier.classify(result)
        assert classified.summary == "Exit code: 1"