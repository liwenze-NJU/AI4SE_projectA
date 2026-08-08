"""Phase 14 SPEC compliance tests — governance pipeline, recoverable semantics,
approval re-validation, and FINAL_VALIDATION.

These tests verify the strict governance pipeline defined in SPEC §3.2:
  Action → ToolRegistry.lookup → SchemaValidator → ActionNormalizer
  → NormalizedAction → RuleEngine → PriorityMerger → GuardrailResult

They complement the Phase 14 scenario tests in test_integration_guardrail_feedback.py
by adding explicit assertions on the governance pipeline steps.
"""

from decimal import Decimal
from datetime import datetime

import pytest

from codeguard.action import Action, ActionKind, LLMResponse, NormalizedAction
from codeguard.composition import CompositionRoot
from codeguard.feedback import FeedbackResult
from codeguard.guardrail import GuardrailDecision, GuardrailResult
from codeguard.guardrail.approval import ApprovalManager, ApprovalStatus, FakeClock
from codeguard.guardrail.engine import RuleEngine
from codeguard.guardrail.normalizer import ActionNormalizer, SchemaValidator
from codeguard.guardrail.rules import WorkspaceBoundaryRule
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.state import AgentState
from codeguard.stop import StopPolicy


def _make_response(action: Action, finish_reason: str = "stop") -> LLMResponse:
    return LLMResponse(
        content="mock",
        next_action=action,
        finish_reason=finish_reason,
        model="mock",
        token_used=0,
        cost_used=Decimal("0"),
        raw_response="",
    )


# ---------------------------------------------------------------------------
# Fix 1: Strict governance pipeline
# ---------------------------------------------------------------------------

class TestStrictGovernancePipeline:
    """RuleEngine and built-in rules must ONLY accept NormalizedAction."""

    def test_rule_engine_rejects_raw_action(self):
        """RuleEngine.evaluate() must raise TypeError when given raw Action."""
        engine = RuleEngine()
        engine.add_rule(
            "workspace",
            WorkspaceBoundaryRule(workspace_root="/home/user/project").evaluate,
        )
        raw_action = Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="delete_file",
            parameters={"path": "/etc/passwd"},
        )
        with pytest.raises(TypeError):
            engine.evaluate(raw_action)

    def test_workspace_boundary_rule_rejects_raw_action(self):
        """Built-in rules must raise TypeError when given raw Action."""
        rule = WorkspaceBoundaryRule(workspace_root="/home/user/project")
        raw_action = Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="delete_file",
            parameters={"path": "/etc/passwd"},
        )
        with pytest.raises(TypeError):
            rule.evaluate(raw_action)

    def test_action_normalizer_produces_normalized_action(self):
        """ActionNormalizer produces a proper NormalizedAction with fingerprint."""
        normalizer = ActionNormalizer(workspace_root="/home/user/project")
        action = Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="read_file",
            parameters={"path": "src/main.py"},
        )
        na = normalizer.normalize(action)
        assert isinstance(na, NormalizedAction)
        assert na.tool_name == "read_file"
        assert na.action_fingerprint != ""
        # Path is resolved (may include drive letter on Windows)
        assert "src" in na.normalized_parameters["path"]
        assert "main.py" in na.normalized_parameters["path"]

    def test_normalizer_resolves_relative_paths(self):
        """Relative paths are resolved against workspace_root."""
        normalizer = ActionNormalizer(workspace_root="/home/user/project")
        action = Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="read_file",
            parameters={"path": "src/main.py"},
        )
        na = normalizer.normalize(action)
        resolved = na.normalized_parameters["path"]
        # The resolved path should contain the workspace root components
        assert "home" in resolved
        assert "user" in resolved
        assert "project" in resolved

    def test_guardrail_result_has_immutable_normalized_action(self):
        """GuardrailResult.normalized_action must be a NormalizedAction."""
        normalizer = ActionNormalizer(workspace_root="/tmp")
        na = normalizer.normalize(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="read_file",
            parameters={"path": "test.txt"},
        ))
        engine = RuleEngine()
        engine.add_rule("allow_all", lambda a: {"decision": "ALLOW", "rule_id": "a", "reason_codes": []})
        result = engine.evaluate(na)
        assert isinstance(result.normalized_action, NormalizedAction)
        # NormalizedAction is frozen (immutable)
        with pytest.raises(Exception):
            result.normalized_action.action_fingerprint = "hacked"


# ---------------------------------------------------------------------------
# Fix 2: BLOCK recoverable semantics
# ---------------------------------------------------------------------------

