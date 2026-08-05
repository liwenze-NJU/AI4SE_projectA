from codeguard.memory.models import MemoryRecord


class ContextBuilder:
    """Builds structured LLM context from system prompt, task, memory, and tools."""

    def build(self, system_prompt: str, task_description: str,
              memory_records: list[MemoryRecord],
              tool_descriptions: list[str]) -> str:
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