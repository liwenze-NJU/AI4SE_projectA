from decimal import Decimal
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
)
from codeguard.guardrail.normalizer import ActionNormalizer
from codeguard.feedback.classifier import FeedbackClassifier
from codeguard.feedback.verifier import ObjectiveVerifier


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
    - test: ScriptedMockLLM + all core components (offline)
    - demo: ScriptedMockLLM + mock boundaries (no real I/O, no network)
    - local: DeepSeekAdapter + KeyringCredentialStore (production)
    """

    def __init__(self, mode: str = "test"):
        self._mode = mode

    def create_loop(self, session_id: str) -> AgentLoop:
        if self._mode == "demo":
            return self._create_demo_loop(session_id)
        if self._mode == "local":
            return self._create_local_loop(session_id)
        return self._create_test_loop(session_id)

    def _create_test_loop(self, session_id: str) -> AgentLoop:
        llm = ScriptedMockLLM(responses=[_make_complete_response()])
        loop = AgentLoop(session_id=session_id, llm=llm)
        self._wire_common(loop, workspace_root=".")
        return loop

    def _create_demo_loop(self, session_id: str) -> AgentLoop:
        llm = ScriptedMockLLM(responses=[_make_complete_response("demo done")])
        loop = AgentLoop(session_id=session_id, llm=llm)
        self._wire_common(loop, workspace_root=".")
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
        self._wire_common(loop, workspace_root=".")
        return loop

    def _wire_common(self, loop: AgentLoop, workspace_root: str) -> None:
        loop.secret_redactor = SecretRedactor()
        loop.tracer = Tracer(secret_redactor=loop.secret_redactor)
        loop.context_builder = ContextBuilder()
        loop.action_parser = ActionParser()
        engine = RuleEngine()
        engine.add_rule(
            "workspace", WorkspaceBoundaryRule(workspace_root=workspace_root).evaluate
        )
        engine.add_rule("credential", CredentialLeakRule().evaluate)
        loop.action_normalizer = ActionNormalizer(workspace_root=workspace_root)
        loop.rule_engine = engine
        loop.approval_manager = ApprovalManager(approval_timeout=60)
        loop.stop_policy = StopPolicy(
            max_steps=50, max_llm_calls=100, no_progress_threshold=3
        )
        loop.feedback_classifier = FeedbackClassifier()
        loop.objective_verifier = ObjectiveVerifier(required_sensors=[])