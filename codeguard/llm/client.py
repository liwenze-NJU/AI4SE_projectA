from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    def generate(self, session_id: str, context: str) -> "LLMResponse":
        """Send context to LLM and return a single response with exactly one Action.

        The request must carry the strict action protocol as a system message
        (see codeguard.llm.deepseek.ACTION_PROTOCOL_PROMPT): exactly one JSON
        object whose "action" is one of tool_call, assistant_message,
        request_user_input, or complete. The response must be parsed with the
        shared ActionParser; malformed or empty responses raise a redacted
        ValueError and are never treated as completions.
        """
        ...
