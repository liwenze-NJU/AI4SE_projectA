"""Process-local bounded chat history tests (interactive CLI plan, Task 2)."""

import dataclasses

import pytest

from codeguard.chat import ChatHistory, ChatMessage, TaskSummary


def test_clear_removes_messages_but_keeps_task_summaries():
    history = ChatHistory(max_messages=4, max_summaries=2)
    history.add_message("user", "fix auth")
    history.add_summary(TaskSummary("t1", "fix auth", "completed", "tests pass"))
    history.clear_messages()
    assert history.messages == []
    assert [s.task_id for s in history.summaries] == ["t1"]


def test_history_evicts_oldest_message_deterministically():
    history = ChatHistory(max_messages=2, max_summaries=2)
    history.add_message("user", "one")
    history.add_message("assistant", "two")
    history.add_message("user", "three")
    assert [m.content for m in history.messages] == ["two", "three"]


def test_add_message_rejects_invalid_roles():
    history = ChatHistory(max_messages=4, max_summaries=2)
    with pytest.raises(ValueError, match="role"):
        history.add_message("system", "not allowed")


def test_add_message_rejects_empty_content():
    history = ChatHistory(max_messages=4, max_summaries=2)
    with pytest.raises(ValueError, match="content"):
        history.add_message("user", "  ")


def test_history_evicts_oldest_summary_when_max_exceeded():
    history = ChatHistory(max_messages=4, max_summaries=2)
    history.add_summary(TaskSummary("t1", "first", "completed", "done"))
    history.add_summary(TaskSummary("t2", "second", "completed", "done"))
    history.add_summary(TaskSummary("t3", "third", "completed", "done"))
    assert [s.task_id for s in history.summaries] == ["t2", "t3"]


def test_chat_message_and_task_summary_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        ChatMessage(role="user", content="hi").role = "assistant"
    with pytest.raises(dataclasses.FrozenInstanceError):
        TaskSummary("t1", "req", "completed", "ok").task_id = "t2"


def test_history_read_only_properties_return_copies():
    history = ChatHistory(max_messages=4, max_summaries=2)
    history.add_message("user", "one")
    history.add_summary(TaskSummary("t1", "req", "completed", "ok"))
    messages = history.messages
    messages.clear()
    summaries = history.summaries
    summaries.clear()
    assert len(history.messages) == 1
    assert len(history.summaries) == 1