class TestBlockRecoverableSemantics:
    """recoverable must be determined by rule results, not hardcoded."""

    def test_rule_exception_is_non_recoverable(self):
        """Rule that raises an exception → non-recoverable BLOCK."""
        engine = RuleEngine()
        engine.add_rule("crash", lambda na: 1 / 0)  # raises ZeroDivisionError
        normalizer = ActionNormalizer()
        na = normalizer.normalize(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="read_file",
            parameters={"path": "test.txt"},
        ))
        result = engine.evaluate(na)
        assert result.decision == GuardrailDecision.BLOCK
        assert result.recoverable is False, (
            "Rule exceptions must produce non-recoverable BLOCK"
        )

    def test_mixed_recoverable_and_non_recoverable_blends_to_non_recoverable(self):
        """If any BLOCK rule is non-recoverable, the merged result is non-recoverable."""
        normalizer = ActionNormalizer()
        na = normalizer.normalize(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="delete_file",
            parameters={"path": "/etc/passwd"},
        ))
        # Rule 1: recoverable BLOCK (out of bounds, can retry)
        # Rule 2: non-recoverable BLOCK (rule error)
        engine = RuleEngine()
        engine.add_rule("bounds", WorkspaceBoundaryRule(workspace_root="/tmp").evaluate)
        engine.add_rule("crash", lambda na: 1 / 0)
        result = engine.evaluate(na)
        assert result.decision == GuardrailDecision.BLOCK
        assert result.recoverable is False, (
            "Mixed recoverable + non-recoverable BLOCK → non-recoverable"
        )

    def test_recoverable_block_allows_retry(self):
        """A recoverable BLOCK does not prevent the agent from retrying."""
        normalizer = ActionNormalizer(workspace_root="/tmp")
        na = normalizer.normalize(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="delete_file",
            parameters={"path": "/etc/passwd"},
        ))
        engine = RuleEngine()
        engine.add_rule("bounds", WorkspaceBoundaryRule(workspace_root="/tmp").evaluate)
        result = engine.evaluate(na)
        assert result.decision == GuardrailDecision.BLOCK
        assert result.recoverable is True, (
            "Workspace boundary violations should be recoverable (agent can try a different path)"
        )


# ---------------------------------------------------------------------------
# Fix 3: Approval re-validation
# ---------------------------------------------------------------------------

class TestApprovalRevalidation:
    """Approval must bind to NormalizedAction and re-validate after approval."""

    def test_approval_binds_to_normalized_action(self):
        """Approval request must be created from NormalizedAction, not raw Action."""
        clock = FakeClock()
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        normalizer = ActionNormalizer(workspace_root="/tmp")
        na = normalizer.normalize(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "output.txt"},
        ))
        req = mgr.create_request(
            session_id="s1",
            normalized_action=na,
            matched_rules=["risk"],
            risk_summary="risky",
        )
        assert req.action_fingerprint == na.action_fingerprint
        assert isinstance(req.normalized_action, NormalizedAction)

    def test_approval_manager_has_public_get_request(self):
        """ApprovalManager must expose a public get_request() instead of
        forcing callers to access _requests."""
        clock = FakeClock()
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        normalizer = ActionNormalizer()
        na = normalizer.normalize(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "out.txt"},
        ))
        req = mgr.create_request("s1", na, ["r1"], "risk")
        # Must have a public method to get the request
        retrieved = mgr.get_request(req.request_id)
        assert retrieved is req

    def test_approval_manager_has_public_check_timeout_for_request(self):
        """ApprovalManager must expose public check_timeout_for_request(request_id)."""
        clock = FakeClock()
        mgr = ApprovalManager(clock=clock, approval_timeout=5)
        normalizer = ActionNormalizer()
        na = normalizer.normalize(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "out.txt"},
        ))
        req = mgr.create_request("s1", na, ["r1"], "risk")
        # Before timeout
        result = mgr.check_timeout_for_request(req.request_id)
        assert result is None
        # After timeout
        clock.advance(10)
        result = mgr.check_timeout_for_request(req.request_id)
        assert result is not None
        assert result.decision == ApprovalStatus.TIMEOUT


# ---------------------------------------------------------------------------
# Fix 4: FINAL_VALIDATION
# ---------------------------------------------------------------------------

