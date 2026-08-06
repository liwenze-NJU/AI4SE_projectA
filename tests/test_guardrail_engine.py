import pytest
from datetime import datetime
from codeguard.action import ActionKind, NormalizedAction
from codeguard.guardrail import GuardrailDecision, GuardrailResult
from codeguard.guardrail.engine import RuleEngine, PriorityMerger
from codeguard.guardrail.rules import WorkspaceBoundaryRule


def _make_na(tool_name="read_file", params=None):
    return NormalizedAction(
        kind=ActionKind.TOOL_CALL,
        tool_name=tool_name,
        normalized_parameters=params or {},
        action_fingerprint="fp",
        original_raw="",
        normalized_at=datetime.now(),
    )


def _allow(rule_id="r1"):
    return {"decision": "ALLOW", "rule_id": rule_id, "reason_codes": []}


def _block(rule_id="r1", reason="danger"):
    return {"decision": "BLOCK", "rule_id": rule_id, "reason_codes": [reason]}


def _approval(rule_id="r1", reason="risky"):
    return {"decision": "REQUEST_APPROVAL", "rule_id": rule_id, "reason_codes": [reason]}


# ── RuleEngine ───────────────────────────────────────────────────────

class TestRuleEngine:
    def test_all_allow(self):
        engine = RuleEngine()
        engine.add_rule("a1", lambda na: _allow("a1"))
        engine.add_rule("a2", lambda na: _allow("a2"))
        result = engine.evaluate(_make_na())
        assert result.decision == GuardrailDecision.ALLOW
        assert set(result.rule_ids) == {"a1", "a2"}

    def test_block_overrides_allow(self):
        engine = RuleEngine()
        engine.add_rule("allow1", lambda na: _allow("allow1"))
        engine.add_rule("block1", lambda na: _block("block1", "danger"))
        result = engine.evaluate(_make_na())
        assert result.decision == GuardrailDecision.BLOCK
        assert "block1" in result.rule_ids

    def test_approval_overrides_allow(self):
        engine = RuleEngine()
        engine.add_rule("allow1", lambda na: _allow("allow1"))
        engine.add_rule("approval1", lambda na: _approval("approval1", "risky"))
        result = engine.evaluate(_make_na())
        assert result.decision == GuardrailDecision.REQUEST_APPROVAL
        assert "approval1" in result.rule_ids

    def test_block_overrides_approval(self):
        engine = RuleEngine()
        engine.add_rule("approval1", lambda na: _approval("approval1", "risky"))
        engine.add_rule("block1", lambda na: _block("block1", "danger"))
        result = engine.evaluate(_make_na())
        assert result.decision == GuardrailDecision.BLOCK

    def test_order_independent(self):
        # BLOCK first, then ALLOW — BLOCK still wins
        engine1 = RuleEngine()
        engine1.add_rule("block1", lambda na: _block("block1"))
        engine1.add_rule("allow1", lambda na: _allow("allow1"))
        r1 = engine1.evaluate(_make_na())
        # ALLOW first, then BLOCK — BLOCK still wins
        engine2 = RuleEngine()
        engine2.add_rule("allow1", lambda na: _allow("allow1"))
        engine2.add_rule("block1", lambda na: _block("block1"))
        r2 = engine2.evaluate(_make_na())
        assert r1.decision == GuardrailDecision.BLOCK
        assert r2.decision == GuardrailDecision.BLOCK

    def test_empty_rules_default_deny(self):
        engine = RuleEngine()
        result = engine.evaluate(_make_na())
        assert result.decision == GuardrailDecision.BLOCK
        assert "default_deny" in result.rule_ids

    def test_rule_exception_fail_closed(self):
        engine = RuleEngine()
        engine.add_rule("allow1", lambda na: _allow("allow1"))
        engine.add_rule("broken", lambda na: 1 / 0)
        result = engine.evaluate(_make_na())
        assert result.decision == GuardrailDecision.BLOCK
        assert "broken" in result.rule_ids
        assert "rule_error" in result.reason_codes

    def test_unknown_decision_fail_closed(self):
        engine = RuleEngine()
        engine.add_rule("weird", lambda na: {"decision": "WEIRD", "rule_id": "weird", "reason_codes": []})
        result = engine.evaluate(_make_na())
        assert result.decision == GuardrailDecision.BLOCK

    def test_missing_decision_field_fail_closed(self):
        engine = RuleEngine()
        engine.add_rule("bad", lambda na: {"rule_id": "bad", "reason_codes": []})
        result = engine.evaluate(_make_na())
        assert result.decision == GuardrailDecision.BLOCK

    def test_missing_rule_id_field(self):
        engine = RuleEngine()
        engine.add_rule("bad", lambda na: {"decision": "ALLOW", "reason_codes": []})
        result = engine.evaluate(_make_na())
        assert result.decision == GuardrailDecision.BLOCK

    def test_reason_codes_aggregated(self):
        engine = RuleEngine()
        engine.add_rule("a1", lambda na: _allow("a1"))
        engine.add_rule("b1", lambda na: _block("b1", "out_of_bounds"))
        engine.add_rule("b2", lambda na: _block("b2", "credential_detected"))
        result = engine.evaluate(_make_na())
        assert "out_of_bounds" in result.reason_codes
        assert "credential_detected" in result.reason_codes

    def test_rule_ids_aggregated(self):
        engine = RuleEngine()
        engine.add_rule("a1", lambda na: _allow("a1"))
        engine.add_rule("a2", lambda na: _allow("a2"))
        result = engine.evaluate(_make_na())
        assert set(result.rule_ids) == {"a1", "a2"}

    def test_supports_callable_rules(self):
        engine = RuleEngine()
        engine.add_rule("test", lambda na: _allow("test"))
        result = engine.evaluate(_make_na())
        assert result.decision == GuardrailDecision.ALLOW

    def test_supports_evaluate_method_rules(self):
        engine = RuleEngine()
        rule = WorkspaceBoundaryRule(workspace_root="/home/user/project")
        engine.add_rule("workspace_boundary", rule)
        na = _make_na(params={"path": "/home/user/project/src/main.py"})
        result = engine.evaluate(na)
        assert result.decision == GuardrailDecision.ALLOW
        assert "workspace_boundary" in result.rule_ids

    def test_returns_guardrail_result_type(self):
        engine = RuleEngine()
        engine.add_rule("a1", lambda na: _allow("a1"))
        result = engine.evaluate(_make_na())
        assert isinstance(result, GuardrailResult)
        assert isinstance(result.decision, GuardrailDecision)
        assert result.action_fingerprint == "fp"
        assert result.normalized_action is not None

    def test_human_readable_message(self):
        engine = RuleEngine()
        engine.add_rule("b1", lambda na: _block("b1", "danger"))
        result = engine.evaluate(_make_na())
        assert "Blocked" in result.human_readable_message
        assert "b1" in result.human_readable_message

    def test_recoverable_false_on_block(self):
        engine = RuleEngine()
        engine.add_rule("b1", lambda na: _block("b1"))
        result = engine.evaluate(_make_na())
        assert result.recoverable is False

    def test_recoverable_true_on_approval(self):
        engine = RuleEngine()
        engine.add_rule("r1", lambda na: _approval("r1"))
        result = engine.evaluate(_make_na())
        assert result.recoverable is True


