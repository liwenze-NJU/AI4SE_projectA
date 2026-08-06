"""Integration tests: Governance-Driven Test Feedback Loop (治理驱动的测试反馈闭环).

Phase 14 — SPEC §3.1, §3.2, §3.3, §3.5, §10.1, §10.2, §10.3.

Each test demonstrates a complete end-to-end scenario using real Harness
components (AgentLoop, RuleEngine, Guardrail, ApprovalManager, FeedbackClassifier,
StopPolicy, ObjectiveVerifier) with ScriptedMockLLM and FakeClock at the
external boundaries.
"""

from decimal import Decimal
from codeguard.composition import CompositionRoot
from codeguard.state import AgentState
from codeguard.action import Action, ActionKind, LLMResponse
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.guardrail.engine import RuleEngine
from codeguard.guardrail.rules import WorkspaceBoundaryRule
from codeguard.guardrail import GuardrailDecision


def _make_response(action: Action, finish_reason: str = "stop") -> LLMResponse:
    """Create an LLMResponse wrapping an Action for ScriptedMockLLM."""
    return LLMResponse(
        content="mock",
        next_action=action,
        finish_reason=finish_reason,
        model="mock",
        token_used=0,
        cost_used=Decimal("0"),
        raw_response="",
    )


def test_scenario_a_block_then_feedback_then_complete():
    """BLOCK -> feedback -> change action -> COMPLETED.

    This is the core governance-driven test feedback loop scenario.
    Phase 1: LLM proposes dangerous action (delete_file outside workspace)
    Phase 2: Guardrail BLOCKs it
    Phase 3: Feedback is injected
    Phase 4: LLM proposes safe action
    Phase 5: Guardrail ALLOWs
    Phase 6: Action executes, COMPLETE_REQUEST -> FINAL_VALIDATION -> COMPLETED
    """
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-a")

    # Replace the default RuleEngine with one that has a real workspace boundary rule
    engine = RuleEngine()
    engine.add_rule(
        "workspace",
        WorkspaceBoundaryRule(workspace_root="/home/user/project").evaluate,
    )
    loop.rule_engine = engine

    # ScriptedMockLLM:
    # 1st call: dangerous action (delete_file outside workspace) -> BLOCKed
    # 2nd call: safe action (read_file inside workspace) -> ALLOWed
    # 3rd call: COMPLETE_REQUEST -> FINAL_VALIDATION -> COMPLETED
    loop.llm = ScriptedMockLLM(responses=[
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="delete_file",
            parameters={"path": "/etc/passwd"},
            raw="",
        )),
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="read_file",
            parameters={"path": "/home/user/project/README.md"},
            raw="",
        )),
        _make_response(Action(
            kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="",
        )),
    ])

    result = loop.run()

    # Verify terminal state
    assert result.terminal_state == AgentState.COMPLETED, (
        f"Expected COMPLETED, got {result.terminal_state}"
    )

    # Verify the BLOCK was recorded
    guardrail_decisions = result.guardrail_decisions
    assert len(guardrail_decisions) >= 2, (
        f"Expected at least 2 guardrail decisions, got {len(guardrail_decisions)}"
    )

    # First decision should be BLOCK
    assert guardrail_decisions[0].decision == GuardrailDecision.BLOCK, (
        f"Expected BLOCK, got {guardrail_decisions[0].decision}"
    )

    # Second decision should be ALLOW
    assert guardrail_decisions[1].decision == GuardrailDecision.ALLOW, (
        f"Expected ALLOW, got {guardrail_decisions[1].decision}"
    )

    # Verify the loop actually made progress (BLOCK didn't count as a step)
    assert result.llm_calls_total == 3, (
        f"Expected 3 LLM calls, got {result.llm_calls_total}"
    )

    # The dangerous action was NOT executed (steps_used only counts executed tools)
    assert result.steps_total == 1, (
        f"Expected 1 executed step (read_file), got {result.steps_total}"
    )