class TestFinalValidation:
    """COMPLETE_REQUEST must run final sensors and require FINAL PASSED."""

    def test_intermediate_passed_alone_does_not_count(self):
        """INTERMEDIATE PASSED without FINAL PASSED → ObjectiveVerifier fails."""
        from codeguard.feedback.verifier import ObjectiveVerifier
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [
            FeedbackResult(
                sensor_id="pytest", program="pytest", args=[],
                status="PASSED", failure_category=None, exit_code=0,
                failure_fingerprint=None, validation_type="INTERMEDIATE",
                summary="ok", diagnostics=[], duration=0.1, retryable=False,
                raw_output_truncated="",
            )
        ]
        assert verifier.verify(results) is False, (
            "INTERMEDIATE PASSED must not satisfy FINAL_VALIDATION requirement"
        )

    def test_final_passed_satisfies_requirement(self):
        """FINAL PASSED → ObjectiveVerifier passes."""
        from codeguard.feedback.verifier import ObjectiveVerifier
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [
            FeedbackResult(
                sensor_id="pytest", program="pytest", args=[],
                status="PASSED", failure_category=None, exit_code=0,
                failure_fingerprint=None, validation_type="FINAL",
                summary="ok", diagnostics=[], duration=0.1, retryable=False,
                raw_output_truncated="",
            )
        ]
        assert verifier.verify(results) is True

    def test_final_failed_does_not_satisfy(self):
        """FINAL FAILED → ObjectiveVerifier fails."""
        from codeguard.feedback.verifier import ObjectiveVerifier
        verifier = ObjectiveVerifier(required_sensors=["pytest"])
        results = [
            FeedbackResult(
                sensor_id="pytest", program="pytest", args=[],
                status="FAILED", failure_category="TEST_FAILURE", exit_code=1,
                failure_fingerprint="abc", validation_type="FINAL",
                summary="fail", diagnostics=[], duration=0.1, retryable=True,
                raw_output_truncated="",
            )
        ]
        assert verifier.verify(results) is False

    def test_missing_required_sensor_fails(self):
        """Missing required sensor → ObjectiveVerifier fails."""
        from codeguard.feedback.verifier import ObjectiveVerifier
        verifier = ObjectiveVerifier(required_sensors=["pytest", "lint"])
        results = [
            FeedbackResult(
                sensor_id="pytest", program="pytest", args=[],
                status="PASSED", failure_category=None, exit_code=0,
                failure_fingerprint=None, validation_type="FINAL",
                summary="ok", diagnostics=[], duration=0.1, retryable=False,
                raw_output_truncated="",
            )
        ]
        assert verifier.verify(results) is False


# ---------------------------------------------------------------------------
# Fix 5: Integration test assertions
# ---------------------------------------------------------------------------

class TestScenarioAPipelineAssertions:
    """Scenario A must verify the governance pipeline steps."""

    def test_blocked_action_not_executed(self):
        """BLOCKed action must never be dispatched to tool_dispatcher."""
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="pipeline-a")

        engine = RuleEngine()
        engine.add_rule(
            "workspace",
            WorkspaceBoundaryRule(workspace_root="/home/user/project").evaluate,
        )
        loop.rule_engine = engine

        # Track dispatch calls
        dispatched = []
        class TrackingDispatcher:
            def dispatch(self, action):
                dispatched.append(action)

        loop.tool_dispatcher = TrackingDispatcher()

        loop.llm = ScriptedMockLLM(responses=[
            _make_response(Action(
                kind=ActionKind.TOOL_CALL,
                tool_name="delete_file",
                parameters={"path": "/etc/passwd"},
            )),
            _make_response(Action(
                kind=ActionKind.TOOL_CALL,
                tool_name="read_file",
                parameters={"path": "/home/user/project/README.md"},
            )),
            _make_response(Action(
                kind=ActionKind.COMPLETE_REQUEST, summary="done",
            )),
        ])

        result = loop.run()
        assert result.terminal_state == AgentState.COMPLETED

        # The dangerous action was NOT dispatched
        dispatched_tools = [a.tool_name for a in dispatched]
        assert "delete_file" not in dispatched_tools, (
            "BLOCKed action must not be dispatched"
        )
        assert "read_file" in dispatched_tools, (
            "ALLOWed action must be dispatched"
        )

    def test_rule_engine_receives_normalized_action(self):
        """RuleEngine must receive NormalizedAction, not raw Action."""
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="pipeline-na")

        received_types = []
        original_evaluate = loop.rule_engine.evaluate

        def tracking_evaluate(action):
            received_types.append(type(action).__name__)
            return original_evaluate(action)

        loop.rule_engine.evaluate = tracking_evaluate

        loop.llm = ScriptedMockLLM(responses=[
            _make_response(Action(
                kind=ActionKind.TOOL_CALL,
                tool_name="read_file",
                parameters={"path": "test.txt"},
            )),
            _make_response(Action(
                kind=ActionKind.COMPLETE_REQUEST, summary="done",
            )),
        ])

        loop.run()
        assert all(t == "NormalizedAction" for t in received_types), (
            f"RuleEngine received non-NormalizedAction types: {received_types}"
        )


