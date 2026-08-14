"""Chat package: process-local conversation history and task summaries,
plus the interactive ChatSession coordinator and CLI event rendering."""

from codeguard.chat.history import ChatHistory, ChatMessage, TaskSummary
from codeguard.chat.session import ChatSession, CLIEventSink

__all__ = ["ChatHistory", "ChatMessage", "TaskSummary", "ChatSession", "CLIEventSink"]
