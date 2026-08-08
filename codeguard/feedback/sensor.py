import os
import subprocess
import time
from codeguard.feedback import SensorDefinition, FeedbackResult


class SensorRunner:
    """Runs a single sensor command and returns structured FeedbackResult.

    Executes via subprocess with shell=False (program + args list).
    Captures stdout and stderr, enforces output_limit, measures real
    duration, and handles timeout/missing-program gracefully.
    """

    def __init__(self, definition: SensorDefinition, cwd: str = ""):
        self._definition = definition
        self._cwd = cwd

    def run(self) -> FeedbackResult:
        start = time.perf_counter()
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        try:
            proc = subprocess.run(
                [self._definition.program, *self._definition.args],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=self._definition.timeout,
                cwd=self._definition.cwd or self._cwd,
                env=env,
            )
            duration = time.perf_counter() - start
            combined = self._combine_output(proc.stdout, proc.stderr)
            combined = self._truncate(combined, self._definition.output_limit)

            passed = proc.returncode in self._definition.allowed_exit_codes
            status = "PASSED" if passed else "FAILED"
            return FeedbackResult(
                sensor_id=self._definition.name,
                program=self._definition.program,
                args=list(self._definition.args),
                status=status,
                failure_category=None if passed else "EXECUTION_ERROR",
                exit_code=proc.returncode,
                failure_fingerprint=None,
                validation_type="INTERMEDIATE",
                summary=f"Exit code: {proc.returncode}",
                diagnostics=[],
                duration=duration,
                retryable=not passed,
                raw_output_truncated=combined,
            )
        except subprocess.TimeoutExpired:
            duration = time.perf_counter() - start
            return FeedbackResult(
                sensor_id=self._definition.name,
                program=self._definition.program,
                args=list(self._definition.args),
                status="TIMEOUT",
                failure_category="TIMEOUT",
                exit_code=None,
                failure_fingerprint=None,
                validation_type="INTERMEDIATE",
                summary="Timed out",
                diagnostics=[],
                duration=duration,
                retryable=True,
                raw_output_truncated="",
            )
        except FileNotFoundError:
            duration = time.perf_counter() - start
            return FeedbackResult(
                sensor_id=self._definition.name,
                program=self._definition.program,
                args=list(self._definition.args),
                status="UNAVAILABLE",
                failure_category="TOOL_NOT_FOUND",
                exit_code=None,
                failure_fingerprint=None,
                validation_type="INTERMEDIATE",
                summary="Program not found",
                diagnostics=[],
                duration=duration,
                retryable=False,
                raw_output_truncated="",
            )

    @staticmethod
    def _combine_output(stdout: str, stderr: str) -> str:
        parts = []
        if stdout:
            parts.append("[stdout]\n" + stdout)
        if stderr:
            parts.append("[stderr]\n" + stderr)
        return "\n".join(parts)

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit]