from codeguard.action import NormalizedAction
from codeguard.guardrail import GuardrailDecision, GuardrailResult

_DECISION_PRIORITY = {"BLOCK": 3, "REQUEST_APPROVAL": 2, "ALLOW": 1}
_VALID_DECISIONS = frozenset(_DECISION_PRIORITY.keys())


class PriorityMerger:
    """Merges multiple rule results by priority: BLOCK > REQUEST_APPROVAL > ALLOW."""

    def merge(self, results: list[dict]) -> dict:
        if not results:
            return {"decision": "BLOCK", "rule_ids": ["default_deny"], "reason_codes": ["no_rule_matched"]}
        merged = {"decision": "ALLOW", "rule_ids": [], "reason_codes": []}
        for r in results:
            if _DECISION_PRIORITY.get(r.get("decision", ""), 0) > _DECISION_PRIORITY.get(merged["decision"], 0):
                merged["decision"] = r["decision"]
            merged["rule_ids"].append(r.get("rule_id", "unknown"))
            merged["reason_codes"].extend(r.get("reason_codes", []))
        return merged


class RuleEngine:
    """Executes all registered rules and merges results by priority.

    Rules can be callables or objects with an evaluate(action) method.
    Default-deny: empty ruleset returns BLOCK.
    Fail-closed: rule exceptions and malformed results are treated as BLOCK.
    """

    def __init__(self):
        self._rules: dict[str, object] = {}
        self._merger = PriorityMerger()

    def add_rule(self, name: str, rule):
        self._rules[name] = rule

    def evaluate(self, action: NormalizedAction) -> GuardrailResult:
        results = []
        for name, rule in self._rules.items():
            try:
                r = self._invoke_rule(rule, action)
                r = self._validate_result(r, name)
                results.append(r)
            except Exception:
                results.append({"decision": "BLOCK", "rule_id": name, "reason_codes": ["rule_error"]})

        merged = self._merger.merge(results)
        return GuardrailResult(
            decision=GuardrailDecision(merged["decision"]),
            rule_ids=merged["rule_ids"],
            reason_codes=merged["reason_codes"],
            human_readable_message=self._format_message(merged),
            recoverable=(merged["decision"] != "BLOCK"),
            normalized_action=action,
            action_fingerprint=action.action_fingerprint,
        )

    def _invoke_rule(self, rule, action: NormalizedAction) -> dict:
        if hasattr(rule, "evaluate"):
            return rule.evaluate(action)
        return rule(action)

    def _validate_result(self, r, name: str) -> dict:
        if not isinstance(r, dict):
            raise ValueError(f"Rule '{name}' returned non-dict: {type(r).__name__}")
        decision = r.get("decision", "")
        if decision not in _VALID_DECISIONS:
            raise ValueError(f"Rule '{name}' returned invalid decision: {decision!r}")
        if "rule_id" not in r:
            raise ValueError(f"Rule '{name}' missing 'rule_id' in result")
        return r

    def _format_message(self, merged: dict) -> str:
        if merged["decision"] == "BLOCK":
            return f"Blocked by rules: {', '.join(merged['rule_ids'])}"
        elif merged["decision"] == "REQUEST_APPROVAL":
            return f"Requires approval: {', '.join(merged['rule_ids'])}"
        return "Allowed"