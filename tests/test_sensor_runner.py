import sys
import pytest
from pathlib import Path
from codeguard.feedback.sensor import SensorRunner
from codeguard.feedback import SensorDefinition, FeedbackResult


@pytest.fixture
def tmp_cwd(tmp_path):
    return str(tmp_path)


# ── Helper ───────────────────────────────────────────────────────────

def _sd(name="test", program=None, args=None, timeout=10, allowed_exit_codes=None,
        output_limit=4096, required=True):
    return SensorDefinition(
        name=name,
        program=program or sys.executable,
        args=args or ["-c", "exit(0)"],
        timeout=timeout,
        allowed_exit_codes=allowed_exit_codes if allowed_exit_codes is not None else {0},
        output_limit=output_limit,
        required=required,
    )


# ── PASSED / FAILED ──────────────────────────────────────────────────

class TestBasicExecution:
    def test_passed_on_allowed_exit_code(self, tmp_cwd):
        sd = _sd(args=["-c", "exit(0)"])
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert result.status == "PASSED"
        assert result.exit_code == 0

    def test_failed_on_non_allowed_exit_code(self, tmp_cwd):
        sd = _sd(args=["-c", "exit(1)"], allowed_exit_codes={0})
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert result.status == "FAILED"
        assert result.exit_code == 1

    def test_non_zero_allowed_exit_code(self, tmp_cwd):
        sd = _sd(args=["-c", "exit(3)"], allowed_exit_codes={0, 3})
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert result.status == "PASSED"
        assert result.exit_code == 3

    def test_returns_feedback_result_type(self, tmp_cwd):
        sd = _sd(args=["-c", "exit(0)"])
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert isinstance(result, FeedbackResult)


# ── Output capture ───────────────────────────────────────────────────

class TestOutputCapture:
    def test_captures_stdout(self, tmp_cwd):
        sd = _sd(args=["-c", "print('hello')"])
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert "hello" in result.raw_output_truncated

    def test_captures_stderr(self, tmp_cwd):
        sd = _sd(args=["-c", "import sys; sys.stderr.write('err msg')"])
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert "err msg" in result.raw_output_truncated

    def test_both_stdout_and_stderr_in_output(self, tmp_cwd):
        sd = _sd(args=["-c", "import sys; print('out'); sys.stderr.write('err')"])
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert "out" in result.raw_output_truncated
        assert "err" in result.raw_output_truncated

    def test_output_truncation(self, tmp_cwd):
        sd = _sd(args=["-c", "print('x' * 5000)"], output_limit=100)
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert len(result.raw_output_truncated) <= 100


# ── Timeout ──────────────────────────────────────────────────────────

class TestTimeout:
    def test_timeout_returns_timeout_status(self, tmp_cwd):
        sd = _sd(args=["-c", "import time; time.sleep(30)"], timeout=1)
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert result.status == "TIMEOUT"

    def test_timeout_return_exit_code_none(self, tmp_cwd):
        sd = _sd(args=["-c", "import time; time.sleep(30)"], timeout=1)
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert result.exit_code is None


# ── Program not found ────────────────────────────────────────────────

class TestProgramNotFound:
    def test_unavailable_on_missing_program(self, tmp_cwd):
        sd = SensorDefinition(
            name="ghost", program="nonexistent_program_xyz_12345", args=[],
            timeout=10, allowed_exit_codes={0}, output_limit=4096,
        )
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert result.status == "UNAVAILABLE"


# ── CWD ──────────────────────────────────────────────────────────────

class TestCWD:
    def test_runs_in_specified_cwd(self, tmp_cwd):
        sd = _sd(args=["-c", "import os; print(os.getcwd())"])
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert tmp_cwd in result.raw_output_truncated

    def test_uses_sensor_definition_cwd(self, tmp_path):
        sd = SensorDefinition(
            name="pwd", program=sys.executable, args=["-c", "import os; print(os.getcwd())"],
            timeout=10, allowed_exit_codes={0}, output_limit=4096, cwd=str(tmp_path),
        )
        result = SensorRunner(sd, cwd="/some/other/path").run()
        assert str(tmp_path) in result.raw_output_truncated


# ── Args integrity ───────────────────────────────────────────────────

class TestArgsIntegrity:
    def test_args_not_interpreted_by_shell(self, tmp_cwd):
        # Pass semicolon in args — should be literal, not shell metachar
        sd = _sd(args=["-c", "import sys; print(sys.argv[1])", ";echo", "injected"])
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        # The child prints argv[1] which is ";echo" — no shell injection
        assert result.status == "PASSED"

    def test_args_with_spaces_preserved(self, tmp_cwd):
        sd = _sd(args=["-c", "import sys; print(repr(sys.argv[1:]))", "hello world", "--flag"])
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert "hello world" in result.raw_output_truncated
        assert "--flag" in result.raw_output_truncated


# ── Unicode / decode safety ──────────────────────────────────────────

class TestUnicodeSafety:
    def test_unicode_output(self, tmp_cwd):
        sd = _sd(args=["-c", "print('中文测试')"])
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert "中文测试" in result.raw_output_truncated

    def test_stderr_unicode(self, tmp_cwd):
        sd = _sd(args=["-c", "import sys; sys.stderr.write('错误信息')"])
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert "错误信息" in result.raw_output_truncated

    def test_unicode_with_cp1252_parent_env(self, tmp_cwd, monkeypatch):
        monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
        monkeypatch.delenv("PYTHONUTF8", raising=False)
        sd = _sd(args=["-c", "print('中文测试')"])
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert "中文测试" in result.raw_output_truncated


# ── Duration ─────────────────────────────────────────────────────────

class TestDuration:
    def test_duration_is_non_negative(self, tmp_cwd):
        sd = _sd(args=["-c", "exit(0)"])
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert result.duration >= 0.0

    def test_duration_measured_for_timeout(self, tmp_cwd):
        sd = _sd(args=["-c", "import time; time.sleep(30)"], timeout=1)
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert result.duration >= 0.0


# ── Failure is still structured ──────────────────────────────────────

class TestFailureReturnsStructured:
    def test_failed_result_has_sensor_id(self, tmp_cwd):
        sd = _sd(args=["-c", "exit(2)"], allowed_exit_codes={0})
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert result.sensor_id == "test"

    def test_failed_result_has_program_and_args(self, tmp_cwd):
        sd = _sd(args=["-c", "exit(2)"], allowed_exit_codes={0})
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert result.program == sys.executable
        assert "-c" in result.args

    def test_timeout_result_is_structured(self, tmp_cwd):
        sd = _sd(args=["-c", "import time; time.sleep(30)"], timeout=1)
        result = SensorRunner(sd, cwd=tmp_cwd).run()
        assert isinstance(result, FeedbackResult)
        assert result.sensor_id == "test"