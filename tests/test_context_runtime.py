"""Bounded runtime context tests (interactive CLI plan, Task 2)."""

from codeguard.context import ContextBuilder
from codeguard.secret import SecretRedactor


def test_runtime_context_priority_and_feedback():
    context = ContextBuilder(max_chars=4000, redactor=SecretRedactor()).build_runtime(
        system_constraints="Never escape workspace",
        task_request="Fix failing parser test",
        conversation_summaries=["Earlier: use pytest"],
        memory_records=[],
        tool_descriptions=["read_file(path)", "run_tests()"],
        latest_result="pytest failed at tests/test_parser.py:12",
        budget_summary="steps 1/20; tokens 100/10000",
    )
    assert context.index("Never escape workspace") < context.index("Fix failing parser test")
    assert "tests/test_parser.py:12" in context
    assert "read_file(path)" in context


def test_runtime_context_never_truncates_task_or_latest_error():
    context = ContextBuilder(max_chars=240, redactor=SecretRedactor()).build_runtime(
        system_constraints="SAFE",
        task_request="CURRENT-TASK",
        conversation_summaries=["old-" * 100],
        memory_records=[],
        tool_descriptions=["read_file(path)"],
        latest_result="LATEST-ERROR",
        budget_summary="steps 1/2",
    )
    assert "CURRENT-TASK" in context
    assert "LATEST-ERROR" in context
    assert len(context) <= 240


def test_runtime_context_redacts_external_strings():
    context = ContextBuilder(max_chars=4000, redactor=SecretRedactor()).build_runtime(
        system_constraints="Keep sk-secret-key safe",
        task_request="Fix auth using token=t0ken",
        conversation_summaries=["seen password=pw"],
        memory_records=[],
        tool_descriptions=["run_test(secret=sk-abc)"],
        latest_result="api_key=sk-other",
        budget_summary="steps 1/2",
    )
    assert "sk-secret-key" not in context
    assert "sk-abc" not in context
    assert "sk-other" not in context
    assert "t0ken" not in context
    assert "pw" not in context
