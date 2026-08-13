"""Bounded process-local chat history and completed-task summaries.

The chat history lives only inside the current process: ``/clear`` and
process exit never delete or rewrite structured project memory. Messages
are kept in strict insertion order and the oldest messages (or summaries)
are evicted deterministically when the configured bounds are exceeded.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChatMessage:
    """A single conversation message with a validated role and content."""

    role: str
    content: str


@dataclass(frozen=True)
class TaskSummary:
    """Summary of a completed task kept across messages."""

    task_id: str
    request: str
    outcome: str
    summary: str


class ChatHistory:
    """Bounded process-local history of messages and task summaries.

    ``clear_messages`` only clears the message list; completed-task
    summaries survive until ``max_summaries`` evicts the oldest ones.
    """

    _VALID_ROLES = frozenset({"user", "assistant"})

    def __init__(self, max_messages: int, max_summaries: int) -> None:
        if max_messages < 1:
            raise ValueError("max_messages must be at least 1")
        if max_summaries < 1:
            raise ValueError("max_summaries must be at least 1")
        self._max_messages = max_messages
        self._max_summaries = max_summaries
        self._messages: list[ChatMessage] = []
        self._summaries: list[TaskSummary] = []

    @property
    def max_messages(self) -> int:
        return self._max_messages

    @property
    def max_summaries(self) -> int:
        return self._max_summaries

    @property
    def messages(self) -> list[ChatMessage]:
        """Read-only snapshot of the current messages."""
        return list(self._messages)

    @property
    def summaries(self) -> list[TaskSummary]:
        """Read-only snapshot of the current task summaries."""
        return list(self._summaries)

    def add_message(self, role: str, content: str) -> None:
        """Append a message, evicting the oldest when over ``max_messages``."""
        if role not in self._VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(self._VALID_ROLES)}, got {role!r}")
        if not content.strip():
            raise ValueError("content must be a non-empty string")
        self._messages.append(ChatMessage(role=role, content=content))
        if len(self._messages) > self._max_messages:
            del self._messages[0]

    def add_summary(self, summary: TaskSummary) -> None:
        """Append a task summary, evicting the oldest when over ``max_summaries``."""
        self._summaries.append(summary)
        if len(self._summaries) > self._max_summaries:
            del self._summaries[0]

    def clear_messages(self) -> None:
        """Remove all messages; task summaries and structured memory are kept."""
        self._messages.clear()