class TestScenarioCCompletedWithFinalValidation:
    """Scenario C must go through FINAL_VALIDATION with required sensors."""

    def test_completed_requires_final_passed(self):
        """COMPLETED must not be reached without FINAL PASSED from all required sensors."""
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="final-val-test")

        # Require two sensors: pytest AND lint
        # Only pytest will run → lint is missing → FAIL
        loop.objective_verifier.required_sensors = ["pytest", "lint"]

        pytest_pass = FeedbackResult(
            sensor_id="pytest", program="pytest", args=[],
            status="PASSED", failure_category=None, exit_code=0,
            failure_fingerprint=None, validation_type="INTERMEDIATE",
            summary="ok", diagnostics=[], duration=0.1, retryable=False,
            raw_output_truncated="",
        )

        class ScriptedSensor:
            def __init__(self):
                self.call_count = 0
            def run_all(self):
                self.call_count += 1
                return [pytest_pass]

        loop.sensor_runner = ScriptedSensor()

        loop.llm = ScriptedMockLLM(responses=[
            _make_response(Action(
                kind=ActionKind.TOOL_CALL,
                tool_name="write_file",
                parameters={"path": "test.py", "content": "x=1"},
            )),
            _make_response(Action(
                kind=ActionKind.COMPLETE_REQUEST, summary="done",
            )),
        ] + [
            _make_response(Action(
                kind=ActionKind.COMPLETE_REQUEST, summary=f"retry{i}",
            )) for i in range(50)
        ])

        result = loop.run()
        # With required_sensors=["pytest", "lint"] and only pytest running,
        # the ObjectiveVerifier should reject completion because lint is missing
        assert result.terminal_state != AgentState.COMPLETED, (
            "COMPLETED must not be reached without all required sensors having FINAL PASSED"
        )


# ---------------------------------------------------------------------------
# Fix 1+2: Complete governance pipeline + no fallback normalization
# ---------------------------------------------------------------------------

from codeguard.tool import ToolDefinition
from codeguard.tool.registry import ToolRegistry


def _make_tool_def(name: str, required_params: list[str] | None = None) -> ToolDefinition:
    """Create a minimal ToolDefinition for testing."""
    schema = {
        "type": "object",
        "properties": {},
        "required": required_params or [],
    }
    for p in (required_params or []):
        schema["properties"][p] = {"type": "string"}
    return ToolDefinition(
        name=name,
        description=f"Test tool: {name}",
        parameters_schema=schema,
        handler=lambda p: None,
        category="FILE",
        side_effect=False,
        default_risk="ALLOW",
        supported_modes=["test"],
        result_schema=None,
        timeout_limit=30,
    )


