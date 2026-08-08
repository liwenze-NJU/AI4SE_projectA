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


def format_feedback_for_llm(results: list[FeedbackResult]) -> str:
    """Format feedback results as structured LLM context block.

    Sensor output is treated as untrusted evidence inside
    [Sensor Evidence] / [End Evidence] boundaries.
    Diagnostics limited to 5 entries, raw output to 200 chars.
    Overall output capped at 5000 chars.
    """
    if not results:
        return "\n[Feedback]\nNo feedback results available."

    MAX_DIAGNOSTICS = 5
    MAX_RAW_CHARS = 200
    MAX_TOTAL = 5000

    parts = ["\n[Feedback]"]
    for r in results:
        parts.append(f"Sensor: {r.sensor_id}")
        parts.append(f"Status: {r.status}")
        if r.failure_category:
            parts.append(f"Category: {r.failure_category}")
        if r.failure_fingerprint:
            parts.append(f"Fingerprint: {r.failure_fingerprint}")
        if r.summary:
            parts.append(f"Summary: {r.summary}")
        if r.diagnostics:
            parts.append("Diagnostics:")
            for d in r.diagnostics[:MAX_DIAGNOSTICS]:
                file = d.get("file", "?")
                line = d.get("line", "?")
                msg = d.get("message", "")
                parts.append(f"  - {file}:{line} {msg}")
        if r.raw_output_truncated:
            parts.append("---[Sensor Evidence]---")
            parts.append(r.raw_output_truncated[:MAX_RAW_CHARS])
            parts.append("---[End Evidence]---")
        parts.append("")

    output = "\n".join(parts)
    if len(output) > MAX_TOTAL:
        output = output[:MAX_TOTAL]
    return output