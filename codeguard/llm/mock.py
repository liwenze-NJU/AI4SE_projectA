from codeguard.action import LLMResponse


class ScriptedMockLLM:
    """Deterministic mock LLM for offline testing.

    Returns pre-scripted LLMResponse objects in order.
    Raises IndexError when responses are exhausted.
    """

    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self._index = 0

    def generate(self, session_id: str, context: str) -> LLMResponse:
        if self._index >= len(self._responses):
            raise IndexError("No more scripted responses")
        response = self._responses[self._index]
        self._index += 1
        return response