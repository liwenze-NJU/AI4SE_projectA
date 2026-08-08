from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    def generate(self, session_id: str, context: str) -> "LLMResponse":
        """Send context to LLM and return a single response with exactly one Action."""
        ...