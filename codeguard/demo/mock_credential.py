"""Mock credential store for demo scenarios.

Returns a placeholder key so the demo never touches Windows
Credential Manager or real API keys.
"""


class MockCredentialStore:
    """Deterministic placeholder credentials (never real)."""

    def get(self, provider: str) -> str:
        return f"mock-key-{provider}"

    def status(self, provider: str) -> str:
        return "mock (not a real credential)"


mock_credential = MockCredentialStore()
