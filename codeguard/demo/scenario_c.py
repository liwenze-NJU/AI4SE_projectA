"""Demo Scenario C — first test fails, feedback classified, repair, pass.

Flow (SPEC §3.9 demo scenario 3):
  Phase 1: LLM writes buggy code → sensor FAILED → classified
  Phase 2: feedback fed back → LLM changes action (repair)
  Phase 3: sensor PASSED → COMPLETE_REQUEST → FINAL_VALIDATION → COMPLETED.

Uses only ScriptedMockLLM + scripted sensor + mock boundaries.
"""

from decimal import Decimal
from codeguard.composition import CompositionRoot
from codeguard.loop import AgentLoop
from codeguard.action import Action, ActionKind, LLMResponse
from codeguard.state import AgentState
from codeguard.feedback import FeedbackResult
from codeguard.guardrail.engine import RuleEngine
from codeguard.guardrail.rules import WorkspaceBoundaryRule, CredentialLeakRule
from codeguard.guardrail.normalizer import ActionNormalizer
from codeguard.demo.mock_tool_dispatcher import mock_tool_dispatcher


def _make_response(action: Action) -> LLMResponse:
    return LLMResponse(
        content="mock",
        next_action=action,
        finish_reason="stop",
        model="mock",
        token_used=0,
        cost_used=Decimal("0"),
        raw_response="",
    )


class ScriptedSensorRunner:
    """Returns pre-scripted FeedbackResult lists in order (deterministic)."""

    def __init__(self, responses: list[list[FeedbackResult]]):
        self._responses = responses
        self._call_count = 0

    def run_all(self) -> list[FeedbackResult]:
        if self._call_count >= len(self._responses):
            return []
        result = self._responses[self._call_count]
        self._call_count += 1
        return result


def run_scenario_c():
    """Run scenario C to a terminal state and return the SessionResult."""
    root = CompositionRoot(mode="demo")
    loop: AgentLoop = root.create_loop(session_id="demo-c")

    # Scripted LLM:
    # 1st: write buggy code → test FAILED
    # 2nd: write fixed code → test PASSED
    # 3rd: COMPLETE_REQUEST → FINAL_VALIDATION → COMPLETED
    loop.llm._responses = [
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "src/add.py", "content": "def add(a, b): return a - b"},
            raw="",
        )),
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "src/add.py", "content": "def add(a, b): return a + b"},
            raw="",
        )),
        _make_response(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ]

    fail_result = FeedbackResult(
        sensor_id="pytest",
        program="python",
        args=["-m", "pytest"],
        status="FAILED",
        failure_category="TEST_ASSERTION_FAILURE",
        exit_code=1,
        failure_fingerprint="mock-fp-fail",
        validation_type="INTERMEDIATE",
        summary="1 test failed: test_add",
        diagnostics=[{"file": "test_add.py", "line": 10, "message": "assert 1 == 2"}],
        duration=0.0,
        retryable=True,
        raw_output_truncated="FAILED test_add - assert 1 == 2",
    )
    pass_result = FeedbackResult(
        sensor_id="pytest",
        program="python",
        args=["-m", "pytest"],
        status="PASSED",
        failure_category=None,
        exit_code=0,
        failure_fingerprint=None,
        validation_type="INTERMEDIATE",
        summary="All tests passed",
        diagnostics=[],
        duration=0.0,
        retryable=False,
        raw_output_truncated="1 passed",
    )
    loop.sensor_runner = ScriptedSensorRunner(
        responses=[[fail_result], [pass_result]]
    )

    # Governance: workspace boundary + credential leak (no mode restriction —
    # scenario C must allow write_file so the repair cycle can execute)
    engine = RuleEngine()
    engine.add_rule("workspace", WorkspaceBoundaryRule(workspace_root="workspace").evaluate)
    engine.add_rule("credential", CredentialLeakRule().evaluate)
    loop.rule_engine = engine
    loop.action_normalizer = ActionNormalizer(workspace_root="workspace")
    loop.tool_dispatcher = mock_tool_dispatcher
    return loop.run()
