"""Direct production-composition wiring tests (plan Task 3).

These tests drive the real handlers, the real dispatcher, and the real
sensor composition through CompositionRoot.  They always pass an explicit
temporary workspace_root so tool execution stays inside tmp_path.
"""

import sys
from pathlib import Path

import pytest

from codeguard.action import Action, ActionKind
from codeguard.composition import CompositionRoot
from codeguard.credentials.store import KeyringCredentialStore
from codeguard.feedback import FeedbackResult, SensorDefinition
from codeguard.guardrail import GuardrailDecision
from codeguard.tool.dispatcher import ToolDispatcher


def test_test_composition_has_dispatcher_and_sensors(tmp_path):
    loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
    assert isinstance(loop.tool_dispatcher, ToolDispatcher)
    assert loop.sensor_runner is not None


def test_read_file_handler_reads_temporary_workspace(tmp_path):
    (tmp_path / "hello.txt").write_text("hello", encoding="utf-8")
    loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
    action = Action(ActionKind.TOOL_CALL, "read_file", {"path": "hello.txt"})
    result = loop.tool_dispatcher.dispatch(action)
    assert result.status == "SUCCESS"
    assert "hello" in result.output_summary


def test_required_sensors_are_not_an_empty_success_in_local_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(KeyringCredentialStore, "get", lambda self, provider: "sk-test")
    loop = CompositionRoot(mode="local", workspace_root=tmp_path).create_loop("s1")
    assert loop.sensor_runner is not None
    assert loop.objective_verifier.required_sensors


def test_write_file_declared_risk_requests_approval(tmp_path):
    loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
    action = loop.action_normalizer.normalize(
        Action(ActionKind.TOOL_CALL, "write_file", {"path": "a.py", "content": "x = 1"})
    )
    result = loop.rule_engine.evaluate(action)
    assert result.decision is GuardrailDecision.REQUEST_APPROVAL


# ---------------------------------------------------------------------------
# CompositeSensorRunner (plan Step 3)
# ---------------------------------------------------------------------------

class TestCompositeSensorRunner:
    def test_run_all_returns_one_result_per_runner(self, tmp_path):
        from codeguard.feedback.composite import CompositeSensorRunner
        from codeguard.feedback.sensor import SensorRunner

        cwd = str(tmp_path)
        runners = [
            SensorRunner(SensorDefinition(name="a", program=sys.executable,
                                          args=["-c", "exit(0)"], timeout=10),
                         cwd=cwd),
            SensorRunner(SensorDefinition(name="b", program=sys.executable,
                                          args=["-c", "exit(0)"], timeout=10),
                         cwd=cwd),
        ]
        composite = CompositeSensorRunner(runners)
        results = composite.run_all()
        assert len(results) == 2
        assert all(isinstance(r, FeedbackResult) for r in results)
        assert [r.sensor_id for r in results] == ["a", "b"]

    def test_rejects_empty_runner_list(self):
        from codeguard.feedback.composite import CompositeSensorRunner
        with pytest.raises(ValueError, match="At least one sensor runner"):
            CompositeSensorRunner([])


# ---------------------------------------------------------------------------
# Dispatcher contract (plan Step 5)
# ---------------------------------------------------------------------------

