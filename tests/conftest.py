import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def mock_llm():
    from codeguard.llm.mock import ScriptedMockLLM

    return ScriptedMockLLM(responses=[])


@pytest.fixture
def fake_clock():
    from codeguard.guardrail.approval import FakeClock

    return FakeClock()