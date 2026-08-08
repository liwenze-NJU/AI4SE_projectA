"""Demo Scenario A — dangerous action BLOCKed, then safe action completes.

Flow (SPEC §3.9 demo scenario 1):
  LLM proposes write_file outside workspace → BLOCK (recoverable)
  → feedback fed back → LLM changes to read_file (safe) → ALLOW
  → EXECUTING → COMPLETED.

Uses only ScriptedMockLLM + mock boundaries (no real I/O, no network).
"""

from decimal import Decimal
from codeguard.composition import CompositionRoot
from codeguard.loop import AgentLoop
from codeguard.action import Action, ActionKind, LLMResponse
from codeguard.state import AgentState
from codeguard.guardrail.engine import RuleEngine
from codeguard.guardrail.rules import (
    WorkspaceBoundaryRule,
    CredentialLeakRule,
    ModeRestrictionRule,
)
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


def run_scenario_a():
    """Run scenario A to a terminal state and return the SessionResult."""
    root = CompositionRoot(mode="demo")
    loop: AgentLoop = root.create_loop(session_id="demo-a")
    loop.llm._responses = [
        # Step 1: dangerous action — write_file outside workspace
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="write_file",
            parameters={"path": "../secret.txt", "content": "leak"},
            raw="",
        )),
        # Step 2: after BLOCK feedback, safe action — read_file in workspace
        _make_response(Action(
            kind=ActionKind.TOOL_CALL,
            tool_name="read_file",
            parameters={"path": "src/auth.py"},
            raw="",
        )),
        # Step 3: complete
        _make_response(Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")),
    ]

    # Governance wiring: workspace boundary + credential + demo mode restriction
    engine = RuleEngine()
    engine.add_rule("workspace", WorkspaceBoundaryRule(workspace_root="workspace").evaluate)
    engine.add_rule("credential", CredentialLeakRule().evaluate)
    engine.add_rule("mode", ModeRestrictionRule(mode="demo").evaluate)
    loop.rule_engine = engine
    loop.action_normalizer = ActionNormalizer(workspace_root="workspace")
    loop.tool_dispatcher = mock_tool_dispatcher

    return loop.run()
