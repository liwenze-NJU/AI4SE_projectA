import pytest
import sys
from codeguard.composition import CompositionRoot
from codeguard.loop import AgentLoop
from codeguard.state import AgentState
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.llm.client import LLMClient
from codeguard.guardrail.engine import RuleEngine
from codeguard.guardrail.approval import ApprovalManager
from codeguard.stop import StopPolicy
from codeguard.feedback.classifier import FeedbackClassifier
from codeguard.feedback.verifier import ObjectiveVerifier
from codeguard.secret import SecretRedactor
from codeguard.tracer import Tracer
from codeguard.context import ContextBuilder
from codeguard.action import ActionParser
from codeguard.events import NullEventSink
from codeguard.tool.dispatcher import ToolDispatcher


def _has_deepseek_in_graph(obj) -> bool:
    """Check if any object in the attribute graph is a DeepSeekAdapter."""
    import codeguard.llm.deepseek as _ds
    return _check_type_in_graph(obj, _ds.DeepSeekAdapter)


def _has_keyring_in_graph(obj) -> bool:
    """Check if keyring types are referenced in the object graph."""
    try:
        import keyring
        return _check_module_types_in_graph(obj, keyring)
    except ImportError:
        return False


def _has_credential_store_in_graph(obj) -> bool:
    """Check if KeyringCredentialStore is referenced in the object graph."""
    try:
        import codeguard.credentials.store as _cs
        return _check_type_in_graph(obj, _cs.KeyringCredentialStore)
    except ImportError:
        return False


def _check_type_in_graph(obj, target_type, visited=None) -> bool:
    if visited is None:
        visited = set()
    obj_id = id(obj)
    if obj_id in visited:
        return False
    visited.add(obj_id)
    if isinstance(obj, target_type):
        return True
    for attr_name in dir(obj):
        if attr_name.startswith('_') and attr_name != '__class__':
            continue
        try:
            attr = getattr(obj, attr_name)
        except Exception:
            continue
        if isinstance(attr, target_type):
            return True
        if hasattr(attr, '__dict__') and not isinstance(attr, (str, int, float, bool, list, dict, tuple, type)):
            if _check_type_in_graph(attr, target_type, visited):
                return True
    return False


def _check_module_types_in_graph(obj, module, visited=None) -> bool:
    if visited is None:
        visited = set()
    obj_id = id(obj)
    if obj_id in visited:
        return False
    visited.add(obj_id)
    obj_type = type(obj)
    if obj_type.__module__ == module.__name__:
        return True
    for attr_name in dir(obj):
        if attr_name.startswith('_') and attr_name != '__class__':
            continue
        try:
            attr = getattr(obj, attr_name)
        except Exception:
            continue
        if type(attr).__module__ == module.__name__:
            return True
        if hasattr(attr, '__dict__') and not isinstance(attr, (str, int, float, bool, list, dict, tuple, type)):
            if _check_module_types_in_graph(attr, module, visited):
                return True
    return False


class TestCompositionRootTestMode:
    def test_creates_agent_loop(self):
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="test-s1")
        assert isinstance(loop, AgentLoop)

    def test_uses_scripted_mock_llm(self):
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="test-s1")
        assert isinstance(loop.llm, ScriptedMockLLM)

    def test_llm_satisfies_protocol(self):
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="test-s1")
        assert isinstance(loop.llm, LLMClient)

    def test_injects_all_core_components(self):
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="test-s1")
        assert isinstance(loop.rule_engine, RuleEngine)
        assert isinstance(loop.approval_manager, ApprovalManager)
        assert isinstance(loop.stop_policy, StopPolicy)
        assert isinstance(loop.feedback_classifier, FeedbackClassifier)
        assert isinstance(loop.objective_verifier, ObjectiveVerifier)
        assert loop.secret_redactor is not None
        assert loop.tracer is not None
        assert loop.context_builder is not None
        assert loop.action_parser is not None

    def test_injects_dispatcher_and_sensor_surface(self):
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="test-s1")
        assert isinstance(loop.tool_dispatcher, ToolDispatcher)
        assert loop.sensor_runner is not None
        assert loop.objective_verifier is not None
        assert loop.tool_registry is not None

    def test_default_event_sink_is_null_sink(self):
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="test-s1")
        assert isinstance(loop.event_sink, NullEventSink)

    def test_injects_custom_event_sink(self):
        from codeguard.events import CollectingEventSink
        sink = CollectingEventSink()
        root = CompositionRoot(mode="test", event_sink=sink)
        loop = root.create_loop(session_id="test-s1")
        assert loop.event_sink is sink

    def test_default_mode_is_test(self):
        root = CompositionRoot()
        loop = root.create_loop(session_id="test-s1")
        assert isinstance(loop.llm, ScriptedMockLLM)

    def test_initial_state_is_initializing(self):
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="test-s1")
        assert loop.state.current_state == AgentState.INITIALIZING

    def test_each_call_creates_unique_loop(self):
        root = CompositionRoot(mode="test")
        loop1 = root.create_loop(session_id="s1")
        loop2 = root.create_loop(session_id="s2")
        assert loop1 is not loop2
        assert loop1.state.session_id == "s1"
        assert loop2.state.session_id == "s2"


