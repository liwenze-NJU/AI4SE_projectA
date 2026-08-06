import hashlib
from codeguard.feedback import FeedbackResult
from codeguard.feedback.parsers import PytestParser, RuffParser, MypyParser, GenericParser


_PARSER_MAP = {
    "pytest": PytestParser(),
    "ruff": RuffParser(),
    "mypy": MypyParser(),
}

_GENERIC = GenericParser()


class FeedbackClassifier:
    """Three-layer classification: execution status -> failure category -> diagnostics.

    Layer 1 (status): PASSED / FAILED / TIMEOUT / UNAVAILABLE / EXECUTION_ERROR
    Layer 2 (failure_category): TEST_FAILURE / LINT_ERROR / TYPE_ERROR / UNKNOWN_FAILURE / ...
    Layer 3 (diagnostics): structured list from the appropriate parser
    """

    def classify(self, result: FeedbackResult) -> FeedbackResult:
        if result.status == "PASSED":
            return result

        if result.status in ("TIMEOUT", "UNAVAILABLE", "EXECUTION_ERROR"):
            result.failure_category = result.status
            return result

        if result.status == "FAILED":
            parser = _PARSER_MAP.get(result.sensor_id, _GENERIC)
            try:
                parsed = parser.parse(result.raw_output_truncated)
            except Exception:
                parsed = {"failure_category": "UNKNOWN_FAILURE", "diagnostics": [], "fingerprint": ""}

            category = parsed.get("failure_category") or "UNKNOWN_FAILURE"
            result.failure_category = category
            result.diagnostics = parsed.get("diagnostics", [])

            fp_data = f"{result.sensor_id}:{category}:{parsed.get('fingerprint', '')}"
            result.failure_fingerprint = hashlib.sha256(fp_data.encode()).hexdigest()

        return result