class TestCompleteGovernancePipeline:
    """SPEC §3.2: Action → ToolRegistry.lookup → SchemaValidator
    → ActionNormalizer → NormalizedAction → RuleEngine."""

    def test_pipeline_call_order(self):
        """Verify the governance pipeline call order with spy tracking."""
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="pipeline-order")

        call_order = []

        # Spy: SchemaValidator
        original_validate = loop.schema_validator.validate
        def spy_validate(params, schema):
            call_order.append("schema_validate")
            return original_validate(params, schema)
        loop.schema_validator.validate = spy_validate

        # Spy: ActionNormalizer
        original_normalize = loop.action_normalizer.normalize
        def spy_normalize(action):
            call_order.append("normalize")
            return original_normalize(action)
        loop.action_normalizer.normalize = spy_normalize

        # Spy: RuleEngine
        original_evaluate = loop.rule_engine.evaluate
        def spy_evaluate(action):
            call_order.append("rule_engine")
            return original_evaluate(action)
        loop.rule_engine.evaluate = spy_evaluate

        # read_file already registered by _register_standard_tools

        loop.llm = ScriptedMockLLM(responses=[
            _make_response(Action(
                kind=ActionKind.TOOL_CALL,
                tool_name="read_file",
                parameters={"path": "test.txt"},
            )),
            _make_response(Action(
                kind=ActionKind.COMPLETE_REQUEST, summary="done",
            )),
        ])

        loop.run()

        # Verify order: schema_validate → normalize → rule_engine
        assert "schema_validate" in call_order, f"Missing schema_validate in {call_order}"
        assert "normalize" in call_order, f"Missing normalize in {call_order}"
        assert "rule_engine" in call_order, f"Missing rule_engine in {call_order}"
        sv_idx = call_order.index("schema_validate")
        n_idx = call_order.index("normalize")
        re_idx = call_order.index("rule_engine")
        assert sv_idx < n_idx < re_idx, (
            f"Expected schema_validate < normalize < rule_engine, got {call_order}"
        )

    def test_unknown_tool_goes_to_feeding_back(self):
        """Unknown tool → VALIDATION_ERROR → FEEDING_BACK, not executed."""
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="unknown-tool")

        dispatched = []
        class TrackingDispatcher:
            def dispatch(self, action):
                dispatched.append(action)
        loop.tool_dispatcher = TrackingDispatcher()

        # Do NOT register any tools — lookup will fail
        loop.tool_registry = ToolRegistry()

        loop.llm = ScriptedMockLLM(responses=[
            _make_response(Action(
                kind=ActionKind.TOOL_CALL,
                tool_name="nonexistent_tool",
                parameters={"path": "test.txt"},
            )),
            _make_response(Action(
                kind=ActionKind.COMPLETE_REQUEST, summary="done",
            )),
        ])

        result = loop.run()
        # Unknown tool → not executed
        assert len(dispatched) == 0, (
            f"Unknown tool must not be dispatched, got {len(dispatched)} calls"
        )
        # The loop should complete (not crash) because the LLM recovers
        assert result.terminal_state in (AgentState.COMPLETED, AgentState.LIMIT_REACHED)

    def test_missing_required_param_validation_error(self):
        """Missing required parameter → VALIDATION_ERROR, tool not executed."""
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="missing-param")

        dispatched = []
        class TrackingDispatcher:
            def dispatch(self, action):
                dispatched.append(action)
        loop.tool_dispatcher = TrackingDispatcher()

        # Replace registry to register custom tool with extra required param
        loop.tool_registry = ToolRegistry()
        loop.tool_registry.register(_make_tool_def("write_file", ["path", "content"]))

        # LLM sends action missing "content"
        loop.llm = ScriptedMockLLM(responses=[
            _make_response(Action(
                kind=ActionKind.TOOL_CALL,
                tool_name="write_file",
                parameters={"path": "test.txt"},  # missing "content"
            )),
            _make_response(Action(
                kind=ActionKind.COMPLETE_REQUEST, summary="done",
            )),
        ])

        result = loop.run()
        assert len(dispatched) == 0, (
            f"Action with missing required param must not be dispatched, "
            f"got {len(dispatched)} calls"
        )

    def test_wrong_param_type_validation_error(self):
        """Wrong parameter type → VALIDATION_ERROR, tool not executed."""
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="wrong-type")

        dispatched = []
        class TrackingDispatcher:
            def dispatch(self, action):
                dispatched.append(action)
        loop.tool_dispatcher = TrackingDispatcher()

        # read_file already registered by _register_standard_tools

        # LLM sends action with path as int instead of string
        loop.llm = ScriptedMockLLM(responses=[
            _make_response(Action(
                kind=ActionKind.TOOL_CALL,
                tool_name="read_file",
                parameters={"path": 12345},  # should be string
            )),
            _make_response(Action(
                kind=ActionKind.COMPLETE_REQUEST, summary="done",
            )),
        ])

        result = loop.run()
        assert len(dispatched) == 0, (
            f"Action with wrong param type must not be dispatched, "
            f"got {len(dispatched)} calls"
        )


class TestNoFallbackNormalization:
    """SPEC §3.2: Missing ActionNormalizer must fail closed, not fallback."""

    def test_missing_normalizer_fails_closed(self):
        """action_normalizer=None → FAILED, no RuleEngine or ToolDispatcher calls."""
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="no-normalizer")

        # Remove the normalizer
        loop.action_normalizer = None

        rule_engine_called = []
        original_evaluate = loop.rule_engine.evaluate
        def tracking_evaluate(action):
            rule_engine_called.append(action)
            return original_evaluate(action)
        loop.rule_engine.evaluate = tracking_evaluate

        dispatched = []
        class TrackingDispatcher:
            def dispatch(self, action):
                dispatched.append(action)
        loop.tool_dispatcher = TrackingDispatcher()

        loop.llm = ScriptedMockLLM(responses=[
            _make_response(Action(
                kind=ActionKind.TOOL_CALL,
                tool_name="read_file",
                parameters={"path": "test.txt"},
            )),
        ])

        result = loop.run()
        # Must fail — no fallback normalization
        assert result.terminal_state == AgentState.FAILED, (
            f"Expected FAILED without normalizer, got {result.terminal_state}"
        )
        assert len(rule_engine_called) == 0, (
            "RuleEngine must not be called when normalizer is missing"
        )
        assert len(dispatched) == 0, (
            "ToolDispatcher must not be called when normalizer is missing"
        )