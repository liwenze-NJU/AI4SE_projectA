from decimal import Decimal
from pathlib import Path

from codeguard.loop import AgentLoop
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.action import Action, ActionKind, LLMResponse
from codeguard.secret import SecretRedactor
from codeguard.tracer import Tracer
from codeguard.context import ContextBuilder
from codeguard.action import ActionParser
from codeguard.stop import StopPolicy
from codeguard.guardrail.engine import RuleEngine
from codeguard.guardrail.approval import ApprovalManager, FakeClock
from codeguard.guardrail.rules import (
    WorkspaceBoundaryRule,
    CredentialLeakRule,
    ModeRestrictionRule,
    UnregisteredToolRule,
    ToolRiskRule,
)
from codeguard.guardrail.normalizer import ActionNormalizer, SchemaValidator
from codeguard.feedback.classifier import FeedbackClassifier
from codeguard.feedback.verifier import ObjectiveVerifier
from codeguard.feedback.composite import CompositeSensorRunner
from codeguard.feedback.sensor import SensorRunner
from codeguard.feedback import SensorDefinition
from codeguard.tool.registry import ToolRegistry
from codeguard.tool.dispatcher import ToolDispatcher
from codeguard.tool import ToolDefinition
from codeguard.tool import file_tools, process_tool
from codeguard.events import EventSink, NullEventSink

import hashlib
import os
import shutil
import sys
import tempfile

# ---------------------------------------------------------------------------
# Tool and sensor configuration
# ---------------------------------------------------------------------------

# The trusted validation tools (run_tests / run_lint / run_typecheck) are
# structured wrappers around configuration-owned SensorDefinition objects.
# They never accept user-supplied program strings.  Only tools available in
# the current environment are registered, so composition never constructs a
# command that cannot resolve.
#
# `program` is the interpreter (prepended by SensorRunner), so `args` must
# NOT repeat sys.executable — SensorRunner executes [program, *args].


def _python_executable() -> str:
    """Resolve the Python interpreter for subprocess-based sensors.

    Priority: CODEGUARD_PYTHON env override (explicit operator choice) →
    the current interpreter when it is a real Python (development runs;
    the venv interpreter is the correct and pytest-capable choice) →
    external ``python`` on PATH (PyInstaller onefile builds, where
    sys.executable IS codeguard.exe — empirically verified:
    sys._base_executable equals the exe too, so ``codeguard.exe -m pytest``
    is never valid) → sys.executable fallback.
    The final fallback only fires under a frozen build with no external
    python and no override: the sensor then fails loudly (UNAVAILABLE/FAILED
    → final validation cannot pass) instead of pretending to succeed.
    """
    override = os.environ.get("CODEGUARD_PYTHON")
    if override:
        return override
    if not getattr(sys, "frozen", False):
        # Development / non-frozen runs: the current interpreter is a real
        # Python with the project dependencies installed (venv).
        return sys.executable
    external = shutil.which("python")
    if external:
        return external
    return sys.executable


_VALIDATION_TOOL_DEFS = {
    "run_tests": ("pytest", ["-m", "pytest", "-q"], 120),
    "run_lint": ("ruff", ["-m", "ruff", "check"], 120),
    "run_typecheck": ("mypy", ["-m", "mypy"], 120),
}


def _tool_with_schema(name, description, required, optional, category,
                      side_effect, default_risk, timeout_limit,
                      supported_modes):
    """Build a ToolDefinition with a complete JSON-schema parameters schema."""
    properties = {}
    for key, key_type in required.items():
        properties[key] = {"type": key_type}
    for key, key_type in optional.items():
        properties[key] = {"type": key_type}
    schema = {
        "type": "object",
        "properties": properties,
        "required": list(required.keys()),
    }
    return ToolDefinition(
        name=name,
        description=description,
        parameters_schema=schema,
        handler=lambda p: None,
        category=category,
        side_effect=side_effect,
        default_risk=default_risk,
        supported_modes=supported_modes,
        timeout_limit=timeout_limit,
    )


