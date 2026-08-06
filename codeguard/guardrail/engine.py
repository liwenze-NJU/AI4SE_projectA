"""RuleEngine — deterministic governance rule evaluation.

Per SPEC §3.2, the governance pipeline is:
  Action → SchemaValidator → ActionNormalizer → NormalizedAction
  → RuleEngine → PriorityMerger → GuardrailResult

The RuleEngine only accepts NormalizedAction. Raw Action objects are rejected
with TypeError to enforce the governance pipeline.
"""

from codeguard.action import NormalizedAction
from codeguard.guardrail import GuardrailDecision, GuardrailResult


_DECISION_PRIORITY = {"BLOCK": 3, "REQUEST_APPROVAL": 2, "ALLOW": 1}
_VALID_DECISIONS = frozenset(_DECISION_PRIORITY.keys())


class PriorityMerger:
    """Merges multiple rule results by priority: BLOCK > REQUEST_APPROVAL > ALLOW.

    Recoverable semantics:
    - Rule results may include a 'recoverable' boolean.
    - If any BLOCK result has recoverable=False, the merged result is
      non-recoverable.
    - Rule exceptions are treated as BLOCK with recoverable=False.
    - Default for non-BLOCK is recoverable=True.
    """

    def merge(self, results: list[dict]) -> dict:
        if not results:
            return {
                "decision": "BLOCK",
                "rule_ids": ["default_deny"],
                "reason_codes": ["no_rule_matched"],
                "recoverable": True,
            }
        merged = {
            "decision": "ALLOW",
            "rule_ids": [],
            "reason_codes": [],
            "recoverable": True,
        }
        any_non_recoverable_block = False
        for r in results:
            d = r.get("decision", "")
            if _DECISION_PRIORITY.get(d, 0) > _DECISION_PRIORITY.get(merged["decision"], 0):
                merged["decision"] = d
            merged["rule_ids"].append(r.get("rule_id", "unknown"))
            merged["reason_codes"].extend(r.get("reason_codes", []))
            if d == "BLOCK" and r.get("recoverable") is False:
                any_non_recoverable_block = True

        if any_non_recoverable_block:
            merged["recoverable"] = False
        return merged


class RuleEngine:
    """Executes all registered rules and merges results by priority.

    Rules must be callables or objects with an evaluate(action) method
    that accepts NormalizedAction.
    Default-deny: empty ruleset returns BLOCK.
    Fail-closed: rule exceptions → BLOCK with recoverable=False.
    """

    def __init__(self):
        self._rules: dict[str, object] = {}
        self._merger = PriorityMerger()

    def add_rule(self, name: str, rule):
        self._rules[name] = rule

    def evaluate(self, action: NormalizedAction) -> GuardrailResult:
        if not isinstance(action, NormalizedAction):
            raise TypeError(
                f"RuleEngine.evaluate() requires NormalizedAction, "
                f"got {type(action).__name__}"
            )
        results = []
        for name, rule in self._rules.items():
            try:
                r = self._invoke_rule(rule, action)
                r = self._validate_result(r, name)
                results.append(r)
            except Exception:
                results.append({
                    "decision": "BLOCK",
                    "rule_id": name,
                    "reason_codes": ["rule_error"],
                    "recoverable": False,
                })

        merged = self._merger.merge(results)
        return GuardrailResult(
            decision=GuardrailDecision(merged["decision"]),
            rule_ids=merged["rule_ids"],
            reason_codes=merged["reason_codes"],
            human_readable_message=self._format_message(merged),
            recoverable=merged.get("recoverable", True),
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