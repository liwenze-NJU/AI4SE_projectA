from codeguard.action import LLMResponse


class ScriptedMockLLM:
    """Deterministic mock LLM for offline testing.

    Returns pre-scripted LLMResponse objects in order.
    Raises IndexError when responses are exhausted.
    """

    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self._index = 0
        # Every exact context passed to generate(), in call order (Task 4).
        self.received_contexts: list[str] = []

    def generate(self, session_id: str, context: str) -> LLMResponse:
        if self._index >= len(self._responses):
            raise IndexError("No more scripted responses")
        self.received_contexts.append(context)
        response = self._responses[self._index]
        self._index += 1
        return response