# ── PriorityMerger ────────────────────────────────────────────────────

class TestPriorityMerger:
    def test_block_wins(self):
        merger = PriorityMerger()
        results = [
            {"decision": "ALLOW", "rule_id": "a1", "reason_codes": []},
            {"decision": "BLOCK", "rule_id": "b1", "reason_codes": ["x"]},
        ]
        merged = merger.merge(results)
        assert merged["decision"] == "BLOCK"

    def test_approval_over_allow(self):
        merger = PriorityMerger()
        results = [
            {"decision": "ALLOW", "rule_id": "a1", "reason_codes": []},
            {"decision": "REQUEST_APPROVAL", "rule_id": "r1", "reason_codes": ["y"]},
        ]
        merged = merger.merge(results)
        assert merged["decision"] == "REQUEST_APPROVAL"

    def test_empty_returns_default_deny(self):
        merger = PriorityMerger()
        merged = merger.merge([])
        assert merged["decision"] == "BLOCK"
        assert merged["rule_ids"] == ["default_deny"]

    def test_all_allow_returns_allow(self):
        merger = PriorityMerger()
        results = [
            {"decision": "ALLOW", "rule_id": "a1", "reason_codes": []},
            {"decision": "ALLOW", "rule_id": "a2", "reason_codes": []},
        ]
        merged = merger.merge(results)
        assert merged["decision"] == "ALLOW"

    def test_aggregates_rule_ids(self):
        merger = PriorityMerger()
        results = [
            {"decision": "ALLOW", "rule_id": "a1", "reason_codes": []},
            {"decision": "ALLOW", "rule_id": "a2", "reason_codes": []},
        ]
        merged = merger.merge(results)
        assert merged["rule_ids"] == ["a1", "a2"]

    def test_aggregates_reason_codes(self):
        merger = PriorityMerger()
        results = [
            {"decision": "BLOCK", "rule_id": "b1", "reason_codes": ["x"]},
            {"decision": "BLOCK", "rule_id": "b2", "reason_codes": ["y"]},
        ]
        merged = merger.merge(results)
        assert merged["reason_codes"] == ["x", "y"]