def _make_validation_tool_definition(name: str, sensor_name: str) -> ToolDefinition:
    """Structured wrapper around a trusted SensorDefinition.

    The handler ignores caller parameters entirely and runs the
    configuration-owned command; a user-supplied program string is never
    accepted for these trusted validation tools.
    """
    _, args, timeout = _VALIDATION_TOOL_DEFS[name]
    definition = SensorDefinition(
        name=sensor_name, program=_python_executable(), args=args,
        cwd=None, timeout=timeout, parser="generic", required=True,
    )

    def _handler(params: dict, workspace_root: str = "") -> dict:
        return _run_sensor_for_tool(definition, workspace_root)

    td = _tool_with_schema(
        name=name,
        description=f"Run {name} (configuration-owned validation)",
        required={},
        optional={},
        category="TEST",
        side_effect=True,
        default_risk="ALLOW",
        timeout_limit=timeout,
        supported_modes=["test", "demo", "local"],
    )
    td.handler = _handler
    return td


def _run_sensor_for_tool(definition: SensorDefinition, workspace_root: str) -> dict:
    """Execute a configuration-owned sensor and shape it as a tool result."""
    runner = SensorRunner(definition, cwd=workspace_root)
    result = runner.run()
    output = result.raw_output_truncated or result.summary or result.status
    if result.status == "PASSED":
        return {"status": "SUCCESS", "stdout": output, "exit_code": result.exit_code}
    return {"status": "FAILURE", "stdout": output, "exit_code": result.exit_code,
            "error_category": result.failure_category}


def _make_standard_tools() -> list[ToolDefinition]:
    """Build all standard tools with complete schemas and real handlers.

    Every tool carries the complete schema matching its real handler and
    declares the real per-tool risk (writes/patch/process -> REQUEST_APPROVAL).
    No legacy variant is kept: a single wiring exists for every mode.
    """
    # write_file: complete schema requires path + content
    write_required = ["path", "content"]
    write_props = {
        "path": {"type": "string"},
        "content": {"type": "string"},
        "sha256_fingerprint": {"type": "string"},
    }
    write_risk = "REQUEST_APPROVAL"

    # apply_patch: complete schema requires path + old_string + new_string
    patch_required = ["path", "old_string", "new_string"]
    patch_props = {
        "path": {"type": "string"},
        "old_string": {"type": "string"},
        "new_string": {"type": "string"},
    }
    patch_risk = "REQUEST_APPROVAL"

    # find_files / search_text: pattern required, optional base_dir
    find_required = ["pattern"]
    find_props = {"pattern": {"type": "string"}, "base_dir": {"type": "string"}}

    # run_process: program required; args/cwd/bounded timeout
    process_props = {
        "program": {"type": "string"},
        "args": {"type": "array", "items": {"type": "string"}},
        "cwd": {"type": "string"},
        "timeout": {"type": "integer", "minimum": 1, "maximum": 300},
    }
    process_required = ["program"]
    process_risk = "REQUEST_APPROVAL"

    tools = [
        ToolDefinition(
            name="read_file", description="Read a file",
            parameters_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=file_tools.read_file, category="FILE", side_effect=False,
            default_risk="ALLOW", supported_modes=["test", "demo", "local"],
            timeout_limit=30,
        ),
        ToolDefinition(
            name="write_file", description="Write a file",
            parameters_schema={
                "type": "object", "properties": write_props,
                "required": write_required,
            },
            handler=file_tools.write_file, category="FILE", side_effect=True,
            default_risk=write_risk, supported_modes=["test", "local"],
            timeout_limit=30,
        ),
        ToolDefinition(
            name="delete_file", description="Delete a file",
            parameters_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=file_tools.delete_file, category="FILE", side_effect=True,
            default_risk="REQUEST_APPROVAL", supported_modes=["test", "local"],
            timeout_limit=30,
        ),
        ToolDefinition(
            name="list_directory", description="List a directory",
            parameters_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=file_tools.list_directory, category="FILE", side_effect=False,
            default_risk="ALLOW", supported_modes=["test", "demo", "local"],
            timeout_limit=30,
        ),
        ToolDefinition(
            name="find_files", description="Find files by pattern",
            parameters_schema={
                "type": "object", "properties": find_props,
                "required": find_required,
            },
            handler=file_tools.find_files, category="FILE", side_effect=False,
            default_risk="ALLOW", supported_modes=["test", "demo", "local"],
            timeout_limit=30,
        ),
        ToolDefinition(
            name="search_text", description="Search text in files",
            parameters_schema={
                "type": "object", "properties": find_props,
                "required": find_required,
            },
            handler=file_tools.search_text, category="FILE", side_effect=False,
            default_risk="ALLOW", supported_modes=["test", "demo", "local"],
            timeout_limit=30,
        ),
        ToolDefinition(
            name="run_process", description="Run a process",
            parameters_schema={
                "type": "object", "properties": process_props,
                "required": process_required,
            },
            handler=process_tool.run_process, category="SHELL", side_effect=True,
            default_risk=process_risk, supported_modes=["test", "local"],
            timeout_limit=30,
        ),
    ]
    # Trusted validation tools: configuration-owned, never model-controlled.
    tools.append(_make_validation_tool_definition("run_tests", "pytest"))
    tools.append(_make_validation_tool_definition("run_lint", "ruff"))
    tools.append(_make_validation_tool_definition("run_typecheck", "mypy"))
    tools.append(ToolDefinition(
        name="apply_patch",
        description=(
            "Apply a patch: replace old_string with new_string in the "
            "target file. path = target file; old_string = text that must "
            "exist exactly in the file (no UTF-8 BOM needed); "
            "new_string = replacement text"
        ),
        parameters_schema={
            "type": "object", "properties": patch_props,
            "required": patch_required,
        },
        handler=file_tools.apply_patch, category="FILE", side_effect=True,
        default_risk=patch_risk, supported_modes=["test", "local"],
        timeout_limit=30,
    ))
    return tools


