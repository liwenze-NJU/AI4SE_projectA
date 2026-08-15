from codeguard.memory.models import MemoryRecord
from codeguard.secret import SecretRedactor


class ContextBuilder:
    """Builds structured LLM context from system prompt, task, memory, and tools."""

    def __init__(self, max_chars: int = 4000,
                 redactor: SecretRedactor | None = None) -> None:
        if max_chars < 1:
            raise ValueError("max_chars must be at least 1")
        self._max_chars = max_chars
        self._redactor = redactor if redactor is not None else SecretRedactor()

    def build(self, system_prompt: str, task_description: str,
              memory_records: list[MemoryRecord] | None,
              tool_descriptions: list[str] | None) -> str:
        parts = []
        parts.append(system_prompt)
        parts.append(f"\n## Task\n{task_description}")

        if memory_records:
            parts.append("\n## Memory")
            for r in memory_records:
                parts.append(f"- [{r.type.value}] {r.content}")
        else:
            parts.append("\n## Memory\nNo relevant memory records.")

        if tool_descriptions:
            parts.append("\n## Available Tools")
            for t in tool_descriptions:
                parts.append(f"- {t}")
        else:
            parts.append("\n## Available Tools\nNo tools available.")

        return "\n".join(parts)

    def build_runtime(
        self,
        system_constraints: str,
        task_request: str,
        conversation_summaries: list[str],
        memory_records: list[MemoryRecord],
        tool_descriptions: list[str],
        latest_result: str,
        budget_summary: str,
        observations: list[str] | None = None,
    ) -> str:
        """Build a bounded runtime context for one agent decision.

        Named sections follow a fixed priority order: system constraints,
        current task, conversation summaries, trusted memory, tool
        descriptions, current-task observations, latest result, and
        budget. Every external string is redacted before inclusion.

        ``observations`` (T8-FIX7) carries several recent tool results of
        the CURRENT task so multi-file workflows see all relevant content
        in one decision. When the assembled context exceeds ``max_chars``,
        sections are cut from the bottom up: oldest conversation summaries
        first, then memory records, then tool descriptions, then the
        OLDEST observations. The system constraints, current task, latest
        result, and budget are mandatory and never dropped; if they alone
        exceed the limit the system constraints are truncated first, and a
        ``ValueError`` is raised when even the remaining mandatory fields
        cannot fit.
        """
        red = self._redactor.redact
        summaries = [red(s) for s in conversation_summaries]
        records = list(memory_records)
        tools = [red(t) for t in tool_descriptions]
        obs = [red(o) for o in (observations or [])]

        def _over(cur_obs):
            return self._is_over(red(system_constraints), red(task_request),
                                 summaries, records, tools,
                                 red(latest_result), red(budget_summary),
                                 cur_obs)

        while _over(obs) and summaries:
            del summaries[0]
        while _over(obs) and records:
            del records[0]
        while _over(obs) and tools:
            if len(tools[0]) > 1:
                tools[0] = tools[0][: len(tools[0]) // 2]
            else:
                del tools[0]
        # T8-FIX7: drop OLDEST observations first (newest kept).
        while _over(obs) and obs:
            del obs[0]

        context = self._assemble(red(system_constraints), red(task_request),
                                 summaries, records, tools,
                                 red(latest_result), red(budget_summary), obs)
        if len(context) <= self._max_chars:
            return context

        # Mandatory fields alone still exceed the limit: truncate the system
        # constraints first, keeping the complete task and latest result.
        constraints = red(system_constraints)
        slack = len(context) - self._max_chars
        constraints = constraints[: max(0, len(constraints) - slack)]
        context = self._assemble(constraints, red(task_request),
                                 [], [], [],
                                 red(latest_result), red(budget_summary), [])
        if len(context) > self._max_chars:
            raise ValueError(
                "Cannot fit mandatory runtime context (system constraints, "
                "task, latest result, budget) within max_chars"
            )
        return context

    def _is_over(self, constraints: str, task: str, summaries: list[str],
                 records: list[MemoryRecord], tools: list[str],
                 latest: str, budget: str,
                 observations: list[str] | None = None) -> bool:
        return len(self._assemble(constraints, task, summaries, records,
                                  tools, latest, budget,
                                  observations or [])) > self._max_chars

    def _assemble(self, constraints: str, task: str, summaries: list[str],
                  records: list[MemoryRecord], tools: list[str],
                  latest: str, budget: str,
                  observations: list[str] | None = None) -> str:
        parts = [
            f"## System Constraints\n{constraints}",
            f"## Task\n{task}",
        ]
        if summaries:
            parts.append("## Conversation")
            parts.extend(f"- {s}" for s in summaries)
        if records:
            parts.append("## Memory")
            parts.extend(
                f"- [{r.type.value}] {self._redactor.redact(r.content)}" for r in records
            )
        if tools:
            parts.append("## Available Tools")
            parts.extend(f"- {t}" for t in tools)
        if observations:
            parts.append("## Current Task Observations")
            parts.extend(f"- {o}" for o in observations)
        parts.append(f"## Latest Result\n{latest}")
        parts.append(f"## Budget\n{budget}")
        return "\n".join(parts)