class TestCompositionRootDemoMode:
    def test_creates_agent_loop(self):
        root = CompositionRoot(mode="demo")
        loop = root.create_loop(session_id="demo-s1")
        assert isinstance(loop, AgentLoop)

    def test_uses_scripted_mock_llm(self):
        root = CompositionRoot(mode="demo")
        loop = root.create_loop(session_id="demo-s1")
        assert isinstance(loop.llm, ScriptedMockLLM)

    def test_no_deepseek_adapter_used(self):
        root = CompositionRoot(mode="demo")
        loop = root.create_loop(session_id="demo-s1")
        assert not _has_deepseek_in_graph(loop)

    def test_no_keyring_used(self):
        root = CompositionRoot(mode="demo")
        loop = root.create_loop(session_id="demo-s1")
        assert not _has_keyring_in_graph(loop)

    def test_no_credential_store_used(self):
        root = CompositionRoot(mode="demo")
        loop = root.create_loop(session_id="demo-s1")
        assert not _has_credential_store_in_graph(loop)

    def test_has_rule_engine(self):
        root = CompositionRoot(mode="demo")
        loop = root.create_loop(session_id="demo-s1")
        assert isinstance(loop.rule_engine, RuleEngine)

    def test_has_approval_manager(self):
        root = CompositionRoot(mode="demo")
        loop = root.create_loop(session_id="demo-s1")
        assert isinstance(loop.approval_manager, ApprovalManager)

    def test_demo_avoids_real_dispatcher_and_sensors(self):
        root = CompositionRoot(mode="demo")
        loop = root.create_loop(session_id="demo-s1")
        # Demo mode explicitly avoids the real dispatcher and sensor surface:
        # no real subprocess can run and no real tool handler can be reached.
        assert loop.tool_dispatcher is None
        assert loop.sensor_runner is None
        assert loop.objective_verifier is not None
        assert loop.objective_verifier.required_sensors == []


class TestCompositionRootLocalMode:
    def test_fails_when_no_api_key(self, monkeypatch):
        import codeguard.credentials.store as cred_store
        monkeypatch.setattr(cred_store.KeyringCredentialStore, 'get', lambda self, p: None)
        root = CompositionRoot(mode="local")
        with pytest.raises(ValueError, match="API key"):
            root.create_loop(session_id="local-s1")

    def test_mode_not_upgradable_from_config(self):
        root = CompositionRoot(mode="demo")
        loop = root.create_loop(session_id="demo-s1")
        assert isinstance(loop.llm, ScriptedMockLLM)


class TestCompositionRootModeSafety:
    def test_demo_cannot_become_local(self):
        root = CompositionRoot(mode="demo")
        loop = root.create_loop(session_id="demo-s1")
        assert not hasattr(loop, '_deepseek')

    def test_test_cannot_become_local(self):
        root = CompositionRoot(mode="test")
        loop = root.create_loop(session_id="test-s1")
        assert isinstance(loop.llm, ScriptedMockLLM)

    def test_each_mode_creates_appropriate_llm(self):
        test_root = CompositionRoot(mode="test")
        test_loop = test_root.create_loop(session_id="s1")
        assert isinstance(test_loop.llm, ScriptedMockLLM)

        demo_root = CompositionRoot(mode="demo")
        demo_loop = demo_root.create_loop(session_id="s2")
        assert isinstance(demo_loop.llm, ScriptedMockLLM)