def _register_standard_tools(registry: ToolRegistry) -> None:
    """Register all standard tools with their parameter schemas."""
    for t in _make_standard_tools():
        try:
            registry.register(t)
        except ValueError:
            pass  # already registered by test setup


def _make_complete_response(summary: str = "done") -> LLMResponse:
    return LLMResponse(
        content='{"action": "complete", "summary": "' + summary + '"}',
        next_action=Action(kind=ActionKind.COMPLETE_REQUEST, summary=summary, raw=""),
        finish_reason="stop",
        model="mock",
        token_used=0,
        cost_used=Decimal("0"),
        raw_response="",
    )


class CompositionRoot:
    """Assembles the correct component variant based on mode.

    Modes:
    - test: ScriptedMockLLM + real tools against an isolated temporary
      workspace (caller-provided) or a per-instance sandbox (default)
    - demo: ScriptedMockLLM + mock boundaries (no real I/O, no network)
    - local: DeepSeekAdapter + KeyringCredentialStore + persistent memory
      (production)
    """

    def __init__(
        self,
        mode: str = "test",
        workspace_root: str | Path | None = None,
        event_sink: EventSink | None = None,
    ):
        self._mode = mode
        self._event_sink = event_sink or NullEventSink()
        self._temp_sandbox: Path | None = None
        self._memory_base: Path | None = None
        self._workspace_root = self._resolve_root(workspace_root)
        self.project_id = self._compute_project_id(self._workspace_root)

    # ------------------------------------------------------------------
    # Root / memory resolution
    # ------------------------------------------------------------------

    def _resolve_root(self, workspace_root: str | Path | None) -> Path:
        if workspace_root is not None:
            return Path(workspace_root).resolve()
        if self._mode == "test":
            # Default test mode: a per-instance sandbox so default-constructed
            # loops never touch the repository.  Callers that want to exercise
            # real handlers must pass an explicit temporary root.
            self._temp_sandbox = Path(tempfile.mkdtemp(prefix="codeguard-test-"))
            return self._temp_sandbox
        if self._mode == "demo":
            # Demo mode must not touch the real filesystem; a deterministic
            # in-process root keeps every mock boundary local.
            self._temp_sandbox = Path(tempfile.mkdtemp(prefix="codeguard-demo-"))
            return self._temp_sandbox
        # local mode: the current project root
        return Path.cwd().resolve()

    @staticmethod
    def _compute_project_id(workspace_root: Path) -> str:
        """SHA-256 of the normalized, case-normalized absolute path."""
        norm = str(workspace_root).casefold()
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    def _resolve_memory_base(self) -> Path:
        if self._memory_base is not None:
            return self._memory_base
        if self._mode in ("test", "demo"):
            # Deterministic caller-provided temporary memory base: a unique
            # sibling directory of the workspace, always inside the temp tree
            # and outside the workspace itself (tools cannot read it).
            base = self._workspace_root.parent / (
                ".memory-" + self._workspace_root.name
            )
        else:
            appdata = os.environ.get("LOCALAPPDATA")
            if not appdata:
                raise ValueError(
                    "LOCALAPPDATA is not set; cannot store structured memory. "
                    "Refusing to start a local session without a memory location."
                )
            base = Path(appdata) / "CodeGuard" / "memory"
            try:
                base.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise ValueError(
                    f"Cannot create memory directory {base}: {e}. "
                    "Refusing to start a local session without persistent memory."
                ) from e
        self._memory_base = base
        return base

    # ------------------------------------------------------------------
    # Loop creation
    # ------------------------------------------------------------------

    def create_loop(self, session_id: str) -> AgentLoop:
        if self._mode == "demo":
            return self._create_demo_loop(session_id)
        if self._mode == "local":
            return self._create_local_loop(session_id)
        return self._create_test_loop(session_id)

    def _create_test_loop(self, session_id: str) -> AgentLoop:
        llm = ScriptedMockLLM(responses=[_make_complete_response()])
        loop = AgentLoop(session_id=session_id, llm=llm)
        root = str(self._workspace_root)
        self._wire_common(loop, workspace_root=root)
        return loop

    def _create_demo_loop(self, session_id: str) -> AgentLoop:
        llm = ScriptedMockLLM(responses=[_make_complete_response("demo done")])
        loop = AgentLoop(session_id=session_id, llm=llm)
        self._wire_common(loop, workspace_root=str(self._workspace_root))
        engine = loop.rule_engine
        engine.add_rule("mode_restriction", ModeRestrictionRule(mode="demo").evaluate)
        loop.approval_manager = ApprovalManager(
            clock=FakeClock(), approval_timeout=15
        )
        return loop

    def _create_local_loop(self, session_id: str) -> AgentLoop:
        from codeguard.llm.deepseek import DeepSeekAdapter
        from codeguard.credentials.store import KeyringCredentialStore

        store = KeyringCredentialStore()
        api_key = store.get("deepseek")
        if not api_key:
            raise ValueError(
                "API key not configured. Run: codeguard key set --provider deepseek"
            )
        llm = DeepSeekAdapter(api_key=api_key)
        loop = AgentLoop(session_id=session_id, llm=llm)
        self._wire_common(loop, workspace_root=str(self._workspace_root))
        return loop

    # ------------------------------------------------------------------
    # Common wiring
    # ------------------------------------------------------------------

    def _wire_common(self, loop: AgentLoop, workspace_root: str) -> None:
        loop.project_id = self.project_id
        loop.secret_redactor = SecretRedactor()
        loop.tracer = Tracer(secret_redactor=loop.secret_redactor)
        loop.context_builder = ContextBuilder()
        loop.action_parser = ActionParser()
        loop.action_normalizer = ActionNormalizer(workspace_root=workspace_root)
        loop.schema_validator = SchemaValidator()
        loop.tool_registry = ToolRegistry()
        _register_standard_tools(loop.tool_registry)

        engine = RuleEngine()
        engine.add_rule(
            "workspace", WorkspaceBoundaryRule(workspace_root=workspace_root).evaluate
        )
        engine.add_rule("credential", CredentialLeakRule().evaluate)
        engine.add_rule(
            "unregistered", UnregisteredToolRule(loop.tool_registry).evaluate
        )
        engine.add_rule(
            "tool_risk", ToolRiskRule(loop.tool_registry).evaluate
        )
        if self._mode == "demo":
            engine.add_rule(
                "mode_restriction", ModeRestrictionRule(mode="demo").evaluate
            )
        loop.rule_engine = engine
        loop.approval_manager = ApprovalManager(approval_timeout=60)
        loop.stop_policy = StopPolicy(
            max_steps=50, max_llm_calls=100, no_progress_threshold=3
        )
        loop.feedback_classifier = FeedbackClassifier()

        # Memory: project-scoped, injected into the loop
        memory_base = self._resolve_memory_base()
        from codeguard.memory.store import JSONMemoryStore
        from codeguard.memory.retriever import MemoryRetriever
        loop.memory_store = JSONMemoryStore(base_dir=str(memory_base))
        loop.memory_retriever = MemoryRetriever(
            loop.memory_store, top_k=10, context_budget=2048
        )

        # Sensors: configuration-owned sensor definitions only.
        # Demo mode keeps a None sensor surface (no real subprocess at all);
        # test/local modes use the deterministic configured sensors.
        if self._mode == "demo":
            loop.sensor_runner = None
            loop.objective_verifier = ObjectiveVerifier(required_sensors=[])
        else:
            sensors = self._make_sensors(workspace_root)
            loop.sensor_runner = CompositeSensorRunner(sensors)
            loop.objective_verifier = ObjectiveVerifier(
                required_sensors=[s.definition.name for s in sensors
                                  if s.definition.required]
            )

        # Dispatcher: real handlers, guarded workspace root.
        # Demo mode keeps a None dispatcher surface (mock scenario helpers
        # inject their own MockToolDispatcher); no real handler is reachable.
        if self._mode == "demo":
            loop.tool_dispatcher = None
        else:
            loop.tool_dispatcher = ToolDispatcher(
                loop.tool_registry,
                workspace_root=workspace_root,
                secret_redactor=loop.secret_redactor,
            )

        # Event sink (Task 4 consumes it; store now for injection)
        loop.event_sink = self._event_sink

    def _make_sensors(self, workspace_root: str) -> list[SensorRunner]:
        """Deterministic configured sensors for the current mode."""
        if self._mode == "demo":
            return []
        if self._mode == "local":
            sensors = []
            for name, sensor_name in (
                ("run_tests", "pytest"),
                ("run_lint", "ruff"),
                ("run_typecheck", "mypy"),
            ):
                _, args, timeout = _VALIDATION_TOOL_DEFS[name]
                try:
                    import importlib.util
                    if name == "run_tests" or importlib.util.find_spec(sensor_name):
                        sensors.append(SensorRunner(
                            SensorDefinition(
                                name=sensor_name, program=_python_executable(),
                                args=args, cwd=workspace_root, timeout=timeout,
                                parser="generic", required=True,
                            ),
                            cwd=workspace_root,
                        ))
                except Exception:
                    continue
            return sensors
        # test mode: deterministic configured sensors (pytest only).
        # They run (so wiring is real) but are not required, so scripted
        # integration scenarios keep their COMPLETED semantics.
        _, args, timeout = _VALIDATION_TOOL_DEFS["run_tests"]
        return [SensorRunner(
            SensorDefinition(
                name="pytest", program=_python_executable(), args=args,
                cwd=workspace_root, timeout=timeout, parser="generic",
                required=False,
            ),
            cwd=workspace_root,
        )]
