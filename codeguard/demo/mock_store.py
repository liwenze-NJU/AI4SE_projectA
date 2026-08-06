"""Mock memory store for demo scenarios.

In-memory only; no real persistence. Compatible shape with the
harness memory store but never touches disk.
"""


class MockMemoryStore:
    """Deterministic in-memory memory records."""

    def __init__(self):
        self._records: list[dict] = []

    def save(self, record: dict) -> None:
        self._records.append(dict(record))

    def list(self) -> list[dict]:
        return [dict(r) for r in self._records]


mock_store = MockMemoryStore()