class TestDispatcherContract:
    def test_dispatch_accepts_normalized_action(self, tmp_path):
        (tmp_path / "n.txt").write_text("normalized", encoding="utf-8")
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        raw = Action(ActionKind.TOOL_CALL, "read_file", {"path": "n.txt"})
        normalized = loop.action_normalizer.normalize(raw)
        result = loop.tool_dispatcher.dispatch(normalized)
        assert result.status == "SUCCESS"
        assert "normalized" in result.output_summary

    def test_unknown_tool_raises_key_error(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        action = Action(ActionKind.TOOL_CALL, "no_such_tool", {})
        with pytest.raises(KeyError):
            loop.tool_dispatcher.dispatch(action)

    def test_handler_exception_never_becomes_success(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        action = Action(ActionKind.TOOL_CALL, "read_file", {"path": "missing.txt"})
        result = loop.tool_dispatcher.dispatch(action)
        assert result.status != "SUCCESS"
        assert result.status == "FAILURE"

    def test_redacts_secrets_from_tool_output(self, tmp_path):
        (tmp_path / "creds.txt").write_text("api_key = sk-1111222233334444", encoding="utf-8")
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        action = Action(ActionKind.TOOL_CALL, "read_file", {"path": "creds.txt"})
        result = loop.tool_dispatcher.dispatch(action)
        assert "sk-1111222233334444" not in result.output_summary


# ---------------------------------------------------------------------------
# Registered tool schemas and handler wiring (plan Step 4)
# ---------------------------------------------------------------------------

class TestRegisteredToolSchemas:
    def test_write_file_schema_requires_content(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        td = loop.tool_registry.lookup("write_file")
        assert "content" in td.parameters_schema.get("required", [])
        assert "path" in td.parameters_schema.get("required", [])

    def test_apply_patch_schema_requires_old_and_new_string(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        td = loop.tool_registry.lookup("apply_patch")
        required = set(td.parameters_schema.get("required", []))
        assert {"path", "old_string", "new_string"} <= required

    def test_run_process_schema_has_program_and_bounded_timeout(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        td = loop.tool_registry.lookup("run_process")
        props = td.parameters_schema.get("properties", {})
        assert "program" in td.parameters_schema.get("required", [])
        assert "args" in props
        assert "timeout" in props
        assert props["timeout"]["type"] == "integer"

    def test_trusted_validation_tools_do_not_accept_user_program(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        for name in ("run_tests", "run_lint", "run_typecheck"):
            td = loop.tool_registry.lookup(name)
            props = td.parameters_schema.get("properties", {})
            assert "program" not in props, f"{name} must not accept a program string"
            assert not td.parameters_schema.get("required", []), (
                f"{name} must take no required parameters"
            )

    def test_real_handler_wired_for_each_standard_tool(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        for name in ("read_file", "list_directory", "find_files", "search_text",
                     "write_file", "apply_patch", "delete_file", "run_process",
                     "run_tests", "run_lint", "run_typecheck"):
            td = loop.tool_registry.lookup(name)
            assert td.handler is not None, f"{name} must have a real handler"
            import codeguard.tool.file_tools as ft
            import codeguard.tool.process_tool as pt
            known = {
                "read_file": ft.read_file, "list_directory": ft.list_directory,
                "find_files": ft.find_files, "search_text": ft.search_text,
                "write_file": ft.write_file, "apply_patch": ft.apply_patch,
                "delete_file": ft.delete_file, "run_process": pt.run_process,
            }
            if name in known:
                assert td.handler is known[name], f"{name} must be the real handler"

    def test_delete_file_risk_is_request_approval(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        action = loop.action_normalizer.normalize(
            Action(ActionKind.TOOL_CALL, "delete_file", {"path": "a.py"})
        )
        result = loop.rule_engine.evaluate(action)
        assert result.decision is GuardrailDecision.REQUEST_APPROVAL

    def test_apply_patch_declared_risk_requests_approval(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        action = loop.action_normalizer.normalize(
            Action(ActionKind.TOOL_CALL, "apply_patch",
                   {"path": "a.py", "old_string": "x", "new_string": "y"})
        )
        result = loop.rule_engine.evaluate(action)
        assert result.decision is GuardrailDecision.REQUEST_APPROVAL

    def test_run_process_declared_risk_requests_approval(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        action = loop.action_normalizer.normalize(
            Action(ActionKind.TOOL_CALL, "run_process",
                   {"program": sys.executable, "args": ["-c", "pass"]})
        )
        result = loop.rule_engine.evaluate(action)
        assert result.decision is GuardrailDecision.REQUEST_APPROVAL


# ---------------------------------------------------------------------------
# Sensor composition (plan Steps 3 + 6)
# ---------------------------------------------------------------------------

class TestComposedSensors:
    def test_test_mode_sensor_runner_runs_deterministic_sensors(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        results = loop.sensor_runner.run_all()
        assert results
        for r in results:
            assert isinstance(r, FeedbackResult)
            assert r.validation_type == "INTERMEDIATE"

    def test_test_mode_required_sensors_empty(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        assert loop.objective_verifier.required_sensors == []

    def test_local_mode_pytest_sensor_is_configured(self, tmp_path, monkeypatch):
        monkeypatch.setattr(KeyringCredentialStore, "get", lambda self, provider: "sk-test")
        loop = CompositionRoot(mode="local", workspace_root=tmp_path).create_loop("s1")
        assert "pytest" in loop.objective_verifier.required_sensors
        names = [r.definition.name for r in loop.sensor_runner._runners]
        assert "pytest" in names

    def test_local_mode_sensor_runs_with_workspace_cwd(self, tmp_path, monkeypatch):
        monkeypatch.setattr(KeyringCredentialStore, "get", lambda self, provider: "sk-test")
        loop = CompositionRoot(mode="local", workspace_root=tmp_path).create_loop("s1")
        results = loop.sensor_runner.run_all()
        # pytest with -q on an empty dir fails but must produce a structured result
        assert any(r.sensor_id == "pytest" for r in results)
        for r in results:
            assert r.status in ("PASSED", "FAILED", "TIMEOUT", "UNAVAILABLE")

    def test_sensor_command_is_not_duplicated_interpreter(self, tmp_path, monkeypatch):
        """Regression: sensor args must not repeat the interpreter (program
        is prepended by SensorRunner), otherwise every validation tool
        fails.  The program comes from the resolver (T8-FIX2 P3)."""
        import codeguard.composition as comp
        monkeypatch.setattr(comp, "_python_executable",
                            lambda: "C:/resolved/python.exe")
        monkeypatch.setattr(KeyringCredentialStore, "get", lambda self, provider: "sk-test")
        loop = CompositionRoot(mode="local", workspace_root=tmp_path).create_loop("s1")
        for r in loop.sensor_runner._runners:
            if r.definition.name == "pytest":
                assert r.definition.program == "C:/resolved/python.exe"
                assert "C:/resolved/python.exe" not in r.definition.args, (
                    f"args must not duplicate interpreter: {r.definition.args}"
                )
                assert r.definition.args[:2] == ["-m", "pytest"], r.definition.args

    def test_pytest_sensor_can_pass_with_real_suite(self, tmp_path, monkeypatch):
        """A real passing pytest suite must yield a PASSED sensor result."""
        (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n",
                                             encoding="utf-8")
        monkeypatch.setattr(KeyringCredentialStore, "get", lambda self, provider: "sk-test")
        loop = CompositionRoot(mode="local", workspace_root=tmp_path).create_loop("s1")
        results = loop.sensor_runner.run_all()
        pytest_result = next(r for r in results if r.sensor_id == "pytest")
        assert pytest_result.status == "PASSED", pytest_result.raw_output_truncated


# ---------------------------------------------------------------------------
# T8-FIX2 P3 — frozen-interpreter resolver (env → external python → fallback)
# ---------------------------------------------------------------------------

class TestPythonExecutableResolver:
    """T8-FIX2 P3: under a PyInstaller onefile build sys.executable IS the
    frozen exe (empirically verified: sys._base_executable equals the exe
    too), so an external interpreter is required for ``python -m pytest``
    sensors.  Priority: CODEGUARD_PYTHON env override → current interpreter
    when not frozen (dev venv) → external ``python`` on PATH (frozen) →
    sys.executable fallback (fail-closed when frozen)."""

    def test_env_override_wins(self, monkeypatch):
        """CODEGUARD_PYTHON is an explicit operator choice and must win."""
        import codeguard.composition as comp
        monkeypatch.setenv("CODEGUARD_PYTHON", "C:/custom/python.exe")
        monkeypatch.setattr(comp.shutil, "which",
                            lambda name: "C:/path/python.exe")
        monkeypatch.setattr(comp.sys, "executable", "C:/frozen/codeguard.exe",
                            raising=False)
        assert comp._python_executable() == "C:/custom/python.exe"

    def test_non_frozen_uses_current_interpreter(self, monkeypatch):
        """Development runs: the current interpreter (venv) is a real,
        pytest-capable Python and must win over any PATH python."""
        import codeguard.composition as comp
        monkeypatch.delenv("CODEGUARD_PYTHON", raising=False)
        monkeypatch.setattr(comp.sys, "frozen", False, raising=False)
        monkeypatch.setattr(comp.shutil, "which",
                            lambda name: "C:/python/python.exe")
        monkeypatch.setattr(comp.sys, "executable", "C:/venv/python.exe",
                            raising=False)
        assert comp._python_executable() == "C:/venv/python.exe"

    def test_frozen_prefers_external_python(self, monkeypatch):
        """Frozen onefile: sys.executable IS codeguard.exe, so an external
        python on PATH must win over the frozen exe."""
        import codeguard.composition as comp
        monkeypatch.delenv("CODEGUARD_PYTHON", raising=False)
        monkeypatch.setattr(comp.sys, "frozen", True, raising=False)
        monkeypatch.setattr(comp.shutil, "which",
                            lambda name: "C:/python/python.exe")
        monkeypatch.setattr(comp.sys, "executable", "C:/frozen/codeguard.exe",
                            raising=False)
        assert comp._python_executable() == "C:/python/python.exe"

    def test_frozen_falls_back_to_executable_fail_closed(self, monkeypatch):
        """Frozen with no external python and no override: fail closed with
        sys.executable so the sensor reports the failure (UNAVAILABLE/FAILED
        → final validation cannot pass) instead of pretending to pass."""
        import codeguard.composition as comp
        monkeypatch.delenv("CODEGUARD_PYTHON", raising=False)
        monkeypatch.setattr(comp.sys, "frozen", True, raising=False)
        monkeypatch.setattr(comp.shutil, "which", lambda name: None)
        monkeypatch.setattr(comp.sys, "executable", "C:/frozen/codeguard.exe",
                            raising=False)
        assert comp._python_executable() == "C:/frozen/codeguard.exe"

    def test_wired_local_loop_pytest_sensor_uses_resolver_program(
            self, tmp_path, monkeypatch):
        """The wired local-mode loop's pytest sensor must use the resolver
        value as program, keeping structured program+args and
        configuration-owned args."""

        def fake_resolver():
            return "C:/resolved/python.exe"

        import codeguard.composition as comp
        monkeypatch.setattr(comp, "_python_executable", fake_resolver)
        monkeypatch.setattr(KeyringCredentialStore, "get", lambda self, provider: "sk-test")
        loop = CompositionRoot(mode="local", workspace_root=tmp_path).create_loop("s1")
        pytest_runner = next(
            r for r in loop.sensor_runner._runners if r.definition.name == "pytest"
        )
        assert pytest_runner.definition.program == "C:/resolved/python.exe"
        assert pytest_runner.definition.args[:2] == ["-m", "pytest"]

    def test_validation_tool_definition_uses_resolver_program(self, monkeypatch):
        """The run_tests tool handler's sensor definition must use the
        resolver value as program (frozen exe must not run pytest as
        `codeguard.exe -m pytest`)."""
        import codeguard.composition as comp

        def fake_resolver():
            return "C:/resolved/python.exe"

        monkeypatch.setattr(comp, "_python_executable", fake_resolver)
        td = comp._make_validation_tool_definition("run_tests", "pytest")
        handler_definition = td.handler.__closure__[0].cell_contents
        assert handler_definition.program == "C:/resolved/python.exe"


# ---------------------------------------------------------------------------
# Memory wiring (plan Step 6)
# ---------------------------------------------------------------------------

class TestMemoryWiring:
    def test_loop_has_memory_retriever(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        assert loop.memory_retriever is not None

    def test_test_mode_memory_base_is_under_tmp(self, tmp_path):
        loop = CompositionRoot(mode="test", workspace_root=tmp_path).create_loop("s1")
        base = Path(loop.memory_store._base)
        # Unique sibling dir inside the tmp tree, outside the workspace
        assert base.parent == tmp_path.parent
        assert base.name == f".memory-{tmp_path.name}"

    def test_local_mode_memory_below_localappdata(self, tmp_path, monkeypatch):
        monkeypatch.setattr(KeyringCredentialStore, "get", lambda self, provider: "sk-test")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
        loop = CompositionRoot(mode="local", workspace_root=tmp_path).create_loop("s1")
        base = Path(loop.memory_store._base)
        expected = tmp_path / "AppData" / "Local" / "CodeGuard" / "memory"
        assert str(base).startswith(str(expected))

    def test_local_mode_fails_closed_without_localappdata(self, tmp_path, monkeypatch):
        monkeypatch.setattr(KeyringCredentialStore, "get", lambda self, provider: "sk-test")
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        with pytest.raises(ValueError, match="LOCALAPPDATA"):
            CompositionRoot(mode="local", workspace_root=tmp_path).create_loop("s1")

    def test_project_id_derived_from_workspace_path(self, tmp_path):
        import hashlib
        root = CompositionRoot(mode="test", workspace_root=tmp_path)
        loop = root.create_loop("s1")
        # SHA-256 of the normalized, case-normalized absolute path
        norm = str(Path(tmp_path).resolve()).casefold()
        expected = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        assert root.project_id == expected
        # Deterministic: same workspace yields the same project_id
        root2 = CompositionRoot(mode="test", workspace_root=tmp_path)
        loop2 = root2.create_loop("s2")
        assert root2.project_id == root.project_id
        # Retrieval path exists and returns ACTIVE records only
        from codeguard.memory.models import MemoryRecord, MemoryType, MemoryStatus, TrustLevel
        from datetime import datetime
        store = loop.memory_store
        store.save(MemoryRecord(
            id="m1", project_id=root.project_id, type=MemoryType.PROJECT_CONVENTION,
            content="record", tags=[], keywords=[], source="user",
            trust_level=TrustLevel.USER_APPROVED, status=MemoryStatus.ACTIVE,
            created_at=datetime.now(), updated_at=datetime.now(), session_id="s1",
        ))
        records = loop.memory_retriever.retrieve(project_id=root.project_id)
        assert len(records) == 1
        assert records[0].id == "m1"
