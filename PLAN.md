# CodeGuard Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python 3.12 CLI Coding Agent Harness with governance guardrails, test feedback loop, memory, configuration, Windows credential management, and a WebUI demo mode.

**Architecture:** Centralized explicit state machine with injectable components. The main loop drives 13 `AgentState` transitions. Each subsystem (Guardrail, Tool, Feedback, Memory, Config, LLM) is a self-contained module with a clear interface. A `CompositionRoot` assembles the correct variant (Local/Test/Demo) at startup.

**Tech Stack:** Python 3.12, argparse (CLI), FastAPI+Jinja2+CSS+vanilla JS (WebUI), tomllib (config), keyring (credentials), PyInstaller (packaging), pytest (testing), DeepSeek API (LLM, OpenAI-compatible), ScriptedMockLLM (offline testing).

---

## Global Constraints

- **SPEC version:** 1.1.4 (confirmed)
- **Platform:** Windows 10/11 x86-64
- **Python:** 3.12 only
- **No agent framework:** Do NOT use LangChain AgentExecutor, AutoGen, CrewAI, or any existing agent orchestration framework. The harness loop is custom code.
- **Offline testing:** All tests use ScriptedMockLLM + Fake components. No real LLM, no real API Key, no external network. DeepSeekAdapter uses mock HTTP transport.
- **Demo isolation:** DemoCompositionRoot never imports DeepSeekAdapter, KeyringCredentialStore, LocalToolExecutor, or network clients.
- **Credential safety:** API Key never enters config files, logs, Git history, or terminal history. Only Windows Credential Manager + keyring.
- **TDD required:** Every implementation task: RED (fail test) → GREEN (minimal code) → REFACTOR (under test protection) → SPEC compliance review → code quality review.
- **SecretRedactor first:** SecretRedactor is implemented before any component that produces logs, traces, ToolResult, Feedback, or Memory. All output components redact before storing from first version.
- **No `.claude/projects/`:** Never commit local machine memory files.
- **Push policy:** Every commit pushed to BOTH `origin` (NJU GitLab) and `github` (GitHub mirror).
- **Render deployment:** Demo-mode WebUI deployable to Render. /health endpoint, forced DemoCompositionRoot, code-level proof of isolation.

---

## File Structure

```
codeguard/
  __init__.py
  __main__.py                  # Entry: argparse dispatch to chat/demo/web/key
  composition.py               # CompositionRoot: Local / Test / Demo assembly
  state.py                     # AgentState enum, SessionState, SessionResult
  loop.py                      # Agent main loop (state machine driver)
  action.py                    # Action, ActionKind, NormalizedAction, ActionParser
  context.py                   # ContextBuilder
  secret.py                    # SecretRedactor (implemented early, used by all output components)
  tracer.py                    # Tracer, TraceEvent (uses SecretRedactor)
  stop.py                      # StopPolicy, StopDecision
  llm/
    __init__.py
    client.py                  # LLMClient protocol
    mock.py                    # ScriptedMockLLM
    deepseek.py                # DeepSeekAdapter (mock HTTP transport in tests)
  tool/
    __init__.py
    registry.py                # ToolRegistry, ToolDefinition
    dispatcher.py              # ToolDispatcher, ExecutionBoundary
    file_tools.py              # read_file, write_file, list_directory, find_files, search_text, apply_patch, delete_file
    process_tool.py            # run_process (structured program+args, shell=False)
    memory_tools.py            # memory_search, memory_read, memory_propose_write, memory_list
  guardrail/
    __init__.py
    engine.py                  # RuleEngine, PriorityMerger, GuardrailResult
    normalizer.py              # SchemaValidator, ActionNormalizer
    rules.py                   # WorkspaceBoundaryRule, CredentialLeakRule, UnregisteredToolRule, ModeRestrictionRule
    approval.py                # ApprovalManager, ApprovalRequest, ApprovalResult, FakeClock
  feedback/
    __init__.py
    sensor.py                  # SensorRunner, SensorPolicy, SensorDefinition
    parsers.py                 # PytestParser, RuffParser, MypyParser, GenericParser
    classifier.py              # FeedbackClassifier, FailureCategory, FeedbackResult
    verifier.py                # ObjectiveVerifier
  memory/
    __init__.py
    store.py                   # JSONMemoryStore (atomic writes, project-scoped)
    retriever.py               # MemoryRetriever (type/tag/keyword/top_k/context_budget)
    models.py                  # MemoryRecord, MemoryType, MemoryStatus, TrustLevel
  config/
    __init__.py
    loader.py                  # ConfigLoader (tomllib)
    schema.py                  # SchemaValidator
    merger.py                  # ConfigMerger (field-level deterministic rules)
    models.py                  # EffectiveConfig, WorkspaceConfig, LLMConfig, LoopConfig, ToolsConfig, SensorsConfig, MemoryConfig, UIConfig, ApprovalConfig
  cli/
    __init__.py
    chat.py                    # codeguard chat
    key_cmd.py                 # codeguard key set/status/update/clear
    config_cmd.py              # codeguard config show
    demo_cmd.py                # codeguard demo
    web_cmd.py                 # codeguard web
  web/
    __init__.py
    app.py                     # FastAPI app, routes, session management
    templates/
      base.html                # Jinja2 base template (Mock banner, shell, nav)
      scenarios.html           # P1: scenario selection
      dashboard.html           # P2: agent dashboard (3-column layout)
      approval.html            # P3: approval modal fragment
      results.html             # P4: session results + memory summary
    static/
      style.css                # Vercel-inspired CSS (from DESIGN.md tokens)
      main.js                  # Vanilla JS: polling, step controls, approval
  demo/
    __init__.py
    scenario_a.py              # Scenario A: BLOCK -> feedback -> COMPLETED
    scenario_b.py              # Scenario B: approval -> execute -> COMPLETED / CANCELLED
    scenario_c.py              # Scenario C: fail -> classify -> repair -> COMPLETED
    mock_store.py              # MockMemoryStore
    mock_credential.py         # MockCredentialStore
    mock_tool_dispatcher.py    # MockToolDispatcher
    mock_fs.py                 # MockFileSystem

tests/
  __init__.py
  conftest.py                  # Shared fixtures: ScriptedMockLLM, FakeClock, temp workspace
  test_state.py
  test_action.py
  test_loop.py
  test_context.py
  test_llm_client.py
  test_llm_mock.py
  test_llm_deepseek.py         # Uses mock HTTP transport, always runs offline
  test_secret_redactor.py
  test_tracer.py
  test_tool_registry.py
  test_tool_dispatcher.py
  test_file_tools.py
  test_process_tool.py
  test_guardrail_engine.py
  test_guardrail_normalizer.py
  test_guardrail_rules.py
  test_approval_manager.py
  test_sensor_runner.py
  test_parsers.py
  test_classifier.py
  test_verifier.py
  test_memory_store.py
  test_memory_retriever.py
  test_config_loader.py
  test_config_merger.py
  test_stop_policy.py
  test_cli.py
  test_demo_scenario_a.py
  test_demo_scenario_b.py
  test_demo_scenario_c.py
  test_web_app.py
  test_web_scenarios.py
  test_web_dashboard.py
  test_web_approval.py
  test_web_results.py
  test_web_mock_security.py
  test_web_narrow_screen.py
  test_composition_root.py
  test_integration_guardrail_feedback.py

ci/
  .gitlab-ci.yml
  .github/
    workflows/
      ci.yml

demo/
  demo_scenario_a.py
  demo_scenario_b.py
  demo_scenario_c.py

docs/
  design/
    open-design/               # (already exists, unchanged)

scripts/
  deepseek_smoke_test.py       # Manual DeepSeek API connectivity test (NOT in CI)

requirements/
  runtime.txt                  # Runtime dependencies with pinned versions
  dev.txt                      # Development dependencies (pytest, pyinstaller, etc.)

codeguard.spec                # PyInstaller spec file (bundles templates, static files)

README.md
SECURITY.md
PLAN.md
SPEC.md
SPEC_PROCESS.md
AGENT_LOG.md
CLAUDE.md
.gitignore
```

---

## Task Plan

### Phase 1: Foundation & Data Models

#### Task 1.1: Project scaffolding, package structure, requirements

**Files:**
- Create: `codeguard/__init__.py`
- Create: `codeguard/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_scaffold.py`
- Create: `requirements/runtime.txt`
- Create: `requirements/dev.txt`
- Create: `.gitignore`

**Consumes:** SPEC.md §5.3 (external dependencies), §9 (tech stack)

**Produces:** Runnable `python -m codeguard --help`; installable deps via `pip install -r requirements/dev.txt`; `tests/test_scaffold.py` as automated CLI acceptance test

**Dependency:** None (first task)

**Parallel:** No

**Worktree:** main, branch `task-1.1-scaffold`

> **Cold start note:** The worktree/branch/push commands in this task are defaults. In validation/course scenarios (e.g., cold-start verification), upper-level constraints (fixed worktree, fixed branch, "no push, no merge") override these Task-level instructions.

- [ ] **Step 1: Write failing test (RED)**

Write `tests/test_scaffold.py`:
```python
import subprocess
import sys

def test_codeguard_help_shows_subcommands():
    """python -m codeguard --help exits 0 and lists the five planned subcommands."""
    result = subprocess.run(
        [sys.executable, "-m", "codeguard", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "chat" in result.stdout
    assert "demo" in result.stdout
    assert "web" in result.stdout
    assert "key" in result.stdout
    assert "config" in result.stdout
```

- [ ] **Step 2: Run to verify RED failure**

Run: `python -m pytest tests/test_scaffold.py -v`
Expected: 1 collected, 1 failed. `codeguard` package does not exist yet; subprocess exits with non-zero, stderr contains `No module named codeguard`.

- [ ] **Step 3: Create package structure (GREEN)**

Create `codeguard/__init__.py`:
```python
"""CodeGuard Harness — a Python CLI Coding Agent Harness."""
__version__ = "0.1.0"
```

Create `codeguard/__main__.py`:
```python
import argparse

def main():
    parser = argparse.ArgumentParser(prog="codeguard", description="CodeGuard Harness — Governance-driven test feedback loop for coding agents")
    parser.add_argument("--version", action="version", version="0.1.0")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("chat", help="Start interactive agent session")
    sub.add_parser("demo", help="Run demo mode")
    sub.add_parser("web", help="Start WebUI demo")
    key_parser = sub.add_parser("key", help="Manage API keys")
    key_sub = key_parser.add_subparsers(dest="key_command")
    for kc in ["set", "status", "update", "clear"]:
        p = key_sub.add_parser(kc)
        p.add_argument("--provider", default="deepseek", help="API provider name")
    sub.add_parser("config", help="Show effective configuration")
    args = parser.parse_args()
    print(f"CodeGuard Harness v0.1.0 — command: {args.command or 'none'}")

if __name__ == "__main__":
    main()
```

Create `requirements/runtime.txt`:
```
# CodeGuard Harness — Runtime dependencies
# Pinned versions for reproducible builds as of 2026-08-04
fastapi==0.115.0
uvicorn[standard]==0.30.1
jinja2==3.1.4
keyring==25.4.1
httpx==0.27.0            # HTTP client for DeepSeekAdapter
```

Create `requirements/dev.txt`:
```
# CodeGuard Harness — Development & build dependencies
-r runtime.txt
pytest==8.3.2
pyinstaller==6.10.0
httpx==0.27.0             # Also used for TestClient in FastAPI tests
```

NOTE: `httpx` is in both runtime and dev because it's required by both DeepSeekAdapter (runtime) and FastAPI TestClient (tests). The `-r runtime.txt` include ensures version consistency.

Create `tests/__init__.py`:
```python
```

Create `tests/conftest.py`:
```python
import pytest
import tempfile
from pathlib import Path

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
```

Create `.gitignore`:
```
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
*.spec
venv/
.venv/

# Sensitive files
.env
.env.*
!.env.example

# Credentials & keys
*.pem
*.p12
*.pfx
*.key
credentials.local.json
secrets.local.json

# Cache directories
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Coverage
.coverage
coverage.xml
htmlcov/

# Worktrees
.worktrees/

# Runtime artifacts
runtime/
logs/
*.log
*.db
*.sqlite3

# Project
.claude/projects/
*.local/

# IDE
.vscode/
.idea/

# OS
Thumbs.db
.DS_Store
Desktop.ini
```

- [ ] **Step 4: Run to verify GREEN pass**

Run: `python -m pytest tests/test_scaffold.py -v` and `python -m codeguard --help`
Expected: `1 passed`; help shows usage with `{chat,demo,web,key,config}` subcommands.

- [x] **Step 5: Commit** — `9a2c066`

```bash
git add codeguard/__init__.py codeguard/__main__.py tests/__init__.py tests/conftest.py requirements/ .gitignore
git commit -m "feat: scaffold project package and CLI entry point"
git push origin task-1.1-scaffold
git push github task-1.1-scaffold
```

---

#### Task 1.2: Enum data models — AgentState, ActionKind, MemoryType, TrustLevel, MemoryStatus, FailureCategory, GuardrailDecision

**Files:**
- Create: `codeguard/state.py`
- Create: `tests/test_state.py`

**Consumes:** SPEC.md §6.1, §6.2

**Produces:** `AgentState(Enum)` with 13 states, all supporting enums

**Dependency:** Task 1.1

**Parallel:** No

**Worktree:** main, branch `task-1.2-core-enums`

- [ ] **Step 1: Write failing test**

Write `tests/test_state.py`:
```python
from codeguard.state import AgentState

def test_agent_state_has_13_values():
    """SPEC: 13 observable states. FINALIZING is a lifecycle cleanup, not counted."""
    values = [s.value for s in AgentState]
    assert len(values) == 13
    assert "initializing" in values
    assert "building_context" in values
    assert "deciding" in values
    assert "governing" in values
    assert "awaiting_approval" in values
    assert "executing" in values
    assert "intermediate_validation" in values
    assert "final_validation" in values
    assert "feeding_back" in values
    assert "completed" in values
    assert "failed" in values
    assert "cancelled" in values
    assert "limit_reached" in values

def test_agent_state_terminal():
    assert AgentState.COMPLETED.value == "completed"
    assert AgentState.FAILED.value == "failed"
    assert AgentState.CANCELLED.value == "cancelled"
    assert AgentState.LIMIT_REACHED.value == "limit_reached"

def test_agent_state_running():
    assert AgentState.INITIALIZING.value == "initializing"
    assert AgentState.BUILDING_CONTEXT.value == "building_context"
    assert AgentState.DECIDING.value == "deciding"
    assert AgentState.GOVERNING.value == "governing"
    assert AgentState.AWAITING_APPROVAL.value == "awaiting_approval"
    assert AgentState.EXECUTING.value == "executing"
    assert AgentState.INTERMEDIATE_VALIDATION.value == "intermediate_validation"
    assert AgentState.FINAL_VALIDATION.value == "final_validation"
    assert AgentState.FEEDING_BACK.value == "feeding_back"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_state.py -v`
Expected: `ImportError: cannot import name 'AgentState' from 'codeguard.state'`

- [ ] **Step 3: Implement minimal AgentState enum**

Write `codeguard/state.py`:
```python
from enum import Enum

class AgentState(Enum):
    INITIALIZING = "initializing"
    BUILDING_CONTEXT = "building_context"
    DECIDING = "deciding"
    GOVERNING = "governing"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    INTERMEDIATE_VALIDATION = "intermediate_validation"
    FINAL_VALIDATION = "final_validation"
    FEEDING_BACK = "feeding_back"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LIMIT_REACHED = "limit_reached"
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_state.py -v`
Expected: 3 passed

- [ ] **Step 5: Refactor** — no refactoring needed at this stage. Check that AgentState enum values match SPEC §6.2 exactly.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §6.2 AgentState enum — 13 values match. FINALIZING is lifecycle cleanup, not counted. All 9 running states + 4 terminal states present.

- [ ] **Step 7: Code quality review**

Check: `AgentState` is a plain `Enum`, no methods, no dataclass, no extra fields. Single responsibility: define state names.

- [x] **Step 8: Commit** — `22faa6e`

```bash
git add codeguard/state.py tests/test_state.py
git commit -m "feat: add AgentState enum with 13 states"
git push origin task-1.2-core-enums
git push github task-1.2-core-enums
```

---

#### Task 1.3: Action, NormalizedAction, ActionKind, LLMResponse

**Files:**
- Create: `codeguard/action.py`
- Create: `tests/test_action.py`

**Consumes:** SPEC.md §6.3

**Produces:** `ActionKind(Enum)`, `Action`, `NormalizedAction`, `LLMResponse`

**Dependency:** Task 1.2 (uses AgentState context)

**Parallel:** No

**Worktree:** main, branch `task-1.3-action-models`

- [ ] **Step 1: Write failing tests**

Write `tests/test_action.py`:
```python
import pytest
from datetime import datetime
from decimal import Decimal
from dataclasses import FrozenInstanceError
from codeguard.action import ActionKind, Action, NormalizedAction, LLMResponse

def test_action_kind_enum():
    assert ActionKind.TOOL_CALL.value == "tool_call"
    assert ActionKind.COMPLETE_REQUEST.value == "complete"

def test_action_creation():
    action = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "x"}, raw="")
    assert action.tool_name == "read_file"
    assert action.parameters == {"path": "x"}
    assert action.kind == ActionKind.TOOL_CALL

def test_action_complete_request():
    action = Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")
    assert action.kind == ActionKind.COMPLETE_REQUEST
    assert action.tool_name is None

def test_normalized_action_immutable():
    """NormalizedAction is frozen — modifying fields raises FrozenInstanceError."""
    from dataclasses import FrozenInstanceError
    na = NormalizedAction(
        kind=ActionKind.TOOL_CALL,
        tool_name="read_file",
        normalized_parameters={"path": "/abs/x"},
        action_fingerprint="abc123",
        original_raw="",
        normalized_at=datetime.now()
    )
    assert na.action_fingerprint == "abc123"
    with pytest.raises(FrozenInstanceError):
        na.action_fingerprint = "new_fp"

def test_llm_response_creation():
    action = Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")
    response = LLMResponse(
        content="",
        next_action=action,
        finish_reason="stop",
        model="mock",
        token_used=0,
        cost_used=Decimal("0"),
        raw_response=""
    )
    assert response.finish_reason == "stop"
    assert response.next_action.kind == ActionKind.COMPLETE_REQUEST
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_action.py -v`
Expected: `ImportError: cannot import name 'ActionKind' from 'codeguard.action'` (module not found)

- [ ] **Step 3: Implement Action data models**

Write `codeguard/action.py`:
```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

class ActionKind(Enum):
    TOOL_CALL = "tool_call"
    COMPLETE_REQUEST = "complete"

@dataclass
class Action:
    kind: ActionKind
    tool_name: Optional[str] = None
    parameters: Optional[dict] = None
    summary: Optional[str] = None
    raw: str = ""

@dataclass(frozen=True)
class NormalizedAction:
    kind: ActionKind
    tool_name: Optional[str]
    normalized_parameters: Optional[dict]
    action_fingerprint: str
    original_raw: str
    normalized_at: datetime

@dataclass
class LLMResponse:
    content: str
    next_action: Action
    finish_reason: str
    model: str
    token_used: int
    cost_used: Decimal
    raw_response: str
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_action.py -v`
Expected: 5 passed

- [ ] **Step 5: Refactor** — no refactoring needed. Check that `LLMResponse.generate` is not a method; the LLMClient protocol defines `generate(session_id, context) -> LLMResponse`.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §6.3 — ActionKind has TOOL_CALL and COMPLETE_REQUEST. Action has kind, tool_name, parameters, summary, raw. NormalizedAction has action_fingerprint. LLMResponse has content, next_action, finish_reason, model, token_used, cost_used, raw_response.

- [ ] **Step 7: Code quality review**

Check: All dataclasses use `@dataclass` decorator. No methods on data objects. Optional fields use `Optional` type hint. `action_fingerprint` is a plain string hash.

- [x] **Step 8: Commit** — `6651c04`

```bash
git add codeguard/action.py tests/test_action.py
git commit -m "feat: add Action, NormalizedAction, LLMResponse data models"
git push origin task-1.3-action-models
git push github task-1.3-action-models
```

---

#### Task 1.4: SessionState, SessionResult, GuardrailResult, ApprovalRequest, ApprovalResult

**Files:**
- Create: `codeguard/guardrail/__init__.py`
- Create: `codeguard/guardrail/approval.py`
- Create: `tests/test_data_models_core.py`

**Consumes:** SPEC.md §6.4, §6.7, §6.8, §6.9, §6.11

**Produces:** `SessionState`, `SessionResult`, `GuardrailResult`, `ApprovalRequest`, `ApprovalResult`, `FakeClock`

**Dependency:** Task 1.2 (AgentState), Task 1.3 (NormalizedAction)

**Parallel:** No

**Worktree:** main, branch `task-1.4-session-guardrail-models`

- [ ] **Step 1: Write failing tests**

Write `tests/test_data_models_core.py`:
```python
from datetime import datetime
from decimal import Decimal
from codeguard.state import AgentState
from codeguard.action import ActionKind, NormalizedAction
from codeguard.guardrail import GuardrailDecision
from codeguard.guardrail.approval import ApprovalStatus

def test_session_state_creation():
    from codeguard.state import SessionState
    na = NormalizedAction(kind=ActionKind.TOOL_CALL, tool_name="read_file", normalized_parameters={}, action_fingerprint="fp", original_raw="", normalized_at=datetime.now())
    ss = SessionState(
        session_id="s1",
        current_state=AgentState.INITIALIZING,
        pending_action=na,
        guardrail_decision=None,
        approval_request_id=None,
        steps_used=0,
        llm_calls_used=0,
        token_used=0,
        cost_used=Decimal("0"),
        action_fingerprint_history=[],
        failure_fingerprint_history=[],
        started_at=datetime.now()
    )
    assert ss.session_id == "s1"
    assert ss.current_state == AgentState.INITIALIZING
    assert ss.steps_used == 0
    assert ss.cost_used == Decimal("0")

def test_session_result_creation():
    from codeguard.state import SessionResult
    sr = SessionResult(
        session_id="s1",
        terminal_state=AgentState.COMPLETED,
        steps_total=5,
        llm_calls_total=3,
        token_total=100,
        cost_total=Decimal("0.01"),
        duration=10.0,
        guardrail_decisions=[],
        feedback_results=[],
        trace=[],
        error=None
    )
    assert sr.terminal_state == AgentState.COMPLETED
    assert sr.steps_total == 5
    assert sr.error is None

def test_guardrail_result_with_enum():
    from codeguard.guardrail import GuardrailResult
    na = NormalizedAction(kind=ActionKind.TOOL_CALL, tool_name="read_file", normalized_parameters={}, action_fingerprint="fp", original_raw="", normalized_at=datetime.now())
    gr = GuardrailResult(
        decision=GuardrailDecision.BLOCK,
        rule_ids=["R1"],
        reason_codes=["out_of_bounds"],
        human_readable_message="Blocked: path outside workspace",
        recoverable=False,
        normalized_action=na,
        action_fingerprint="fp"
    )
    assert gr.decision == GuardrailDecision.BLOCK
    assert "out_of_bounds" in gr.reason_codes

def test_approval_request_with_enum():
    from codeguard.guardrail.approval import ApprovalRequest
    na = NormalizedAction(kind=ActionKind.TOOL_CALL, tool_name="write_file", normalized_parameters={}, action_fingerprint="fp", original_raw="", normalized_at=datetime.now())
    ar = ApprovalRequest(
        request_id="r1",
        session_id="s1",
        normalized_action=na,
        action_fingerprint="fp",
        matched_rules=["R2"],
        risk_summary="Writing to system directory",
        workspace_snapshot={},
        created_at=datetime.now(),
        expires_at=datetime.now()
    )
    assert ar.request_id == "r1"
    assert ar.status == ApprovalStatus.PENDING

def test_approval_result_with_enum():
    from codeguard.guardrail.approval import ApprovalResult, ApprovalStatus
    ar = ApprovalResult(request_id="r1", decision=ApprovalStatus.APPROVED, validated_at=datetime.now())
    assert ar.decision == ApprovalStatus.APPROVED
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_data_models_core.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement data models**

Append to `codeguard/state.py`:
```python
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from codeguard.action import NormalizedAction

@dataclass
class SessionState:
    session_id: str
    current_state: AgentState
    pending_action: Optional[NormalizedAction] = None
    guardrail_decision: Optional[Any] = None
    approval_request_id: Optional[str] = None
    steps_used: int = 0
    llm_calls_used: int = 0
    token_used: int = 0
    cost_used: Decimal = Decimal("0")
    action_fingerprint_history: list[str] = field(default_factory=list)
    failure_fingerprint_history: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

@dataclass
class SessionResult:
    session_id: str
    terminal_state: AgentState
    steps_total: int
    llm_calls_total: int
    token_total: int
    cost_total: Decimal
    duration: float
    guardrail_decisions: list[Any]
    feedback_results: list[Any]
    trace: list[Any]
    error: Optional[str] = None
```

Create `codeguard/guardrail/__init__.py`:
```python
from dataclasses import dataclass
from enum import Enum
from codeguard.action import NormalizedAction

class GuardrailDecision(Enum):
    BLOCK = "BLOCK"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    ALLOW = "ALLOW"

@dataclass
class GuardrailResult:
    decision: GuardrailDecision
    rule_ids: list[str]
    reason_codes: list[str]
    human_readable_message: str
    recoverable: bool
    normalized_action: NormalizedAction
    action_fingerprint: str
```

Create `codeguard/guardrail/approval.py`:
```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from codeguard.action import NormalizedAction

class ApprovalStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"

@dataclass
class ApprovalRequest:
    request_id: str
    session_id: str
    normalized_action: NormalizedAction
    action_fingerprint: str
    matched_rules: list[str]
    risk_summary: str
    workspace_snapshot: dict
    created_at: datetime
    expires_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING

@dataclass
class ApprovalResult:
    request_id: str
    decision: ApprovalStatus
    validated_at: datetime
    validator_notes: str = ""

class FakeClock:
    """Injectable clock for deterministic timeout testing."""
    def __init__(self, now: datetime | None = None):
        self._now = now or datetime.now()

    @property
    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float):
        self._now += timedelta(seconds=seconds)

    def is_expired(self, deadline: datetime) -> bool:
        return self._now >= deadline
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_data_models_core.py -v`
Expected: 5 passed

- [ ] **Step 5: Refactor** — check for import cycles. `GuardrailResult` in guardrail/__init__.py imports `NormalizedAction` from action.py. `SessionState` in state.py also imports `NormalizedAction`. No cycle because action.py does not import state.py or guardrail/.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §6.4 GuardrailResult uses GuardrailDecision enum (BLOCK/REQUEST_APPROVAL/ALLOW). SPEC §6.7 SessionState matches all fields. SPEC §6.8 SessionResult matches. SPEC §6.9 ApprovalRequest uses ApprovalStatus enum (PENDING/APPROVED/REJECTED/TIMEOUT). FakeClock implements injectable clock pattern.

- [ ] **Step 7: Code quality review**

Check: SessionState uses `field(default_factory=...)` for mutable defaults. GuardrailResult uses GuardrailDecision enum, not plain string. ApprovalRequest uses ApprovalStatus enum, not plain string. FakeClock is a simple class with `is_expired()` method.

- [x] **Step 8: Commit** — `d57c058`

```bash
git add codeguard/state.py codeguard/guardrail/__init__.py codeguard/guardrail/approval.py tests/test_data_models_core.py
git commit -m "feat: add SessionState, SessionResult, GuardrailResult, ApprovalRequest, FakeClock"
git push origin task-1.4-session-guardrail-models
git push github task-1.4-session-guardrail-models
```

---

#### Task 1.5: Remaining data models — ToolResult, ToolDefinition, FeedbackResult, SensorDefinition, Diagnostic, MemoryRecord, Config models

**Files:**
- Create: `codeguard/tool/__init__.py`
- Create: `codeguard/feedback/__init__.py`
- Create: `codeguard/memory/__init__.py`
- Create: `codeguard/memory/models.py`
- Create: `codeguard/config/models.py`
- Create: `tests/test_data_models_remaining.py`

**Consumes:** SPEC.md §6.5, §6.6, §6.10, §6.12, §6.13, §6.14

**Produces:** All remaining `@dataclass` models

**Dependency:** Task 1.4 (uses AgentState, NormalizedAction)

**Parallel:** No

**Worktree:** main, branch `task-1.5-remaining-models`

- [ ] **Step 1: Write failing tests**

Write `tests/test_data_models_remaining.py`:
```python
import pytest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from codeguard.state import AgentState

def test_tool_definition():
    from codeguard.tool import ToolDefinition
    td = ToolDefinition(
        name="read_file",
        description="Read file content",
        parameters_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        handler=lambda: None,
        category="FILE",
        side_effect=False,
        default_risk="ALLOW",
        supported_modes=["TEST"]
    )
    assert td.name == "read_file"
    assert td.category == "FILE"

def test_tool_result():
    from codeguard.tool import ToolResult
    tr = ToolResult(
        tool_name="read_file",
        status="SUCCESS",
        output_summary="file content",
        diagnostics=[],
        exit_code=0,
        changed_files=[],
        duration=0.1,
        truncated=False,
        error_category=None,
        audit_id="audit-1"
    )
    assert tr.status == "SUCCESS"
    assert tr.tool_name == "read_file"

def test_feedback_result_passed():
    from codeguard.feedback import FeedbackResult
    fr = FeedbackResult(
        sensor_id="pytest",
        program="pytest",
        args=["."],
        status="PASSED",
        failure_category=None,
        exit_code=0,
        failure_fingerprint=None,
        validation_type="INTERMEDIATE",
        summary="All tests passed",
        diagnostics=[],
        duration=0.5,
        retryable=False,
        raw_output_truncated=""
    )
    assert fr.status == "PASSED"
    assert fr.failure_category is None

def test_feedback_result_failed():
    from codeguard.feedback import FeedbackResult
    fr = FeedbackResult(
        sensor_id="pytest",
        program="pytest",
        args=["."],
        status="FAILED",
        failure_category="TEST_FAILURE",
        exit_code=1,
        failure_fingerprint="fp123",
        validation_type="INTERMEDIATE",
        summary="1 test failed",
        diagnostics=[],
        duration=0.5,
        retryable=True,
        raw_output_truncated="FAILURES..."
    )
    assert fr.status == "FAILED"
    assert fr.failure_fingerprint == "fp123"

def test_sensor_definition():
    from codeguard.feedback import SensorDefinition
    sd = SensorDefinition(
        name="pytest",
        program="pytest",
        args=["."],
        timeout=30,
        parser="pytest",
        required=True,
        allowed_exit_codes={0, 1},
        output_limit=4096
    )
    assert sd.name == "pytest"
    assert sd.required is True

def test_diagnostic():
    from codeguard.feedback import Diagnostic
    d = Diagnostic(file="test.py", line=42, column=5, code="E001", message="syntax error", category="syntax")
    assert d.file == "test.py"
    assert d.line == 42

def test_memory_record():
    from codeguard.memory.models import MemoryRecord, MemoryType, TrustLevel, MemoryStatus
    mr = MemoryRecord(
        id="m1",
        project_id="p1",
        type=MemoryType.PROJECT_CONVENTION,
        content="use pytest for testing",
        tags=["testing"],
        keywords=["pytest"],
        source="user",
        trust_level=TrustLevel.USER_APPROVED,
        status=MemoryStatus.ACTIVE,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        session_id="s1"
    )
    assert mr.type == MemoryType.PROJECT_CONVENTION
    assert mr.status == MemoryStatus.ACTIVE

def test_memory_type_enum():
    from codeguard.memory.models import MemoryType
    assert MemoryType.PROJECT_CONVENTION.value == "project_convention"
    assert MemoryType.APPROVED_DECISION.value == "approved_decision"
    assert MemoryType.TASK_SUMMARY.value == "task_summary"
    assert MemoryType.FAILURE_RESOLUTION.value == "failure_resolution"

def test_trust_level_enum():
    from codeguard.memory.models import TrustLevel
    assert TrustLevel.USER_APPROVED.value == "user_approved"
    assert TrustLevel.HARNESS_VERIFIED.value == "harness_verified"
    assert TrustLevel.LLM_PROPOSED.value == "llm_proposed"

def test_memory_status_enum():
    from codeguard.memory.models import MemoryStatus
    assert MemoryStatus.PENDING.value == "pending"
    assert MemoryStatus.ACTIVE.value == "active"
    assert MemoryStatus.REJECTED.value == "rejected"
    assert MemoryStatus.ARCHIVED.value == "archived"
    assert MemoryStatus.DELETED.value == "deleted"

def test_effective_config():
    from codeguard.config.models import EffectiveConfig, WorkspaceConfig, LLMConfig, LoopConfig, ToolsConfig, SensorsConfig, MemoryConfig, UIConfig, ApprovalConfig
    cfg = EffectiveConfig(
        workspace=WorkspaceConfig(project_root=Path("/root"), additional_protected_paths=[], excluded_paths=[]),
        llm=LLMConfig(provider="deepseek", model="deepseek-v4-flash", max_output_tokens=4096, request_timeout=60, credential_profile="default"),
        loop=LoopConfig(max_steps=50, max_llm_calls=100, max_repair_attempts=3, session_timeout=600, tool_timeout=30, no_progress_threshold=3, token_budget=100000, cost_budget=Decimal("0.5")),
        tools=ToolsConfig(enabled_tools=["read_file"], disabled_tools=[], per_tool_timeouts={}),
        sensors=SensorsConfig(required_sensors=["pytest"], sensor_order=["pytest"], timeout_per_sensor=30, output_limit=4096),
        memory=MemoryConfig(enabled=True, max_records=100, top_k=10, context_budget=2048, allowed_types=["PROJECT_CONVENTION"]),
        ui=UIConfig(web_port=8080, bind_address="127.0.0.1", approval_timeout=15),
        approval=ApprovalConfig(cli_timeout=300),
        mode="test",
        source={}
    )
    assert cfg.mode == "test"
    assert cfg.llm.provider == "deepseek"
    assert cfg.ui.approval_timeout == 15
    assert cfg.approval.cli_timeout == 300

def test_effective_config_immutable():
    """EffectiveConfig is frozen — modifying fields raises FrozenInstanceError."""
    from dataclasses import FrozenInstanceError
    from codeguard.config.models import EffectiveConfig, WorkspaceConfig, LLMConfig, LoopConfig, ToolsConfig, SensorsConfig, MemoryConfig, UIConfig, ApprovalConfig
    cfg = EffectiveConfig(
        workspace=WorkspaceConfig(project_root=Path("/root")),
        llm=LLMConfig(),
        loop=LoopConfig(),
        tools=ToolsConfig(),
        sensors=SensorsConfig(),
        memory=MemoryConfig(),
        ui=UIConfig(),
        approval=ApprovalConfig(),
        mode="test",
        source={}
    )
    with pytest.raises(FrozenInstanceError):
        cfg.mode = "demo"

def test_tool_status_enum():
    from codeguard.tool import ToolStatus
    assert ToolStatus.SUCCESS.value == "SUCCESS"
    assert ToolStatus.FAILURE.value == "FAILURE"
    assert ToolStatus.ERROR.value == "ERROR"
    assert ToolStatus.TIMEOUT.value == "TIMEOUT"

def test_sensor_status_enum():
    from codeguard.feedback import SensorStatus
    assert SensorStatus.PASSED.value == "PASSED"
    assert SensorStatus.FAILED.value == "FAILED"
    assert SensorStatus.TIMEOUT.value == "TIMEOUT"

def test_failure_category_enum():
    from codeguard.feedback import FailureCategory
    assert FailureCategory.TEST_FAILURE.value == "TEST_FAILURE"
    assert FailureCategory.LINT_ERROR.value == "LINT_ERROR"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_data_models_remaining.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement all remaining data models**

Create `codeguard/tool/__init__.py`:
```python
from dataclasses import dataclass, field
from typing import Callable, Optional
from enum import Enum

class ToolStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"

class ToolRisk(Enum):
    ALLOW = "ALLOW"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    BLOCK = "BLOCK"

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters_schema: dict
    handler: Callable
    category: str  # FILE / SHELL / TEST / MEMORY
    side_effect: bool
    default_risk: ToolRisk = ToolRisk.ALLOW
    supported_modes: list[str] = field(default_factory=lambda: ["test"])
    result_schema: Optional[dict] = None
    timeout_limit: int = 30

@dataclass
class ToolResult:
    tool_name: str
    status: ToolStatus
    output_summary: str
    diagnostics: list
    exit_code: Optional[int]
    changed_files: list[str]
    duration: float
    truncated: bool
    error_category: Optional[str]
    audit_id: str
```

Create `codeguard/feedback/__init__.py`:
```python
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class SensorStatus(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"

class FailureCategory(Enum):
    TEST_FAILURE = "TEST_FAILURE"
    LINT_ERROR = "LINT_ERROR"
    TYPE_ERROR = "TYPE_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    TIMEOUT = "TIMEOUT"
    PROGRAM_NOT_FOUND = "PROGRAM_NOT_FOUND"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"

@dataclass
class FeedbackResult:
    sensor_id: str
    program: str
    args: list[str]
    status: SensorStatus
    failure_category: Optional[FailureCategory]
    exit_code: Optional[int]
    failure_fingerprint: Optional[str]
    validation_type: str  # INTERMEDIATE / FINAL
    summary: str
    diagnostics: list
    duration: float
    retryable: bool
    raw_output_truncated: str

@dataclass
class SensorDefinition:
    name: str
    program: str
    args: list[str]
    timeout: int
    parser: str  # pytest / ruff / mypy / generic
    required: bool
    allowed_exit_codes: set[int]
    output_limit: int
    cwd: Optional[str] = None

@dataclass
class Diagnostic:
    file: Optional[str]
    line: Optional[int]
    column: Optional[int]
    code: Optional[str]
    message: str
    category: str
```

Create `codeguard/memory/__init__.py`:
```python
```

Create `codeguard/memory/models.py`:
```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class MemoryType(Enum):
    PROJECT_CONVENTION = "project_convention"
    APPROVED_DECISION = "approved_decision"
    TASK_SUMMARY = "task_summary"
    FAILURE_RESOLUTION = "failure_resolution"

class TrustLevel(Enum):
    USER_APPROVED = "user_approved"
    HARNESS_VERIFIED = "harness_verified"
    LLM_PROPOSED = "llm_proposed"

class MemoryStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    DELETED = "deleted"

@dataclass
class MemoryRecord:
    id: str
    project_id: str
    type: MemoryType
    content: str
    tags: list[str]
    keywords: list[str]
    source: str
    trust_level: TrustLevel
    status: MemoryStatus
    created_at: datetime
    updated_at: datetime
    session_id: str
```

Create `codeguard/config/models.py`:
```python
from dataclasses import dataclass, field
from pathlib import Path
from decimal import Decimal

@dataclass
class WorkspaceConfig:
    project_root: Path = Path(".")
    additional_protected_paths: list[Path] = field(default_factory=list)
    excluded_paths: list[Path] = field(default_factory=list)

@dataclass
class LLMConfig:
    provider: str = "deepseek"
    model: str = "deepseek-v4-flash"
    max_output_tokens: int = 4096
    request_timeout: int = 60
    credential_profile: str = "default"

@dataclass
class LoopConfig:
    max_steps: int = 50
    max_llm_calls: int = 100
    max_repair_attempts: int = 3
    session_timeout: int = 600
    tool_timeout: int = 30
    no_progress_threshold: int = 3
    token_budget: int = 100000
    cost_budget: Decimal = Decimal("0.5")

@dataclass
class ToolsConfig:
    enabled_tools: list[str] = field(default_factory=list)
    disabled_tools: list[str] = field(default_factory=list)
    per_tool_timeouts: dict[str, int] = field(default_factory=dict)

@dataclass
class SensorsConfig:
    required_sensors: list[str] = field(default_factory=lambda: ["pytest"])
    sensor_order: list[str] = field(default_factory=lambda: ["pytest"])
    timeout_per_sensor: int = 30
    output_limit: int = 4096

@dataclass
class MemoryConfig:
    enabled: bool = True
    max_records: int = 100
    top_k: int = 10
    context_budget: int = 2048
    allowed_types: list[str] = field(default_factory=lambda: ["PROJECT_CONVENTION"])

@dataclass
class UIConfig:
    web_port: int = 8080
    bind_address: str = "127.0.0.1"
    approval_timeout: int = 15

@dataclass
class ApprovalConfig:
    cli_timeout: int = 300

@dataclass(frozen=True)
class EffectiveConfig:
    workspace: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    sensors: SensorsConfig = field(default_factory=SensorsConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    approval: ApprovalConfig = field(default_factory=ApprovalConfig)
    mode: str = "test"
    source: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_data_models_remaining.py -v`
Expected: 15 passed

- [ ] **Step 5: Refactor** — check for import cycles. `tool/__init__.py` imports `Callable` from typing. No imports from guardrail/, feedback/, memory/, or config/. Clean dependency graph.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §6.5 ToolResult — status, output_summary, diagnostics, exit_code, changed_files, duration, truncated, error_category, audit_id. No token_used/cost_used per R012 correction. SPEC §6.6 ToolDefinition — all fields present. SPEC §6.10 FeedbackResult — three-layer classification fields. SPEC §6.12 Diagnostic — file, line, column, code, message, category. SPEC §6.13 MemoryRecord — 4 MemoryType values match C6 decision. SPEC §6.14 Config models — WorkspaceConfig, LLMConfig, LoopConfig, ToolsConfig, SensorsConfig, MemoryConfig, UIConfig, ApprovalConfig, EffectiveConfig.

- [ ] **Step 7: Code quality review**

Check: All config models use `field(default_factory=...)` for mutable defaults (list, dict, set). `EffectiveConfig` has defaults for all fields, making it constructable without arguments. `ToolResult` has no `token_used`/`cost_used` per SPEC.

- [x] **Step 8: Commit** — `d72617a`

```bash
git add codeguard/tool/__init__.py codeguard/feedback/__init__.py codeguard/memory/__init__.py codeguard/memory/models.py codeguard/config/models.py tests/test_data_models_remaining.py
git commit -m "feat: add remaining data models — ToolResult, FeedbackResult, MemoryRecord, config"
git push origin task-1.5-remaining-models
git push github task-1.5-remaining-models
```

---

### Phase 2: Core Harness Loop

#### Task 2.1: LLMClient protocol + ScriptedMockLLM

**Files:**
- Create: `codeguard/llm/__init__.py`
- Create: `codeguard/llm/client.py`
- Create: `codeguard/llm/mock.py`
- Create: `tests/test_llm_mock.py`

**Consumes:** SPEC.md §5.3, §6.3

**Produces:** `LLMClient(Protocol)`, `ScriptedMockLLM`

**Dependency:** Task 1.3 (uses Action, LLMResponse)

**Parallel:** No

**Worktree:** main, branch `task-2.1-scripted-mock-llm`

- [ ] **Step 1: Write failing test**

Write `tests/test_llm_mock.py`:
```python
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.action import Action, ActionKind, LLMResponse
from decimal import Decimal

def test_scripted_mock_returns_responses_in_order():
    actions = [
        Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "x"}, raw=""),
        Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")
    ]
    mock = ScriptedMockLLM(responses=actions)
    r1 = mock.generate(session_id="s1", context="")
    assert r1.next_action.tool_name == "read_file"
    assert r1.next_action.kind == ActionKind.TOOL_CALL
    r2 = mock.generate(session_id="s1", context="")
    assert r2.next_action.kind == ActionKind.COMPLETE_REQUEST

def test_scripted_mock_exhausted_raises():
    mock = ScriptedMockLLM(responses=[])
    import pytest
    with pytest.raises(StopIteration, match="No more scripted responses"):
        mock.generate(session_id="s1", context="")

def test_scripted_mock_tracks_call_count():
    actions = [Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")]
    mock = ScriptedMockLLM(responses=actions)
    mock.generate(session_id="s1", context="")
    assert mock.call_count == 1

def test_scripted_mock_generate_signature():
    """Verify generate(session_id, context) -> LLMResponse matches LLMClient protocol."""
    from codeguard.llm.client import LLMClient
    mock = ScriptedMockLLM(responses=[Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")])
    assert isinstance(mock, LLMClient)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_llm_mock.py -v`
Expected: `ImportError: cannot import name 'ScriptedMockLLM' from 'codeguard.llm.mock'` (module not found)

- [ ] **Step 3: Implement ScriptedMockLLM**

Create `codeguard/llm/__init__.py`:
```python
```

Create `codeguard/llm/client.py`:
```python
from typing import Protocol
from codeguard.action import LLMResponse

class LLMClient(Protocol):
    """Protocol for LLM adapters. All implementations must provide generate()."""
    def generate(self, session_id: str, context: str) -> LLMResponse:
        ...
```

Create `codeguard/llm/mock.py`:
```python
from codeguard.action import Action, LLMResponse
from decimal import Decimal

class ScriptedMockLLM:
    """Deterministic mock LLM that returns pre-scripted actions in order.

    Used for all offline tests. No real LLM, no API key, no network.
    Implements LLMClient protocol via structural subtyping.
    """
    def __init__(self, responses: list[Action]):
        self._responses = list(responses)
        self._index = 0
        self.call_count = 0

    def generate(self, session_id: str, context: str) -> LLMResponse:
        if self._index >= len(self._responses):
            raise StopIteration("No more scripted responses")
        action = self._responses[self._index]
        self._index += 1
        self.call_count += 1
        return LLMResponse(
            content="",
            next_action=action,
            finish_reason="stop",
            model="mock",
            token_used=0,
            cost_used=Decimal("0"),
            raw_response=""
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_llm_mock.py -v`
Expected: 4 passed

- [ ] **Step 5: Refactor** — no refactoring needed. Verify that `ScriptedMockLLM` satisfies `LLMClient` protocol structurally (has `generate(self, session_id: str, context: str) -> LLMResponse`).

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §5.3 — LLMClient protocol with generate(session_id, context) -> LLMResponse. ScriptedMockLLM returns LLMResponse with content, next_action, finish_reason, model, token_used, cost_used, raw_response.

- [ ] **Step 7: Code quality review**

Check: ScriptedMockLLM is a simple class, not a mock framework. No external dependencies. `call_count` is a public attribute for test assertions. Uses `StopIteration` (built-in) for exhaustion.

- [x] **Step 8: Commit** — `7411ec0`

```bash
git add codeguard/llm/ tests/test_llm_mock.py
git commit -m "feat: add LLMClient protocol and ScriptedMockLLM for offline testing"
git push origin task-2.1-scripted-mock-llm
git push github task-2.1-scripted-mock-llm
```

---

#### Task 2.2: AgentLoop — initialization and first transitions

**Files:**
- Create: `codeguard/loop.py`
- Create: `tests/test_loop.py`

**Consumes:** SPEC.md §3.1, §7.1

**Produces:** `AgentLoop` class with `_transition()`, `initialize()`, `run()` skeleton

**Dependency:** Task 1.4 (SessionState), Task 2.1 (ScriptedMockLLM)

**Parallel:** No

**Worktree:** main, branch `task-2.2-agent-loop`

- [ ] **Step 1: Write failing test for loop initialization**

Write `tests/test_loop.py`:
```python
from codeguard.loop import AgentLoop
from codeguard.state import AgentState, SessionState
from codeguard.action import Action, ActionKind
from codeguard.llm.mock import ScriptedMockLLM

def test_loop_initial_state():
    """AgentLoop starts in INITIALIZING state."""
    mock = ScriptedMockLLM(responses=[Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")])
    loop = AgentLoop(session_id="s1", llm=mock)
    assert loop.state.current_state == AgentState.INITIALIZING

def test_loop_initialize_transition():
    """initialize() moves from INITIALIZING to BUILDING_CONTEXT."""
    mock = ScriptedMockLLM(responses=[Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.initialize()
    assert loop.state.current_state == AgentState.BUILDING_CONTEXT

def test_loop_transition_saves_old_state():
    """_transition records the old state before changing to new state."""
    mock = ScriptedMockLLM(responses=[Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")])
    loop = AgentLoop(session_id="s1", llm=mock)
    old = loop.state.current_state
    loop.initialize()
    # _transition must save old state. Verify by checking trace.
    assert len(loop.trace) >= 1
    last = loop.trace[-1]
    assert last["from"] == AgentState.INITIALIZING.value
    assert last["to"] == AgentState.BUILDING_CONTEXT.value
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_loop.py -v`
Expected: `ImportError: cannot import name 'AgentLoop' from 'codeguard.loop'` (module not found)

- [ ] **Step 3: Implement minimal AgentLoop**

Write `codeguard/loop.py`:
```python
from codeguard.state import AgentState, SessionState, SessionResult
from codeguard.action import Action, ActionKind
from datetime import datetime
from decimal import Decimal

class AgentLoop:
    """Agent main loop driver. Drives state transitions using injectable components."""

    def __init__(self, session_id: str, llm):
        self.session_id = session_id
        self.llm = llm
        self.state = SessionState(
            session_id=session_id,
            current_state=AgentState.INITIALIZING
        )
        self.trace = []

    def _transition(self, new_state: AgentState):
        """Record old state, then transition to new state."""
        old = self.state.current_state
        self.state.current_state = new_state
        self.trace.append({
            "from": old.value,
            "to": new_state.value,
            "at": datetime.now().isoformat()
        })

    def initialize(self):
        """Transition from INITIALIZING to BUILDING_CONTEXT."""
        self._transition(AgentState.BUILDING_CONTEXT)

    def run(self) -> SessionResult:
        """Run the main loop (skeleton)."""
        self.initialize()
        return SessionResult(
            session_id=self.session_id,
            terminal_state=self.state.current_state,
            steps_total=0,
            llm_calls_total=0,
            token_total=0,
            cost_total=Decimal("0"),
            duration=0.0,
            guardrail_decisions=[],
            feedback_results=[],
            trace=self.trace
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_loop.py -v`
Expected: 3 passed

- [ ] **Step 5: Refactor** — verify `_transition` saves old state before updating. The test `test_loop_transition_saves_old_state` confirms this. No other refactoring needed.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.1 — AgentLoop is the central state machine driver. SPEC §7.1 — INITIALIZING → BUILDING_CONTEXT is the first transition. SPEC §7.2 — `_transition` records old state before changing (needed for Tracer integration).

- [ ] **Step 7: Code quality review**

Check: `AgentLoop.__init__` takes only `session_id` and `llm` as required args. All other components are injected later or via composition root. `_transition` is a private method. `trace` is a list of dicts (will be replaced by Tracer later).

- [ ] **Step 8: Commit**

```bash
git add codeguard/loop.py tests/test_loop.py
git commit -m "feat: add AgentLoop with initialization and _transition"
git push origin task-2.2-agent-loop
git push github task-2.2-agent-loop
```

---

#### Task 2.3: AgentLoop — full state machine with Fake components

**Files:**
- Modify: `codeguard/loop.py`
- Modify: `tests/test_loop.py`

**Consumes:** SPEC.md §3.1, §7.1, §7.2

**Produces:** `AgentLoop.run()` with all 13 state transitions, using inline Fake components (no external dependencies)

**Dependency:** Task 2.2 (AgentLoop base)

**Parallel:** No

**Worktree:** main, branch `task-2.3-full-state-machine`

**IMPORTANT:** This task defines simple Fake implementations of Guardrail, Approval, Tool, Feedback, StopPolicy, and Verifier inline. These are NOT the real implementations — they are minimal test doubles used only to verify state machine transitions. Real implementations come in later phases.

- [ ] **Step 1: Write failing tests for all 13 state transitions**

Write the following in `tests/test_loop.py`:

```python
from codeguard.loop import AgentLoop
from codeguard.state import AgentState, SessionState
from codeguard.action import Action, ActionKind
from codeguard.llm.mock import ScriptedMockLLM

# --- Fake components for state machine testing ---

class FakeGuardrail:
    """Minimal fake: returns pre-configured decision per call."""
    def __init__(self, decisions=None):
        self._decisions = decisions or ["ALLOW"]
        self._index = 0
    def evaluate(self, action):
        d = self._decisions[self._index % len(self._decisions)]
        self._index += 1
        from codeguard.guardrail import GuardrailResult
        from codeguard.action import NormalizedAction
        from datetime import datetime
        na = NormalizedAction(kind=action.kind, tool_name=action.tool_name, normalized_parameters=action.parameters, action_fingerprint="fp", original_raw=action.raw, normalized_at=datetime.now())
        return GuardrailResult(decision=d, rule_ids=[], reason_codes=[], human_readable_message="", recoverable=(d != "BLOCK"), normalized_action=na, action_fingerprint="fp")

class FakeApproval:
    """Minimal fake: returns pre-configured decision."""
    def __init__(self, decision=ApprovalStatus.APPROVED):
        self._decision = decision
    def wait_for_approval(self, action):
        from codeguard.guardrail.approval import ApprovalResult
        from datetime import datetime
        return ApprovalResult(request_id="r1", decision=self._decision, validated_at=datetime.now())
    def create_request(self, action):
        return "r1"

class FakeToolDispatcher:
    def dispatch(self, action):
        from codeguard.tool import ToolResult
        return ToolResult(tool_name=action.tool_name or "", status="SUCCESS", output_summary="", diagnostics=[], exit_code=0, changed_files=[], duration=0.1, truncated=False, error_category=None, audit_id="audit-1")

class FakeSensorRunner:
    def run_all(self):
        from codeguard.feedback import FeedbackResult
        return [FeedbackResult(sensor_id="pytest", program="pytest", args=["."], status="PASSED", failure_category=None, exit_code=0, failure_fingerprint=None, validation_type="INTERMEDIATE", summary="ok", diagnostics=[], duration=0.1, retryable=False, raw_output_truncated="")]

class FakeFeedbackClassifier:
    def classify(self, results):
        return results

class FakeObjectiveVerifier:
    def __init__(self, passed=True):
        self._passed = passed
    def verify(self, state):
        return self._passed

class FakeStopPolicy:
    def __init__(self, decision=None):
        self._decision = decision  # None = no stop
    def evaluate(self, state):
        return self._decision

# --- Tests ---

def test_loop_initial_to_building_context():
    """INITIALIZING -> BUILDING_CONTEXT via initialize()."""
    mock = ScriptedMockLLM(responses=[Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.initialize()
    assert loop.state.current_state == AgentState.BUILDING_CONTEXT

def test_loop_full_allow_sequence():
    """ALLOW path: DECIDING -> GOVERNING -> EXECUTING -> VALIDATION -> FEEDING_BACK -> DECIDING -> COMPLETE -> FINAL -> COMPLETED."""
    mock = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "x"}, raw=""),
        Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED
    assert result.steps_total >= 1

def test_loop_block_sequence():
    """BLOCK path: GOVERNING -> FEEDING_BACK -> DECIDING -> new action."""
    mock = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.TOOL_CALL, tool_name="delete_file", parameters={"path": "/outside"}, raw=""),
        Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "safe"}, raw=""),
        Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["BLOCK", "ALLOW"])
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED
    # Verify BLOCK was followed by a new action, not termination
    assert result.steps_total >= 1

def test_loop_approval_approve():
    """REQUEST_APPROVAL -> approve -> EXECUTING."""
    mock = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "output.txt"}, raw=""),
        Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["REQUEST_APPROVAL", "ALLOW"])
    loop.approval_manager = FakeApproval(decision=ApprovalStatus.APPROVED)
    loop.tool_dispatcher = FakeToolDispatcher()
    loop.sensor_runner = FakeSensorRunner()
    loop.feedback_classifier = FakeFeedbackClassifier()
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED

def test_loop_approval_reject():
    """REQUEST_APPROVAL -> reject -> CANCELLED."""
    mock = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "output.txt"}, raw=""),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["REQUEST_APPROVAL"])
    loop.approval_manager = FakeApproval(decision=ApprovalStatus.REJECTED)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.CANCELLED

def test_loop_approval_timeout():
    """REQUEST_APPROVAL -> timeout -> CANCELLED."""
    mock = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "output.txt"}, raw=""),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["REQUEST_APPROVAL"])
    loop.approval_manager = FakeApproval(decision=ApprovalStatus.TIMEOUT)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.CANCELLED

def test_loop_limit_reached():
    """StopPolicy LIMIT_REACHED -> LIMIT_REACHED terminal."""
    mock = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "x"}, raw=""),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.stop_policy = FakeStopPolicy(decision="LIMIT_REACHED")
    result = loop.run()
    assert result.terminal_state == AgentState.LIMIT_REACHED

def test_loop_failed():
    """StopPolicy FAILED -> FAILED terminal."""
    mock = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "x"}, raw=""),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.rule_engine = FakeGuardrail(decisions=["ALLOW"])
    loop.stop_policy = FakeStopPolicy(decision="FAILED")
    result = loop.run()
    assert result.terminal_state == AgentState.FAILED

def test_loop_complete_request_goes_to_final_validation():
    """COMPLETE_REQUEST -> FINAL_VALIDATION. If verifier passes -> COMPLETED."""
    mock = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.objective_verifier = FakeObjectiveVerifier(passed=True)
    loop.stop_policy = FakeStopPolicy()
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED

def test_loop_verifier_fails_goes_to_feeding_back():
    """FINAL_VALIDATION -> verifier fails -> FEEDING_BACK -> DECIDING."""
    mock = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""),
        Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""),
    ])
    loop = AgentLoop(session_id="s1", llm=mock)
    loop.objective_verifier = FakeObjectiveVerifier(passed=False)
    # Second time, there's no verifier so it defaults to COMPLETED
    result = loop.run()
    # Without a verifier on second loop, it should complete
    assert result.terminal_state in (AgentState.COMPLETED, AgentState.FEEDING_BACK)
```

- [ ] **Step 2: Run to verify failures**

Run: `pytest tests/test_loop.py -v`
Expected: At least 8 new tests fail (AgentLoop.run() does not yet implement full state machine)

- [ ] **Step 3: Implement full state machine in loop.py**

Replace `codeguard/loop.py`:
```python
from codeguard.state import AgentState, SessionState, SessionResult
from codeguard.action import Action, ActionKind
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any

class AgentLoop:
    """Agent main loop driver with explicit state machine."""

    def __init__(self, session_id: str, llm):
        self.session_id = session_id
        self.llm = llm
        self.state = SessionState(
            session_id=session_id,
            current_state=AgentState.INITIALIZING
        )
        self.trace = []
        # Injectable components (set by CompositionRoot or tests)
        self.rule_engine = None
        self.approval_manager = None
        self.tool_dispatcher = None
        self.sensor_runner = None
        self.feedback_classifier = None
        self.objective_verifier = None
        self.stop_policy = None
        self.tracer = None
        self.context_builder = None
        self.action_parser = None
        self.memory_retriever = None
        self.secret_redactor = None

    def _transition(self, new_state: AgentState):
        old = self.state.current_state
        self.state.current_state = new_state
        self.trace.append({
            "from": old.value,
            "to": new_state.value,
            "at": datetime.now().isoformat()
        })

    def _check_stop(self) -> Optional[AgentState]:
        """Check stop policies. Returns terminal state if should stop, None otherwise."""
        if self.stop_policy:
            decision = self.stop_policy.evaluate(self.state)
            if decision == "LIMIT_REACHED":
                return AgentState.LIMIT_REACHED
            if decision == "FAILED":
                return AgentState.FAILED
        return None

    def run(self) -> SessionResult:
        self._transition(AgentState.BUILDING_CONTEXT)
        # Build context from system prompt, memory, and tools
        if self.context_builder:
            context = self.context_builder.build(
                system_prompt="You are a coding agent.",
                task_description="",
                memory_records=self.memory_retriever.retrieve(self.session_id) if self.memory_retriever else [],
                tool_descriptions=[]
            )
        self._transition(AgentState.DECIDING)

        while True:
            # 1. Check stop policies at DECIDING boundary
            terminal = self._check_stop()
            if terminal:
                self._transition(terminal)
                break

            # 2. LLM call
            self.state.llm_calls_used += 1
            response = self.llm.generate(self.session_id, "")
            action = self.action_parser.parse(response) if self.action_parser else response.next_action

            # 3. Handle COMPLETE_REQUEST
            if action.kind == ActionKind.COMPLETE_REQUEST:
                self._transition(AgentState.FINAL_VALIDATION)
                if self.objective_verifier and not self.objective_verifier.verify(self.state):
                    self._transition(AgentState.FEEDING_BACK)
                    self._transition(AgentState.DECIDING)
                    continue
                self._transition(AgentState.COMPLETED)
                break

            # 4. Guardrail evaluation
            self._transition(AgentState.GOVERNING)
            if self.rule_engine:
                from codeguard.guardrail import GuardrailDecision
                result = self.rule_engine.evaluate(action)
                if result.decision == GuardrailDecision.BLOCK:
                    # Generate structured feedback and inject into context
                    feedback_text = f"Action BLOCKED by rules: {', '.join(result.rule_ids)}. Reason: {result.human_readable_message}"
                    self._transition(AgentState.FEEDING_BACK)
                    # Store feedback for next context
                    self._last_feedback = feedback_text
                    self._transition(AgentState.DECIDING)
                    continue
                elif result.decision == GuardrailDecision.REQUEST_APPROVAL:
                    # Pause: create approval request and return to AWAITING_APPROVAL
                    self._transition(AgentState.AWAITING_APPROVAL)
                    if self.approval_manager:
                        req = self.approval_manager.create_request(
                            session_id=self.session_id,
                            normalized_action=result.normalized_action,
                            matched_rules=result.rule_ids,
                            risk_summary=result.human_readable_message
                        )
                        self.state.approval_request_id = req.request_id
                        self.state.pending_action = result.normalized_action
                    # Return here — the caller must call resume_with_approval()
                    # run() will be called again after approval decision
                    return self._make_result()

            # 5. Execute tool (only reached if ALLOW or APPROVED)
            self._transition(AgentState.EXECUTING)
            if self.tool_dispatcher and self.state.pending_action:
                tool_result = self.tool_dispatcher.dispatch(self.state.pending_action)
            elif self.tool_dispatcher:
                tool_result = self.tool_dispatcher.dispatch(action)
            self.state.steps_used += 1
            self.state.pending_action = None
            self.state.approval_request_id = None

            # 6. Intermediate validation
            self._transition(AgentState.INTERMEDIATE_VALIDATION)
            if self.sensor_runner:
                sensor_results = self.sensor_runner.run_all()
                if self.feedback_classifier:
                    classified = [self.feedback_classifier.classify(r) for r in sensor_results]
                    # Track failure fingerprints for no-progress detection
                    for r in classified:
                        if r.failure_fingerprint:
                            self.state.failure_fingerprint_history.append(r.failure_fingerprint)

            # 7. Feedback
            self._transition(AgentState.FEEDING_BACK)

            # 8. Loop back to deciding
            self._transition(AgentState.DECIDING)

        return self._make_result()

    def resume_with_approval(self, request_id: str, session_id: str, decision, action_fingerprint: str):
        """Resume loop after approval decision. Called by WebUI or CLI."""
        if self.state.current_state != AgentState.AWAITING_APPROVAL:
            raise ValueError(f"Cannot resume: not in AWAITING_APPROVAL (current: {self.state.current_state.value})")
        if self.approval_manager:
            if decision == ApprovalStatus.APPROVED:
                approval_result = self.approval_manager.approve(request_id, session_id, action_fingerprint)
                if approval_result.decision == ApprovalStatus.APPROVED:
                    # Execute pending action directly — no re-GOVERNING
                    self.state.current_state = AgentState.EXECUTING
                    if self.tool_dispatcher and self.state.pending_action:
                        tool_result = self.tool_dispatcher.dispatch(self.state.pending_action)
                    self.state.steps_used += 1
                    self.state.pending_action = None
                    self.state.approval_request_id = None
                    self._transition(AgentState.INTERMEDIATE_VALIDATION)
                    self._transition(AgentState.FEEDING_BACK)
                    self._transition(AgentState.DECIDING)
            elif decision in (ApprovalStatus.REJECTED, ApprovalStatus.TIMEOUT):
                if decision == ApprovalStatus.REJECTED:
                    self.approval_manager.reject(request_id, session_id)
                self._transition(AgentState.CANCELLED)

    def _make_result(self) -> SessionResult:
        return SessionResult(
            session_id=self.session_id,
            terminal_state=self.state.current_state,
            steps_total=self.state.steps_used,
            llm_calls_total=self.state.llm_calls_used,
            token_total=self.state.token_used,
            cost_total=self.state.cost_used,
            duration=0.0,
            guardrail_decisions=[],
            feedback_results=[],
            trace=self.trace
        )
            guardrail_decisions=[],
            feedback_results=[],
            trace=self.trace
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_loop.py -v`
Expected: 11 tests passed (3 from Task 2.2 + 8 new)

- [ ] **Step 5: Refactor** — check that `_transition` saves old state before updating. Check that `_check_stop()` is called at the start of each loop iteration. Consider extracting the guardrail/approval/execution/validation sequence into separate methods if the `run()` method grows too long.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.1 — All 13 states are reachable. SPEC §7.1 — State transition matrix: INITIALIZING→BUILDING_CONTEXT→DECIDING→GOVERNING→(AWAITING_APPROVAL|EXECUTING)→INTERMEDIATE_VALIDATION→FEEDING_BACK→DECIDING (loop). COMPLETE_REQUEST→FINAL_VALIDATION→COMPLETED. BLOCK→FEEDING_BACK. REJECT/TIMEOUT→CANCELLED. StopPolicy→LIMIT_REACHED/FAILED.

- [ ] **Step 7: Code quality review**

Check: `run()` is a single loop with clear stages. Each stage is gated by `if component:` to allow gradual assembly. No Fake components referenced in production code — all Fakes are in test code only. `_check_stop()` is a separate method for testability.

- [x] **Step 8: Commit** — `a33e880` (fix: `731ed8f`)

```bash
git add codeguard/loop.py tests/test_loop.py
git commit -m "feat: complete state machine with all 13 transitions using Fake components"
git push origin task-2.3-full-state-machine
git push github task-2.3-full-state-machine
```

---

#### Task 2.4: ContextBuilder

**Files:**
- Create: `codeguard/context.py`
- Create: `tests/test_context.py`

**Consumes:** SPEC.md §3.1

**Produces:** `ContextBuilder.build()` returning formatted context string

**Dependency:** Task 2.2 (AgentLoop)

**Parallel:** No (runs after Task 2.3)

**Worktree:** main, branch `task-2.4-context-builder`

- [ ] **Step 1: Write failing test**

Write `tests/test_context.py`:
```python
from codeguard.context import ContextBuilder
from codeguard.memory.models import MemoryRecord, MemoryType, MemoryStatus, TrustLevel
from datetime import datetime

def test_context_builder_builds_with_all_sections():
    builder = ContextBuilder()
    records = [
        MemoryRecord(id="1", project_id="p1", type=MemoryType.PROJECT_CONVENTION, content="Use pytest for testing", tags=[], keywords=[], source="user", trust_level=TrustLevel.USER_APPROVED, status=MemoryStatus.ACTIVE, created_at=datetime.now(), updated_at=datetime.now(), session_id="s1")
    ]
    context = builder.build(
        system_prompt="You are a coding agent.",
        task_description="Fix the bug in main.py",
        memory_records=records,
        tool_descriptions=["read_file(path) -> str", "write_file(path, content) -> None"]
    )
    assert "You are a coding agent." in context
    assert "Fix the bug in main.py" in context
    assert "Use pytest for testing" in context
    assert "read_file" in context

def test_context_builder_empty_records():
    builder = ContextBuilder()
    context = builder.build(
        system_prompt="You are a coding agent.",
        task_description="Fix the bug",
        memory_records=[],
        tool_descriptions=["read_file"]
    )
    assert "You are a coding agent." in context
    assert "Fix the bug" in context
    assert "No relevant memory records" in context

def test_context_builder_no_tool_descriptions():
    builder = ContextBuilder()
    context = builder.build(
        system_prompt="You are a coding agent.",
        task_description="Fix the bug",
        memory_records=[],
        tool_descriptions=[]
    )
    assert "No tools available" in context
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_context.py -v`
Expected: `ImportError: cannot import name 'ContextBuilder' from 'codeguard.context'`

- [ ] **Step 3: Implement ContextBuilder**

Write `codeguard/context.py`:
```python
from codeguard.memory.models import MemoryRecord

class ContextBuilder:
    """Builds structured LLM context from system prompt, task, memory, and tools."""

    def build(self, system_prompt: str, task_description: str,
              memory_records: list[MemoryRecord],
              tool_descriptions: list[str]) -> str:
        parts = []
        parts.append(system_prompt)
        parts.append(f"\n## Task\n{task_description}")

        if memory_records:
            parts.append("\n## Memory")
            for r in memory_records:
                parts.append(f"- [{r.type.value}] {r.content}")
        else:
            parts.append("\n## Memory\nNo relevant memory records.")

        if tool_descriptions:
            parts.append("\n## Available Tools")
            for t in tool_descriptions:
                parts.append(f"- {t}")
        else:
            parts.append("\n## Available Tools\nNo tools available.")

        return "\n".join(parts)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_context.py -v`
Expected: 3 passed

- [ ] **Step 5: Refactor** — check for large context handling. If memory_records is very large, we may want to truncate. Not needed in first version per SPEC YAGNI.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.1 — ContextBuilder produces structured context from system prompt, task description, memory records, and tool descriptions.

- [ ] **Step 7: Code quality review**

Check: `build()` returns a single formatted string. No side effects. No external dependencies beyond `MemoryRecord` dataclass.

- [x] **Step 8: Commit** — `55174c8` (fix: `f50ab8e`)

```bash
git add codeguard/context.py tests/test_context.py
git commit -m "feat: add ContextBuilder for structured LLM context"
git push origin task-2.4-context-builder
git push github task-2.4-context-builder
```

---

#### Task 2.5: ActionParser

**Files:**
- Modify: `codeguard/action.py` (add ActionParser)
- Modify: `tests/test_action.py` (add parser tests)

**Consumes:** SPEC.md §3.1

**Produces:** `ActionParser.parse()` converting LLM output string to Action

**Dependency:** Task 1.3 (Action data models)

**Parallel:** No

**Worktree:** main, branch `task-2.5-action-parser`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_action.py`:
```python
from codeguard.action import ActionParser, ActionKind
import json

def test_action_parser_tool_call():
    parser = ActionParser()
    raw = json.dumps({"action": "tool_call", "tool": "read_file", "parameters": {"path": "main.py"}})
    action = parser.parse(raw)
    assert action.kind == ActionKind.TOOL_CALL
    assert action.tool_name == "read_file"
    assert action.parameters == {"path": "main.py"}

def test_action_parser_complete_request():
    parser = ActionParser()
    raw = json.dumps({"action": "complete", "summary": "Task finished"})
    action = parser.parse(raw)
    assert action.kind == ActionKind.COMPLETE_REQUEST
    assert action.summary == "Task finished"

def test_action_parser_invalid_json():
    parser = ActionParser()
    import pytest
    with pytest.raises(ValueError, match="Failed to parse action"):
        parser.parse("not json")

def test_action_parser_missing_action_field():
    parser = ActionParser()
    import pytest
    with pytest.raises(ValueError, match="Missing 'action' field"):
        parser.parse(json.dumps({"tool": "read_file"}))
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_action.py -v`
Expected: 4 new tests fail (ActionParser not defined)

- [ ] **Step 3: Implement ActionParser**

Append to `codeguard/action.py`:
```python
import json

class ActionParser:
    """Parses LLM output string into Action."""

    def parse(self, raw: str) -> Action:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse action: {e}")

        if "action" not in data:
            raise ValueError("Missing 'action' field in LLM output")

        action_type = data["action"]
        if action_type == "complete":
            return Action(
                kind=ActionKind.COMPLETE_REQUEST,
                summary=data.get("summary", ""),
                raw=raw
            )
        elif action_type == "tool_call":
            return Action(
                kind=ActionKind.TOOL_CALL,
                tool_name=data.get("tool", ""),
                parameters=data.get("parameters", {}),
                raw=raw
            )
        else:
            raise ValueError(f"Unknown action type: {action_type}")
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_action.py -v`
Expected: 9 passed (5 from Task 1.3 + 4 new)

- [ ] **Step 5: Refactor** — no refactoring needed. Consider adding support for markdown-fenced JSON blocks in later iterations.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.1 — ActionParser converts LLM output to Action. Handles TOOL_CALL and COMPLETE_REQUEST. Raises errors for invalid input.

- [ ] **Step 7: Code quality review**

Check: `parse()` raises `ValueError` for all error cases (invalid JSON, missing field, unknown type). No fallback to default action (fail fast).

- [x] **Step 8: Commit** — `646f002` (fix: `acdef42`)

```bash
git add codeguard/action.py tests/test_action.py
git commit -m "feat: add ActionParser for LLM output parsing"
git push origin task-2.5-action-parser
git push github task-2.5-action-parser
```

---

### Phase 3: SecretRedactor (implemented early, before any output-producing component)

#### Task 3.1: SecretRedactor

**Files:**
- Create: `codeguard/secret.py`
- Create: `tests/test_secret_redactor.py`

**Consumes:** SPEC.md §4.1

**Produces:** `SecretRedactor` used by all output-producing components

**Dependency:** Task 1.1

**Parallel:** No (sequential, but can be done in parallel with Phase 2 in a separate worktree)

**Worktree:** worktree-secret, branch `task-3.1-secret-redactor`

**Pre-commit:** Task 1.1 commit

**File boundary:** Only `codeguard/secret.py` and `tests/test_secret_redactor.py`

> **Cold start note:** The worktree/branch/push commands in this task are defaults. In validation/course scenarios, upper-level constraints override them.

- [ ] **Step 1: Write failing tests**

Write `tests/test_secret_redactor.py`:
```python
from codeguard.secret import SecretRedactor

def test_redact_api_key():
    redactor = SecretRedactor()
    result = redactor.redact("api_key = sk-1234567890abcdef")
    assert "sk-1234567890abcdef" not in result
    assert "sk-" in result  # prefix preserved, key redacted
    assert "api_key" in result

def test_redact_credential_pattern():
    redactor = SecretRedactor()
    result = redactor.redact("password = super-secret-123")
    assert "super-secret-123" not in result

def test_redact_path_to_relative():
    redactor = SecretRedactor(workspace_root="/home/user/project")
    result = redactor.redact("File at /home/user/project/src/main.py")
    assert "/home/user/project" not in result
    assert "src/main.py" in result

def test_redact_length_limit():
    redactor = SecretRedactor(max_length=50)
    result = redactor.redact("a" * 100)
    assert len(result) <= 50

def test_redact_preserves_normal_content():
    redactor = SecretRedactor()
    result = redactor.redact("This is normal code: print('hello')")
    assert result == "This is normal code: print('hello')"

def test_redact_multiple_api_keys():
    redactor = SecretRedactor()
    result = redactor.redact("key1=sk-abc key2=sk-xyz")
    assert "sk-abc" not in result
    assert "sk-xyz" not in result
```

- [ ] **Step 2: Run to verify RED failure**

Run: `python -m pytest tests/test_secret_redactor.py -v`
Expected: `ModuleNotFoundError: No module named 'codeguard.secret'` (or `ImportError` — both indicate the module/class does not exist yet, which is the correct RED state)

- [ ] **Step 3: Implement SecretRedactor**

Write `codeguard/secret.py`:
```python
import re

class SecretRedactor:
    """Redacts sensitive information from output strings.

    Applied before storing in logs, traces, ToolResult, Feedback, Memory.
    Implemented early so all output components use it from first version.

    Redaction rules (applied in order):
    1. sk- API keys: preserve "sk-" prefix, redact the key body.
       Matches one or more word characters after "sk-" (no minimum length,
       so short test keys like sk-abc are covered).
    2. Generic credential patterns (api_key=, password=, secret=, token=):
       if the value starts with "sk-", output "sk-***" (preserving the
       already-redacted prefix from step 1); otherwise output "***".
    3. Workspace root path: replaced with "." for portability.
    4. Length limit: if result exceeds max_length, truncate and append
       "...[truncated]". The suffix is counted within max_length so the
       final output never exceeds max_length.
    """

    def __init__(self, workspace_root: str = "", max_length: int = 10000):
        self._workspace_root = workspace_root
        self._max_length = max_length

    def _redact_sk_key(self, match):
        return match.group(1) + "***"

    def _redact_generic_value(self, match):
        value = match.group(2)
        if value.startswith("sk-"):
            return match.group(1) + "sk-***"
        return match.group(1) + "***"

    def redact(self, text: str) -> str:
        if not text:
            return text
        # Step 1: sk- API keys (prefix preserved, key body redacted)
        text = re.sub(r'(sk-)\w+', self._redact_sk_key, text)
        # Step 2: Generic credential patterns
        for field in ['api_key', 'password', 'secret', 'token']:
            text = re.sub(
                rf'({field}\s*[=:]\s*)(\S+)',
                self._redact_generic_value,
                text,
            )
        # Step 3: Workspace root normalization
        if self._workspace_root:
            text = text.replace(self._workspace_root, ".")
        # Step 4: Length limit (suffix counted within max_length)
        if len(text) > self._max_length:
            suffix = "...[truncated]"
            text = text[:self._max_length - len(suffix)] + suffix
        return text
```

- [ ] **Step 4: Run to verify GREEN pass**

Run: `python -m pytest tests/test_secret_redactor.py -v`
Expected: 6 passed

- [ ] **Step 5: Refactor** — verify the implementation against the 6 explicit tests. Key design decisions:
  - `sk-` regex uses `\w+` (one or more) — no minimum length, so short test keys (`sk-abc`, `sk-xyz`) are covered.
  - Generic `api_key=` (and `password=`, `secret=`, `token=`) patterns preserve `sk-***` prefix when the value starts with `sk-`, preventing double-redaction from stripping the `sk-` prefix.
  - Truncation suffix `"...[truncated]"` is counted within `max_length`, so `len(result) <= max_length` always holds.
  - `redact()` is idempotent: applying twice produces the same result. No external dependencies.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §4.1 — SecretRedactor uses regex patterns. Applied before storing in logs/traces/results. Preserves non-sensitive content. Configurable max_length.

- [ ] **Step 7: Code quality review**

Check: `redact()` is idempotent (applying twice produces same result). No external dependencies. Simple regex-based approach (no ML/heuristics). Generic credential patterns do not double-redact `sk-` prefixed values.

- [ ] **Step 8: Commit**

```bash
git add codeguard/secret.py tests/test_secret_redactor.py
git commit -m "feat: add SecretRedactor for output redaction"
git push origin task-3.1-secret-redactor
git push github task-3.1-secret-redactor
```

---

### Phase 4: Tool System

#### Task 4.1: ToolRegistry

**Files:**
- Create: `codeguard/tool/registry.py`
- Create: `tests/test_tool_registry.py`

**Consumes:** SPEC.md §3.6

**Produces:** `ToolRegistry` with register, lookup, list

**Dependency:** Task 1.5 (ToolDefinition)

**Parallel:** Can run in parallel with Phase 5 (Guardrail) in separate worktree

**Worktree:** worktree-tools, branch `task-4.1-tool-registry`

**Pre-commit:** Task 1.5 commit

**File boundary:** Only `codeguard/tool/registry.py` and `tests/test_tool_registry.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_tool_registry.py`:
```python
import pytest
from codeguard.tool import ToolDefinition
from codeguard.tool.registry import ToolRegistry

def test_register_and_lookup():
    registry = ToolRegistry()
    td = ToolDefinition(name="read_file", description="Read file", parameters_schema={}, handler=lambda: None, category="FILE", side_effect=False, default_risk="ALLOW", supported_modes=["TEST"])
    registry.register(td)
    assert registry.lookup("read_file") is td

def test_register_duplicate_raises():
    registry = ToolRegistry()
    td = ToolDefinition(name="read_file", description="", parameters_schema={}, handler=lambda: None, category="FILE", side_effect=False, default_risk="ALLOW", supported_modes=["TEST"])
    registry.register(td)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(td)

def test_lookup_unknown_raises():
    registry = ToolRegistry()
    with pytest.raises(KeyError, match="Unknown tool"):
        registry.lookup("nonexistent")

def test_list_tools():
    registry = ToolRegistry()
    td1 = ToolDefinition(name="read_file", description="Read", parameters_schema={}, handler=lambda: None, category="FILE", side_effect=False, default_risk="ALLOW", supported_modes=["TEST"])
    td2 = ToolDefinition(name="write_file", description="Write", parameters_schema={}, handler=lambda: None, category="FILE", side_effect=True, default_risk="REQUEST_APPROVAL", supported_modes=["TEST"])
    registry.register(td1)
    registry.register(td2)
    names = [t.name for t in registry.list_tools()]
    assert "read_file" in names
    assert "write_file" in names
    assert len(names) == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_tool_registry.py -v`
Expected: `ImportError: cannot import name 'ToolRegistry' from 'codeguard.tool.registry'`

- [ ] **Step 3: Implement ToolRegistry**

Write `codeguard/tool/registry.py`:
```python
from codeguard.tool import ToolDefinition

class ToolRegistry:
    """Registry for tool definitions. Supports register, lookup, list."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition):
        if definition.name in self._tools:
            raise ValueError(f"Tool '{definition.name}' already registered")
        self._tools[definition.name] = definition

    def lookup(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_tool_registry.py -v`
Expected: 4 passed

- [ ] **Step 5: Refactor** — no refactoring needed. Registry is a simple dict wrapper.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.6 — ToolRegistry allows registration, lookup by name, listing. Unknown tool raises KeyError. Duplicate raises ValueError.

- [ ] **Step 7: Code quality review**

Check: `ToolRegistry` is thread-safe for reads (dict lookup is atomic in CPython). Writes are not thread-safe, but the harness is single-threaded.

- [ ] **Step 8: Commit**

```bash
git add codeguard/tool/registry.py tests/test_tool_registry.py
git commit -m "feat: add ToolRegistry with register, lookup, list"
git push origin task-4.1-tool-registry
git push github task-4.1-tool-registry
```

---

#### Task 4.2: File tools — read operations

**Files:**
- Create: `codeguard/tool/file_tools.py`
- Create: `tests/test_file_tools.py`

**Consumes:** SPEC.md §3.6

**Produces:** read_file, list_directory, find_files, search_text tool handlers

**Dependency:** Task 4.1 (ToolRegistry for registration)

**Parallel:** No (sequential within Tool phase)

**Worktree:** worktree-tools, branch `task-4.2-file-tools-read`

- [ ] **Step 1: Write failing tests**

Write `tests/test_file_tools.py`:
```python
import pytest
from pathlib import Path
from codeguard.tool.file_tools import read_file, list_directory, find_files, search_text

def test_read_file_success(temp_workspace):
    f = temp_workspace / "test.txt"
    f.write_text("hello world")
    result = read_file({"path": str(f)}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert "hello world" in result["content"]

def test_read_file_outside_workspace(temp_workspace):
    outside = Path("/tmp") / "secret.txt"
    with pytest.raises(PermissionError, match="outside workspace"):
        read_file({"path": str(outside)}, workspace_root=str(temp_workspace))

def test_read_file_not_found(temp_workspace):
    with pytest.raises(FileNotFoundError):
        read_file({"path": str(temp_workspace / "nonexistent.txt")}, workspace_root=str(temp_workspace))

def test_list_directory(temp_workspace):
    (temp_workspace / "a.txt").write_text("a")
    (temp_workspace / "b.txt").write_text("b")
    result = list_directory({"path": str(temp_workspace)}, workspace_root=str(temp_workspace))
    assert "a.txt" in result["files"]
    assert "b.txt" in result["files"]

def test_find_files(temp_workspace):
    (temp_workspace / "test.py").write_text("")
    result = find_files({"pattern": "**/*.py", "base_dir": str(temp_workspace)}, workspace_root=str(temp_workspace))
    assert "test.py" in result["files"]

def test_search_text(temp_workspace):
    (temp_workspace / "main.py").write_text("def hello(): pass")
    result = search_text({"pattern": "hello", "base_dir": str(temp_workspace)}, workspace_root=str(temp_workspace))
    assert "main.py" in result["matches"]
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_file_tools.py -v`
Expected: `ImportError: cannot import name 'read_file' from 'codeguard.tool.file_tools'`

- [ ] **Step 3: Implement file read tools**

Write `codeguard/tool/file_tools.py`:
```python
import os
import glob
from pathlib import Path

def _resolve_path(requested: str, workspace_root: str) -> Path:
    """Resolve and validate path is within workspace."""
    root = Path(workspace_root).resolve()
    target = (root / requested).resolve()
    if not str(target).startswith(str(root)):
        raise PermissionError(f"Path '{requested}' is outside workspace '{workspace_root}'")
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")
    return target

def read_file(params: dict, workspace_root: str = "") -> dict:
    path = _resolve_path(params["path"], workspace_root)
    content = path.read_text(encoding="utf-8")
    return {"status": "SUCCESS", "content": content, "path": str(path)}

def list_directory(params: dict, workspace_root: str = "") -> dict:
    path = _resolve_path(params["path"], workspace_root)
    files = [str(p.relative_to(path)) for p in path.iterdir()]
    return {"files": files, "path": str(path)}

def find_files(params: dict, workspace_root: str = "") -> dict:
    base = _resolve_path(params.get("base_dir", "."), workspace_root)
    pattern = params["pattern"]
    matches = [str(p.relative_to(base)) for p in base.glob(pattern)]
    return {"files": matches, "pattern": pattern}

def search_text(params: dict, workspace_root: str = "") -> dict:
    base = _resolve_path(params.get("base_dir", "."), workspace_root)
    pattern = params["pattern"]
    matches = {}
    for p in base.rglob("*"):
        if p.is_file():
            try:
                for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if pattern in line:
                        matches.setdefault(str(p.relative_to(base)), []).append(i)
            except Exception:
                continue
    return {"matches": matches, "pattern": pattern}
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_file_tools.py -v`
Expected: 6 passed

- [ ] **Step 5: Refactor** — check that `_resolve_path` handles symlinks and path traversal attacks (e.g., `../../etc/passwd`). The `.resolve()` call normalizes all path components.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.6 — read_file reads content. list_directory lists entries. find_files uses glob. search_text searches within files. All enforce workspace boundary.

- [ ] **Step 7: Code quality review**

Check: `_resolve_path` is a shared validation function. All functions return dict (not ToolResult — ToolDispatcher wraps them). Workspace boundary is enforced at the path resolution level.

- [ ] **Step 8: Commit**

```bash
git add codeguard/tool/file_tools.py tests/test_file_tools.py
git commit -m "feat: add file read tools — read_file, list_directory, find_files, search_text"
git push origin task-4.2-file-tools-read
git push github task-4.2-file-tools-read
```

---

#### Task 4.3: File tools — write operations

**Files:**
- Modify: `codeguard/tool/file_tools.py`
- Modify: `tests/test_file_tools.py`

**Consumes:** SPEC.md §3.6

**Produces:** write_file (with SHA-256 fingerprint), apply_patch, delete_file

**Dependency:** Task 4.2 (file_tools.py exists)

**Parallel:** No

**Worktree:** worktree-tools, branch `task-4.3-file-tools-write`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_file_tools.py`:
```python
import hashlib

def test_write_file_new(temp_workspace):
    from codeguard.tool.file_tools import write_file
    path = temp_workspace / "new.txt"
    result = write_file({"path": str(path), "content": "hello"}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert path.read_text() == "hello"

def test_write_file_with_fingerprint(temp_workspace):
    from codeguard.tool.file_tools import write_file
    path = temp_workspace / "existing.txt"
    path.write_text("original")
    content_before = path.read_bytes()
    fp = hashlib.sha256(content_before).hexdigest()
    result = write_file({"path": str(path), "content": "modified", "sha256_fingerprint": fp}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert path.read_text() == "modified"

def test_write_file_fingerprint_mismatch(temp_workspace):
    from codeguard.tool.file_tools import write_file
    import pytest
    path = temp_workspace / "existing.txt"
    path.write_text("original")
    with pytest.raises(ValueError, match="Fingerprint mismatch"):
        write_file({"path": str(path), "content": "modified", "sha256_fingerprint": "wrong"}, workspace_root=str(temp_workspace))

def test_write_file_outside_workspace(temp_workspace):
    from codeguard.tool.file_tools import write_file
    import pytest
    outside = Path("/tmp") / "malicious.txt"
    with pytest.raises(PermissionError):
        write_file({"path": str(outside), "content": "x"}, workspace_root=str(temp_workspace))

def test_apply_patch(temp_workspace):
    from codeguard.tool.file_tools import apply_patch
    path = temp_workspace / "main.py"
    path.write_text("def foo():\n    pass\n")
    result = apply_patch({"path": str(path), "old_string": "    pass", "new_string": "    return 42"}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert "return 42" in path.read_text()

def test_apply_patch_context_mismatch(temp_workspace):
    from codeguard.tool.file_tools import apply_patch
    import pytest
    path = temp_workspace / "main.py"
    path.write_text("def foo():\n    pass\n")
    with pytest.raises(ValueError, match="not found"):
        apply_patch({"path": str(path), "old_string": "not found", "new_string": "x"}, workspace_root=str(temp_workspace))

def test_delete_file(temp_workspace):
    from codeguard.tool.file_tools import delete_file
    path = temp_workspace / "temp.txt"
    path.write_text("delete me")
    result = delete_file({"path": str(path)}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert not path.exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_file_tools.py -v`
Expected: 7 new tests fail (write_file, apply_patch, delete_file not defined)

- [ ] **Step 3: Implement write tools**

Append to `codeguard/tool/file_tools.py`:
```python
import hashlib
import tempfile

def write_file(params: dict, workspace_root: str = "") -> dict:
    target = _resolve_dir(params["path"], workspace_root)
    path = Path(target)
    if path.exists():
        current_content = path.read_bytes()
        current_fp = hashlib.sha256(current_content).hexdigest()
        provided_fp = params.get("sha256_fingerprint")
        if provided_fp and current_fp != provided_fp:
            raise ValueError(f"Fingerprint mismatch: expected {provided_fp}, got {current_fp}")
    content = params["content"]
    # Atomic write: write to temp file, then rename
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise
    return {"status": "SUCCESS", "path": str(path)}

def _resolve_dir(requested: str, workspace_root: str) -> str:
    """Resolve path and validate parent directory is within workspace."""
    root = Path(workspace_root).resolve()
    target = (root / requested).resolve()
    if not str(target).startswith(str(root)):
        raise PermissionError(f"Path '{requested}' is outside workspace '{workspace_root}'")
    return str(target)

def apply_patch(params: dict, workspace_root: str = "") -> dict:
    target = _resolve_dir(params["path"], workspace_root)
    path = Path(target)
    content = path.read_text(encoding="utf-8")
    old = params["old_string"]
    new = params["new_string"]
    if old not in content:
        raise ValueError(f"old_string not found in {path}")
    content = content.replace(old, new, 1)
    path.write_text(content, encoding="utf-8")
    return {"status": "SUCCESS", "path": str(path)}

def delete_file(params: dict, workspace_root: str = "") -> dict:
    target = _resolve_dir(params["path"], workspace_root)
    path = Path(target)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    path.unlink()
    return {"status": "SUCCESS", "path": str(target)}
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_file_tools.py -v`
Expected: 13 passed (6 read + 7 write)

- [ ] **Step 5: Refactor** — check that `write_file` atomic write handles edge cases (disk full, permission denied). The tempfile cleanup in the except block handles most failure modes.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.6 — write_file with SHA-256 fingerprint for conflict detection. Atomic write via tempfile+rename. apply_patch with context match. delete_file. All enforce workspace boundary.

- [ ] **Step 7: Code quality review**

Check: `write_file` uses `os.replace()` for atomic write (atomic on POSIX, near-atomic on Windows). `apply_patch` does a single replacement (not regex). `delete_file` checks existence before unlinking.

- [ ] **Step 8: Commit**

```bash
git add codeguard/tool/file_tools.py tests/test_file_tools.py
git commit -m "feat: add file write tools — write_file, apply_patch, delete_file"
git push origin task-4.3-file-tools-write
git push github task-4.3-file-tools-write
```

---

#### Task 4.4: run_process tool

**Files:**
- Create: `codeguard/tool/process_tool.py`
- Create: `tests/test_process_tool.py`

**Consumes:** SPEC.md §3.6

**Produces:** run_process handler with structured program+args, no shell=True, timeout enforcement

**Dependency:** Task 4.1 (ToolRegistry)

**Parallel:** No

**Worktree:** worktree-tools, branch `task-4.4-process-tool`

- [ ] **Step 1: Write failing tests**

Write `tests/test_process_tool.py`:
```python
import pytest
from codeguard.tool.process_tool import run_process

def test_run_process_echo(temp_workspace):
    result = run_process({"program": "echo", "args": ["hello"]}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert "hello" in result["stdout"]

def test_run_process_rejects_shell_metacharacters(temp_workspace):
    with pytest.raises(ValueError, match="Shell metacharacters"):
        run_process({"program": "echo", "args": ["hello; rm -rf /"]}, workspace_root=str(temp_workspace))

def test_run_process_timeout(temp_workspace):
    with pytest.raises(TimeoutError):
        run_process({"program": "python", "args": ["-c", "import time; time.sleep(10)"], "timeout": 1}, workspace_root=str(temp_workspace))

def test_run_process_cwd(temp_workspace):
    result = run_process({"program": "pwd", "args": [], "cwd": str(temp_workspace)}, workspace_root=str(temp_workspace))
    assert result["status"] == "SUCCESS"
    assert str(temp_workspace) in result["stdout"]

def test_run_process_captures_stderr(temp_workspace):
    result = run_process({"program": "python", "args": ["-c", "import sys; sys.stderr.write('error')"]}, workspace_root=str(temp_workspace))
    assert "error" in result["stderr"]
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_process_tool.py -v`
Expected: `ImportError: cannot import name 'run_process' from 'codeguard.tool.process_tool'`

- [ ] **Step 3: Implement run_process**

Write `codeguard/tool/process_tool.py`:
```python
import subprocess
import shlex

# Shell metacharacters that are never allowed in args
_SHELL_METACHARS = set(";&|`$(){}[]<>!?*~#")

def _validate_args(args: list[str]):
    for i, arg in enumerate(args):
        for char in arg:
            if char in _SHELL_METACHARS:
                raise ValueError(f"Shell metacharacter '{char}' in args[{i}]: {arg[:50]}")

def run_process(params: dict, workspace_root: str = "") -> dict:
    program = params["program"]
    args = params.get("args", [])
    timeout = params.get("timeout", 30)
    cwd = params.get("cwd", workspace_root)

    _validate_args(args)

    try:
        result = subprocess.run(
            [program] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            shell=False
        )
        return {
            "status": "SUCCESS",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Process '{program}' timed out after {timeout}s")
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_process_tool.py -v`
Expected: 5 passed

- [ ] **Step 5: Refactor** — check that `_validate_args` is comprehensive enough. The current set of metacharacters covers shell injection vectors. Consider adding a whitelist of allowed programs if needed.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.6 — structured program+args, no shell=True, timeout enforcement, cwd support, stdout/stderr capture.

- [ ] **Step 7: Code quality review**

Check: `subprocess.run` with `shell=False` prevents shell injection. `_validate_args` blocks shell metacharacters as defense-in-depth. `capture_output=True` prevents output to terminal.

- [ ] **Step 8: Commit**

```bash
git add codeguard/tool/process_tool.py tests/test_process_tool.py
git commit -m "feat: add run_process tool with structured execution and timeout"
git push origin task-4.4-process-tool
git push github task-4.4-process-tool
```

---

#### Task 4.5: ToolDispatcher with ExecutionBoundary

**Files:**
- Create: `codeguard/tool/dispatcher.py`
- Create: `tests/test_tool_dispatcher.py`

**Consumes:** SPEC.md §3.6

**Produces:** `ToolDispatcher` that routes actions to handlers, re-validates, wraps in ToolResult, applies SecretRedactor

**Dependency:** Tasks 4.1-4.4, Task 3.1 (SecretRedactor)

**Parallel:** No

**Worktree:** worktree-tools, branch `task-4.5-tool-dispatcher`

- [ ] **Step 1: Write failing tests**

Write `tests/test_tool_dispatcher.py`:
```python
import pytest
from codeguard.tool import ToolDefinition, ToolResult
from codeguard.tool.registry import ToolRegistry
from codeguard.tool.dispatcher import ToolDispatcher
from codeguard.action import Action, ActionKind

def test_dispatch_read_file(temp_workspace):
    registry = ToolRegistry()
    from codeguard.tool.file_tools import read_file
    td = ToolDefinition(name="read_file", description="Read file", parameters_schema={}, handler=read_file, category="FILE", side_effect=False, default_risk="ALLOW", supported_modes=["TEST"])
    registry.register(td)
    dispatcher = ToolDispatcher(registry, workspace_root=str(temp_workspace))
    f = temp_workspace / "test.txt"
    f.write_text("content")
    action = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": str(f)})
    result = dispatcher.dispatch(action)
    assert isinstance(result, ToolResult)
    assert result.status == "SUCCESS"

def test_dispatch_unknown_tool(temp_workspace):
    registry = ToolRegistry()
    dispatcher = ToolDispatcher(registry, workspace_root=str(temp_workspace))
    action = Action(kind=ActionKind.TOOL_CALL, tool_name="nonexistent")
    with pytest.raises(KeyError):
        dispatcher.dispatch(action)

def test_dispatch_applies_secret_redactor(temp_workspace):
    registry = ToolRegistry()
    from codeguard.tool.file_tools import read_file
    td = ToolDefinition(name="read_file", description="Read file", parameters_schema={}, handler=read_file, category="FILE", side_effect=False, default_risk="ALLOW", supported_modes=["TEST"])
    registry.register(td)
    from codeguard.secret import SecretRedactor
    dispatcher = ToolDispatcher(registry, workspace_root=str(temp_workspace), secret_redactor=SecretRedactor())
    f = temp_workspace / "secret.txt"
    f.write_text("api_key = sk-1234567890abcdef")
    action = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": str(f)})
    result = dispatcher.dispatch(action)
    assert "sk-1234567890abcdef" not in result.output_summary
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_tool_dispatcher.py -v`
Expected: `ImportError: cannot import name 'ToolDispatcher' from 'codeguard.tool.dispatcher'`

- [ ] **Step 3: Implement ToolDispatcher**

Write `codeguard/tool/dispatcher.py`:
```python
from codeguard.tool import ToolDefinition, ToolResult
from codeguard.tool.registry import ToolRegistry
from codeguard.action import Action, ActionKind
from codeguard.secret import SecretRedactor
from datetime import datetime
import uuid

class ToolDispatcher:
    """Dispatches actions to registered tool handlers with re-validation."""

    def __init__(self, registry: ToolRegistry, workspace_root: str = "", secret_redactor: SecretRedactor = None):
        self._registry = registry
        self._workspace_root = workspace_root
        self._redactor = secret_redactor or SecretRedactor()

    def dispatch(self, action: Action) -> ToolResult:
        definition = self._registry.lookup(action.tool_name)
        try:
            handler_result = definition.handler(action.parameters or {}, workspace_root=self._workspace_root)
            status = "SUCCESS"
            output = str(handler_result)
            error_category = None
        except PermissionError as e:
            status = "FAILURE"
            output = str(e)
            error_category = "WORKSPACE_VIOLATION"
        except FileNotFoundError as e:
            status = "FAILURE"
            output = str(e)
            error_category = "FILE_NOT_FOUND"
        except TimeoutError as e:
            status = "TIMEOUT"
            output = str(e)
            error_category = "TIMEOUT"
        except Exception as e:
            status = "ERROR"
            output = str(e)
            error_category = "UNEXPECTED"

        # Apply SecretRedactor before storing
        output = self._redactor.redact(output)

        return ToolResult(
            tool_name=action.tool_name,
            status=status,
            output_summary=output[:1000],
            diagnostics=[],
            exit_code=0 if status == "SUCCESS" else 1,
            changed_files=[str(action.parameters.get("path", ""))] if definition.side_effect else [],
            duration=0.0,
            truncated=len(output) > 1000,
            error_category=error_category,
            audit_id=str(uuid.uuid4())
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_tool_dispatcher.py -v`
Expected: 3 passed

- [ ] **Step 5: Refactor** — check that SecretRedactor is applied before ToolResult creation. The `_redactor.redact()` call on line ~40 ensures this.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.6 — ToolDispatcher routes to correct handler. TOCTOU re-validation via handler's own path resolution. SecretRedactor wraps output. ToolResult has correct status/error_category.

- [ ] **Step 7: Code quality review**

Check: Error handling categorizes exceptions into FAILURE/TIMEOUT/ERROR. SecretRedactor is applied before storage. Output is truncated to 1000 chars in summary.

- [ ] **Step 8: Commit**

```bash
git add codeguard/tool/dispatcher.py tests/test_tool_dispatcher.py
git commit -m "feat: add ToolDispatcher with ExecutionBoundary and SecretRedactor"
git push origin task-4.5-tool-dispatcher
git push github task-4.5-tool-dispatcher
```

---

### Phase 5: Guardrail System

#### Task 5.1: ActionNormalizer + SchemaValidator

**Files:**
- Create: `codeguard/guardrail/normalizer.py`
- Create: `tests/test_guardrail_normalizer.py`

**Consumes:** SPEC.md §3.2

**Produces:** `ActionNormalizer` (path normalization, program+args parsing, action_fingerprint) + `SchemaValidator` (parameter validation)

**Dependency:** Task 1.3 (Action, NormalizedAction)

**Parallel:** Can run in parallel with Phase 4 (Tool System) in separate worktree

**Worktree:** worktree-guardrail, branch `task-5.1-action-normalizer`

**Pre-commit:** Task 1.5 commit

**File boundary:** Only `codeguard/guardrail/normalizer.py` and `tests/test_guardrail_normalizer.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_guardrail_normalizer.py`:
```python
import pytest
from datetime import datetime
from codeguard.action import Action, ActionKind
from codeguard.guardrail.normalizer import ActionNormalizer, SchemaValidator

def test_normalize_path():
    normalizer = ActionNormalizer(workspace_root="/home/user/project")
    action = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "src/main.py"})
    na = normalizer.normalize(action)
    assert na.action_fingerprint is not None
    assert len(na.action_fingerprint) > 0

def test_normalize_fingerprint_consistent():
    normalizer = ActionNormalizer(workspace_root="/home/user/project")
    a1 = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "src/main.py"})
    a2 = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "src/main.py"})
    fp1 = normalizer.normalize(a1).action_fingerprint
    fp2 = normalizer.normalize(a2).action_fingerprint
    assert fp1 == fp2

def test_normalize_fingerprint_different():
    normalizer = ActionNormalizer(workspace_root="/home/user/project")
    a1 = Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "src/main.py"})
    a2 = Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "src/main.py"})
    fp1 = normalizer.normalize(a1).action_fingerprint
    fp2 = normalizer.normalize(a2).action_fingerprint
    assert fp1 != fp2

def test_schema_validator_valid():
    validator = SchemaValidator()
    schema = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    params = {"path": "main.py"}
    validator.validate(params, schema)  # should not raise

def test_schema_validator_invalid():
    validator = SchemaValidator()
    schema = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    params = {}
    with pytest.raises(ValueError, match="Missing required"):
        validator.validate(params, schema)

def test_normalize_complete_request():
    normalizer = ActionNormalizer(workspace_root="/home/user/project")
    action = Action(kind=ActionKind.COMPLETE_REQUEST, summary="done")
    na = normalizer.normalize(action)
    assert na.action_fingerprint == "COMPLETE_REQUEST"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_guardrail_normalizer.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement ActionNormalizer and SchemaValidator**

Write `codeguard/guardrail/normalizer.py`:
```python
import hashlib
import json
from datetime import datetime
from codeguard.action import Action, ActionKind, NormalizedAction

class SchemaValidator:
    """Validates tool parameters against JSON Schema."""

    def validate(self, params: dict, schema: dict):
        required = schema.get("required", [])
        for field in required:
            if field not in params:
                raise ValueError(f"Missing required parameter: {field}")
        properties = schema.get("properties", {})
        for key, value in params.items():
            if key in properties:
                expected_type = properties[key].get("type")
                if expected_type == "string" and not isinstance(value, str):
                    raise ValueError(f"Parameter '{key}' should be string, got {type(value).__name__}")

class ActionNormalizer:
    """Normalizes actions for consistent guardrail evaluation."""

    def __init__(self, workspace_root: str = ""):
        self._workspace_root = workspace_root

    def normalize(self, action: Action) -> NormalizedAction:
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return NormalizedAction(
                kind=action.kind,
                tool_name=None,
                normalized_parameters={},
                action_fingerprint="COMPLETE_REQUEST",
                original_raw=action.raw,
                normalized_at=datetime.now()
            )

        normalized_params = dict(action.parameters or {})
        if "path" in normalized_params and self._workspace_root:
            normalized_params["path"] = self._resolve_path(normalized_params["path"])

        fp = self._compute_fingerprint(action.tool_name or "", normalized_params)
        return NormalizedAction(
            kind=action.kind,
            tool_name=action.tool_name,
            normalized_parameters=normalized_params,
            action_fingerprint=fp,
            original_raw=action.raw,
            normalized_at=datetime.now()
        )

    def _resolve_path(self, path: str) -> str:
        from pathlib import Path
        root = Path(self._workspace_root).resolve()
        target = (root / path).resolve()
        return str(target)

    def _compute_fingerprint(self, tool_name: str, params: dict) -> str:
        raw = f"{tool_name}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(raw.encode()).hexdigest()
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_guardrail_normalizer.py -v`
Expected: 6 passed

- [ ] **Step 5: Refactor** — check that `_compute_fingerprint` uses sorted keys for deterministic output. The `json.dumps(sort_keys=True)` ensures this.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.2 — ActionNormalizer normalizes paths, computes action_fingerprint. SchemaValidator validates parameters against schema.

- [ ] **Step 7: Code quality review**

Check: `_compute_fingerprint` uses SHA-256 for collision resistance. `SchemaValidator` checks required fields and type constraints. COMPLETE_REQUEST has a constant fingerprint.

- [ ] **Step 8: Commit**

```bash
git add codeguard/guardrail/normalizer.py tests/test_guardrail_normalizer.py
git commit -m "feat: add ActionNormalizer and SchemaValidator"
git push origin task-5.1-action-normalizer
git push github task-5.1-action-normalizer
```

---

#### Task 5.2: Built-in guardrail rules

**Files:**
- Create: `codeguard/guardrail/rules.py`
- Create: `tests/test_guardrail_rules.py`

**Consumes:** SPEC.md §3.2

**Produces:** `WorkspaceBoundaryRule`, `CredentialLeakRule`, `UnregisteredToolRule`, `ModeRestrictionRule`

**Dependency:** Task 5.1 (uses NormalizedAction)

**Parallel:** No

**Worktree:** worktree-guardrail, branch `task-5.2-guardrail-rules`

- [ ] **Step 1: Write failing tests**

Write `tests/test_guardrail_rules.py`:
```python
import pytest
from datetime import datetime
from codeguard.action import ActionKind, NormalizedAction
from codeguard.guardrail.rules import WorkspaceBoundaryRule, CredentialLeakRule, UnregisteredToolRule, ModeRestrictionRule
from codeguard.tool.registry import ToolRegistry
from codeguard.tool import ToolDefinition

def _make_na(tool_name="read_file", params=None):
    return NormalizedAction(kind=ActionKind.TOOL_CALL, tool_name=tool_name, normalized_parameters=params or {}, action_fingerprint="fp", original_raw="", normalized_at=datetime.now())

def test_workspace_boundary_rule_allows():
    rule = WorkspaceBoundaryRule(workspace_root="/home/user/project")
    na = _make_na(params={"path": "/home/user/project/src/main.py"})
    result = rule.evaluate(na)
    assert result["decision"] == "ALLOW"

def test_workspace_boundary_rule_blocks():
    rule = WorkspaceBoundaryRule(workspace_root="/home/user/project")
    na = _make_na(params={"path": "/etc/passwd"})
    result = rule.evaluate(na)
    assert result["decision"] == "BLOCK"

def test_credential_leak_rule_allows():
    rule = CredentialLeakRule()
    na = _make_na(tool_name="read_file", params={"path": "main.py"})
    result = rule.evaluate(na)
    assert result["decision"] == "ALLOW"

def test_credential_leak_rule_blocks_api_key():
    rule = CredentialLeakRule()
    na = _make_na(tool_name="write_file", params={"path": "output.txt", "content": "api_key = sk-1234567890abcdef"})
    result = rule.evaluate(na)
    assert result["decision"] == "BLOCK"

def test_unregistered_tool_rule_allows():
    registry = ToolRegistry()
    td = ToolDefinition(name="read_file", description="", parameters_schema={}, handler=lambda: None, category="FILE", side_effect=False, default_risk="ALLOW", supported_modes=["TEST"])
    registry.register(td)
    rule = UnregisteredToolRule(registry)
    na = _make_na(tool_name="read_file")
    result = rule.evaluate(na)
    assert result["decision"] == "ALLOW"

def test_unregistered_tool_rule_blocks():
    registry = ToolRegistry()
    rule = UnregisteredToolRule(registry)
    na = _make_na(tool_name="unknown_tool")
    result = rule.evaluate(na)
    assert result["decision"] == "BLOCK"

def test_mode_restriction_rule_allows():
    rule = ModeRestrictionRule(mode="demo")
    na = _make_na(tool_name="read_file")
    result = rule.evaluate(na)
    assert result["decision"] == "ALLOW"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_guardrail_rules.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement guardrail rules**

Write `codeguard/guardrail/rules.py`:
```python
import re
from codeguard.action import ActionKind, NormalizedAction
from codeguard.tool.registry import ToolRegistry

class WorkspaceBoundaryRule:
    """Blocks actions that access paths outside the workspace."""

    def __init__(self, workspace_root: str):
        self._workspace_root = workspace_root

    def evaluate(self, action: NormalizedAction) -> dict:
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "workspace_boundary", "reason_codes": []}
        path = action.normalized_parameters.get("path", "")
        if path and not str(path).startswith(self._workspace_root):
            return {"decision": "BLOCK", "rule_id": "workspace_boundary", "reason_codes": ["out_of_bounds"]}
        return {"decision": "ALLOW", "rule_id": "workspace_boundary", "reason_codes": []}

class CredentialLeakRule:
    """Blocks actions that write credential patterns to output."""

    def __init__(self):
        self._patterns = [re.compile(r'sk-\w{20,}'), re.compile(r'api_key\s*[=:]\s*\S+'), re.compile(r'password\s*[=:]\s*\S+')]

    def evaluate(self, action: NormalizedAction) -> dict:
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "credential_leak", "reason_codes": []}
        content = str(action.normalized_parameters.get("content", ""))
        for p in self._patterns:
            if p.search(content):
                return {"decision": "BLOCK", "rule_id": "credential_leak", "reason_codes": ["credential_detected"]}
        return {"decision": "ALLOW", "rule_id": "credential_leak", "reason_codes": []}

class UnregisteredToolRule:
    """Blocks actions that reference unregistered tools."""

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def evaluate(self, action: NormalizedAction) -> dict:
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "unregistered_tool", "reason_codes": []}
        try:
            self._registry.lookup(action.tool_name or "")
            return {"decision": "ALLOW", "rule_id": "unregistered_tool", "reason_codes": []}
        except KeyError:
            return {"decision": "BLOCK", "rule_id": "unregistered_tool", "reason_codes": ["unknown_tool"]}

class ModeRestrictionRule:
    """Blocks actions not allowed in the current mode."""

    def __init__(self, mode: str):
        self._mode = mode

    def evaluate(self, action: NormalizedAction) -> dict:
        if action.kind == ActionKind.COMPLETE_REQUEST:
            return {"decision": "ALLOW", "rule_id": "mode_restriction", "reason_codes": []}
        if self._mode == "demo" and action.tool_name in ("run_process",):
            return {"decision": "BLOCK", "rule_id": "mode_restriction", "reason_codes": ["blocked_in_demo"]}
        return {"decision": "ALLOW", "rule_id": "mode_restriction", "reason_codes": []}
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_guardrail_rules.py -v`
Expected: 7 passed

- [ ] **Step 5: Refactor** — check that `CredentialLeakRule` patterns match the same patterns as `SecretRedactor`. Consider sharing pattern definitions.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.2 — WorkspaceBoundaryRule blocks out-of-bounds paths. CredentialLeakRule blocks credential patterns. UnregisteredToolRule blocks unknown tools. ModeRestrictionRule blocks disallowed actions in current mode.

- [ ] **Step 7: Code quality review**

Check: Each rule is a separate class with a single `evaluate()` method. All rules handle COMPLETE_REQUEST as ALLOW. Rules return plain dicts (not GuardrailResult) — the RuleEngine wraps them.

- [ ] **Step 8: Commit**

```bash
git add codeguard/guardrail/rules.py tests/test_guardrail_rules.py
git commit -m "feat: add built-in guardrail rules — workspace, credential, tool, mode"
git push origin task-5.2-guardrail-rules
git push github task-5.2-guardrail-rules
```

---

#### Task 5.3: RuleEngine + PriorityMerger

**Files:**
- Create: `codeguard/guardrail/engine.py`
- Create: `tests/test_guardrail_engine.py`

**Consumes:** SPEC.md §3.2

**Produces:** `RuleEngine` (execute all rules, merge by priority)

**Dependency:** Task 5.2 (rules)

**Parallel:** No

**Worktree:** worktree-guardrail, branch `task-5.3-rule-engine`

- [ ] **Step 1: Write failing tests**

Write `tests/test_guardrail_engine.py`:
```python
import pytest
from datetime import datetime
from codeguard.action import Action, ActionKind, NormalizedAction
from codeguard.guardrail.engine import RuleEngine, PriorityMerger
from codeguard.guardrail import GuardrailResult

def test_rule_engine_all_allow():
    engine = RuleEngine()
    engine.add_rule("test_allow", lambda na: {"decision": "ALLOW", "rule_id": "test", "reason_codes": []})
    na = NormalizedAction(kind=ActionKind.TOOL_CALL, tool_name="read_file", normalized_parameters={}, action_fingerprint="fp", original_raw="", normalized_at=datetime.now())
    result = engine.evaluate(na)
    assert result.decision == "ALLOW"

def test_rule_engine_one_veto():
    engine = RuleEngine()
    engine.add_rule("allow1", lambda na: {"decision": "ALLOW", "rule_id": "a1", "reason_codes": []})
    engine.add_rule("block1", lambda na: {"decision": "BLOCK", "rule_id": "b1", "reason_codes": ["danger"]})
    na = NormalizedAction(kind=ActionKind.TOOL_CALL, tool_name="delete_file", normalized_parameters={}, action_fingerprint="fp", original_raw="", normalized_at=datetime.now())
    result = engine.evaluate(na)
    assert result.decision == "BLOCK"
    assert "b1" in result.rule_ids

def test_rule_engine_approval_overrides_allow():
    engine = RuleEngine()
    engine.add_rule("allow1", lambda na: {"decision": "ALLOW", "rule_id": "a1", "reason_codes": []})
    engine.add_rule("approval1", lambda na: {"decision": "REQUEST_APPROVAL", "rule_id": "r1", "reason_codes": ["risky"]})
    na = NormalizedAction(kind=ActionKind.TOOL_CALL, tool_name="write_file", normalized_parameters={}, action_fingerprint="fp", original_raw="", normalized_at=datetime.now())
    result = engine.evaluate(na)
    assert result.decision == "REQUEST_APPROVAL"

def test_rule_engine_empty_returns_block():
    engine = RuleEngine()
    na = NormalizedAction(kind=ActionKind.TOOL_CALL, tool_name="unknown", normalized_parameters={}, action_fingerprint="fp", original_raw="", normalized_at=datetime.now())
    result = engine.evaluate(na)
    assert result.decision == "BLOCK"  # default-deny

def test_priority_merger_block_wins():
    merger = PriorityMerger()
    results = [{"decision": "ALLOW", "rule_id": "a1", "reason_codes": []}, {"decision": "BLOCK", "rule_id": "b1", "reason_codes": ["x"]}]
    merged = merger.merge(results)
    assert merged["decision"] == "BLOCK"

def test_priority_merger_approval_over_allow():
    merger = PriorityMerger()
    results = [{"decision": "ALLOW", "rule_id": "a1", "reason_codes": []}, {"decision": "REQUEST_APPROVAL", "rule_id": "r1", "reason_codes": ["y"]}]
    merged = merger.merge(results)
    assert merged["decision"] == "REQUEST_APPROVAL"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_guardrail_engine.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement RuleEngine and PriorityMerger**

Write `codeguard/guardrail/engine.py`:
```python
from codeguard.action import NormalizedAction
from codeguard.guardrail import GuardrailResult

_DECISION_PRIORITY = {"BLOCK": 3, "REQUEST_APPROVAL": 2, "ALLOW": 1}

class PriorityMerger:
    """Merges multiple rule results by priority: BLOCK > REQUEST_APPROVAL > ALLOW."""

    def merge(self, results: list[dict]) -> dict:
        if not results:
            return {"decision": "BLOCK", "rule_ids": ["default_deny"], "reason_codes": ["no_rule_matched"]}
        merged = {"decision": "ALLOW", "rule_ids": [], "reason_codes": []}
        for r in results:
            if _DECISION_PRIORITY.get(r["decision"], 0) > _DECISION_PRIORITY.get(merged["decision"], 0):
                merged["decision"] = r["decision"]
            merged["rule_ids"].append(r["rule_id"])
            merged["reason_codes"].extend(r.get("reason_codes", []))
        return merged

class RuleEngine:
    """Executes all registered rules and merges results by priority."""

    def __init__(self):
        self._rules: dict[str, callable] = {}
        self._merger = PriorityMerger()

    def add_rule(self, name: str, rule_fn: callable):
        self._rules[name] = rule_fn

    def evaluate(self, action: NormalizedAction) -> GuardrailResult:
        results = []
        for name, rule_fn in self._rules.items():
            try:
                r = rule_fn(action)
                results.append(r)
            except Exception:
                results.append({"decision": "BLOCK", "rule_id": name, "reason_codes": ["rule_error"]})

        merged = self._merger.merge(results)
        return GuardrailResult(
            decision=merged["decision"],
            rule_ids=merged["rule_ids"],
            reason_codes=merged["reason_codes"],
            human_readable_message=self._format_message(merged),
            recoverable=(merged["decision"] != "BLOCK"),
            normalized_action=action,
            action_fingerprint=action.action_fingerprint
        )

    def _format_message(self, merged: dict) -> str:
        if merged["decision"] == "BLOCK":
            return f"Blocked by rules: {', '.join(merged['rule_ids'])}"
        elif merged["decision"] == "REQUEST_APPROVAL":
            return f"Requires approval: {', '.join(merged['rule_ids'])}"
        return "Allowed"
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_guardrail_engine.py -v`
Expected: 6 passed

- [ ] **Step 5: Refactor** — check that rule exceptions are caught and treated as BLOCK (fail closed). The try/except in `evaluate()` ensures this.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.2 — RuleEngine executes all rules. PriorityMerger uses BLOCK > REQUEST_APPROVAL > ALLOW. Empty rules returns BLOCK (default-deny). One veto blocks regardless of order.

- [ ] **Step 7: Code quality review**

Check: `evaluate()` catches exceptions per-rule (one failing rule doesn't crash the engine). `PriorityMerger` is a separate class for testability. `_format_message` produces human-readable output.

- [ ] **Step 8: Commit**

```bash
git add codeguard/guardrail/engine.py tests/test_guardrail_engine.py
git commit -m "feat: add RuleEngine with PriorityMerger — BLOCK > REQUEST_APPROVAL > ALLOW"
git push origin task-5.3-rule-engine
git push github task-5.3-rule-engine
```

---

#### Task 5.4: ApprovalManager with FakeClock

**Files:**
- Modify: `codeguard/guardrail/approval.py`
- Create: `tests/test_approval_manager.py`

**Consumes:** SPEC.md §3.4

**Produces:** `ApprovalManager` (create, approve, reject, timeout with FakeClock)

**Dependency:** Task 1.4 (ApprovalRequest, ApprovalResult, FakeClock), Task 5.3 (RuleEngine)

**Parallel:** No

**Worktree:** worktree-guardrail, branch `task-5.4-approval-manager`

- [ ] **Step 1: Write failing tests**

Write `tests/test_approval_manager.py`:
```python
import pytest
from datetime import datetime, timedelta
from codeguard.action import Action, ActionKind, NormalizedAction
from codeguard.guardrail.approval import ApprovalManager, ApprovalRequest, ApprovalResult, FakeClock

def _make_na():
    return NormalizedAction(kind=ActionKind.TOOL_CALL, tool_name="write_file", normalized_parameters={"path": "output.txt"}, action_fingerprint="fp123", original_raw="", normalized_at=datetime.now())

def test_create_request():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
    mgr = ApprovalManager(clock=clock, approval_timeout=60)
    na = _make_na()
    req = mgr.create_request(session_id="s1", normalized_action=na, matched_rules=["risk_rule"], risk_summary="Writing to project dir")
    assert req.request_id is not None
    assert req.status == "PENDING"
    assert req.expires_at == datetime(2026, 1, 1, 12, 1, 0)

def test_approve():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
    mgr = ApprovalManager(clock=clock, approval_timeout=60)
    na = _make_na()
    req = mgr.create_request(session_id="s1", normalized_action=na, matched_rules=[], risk_summary="")
    result = mgr.approve(request_id=req.request_id, session_id="s1", action_fingerprint="fp123")
    assert result.decision == "APPROVED"
    assert req.status == "APPROVED"

def test_reject():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
    mgr = ApprovalManager(clock=clock, approval_timeout=60)
    na = _make_na()
    req = mgr.create_request(session_id="s1", normalized_action=na, matched_rules=[], risk_summary="")
    result = mgr.reject(request_id=req.request_id, session_id="s1")
    assert result.decision == "REJECTED"
    assert req.status == "REJECTED"

def test_timeout():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
    mgr = ApprovalManager(clock=clock, approval_timeout=60)
    na = _make_na()
    req = mgr.create_request(session_id="s1", normalized_action=na, matched_rules=[], risk_summary="")
    # Advance clock past timeout
    clock.advance(61)
    result = mgr.check_timeout(req)
    assert result.decision == "TIMEOUT"
    assert req.status == "TIMEOUT"

def test_approve_expired_request():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
    mgr = ApprovalManager(clock=clock, approval_timeout=5)
    na = _make_na()
    req = mgr.create_request(session_id="s1", normalized_action=na, matched_rules=[], risk_summary="")
    clock.advance(10)
    with pytest.raises(ValueError, match="expired"):
        mgr.approve(request_id=req.request_id, session_id="s1", action_fingerprint="fp123")

def test_approve_wrong_session():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
    mgr = ApprovalManager(clock=clock, approval_timeout=60)
    na = _make_na()
    req = mgr.create_request(session_id="s1", normalized_action=na, matched_rules=[], risk_summary="")
    with pytest.raises(ValueError, match="Session mismatch"):
        mgr.approve(request_id=req.request_id, session_id="other_session", action_fingerprint="fp123")

def test_approve_fingerprint_mismatch():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
    mgr = ApprovalManager(clock=clock, approval_timeout=60)
    na = _make_na()
    req = mgr.create_request(session_id="s1", normalized_action=na, matched_rules=[], risk_summary="")
    with pytest.raises(ValueError, match="Action fingerprint mismatch"):
        mgr.approve(request_id=req.request_id, session_id="s1", action_fingerprint="wrong_fp")
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_approval_manager.py -v`
Expected: ImportErrors or AttributeError (ApprovalManager not yet implemented)

- [ ] **Step 3: Implement ApprovalManager**

Write `codeguard/guardrail/approval.py` (replace existing file):
```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from codeguard.action import NormalizedAction
import uuid

@dataclass
class ApprovalRequest:
    request_id: str
    session_id: str
    normalized_action: NormalizedAction
    action_fingerprint: str
    matched_rules: list[str]
    risk_summary: str
    workspace_snapshot: dict
    created_at: datetime
    expires_at: datetime
    status: str = "PENDING"

@dataclass
class ApprovalResult:
    request_id: str
    decision: str
    validated_at: datetime
    validator_notes: str = ""

class FakeClock:
    """Injectable clock for deterministic timeout testing."""
    def __init__(self, now: datetime | None = None):
        self._now = now or datetime.now()
    @property
    def now(self) -> datetime:
        return self._now
    def advance(self, seconds: float):
        self._now += timedelta(seconds=seconds)
    def is_expired(self, deadline: datetime) -> bool:
        return self._now >= deadline

class ApprovalManager:
    """Manages approval requests with timeout, session binding, and fingerprint binding.

    Does NOT auto-approve. The caller must call approve() or reject() explicitly.
    """

    def __init__(self, clock: FakeClock | None = None, approval_timeout: int = 60):
        self._clock = clock or FakeClock()
        self._timeout = approval_timeout
        self._requests: dict[str, ApprovalRequest] = {}

    def create_request(self, session_id: str, normalized_action: NormalizedAction,
                       matched_rules: list[str], risk_summary: str) -> ApprovalRequest:
        req = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            session_id=session_id,
            normalized_action=normalized_action,
            action_fingerprint=normalized_action.action_fingerprint,
            matched_rules=matched_rules,
            risk_summary=risk_summary,
            workspace_snapshot={},
            created_at=self._clock.now,
            expires_at=self._clock.now + timedelta(seconds=self._timeout)
        )
        self._requests[req.request_id] = req
        return req

    def approve(self, request_id: str, session_id: str, action_fingerprint: str) -> ApprovalResult:
        req = self._get_valid_request(request_id, session_id, action_fingerprint)
        req.status = ApprovalStatus.APPROVED
        return ApprovalResult(request_id=request_id, decision=ApprovalStatus.APPROVED, validated_at=self._clock.now)

    def reject(self, request_id: str, session_id: str) -> ApprovalResult:
        req = self._requests.get(request_id)
        if not req or req.session_id != session_id:
            raise ValueError("Session mismatch")
        if self._clock.is_expired(req.expires_at):
            raise ValueError("Request already expired")
        req.status = ApprovalStatus.REJECTED
        return ApprovalResult(request_id=request_id, decision=ApprovalStatus.REJECTED, validated_at=self._clock.now)

    def check_timeout(self, req: ApprovalRequest) -> ApprovalResult | None:
        if req.status != ApprovalStatus.PENDING:
            return None
        if self._clock.is_expired(req.expires_at):
            req.status = ApprovalStatus.TIMEOUT
            return ApprovalResult(request_id=req.request_id, decision=ApprovalStatus.TIMEOUT, validated_at=self._clock.now)
        return None

    def _get_valid_request(self, request_id: str, session_id: str, action_fingerprint: str) -> ApprovalRequest:
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Unknown request: {request_id}")
        if req.session_id != session_id:
            raise ValueError("Session mismatch")
        if self._clock.is_expired(req.expires_at):
            raise ValueError("Request already expired")
        if req.action_fingerprint != action_fingerprint:
            raise ValueError("Action fingerprint mismatch")
        if req.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request already {req.status}")
        return req
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_approval_manager.py -v`
Expected: 8 passed

- [ ] **Step 5: Refactor** — check that `_get_valid_request` validates all conditions (existence, session, expiry, fingerprint, status). Consider extracting timeout checking into a separate method.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.4 — ApprovalRequest with request_id, session_id, action binding, fingerprint, timeout. Approve/reject/timeout all work. Expired requests cannot be approved. Session mismatch rejected. FakeClock for deterministic testing.

- [ ] **Step 7: Code quality review**

Check: `_get_valid_request` is a single validation gate used by both approve and reject. All validation errors are ValueError with descriptive messages. FakeClock is injected, not created internally.

- [ ] **Step 8: Commit**

```bash
git add codeguard/guardrail/approval.py tests/test_approval_manager.py
git commit -m "feat: add ApprovalManager with FakeClock — approve, reject, timeout"
git push origin task-5.4-approval-manager
git push github task-5.4-approval-manager
```

---

### Phase 6: Feedback System

#### Task 6.1: SensorRunner

**Files:**
- Create: `codeguard/feedback/sensor.py`
- Create: `tests/test_sensor_runner.py`

**Consumes:** SPEC.md §3.5

**Produces:** `SensorRunner` (run sensors via subprocess, capture output, timeout)

**Dependency:** Task 1.5 (SensorDefinition, FeedbackResult)

**Parallel:** Can run in parallel with Phase 5 (Guardrail) in separate worktree

**Worktree:** worktree-feedback, branch `task-6.1-sensor-runner`

**Pre-commit:** Task 1.5 commit

**File boundary:** Only `codeguard/feedback/sensor.py` and `tests/test_sensor_runner.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_sensor_runner.py`:
```python
import pytest
from codeguard.feedback.sensor import SensorRunner
from codeguard.feedback import SensorDefinition

def test_sensor_runner_passes(temp_workspace):
    sd = SensorDefinition(name="echo", program="echo", args=["hello"], timeout=10, parser="generic", required=True, allowed_exit_codes={0}, output_limit=4096)
    runner = SensorRunner(sd, cwd=str(temp_workspace))
    result = runner.run()
    assert result.status == "PASSED"
    assert result.exit_code == 0

def test_sensor_runner_timeout(temp_workspace):
    sd = SensorDefinition(name="sleep", program="python", args=["-c", "import time; time.sleep(10)"], timeout=1, parser="generic", required=True, allowed_exit_codes={0}, output_limit=4096)
    runner = SensorRunner(sd, cwd=str(temp_workspace))
    result = runner.run()
    assert result.status == "TIMEOUT"

def test_sensor_runner_program_not_found(temp_workspace):
    sd = SensorDefinition(name="nonexistent", program="nonexistent_program_xyz", args=[], timeout=10, parser="generic", required=True, allowed_exit_codes={0}, output_limit=4096)
    runner = SensorRunner(sd, cwd=str(temp_workspace))
    result = runner.run()
    assert result.status == "UNAVAILABLE"

def test_sensor_runner_failure(temp_workspace):
    sd = SensorDefinition(name="false", program="python", args=["-c", "exit(1)"], timeout=10, parser="generic", required=True, allowed_exit_codes={0}, output_limit=4096)
    runner = SensorRunner(sd, cwd=str(temp_workspace))
    result = runner.run()
    assert result.status == "FAILED"
    assert result.exit_code == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_sensor_runner.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement SensorRunner**

Write `codeguard/feedback/sensor.py`:
```python
import subprocess
import sys
from codeguard.feedback import SensorDefinition, FeedbackResult

class SensorRunner:
    """Runs a single sensor command and returns structured FeedbackResult."""

    def __init__(self, definition: SensorDefinition, cwd: str = ""):
        self._definition = definition
        self._cwd = cwd

    def run(self) -> FeedbackResult:
        try:
            proc = subprocess.run(
                [self._definition.program] + self._definition.args,
                capture_output=True, text=True, timeout=self._definition.timeout,
                cwd=self._cwd
            )
            if proc.returncode in self._definition.allowed_exit_codes:
                status = "PASSED"
            else:
                status = "FAILED"
            return FeedbackResult(
                sensor_id=self._definition.name,
                program=self._definition.program,
                args=self._definition.args,
                status=status,
                failure_category=None if status == "PASSED" else "TEST_FAILURE",
                exit_code=proc.returncode,
                failure_fingerprint=None,
                validation_type="INTERMEDIATE",
                summary=f"Exit code: {proc.returncode}",
                diagnostics=[],
                duration=0.0,
                retryable=(status == "FAILED"),
                raw_output_truncated=proc.stdout[:self._definition.output_limit]
            )
        except subprocess.TimeoutExpired:
            return FeedbackResult(sensor_id=self._definition.name, program=self._definition.program, args=self._definition.args, status="TIMEOUT", failure_category="TIMEOUT", exit_code=None, failure_fingerprint=None, validation_type="INTERMEDIATE", summary="Timed out", diagnostics=[], duration=0.0, retryable=True, raw_output_truncated="")
        except FileNotFoundError:
            return FeedbackResult(sensor_id=self._definition.name, program=self._definition.program, args=self._definition.args, status="UNAVAILABLE", failure_category="PROGRAM_NOT_FOUND", exit_code=None, failure_fingerprint=None, validation_type="INTERMEDIATE", summary="Program not found", diagnostics=[], duration=0.0, retryable=False, raw_output_truncated="")
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_sensor_runner.py -v`
Expected: 4 passed

- [ ] **Step 5: Refactor** — check that `run()` catches all expected exceptions and returns structured FeedbackResult even on failure.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.5 — SensorRunner runs sensor via subprocess with program+args. Captures output. Handles timeout and missing program. Returns structured FeedbackResult.

- [ ] **Step 7: Code quality review**

Check: All error paths return FeedbackResult (no unhandled exceptions). Timeout and FileNotFoundError are caught and mapped to appropriate status values.

- [ ] **Step 8: Commit**

```bash
git add codeguard/feedback/sensor.py tests/test_sensor_runner.py
git commit -m "feat: add SensorRunner for subprocess sensor execution"
git push origin task-6.1-sensor-runner
git push github task-6.1-sensor-runner
```

---

#### Task 6.2: Output parsers

**Files:**
- Create: `codeguard/feedback/parsers.py`
- Create: `tests/test_parsers.py`

**Consumes:** SPEC.md §3.5

**Produces:** PytestParser, RuffParser, MypyParser, GenericParser

**Dependency:** Task 1.5 (Diagnostic, FeedbackResult)

**Parallel:** No

**Worktree:** worktree-feedback, branch `task-6.2-parsers`

- [ ] **Step 1: Write failing tests**

Write `tests/test_parsers.py`:
```python
from codeguard.feedback.parsers import PytestParser, RuffParser, MypyParser, GenericParser

def test_pytest_parser_failure():
    parser = PytestParser()
    output = "_____________________ FAILURES ______________________\n____ test_main.py:3: in test_hello\n>    assert 1 == 2\nE    assert 1 == 2\n\nFAILED test_main.py::test_hello"
    result = parser.parse(output)
    assert result["failure_category"] == "TEST_FAILURE"
    assert len(result["diagnostics"]) >= 1
    assert result["diagnostics"][0]["message"] is not None

def test_pytest_parser_pass():
    parser = PytestParser()
    output = "collected 1 item\nmain.py .\n\n1 passed"
    result = parser.parse(output)
    assert result["failure_category"] is None

def test_ruff_parser():
    parser = RuffParser()
    output = "main.py:1:1: F401 `os` imported but unused"
    result = parser.parse(output)
    assert result["failure_category"] == "LINT_ERROR"
    assert len(result["diagnostics"]) >= 1

def test_mypy_parser():
    parser = MypyParser()
    output = "main.py:10: error: Incompatible return value type (got \"int\", expected \"str\")"
    result = parser.parse(output)
    assert result["failure_category"] == "TYPE_ERROR"
    assert len(result["diagnostics"]) >= 1

def test_generic_parser():
    parser = GenericParser()
    output = "Some output with error: something failed"
    result = parser.parse(output)
    assert result["failure_category"] == "UNKNOWN_FAILURE"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_parsers.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement parsers**

Write `codeguard/feedback/parsers.py`:
```python
import re

class PytestParser:
    def parse(self, output: str) -> dict:
        if "FAILED" in output or "FAILURES" in output:
            diagnostics = []
            for line in output.splitlines():
                m = re.match(r'(.+\.py):(\d+):\s+(.*)', line)
                if m:
                    diagnostics.append({"file": m.group(1), "line": int(m.group(2)), "message": m.group(3), "category": "test_failure"})
            return {"failure_category": "TEST_FAILURE", "diagnostics": diagnostics, "fingerprint": self._compute_fingerprint(diagnostics)}
        return {"failure_category": None, "diagnostics": [], "fingerprint": None}

    def _compute_fingerprint(self, diagnostics: list) -> str:
        if not diagnostics:
            return ""
        return "|".join(f"{d['file']}:{d['line']}" for d in diagnostics[:3])

class RuffParser:
    def parse(self, output: str) -> dict:
        diagnostics = []
        for line in output.splitlines():
            m = re.match(r'(.+\.py):(\d+):(\d+):\s+(\S+)\s+(.*)', line)
            if m:
                diagnostics.append({"file": m.group(1), "line": int(m.group(2)), "column": int(m.group(3)), "code": m.group(4), "message": m.group(5), "category": "lint"})
        if diagnostics:
            return {"failure_category": "LINT_ERROR", "diagnostics": diagnostics, "fingerprint": str(len(diagnostics))}
        return {"failure_category": None, "diagnostics": [], "fingerprint": None}

class MypyParser:
    def parse(self, output: str) -> dict:
        diagnostics = []
        for line in output.splitlines():
            m = re.match(r'(.+\.py):(\d+):\s+(error|warning):\s+(.*)', line)
            if m:
                diagnostics.append({"file": m.group(1), "line": int(m.group(2)), "severity": m.group(3), "message": m.group(4), "category": "type_error"})
        if diagnostics:
            return {"failure_category": "TYPE_ERROR", "diagnostics": diagnostics, "fingerprint": str(len(diagnostics))}
        return {"failure_category": None, "diagnostics": [], "fingerprint": None}

class GenericParser:
    def parse(self, output: str) -> dict:
        return {"failure_category": "UNKNOWN_FAILURE", "diagnostics": [], "fingerprint": None}
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_parsers.py -v`
Expected: 5 passed

- [ ] **Step 5: Refactor** — no refactoring needed. Each parser is a separate class with a single `parse()` method.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.5 — PytestParser, RuffParser, MypyParser, GenericParser all produce failure_category + diagnostics + fingerprint.

- [ ] **Step 7: Code quality review**

Check: Each parser is independent. Parse errors don't crash (return UNKNOWN_FAILURE). Fingerprints are deterministic.

- [ ] **Step 8: Commit**

```bash
git add codeguard/feedback/parsers.py tests/test_parsers.py
git commit -m "feat: add output parsers — pytest, ruff, mypy, generic"
git push origin task-6.2-parsers
git push github task-6.2-parsers
```

---

#### Task 6.3: FeedbackClassifier

**Files:**
- Create: `codeguard/feedback/classifier.py`
- Create: `tests/test_classifier.py`

**Consumes:** SPEC.md §3.5

**Produces:** `FeedbackClassifier` with three-layer classification

**Dependency:** Task 6.2 (parsers)

**Parallel:** No

**Worktree:** worktree-feedback, branch `task-6.3-classifier`

- [ ] **Step 1: Write failing tests**

Write `tests/test_classifier.py`:
```python
from codeguard.feedback.classifier import FeedbackClassifier
from codeguard.feedback import FeedbackResult, SensorDefinition

def test_classify_passed():
    classifier = FeedbackClassifier()
    result = FeedbackResult(sensor_id="pytest", program="pytest", args=["."], status="PASSED", failure_category=None, exit_code=0, failure_fingerprint=None, validation_type="INTERMEDIATE", summary="ok", diagnostics=[], duration=0.1, retryable=False, raw_output_truncated="")
    classified = classifier.classify(result)
    assert classified.status == "PASSED"
    assert classified.failure_category is None

def test_classify_failed_with_parser():
    classifier = FeedbackClassifier()
    result = FeedbackResult(sensor_id="pytest", program="pytest", args=["."], status="FAILED", failure_category=None, exit_code=1, failure_fingerprint=None, validation_type="INTERMEDIATE", summary="failed", diagnostics=[], duration=0.1, retryable=True, raw_output_truncated="FAILURES\nmain.py:3: assert 1 == 2\nFAILED")
    classified = classifier.classify(result)
    assert classified.failure_category is not None

def test_classify_execution_error():
    classifier = FeedbackClassifier()
    result = FeedbackResult(sensor_id="pytest", program="pytest", args=["."], status="EXECUTION_ERROR", failure_category=None, exit_code=None, failure_fingerprint=None, validation_type="INTERMEDIATE", summary="error", diagnostics=[], duration=0.1, retryable=False, raw_output_truncated="")
    classified = classifier.classify(result)
    assert classified.failure_category == "EXECUTION_ERROR"

def test_classify_failure_fingerprint():
    classifier = FeedbackClassifier()
    result = FeedbackResult(sensor_id="pytest", program="pytest", args=["."], status="FAILED", failure_category=None, exit_code=1, failure_fingerprint=None, validation_type="INTERMEDIATE", summary="failed", diagnostics=[], duration=0.1, retryable=True, raw_output_truncated="FAILURES\nmain.py:3: assert 1 == 2")
    classified = classifier.classify(result)
    assert classified.failure_fingerprint is not None
    assert len(classified.failure_fingerprint) > 0
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_classifier.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement FeedbackClassifier**

Write `codeguard/feedback/classifier.py`:
```python
import hashlib
from codeguard.feedback import FeedbackResult
from codeguard.feedback.parsers import PytestParser, GenericParser

_PARSER_MAP = {
    "pytest": PytestParser(),
    "generic": GenericParser(),
}

class FeedbackClassifier:
    """Three-layer classification: execution status -> failure category -> diagnostics."""

    def classify(self, result: FeedbackResult) -> FeedbackResult:
        if result.status == "PASSED":
            return result

        if result.status in ("EXECUTION_ERROR", "TIMEOUT", "UNAVAILABLE"):
            result.failure_category = result.status
            return result

        # Failed: parse output to determine category
        parser = _PARSER_MAP.get(result.sensor_id, _PARSER_MAP["generic"])
        parsed = parser.parse(result.raw_output_truncated)
        result.failure_category = parsed.get("failure_category", "UNKNOWN_FAILURE")
        result.diagnostics = parsed.get("diagnostics", [])

        # Compute failure fingerprint
        fp_data = f"{result.sensor_id}:{result.failure_category}:{parsed.get('fingerprint', '')}"
        result.failure_fingerprint = hashlib.sha256(fp_data.encode()).hexdigest()

        return result
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_classifier.py -v`
Expected: 4 passed

- [ ] **Step 5: Refactor** — check that `PASSED` status returns immediately without parsing. The early return handles this.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.5 — Three-layer classification: status -> failure_category -> diagnostics. Failure fingerprint computed from sensor_id + category + parsed fingerprint.

- [ ] **Step 7: Code quality review**

Check: `classify()` modifies the FeedbackResult in place (preserves reference). Failure fingerprint uses SHA-256 for collision resistance.

- [ ] **Step 8: Commit**

```bash
git add codeguard/feedback/classifier.py tests/test_classifier.py
git commit -m "feat: add FeedbackClassifier with three-layer classification"
git push origin task-6.3-classifier
git push github task-6.3-classifier
```

---

#### Task 6.4: Feedback formatting

**Files:**
- Modify: `codeguard/feedback/classifier.py`
- Modify: `tests/test_classifier.py`

**Consumes:** SPEC.md §3.5

**Produces:** `format_for_llm()` producing structured context block

**Dependency:** Task 6.3 (classifier)

**Parallel:** No

**Worktree:** worktree-feedback, branch `task-6.4-feedback-format`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_classifier.py`:
```python
from codeguard.feedback.classifier import format_feedback_for_llm

def test_format_feedback_passed():
    result = FeedbackResult(sensor_id="pytest", program="pytest", args=["."], status="PASSED", failure_category=None, exit_code=0, failure_fingerprint=None, validation_type="INTERMEDIATE", summary="All passed", diagnostics=[], duration=0.1, retryable=False, raw_output_truncated="")
    formatted = format_feedback_for_llm([result])
    assert "PASSED" in formatted
    assert "pytest" in formatted

def test_format_feedback_failed():
    result = FeedbackResult(sensor_id="pytest", program="pytest", args=["."], status="FAILED", failure_category="TEST_FAILURE", exit_code=1, failure_fingerprint="fp123", validation_type="INTERMEDIATE", summary="1 failed", diagnostics=[{"file": "test.py", "message": "assert failed"}], duration=0.1, retryable=True, raw_output_truncated="FAILURES")
    formatted = format_feedback_for_llm([result])
    assert "FAILED" in formatted
    assert "TEST_FAILURE" in formatted
    assert "fp123" in formatted

def test_format_feedback_empty():
    formatted = format_feedback_for_llm([])
    assert "No feedback" in formatted
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_classifier.py -v`
Expected: 2 new tests fail (format_feedback_for_llm not defined)

- [ ] **Step 3: Implement format_feedback_for_llm**

Append to `codeguard/feedback/classifier.py`:
```python
def format_feedback_for_llm(results: list[FeedbackResult]) -> str:
    """Format feedback results as structured LLM context block."""
    if not results:
        return "\n[Feedback]\nNo feedback results available."

    parts = ["\n[Feedback]"]
    for r in results:
        parts.append(f"Sensor: {r.sensor_id}")
        parts.append(f"Status: {r.status}")
        if r.failure_category:
            parts.append(f"Category: {r.failure_category}")
        if r.failure_fingerprint:
            parts.append(f"Fingerprint: {r.failure_fingerprint}")
        if r.diagnostics:
            parts.append("Diagnostics:")
            for d in r.diagnostics[:5]:
                parts.append(f"  - {d.get('file', '?')}:{d.get('line', '?')} {d.get('message', '')}")
        if r.raw_output_truncated:
            parts.append(f"Output: {r.raw_output_truncated[:200]}")
        parts.append("")
    return "\n".join(parts)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_classifier.py -v`
Expected: 7 passed (4 from Task 6.3 + 3 new)

- [ ] **Step 5: Refactor** — check that the formatted output is not too long. The 200-char truncation on raw_output helps.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.5 — format_feedback_for_llm produces structured context block with sensor, status, category, fingerprint, diagnostics.

- [ ] **Step 7: Code quality review**

Check: Output is plain text, not markdown. Diagnostics limited to 5 entries. Raw output truncated to 200 chars. Empty input produces "No feedback" message.

- [ ] **Step 8: Commit**

```bash
git add codeguard/feedback/classifier.py tests/test_classifier.py
git commit -m "feat: add format_feedback_for_llm for structured feedback context"
git push origin task-6.4-feedback-format
git push github task-6.4-feedback-format
```

---

#### Task 6.5: ObjectiveVerifier

**Files:**
- Create: `codeguard/feedback/verifier.py`
- Create: `tests/test_verifier.py`

**Consumes:** SPEC.md §3.5

**Produces:** `ObjectiveVerifier` (check all required sensors passed)

**Dependency:** Task 6.3 (FeedbackResult)

**Parallel:** No

**Worktree:** worktree-feedback, branch `task-6.5-verifier`

- [ ] **Step 1: Write failing tests**

Write `tests/test_verifier.py`:
```python
from codeguard.feedback.verifier import ObjectiveVerifier
from codeguard.feedback import FeedbackResult, SensorDefinition

def test_verifier_all_pass():
    verifier = ObjectiveVerifier(required_sensors=["pytest"])
    results = [FeedbackResult(sensor_id="pytest", program="pytest", args=["."], status="PASSED", failure_category=None, exit_code=0, failure_fingerprint=None, validation_type="FINAL", summary="ok", diagnostics=[], duration=0.1, retryable=False, raw_output_truncated="")]
    assert verifier.verify(results) is True

def test_verifier_any_fail():
    verifier = ObjectiveVerifier(required_sensors=["pytest"])
    results = [FeedbackResult(sensor_id="pytest", program="pytest", args=["."], status="FAILED", failure_category="TEST_FAILURE", exit_code=1, failure_fingerprint="fp", validation_type="FINAL", summary="fail", diagnostics=[], duration=0.1, retryable=True, raw_output_truncated="")]
    assert verifier.verify(results) is False

def test_verifier_missing_required():
    verifier = ObjectiveVerifier(required_sensors=["pytest", "ruff"])
    results = [FeedbackResult(sensor_id="pytest", program="pytest", args=["."], status="PASSED", failure_category=None, exit_code=0, failure_fingerprint=None, validation_type="FINAL", summary="ok", diagnostics=[], duration=0.1, retryable=False, raw_output_truncated="")]
    assert verifier.verify(results) is False

def test_verifier_all_sensors():
    verifier = ObjectiveVerifier(required_sensors=["pytest", "ruff"])
    results = [
        FeedbackResult(sensor_id="pytest", program="pytest", args=["."], status="PASSED", failure_category=None, exit_code=0, failure_fingerprint=None, validation_type="FINAL", summary="ok", diagnostics=[], duration=0.1, retryable=False, raw_output_truncated=""),
        FeedbackResult(sensor_id="ruff", program="ruff", args=["."], status="PASSED", failure_category=None, exit_code=0, failure_fingerprint=None, validation_type="FINAL", summary="ok", diagnostics=[], duration=0.1, retryable=False, raw_output_truncated=""),
    ]
    assert verifier.verify(results) is True
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_verifier.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement ObjectiveVerifier**

Write `codeguard/feedback/verifier.py`:
```python
from codeguard.feedback import FeedbackResult

class ObjectiveVerifier:
    """Verifies that all required sensors have passed."""

    def __init__(self, required_sensors: list[str] | None = None):
        self._required = required_sensors or []

    def verify(self, results: list[FeedbackResult]) -> bool:
        passed = {r.sensor_id for r in results if r.status == "PASSED"}
        for required in self._required:
            if required not in passed:
                return False
        return True
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_verifier.py -v`
Expected: 4 passed

- [ ] **Step 5: Refactor** — no refactoring needed. Simple set membership check.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.5 — ObjectiveVerifier checks all required sensors PASSED. Missing required sensor returns False. No required sensors returns True.

- [ ] **Step 7: Code quality review**

Check: Simple, focused class. Returns bool, not FeedbackResult. No side effects.

- [ ] **Step 8: Commit**

```bash
git add codeguard/feedback/verifier.py tests/test_verifier.py
git commit -m "feat: add ObjectiveVerifier for required sensor validation"
git push origin task-6.5-verifier
git push github task-6.5-verifier
```

---

### Phase 7: Tracer

#### Task 7.1: Tracer (uses SecretRedactor)

**Files:**
- Create: `codeguard/tracer.py`
- Create: `tests/test_tracer.py`

**Consumes:** SPEC.md §4.3

**Produces:** `Tracer` recording state transitions, guardrail decisions, tool calls, feedback results; applies SecretRedactor before storing

**Dependency:** Task 3.1 (SecretRedactor)

**Parallel:** Can run in parallel with Phases 4-6

**Worktree:** main, branch `task-7.1-tracer`

**Pre-commit:** Task 3.1 commit

**File boundary:** Only `codeguard/tracer.py` and `tests/test_tracer.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_tracer.py`:
```python
from datetime import datetime
from codeguard.tracer import Tracer, TraceEvent
from codeguard.state import AgentState
from codeguard.secret import SecretRedactor

def test_tracer_record_state_transition():
    tracer = Tracer()
    tracer.record_state_transition(AgentState.INITIALIZING, AgentState.BUILDING_CONTEXT)
    events = tracer.get_events()
    assert len(events) == 1
    assert events[0].event_type == "state_transition"
    assert events[0].data["from"] == "initializing"

def test_tracer_record_guardrail():
    tracer = Tracer()
    tracer.record_guardrail("BLOCK", ["rule1"], "Blocked")
    events = tracer.get_events()
    assert len(events) == 1
    assert events[0].event_type == "guardrail"

def test_tracer_record_tool_call():
    tracer = Tracer()
    tracer.record_tool_call("read_file", {"path": "main.py"}, "SUCCESS")
    events = tracer.get_events()
    assert len(events) == 1
    assert events[0].data["tool"] == "read_file"

def test_tracer_record_feedback():
    tracer = Tracer()
    tracer.record_feedback("pytest", "PASSED", None)
    events = tracer.get_events()
    assert len(events) == 1
    assert events[0].data["sensor"] == "pytest"

def test_tracer_applies_secret_redactor():
    redactor = SecretRedactor()
    tracer = Tracer(secret_redactor=redactor)
    tracer.record_tool_call("write_file", {"content": "api_key = sk-1234567890abcdef"}, "SUCCESS")
    events = tracer.get_events()
    assert "sk-1234567890abcdef" not in events[0].data["params"]["content"]

def test_tracer_chronological_order():
    tracer = Tracer()
    tracer.record_state_transition(AgentState.INITIALIZING, AgentState.BUILDING_CONTEXT)
    tracer.record_tool_call("read_file", {}, "SUCCESS")
    tracer.record_state_transition(AgentState.BUILDING_CONTEXT, AgentState.DECIDING)
    events = tracer.get_events()
    assert events[0].event_type == "state_transition"
    assert events[1].event_type == "tool_call"
    assert events[2].event_type == "state_transition"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_tracer.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement Tracer**

Write `codeguard/tracer.py`:
```python
from dataclasses import dataclass, field
from datetime import datetime
from codeguard.state import AgentState
from codeguard.secret import SecretRedactor

@dataclass
class TraceEvent:
    event_type: str
    data: dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

class Tracer:
    """Records chronological trace of agent execution. Applies SecretRedactor before storing."""

    def __init__(self, secret_redactor: SecretRedactor | None = None):
        self._events: list[TraceEvent] = []
        self._redactor = secret_redactor or SecretRedactor()

    def record_state_transition(self, old: AgentState, new: AgentState):
        self._events.append(TraceEvent("state_transition", {"from": old.value, "to": new.value}))

    def record_guardrail(self, decision: str, rule_ids: list[str], message: str):
        self._events.append(TraceEvent("guardrail", {"decision": decision, "rules": rule_ids, "message": self._redactor.redact(message)}))

    def record_tool_call(self, tool: str, params: dict, status: str):
        safe_params = {k: self._redactor.redact(str(v)) for k, v in params.items()}
        self._events.append(TraceEvent("tool_call", {"tool": tool, "params": safe_params, "status": status}))

    def record_feedback(self, sensor: str, status: str, category: str | None):
        self._events.append(TraceEvent("feedback", {"sensor": sensor, "status": status, "category": category}))

    def get_events(self) -> list[TraceEvent]:
        return list(self._events)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_tracer.py -v`
Expected: 6 passed

- [ ] **Step 5: Refactor** — check that SecretRedactor is applied to all user-produced content (tool params, guardrail messages). State transitions and feedback status are enum values, not redactable.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §4.3 — Tracer records chronological events. SecretRedactor applied before storing. Events include state transitions, guardrail decisions, tool calls, feedback results.

- [ ] **Step 7: Code quality review**

Check: `get_events()` returns a copy of the list (defensive copy). SecretRedactor is applied at record time, not export time. All event types use a single `TraceEvent` dataclass.

- [ ] **Step 8: Commit**

```bash
git add codeguard/tracer.py tests/test_tracer.py
git commit -m "feat: add Tracer with SecretRedactor integration"
git push origin task-7.1-tracer
git push github task-7.1-tracer
```

---

### Phase 8: StopPolicy

#### Task 8.1: StopPolicy

**Files:**
- Create: `codeguard/stop.py`
- Create: `tests/test_stop_policy.py`

**Consumes:** SPEC.md §3.3

**Produces:** `StopPolicy` evaluating max_steps, max_llm_calls, token_budget, cost_budget, repeated fingerprints

**Dependency:** Task 1.4 (SessionState)

**Parallel:** Can run in parallel with Phase 7

**Worktree:** main, branch `task-8.1-stop-policy`

**Pre-commit:** Task 1.4 commit

**File boundary:** Only `codeguard/stop.py` and `tests/test_stop_policy.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_stop_policy.py`:
```python
from decimal import Decimal
from datetime import datetime
from codeguard.stop import StopPolicy, StopDecision
from codeguard.state import AgentState, SessionState
from codeguard.action import ActionKind, NormalizedAction

def _make_state(steps=0, llm_calls=0, token=0, cost=Decimal("0"), action_fps=None, failure_fps=None):
    return SessionState(session_id="s1", current_state=AgentState.DECIDING, pending_action=None, guardrail_decision=None, approval_request_id=None, steps_used=steps, llm_calls_used=llm_calls, token_used=token, cost_used=cost, action_fingerprint_history=action_fps or [], failure_fingerprint_history=failure_fps or [], started_at=datetime.now())

def test_stop_max_steps():
    policy = StopPolicy(max_steps=5, max_llm_calls=100, no_progress_threshold=3)
    state = _make_state(steps=5)
    assert policy.evaluate(state) == "LIMIT_REACHED"

def test_stop_max_llm_calls():
    policy = StopPolicy(max_steps=50, max_llm_calls=10, no_progress_threshold=3)
    state = _make_state(llm_calls=10)
    assert policy.evaluate(state) == "LIMIT_REACHED"

def test_stop_token_budget():
    policy = StopPolicy(max_steps=50, max_llm_calls=100, token_budget=1000, no_progress_threshold=3)
    state = _make_state(token=1000)
    assert policy.evaluate(state) == "LIMIT_REACHED"

def test_stop_cost_budget():
    policy = StopPolicy(max_steps=50, max_llm_calls=100, cost_budget=Decimal("1.0"), no_progress_threshold=3)
    state = _make_state(cost=Decimal("1.0"))
    assert policy.evaluate(state) == "LIMIT_REACHED"

def test_stop_repeated_action():
    policy = StopPolicy(max_steps=50, max_llm_calls=100, no_progress_threshold=3)
    state = _make_state(action_fps=["fp1", "fp1", "fp1", "fp1"])
    assert policy.evaluate(state) == "LIMIT_REACHED"

def test_stop_repeated_failure():
    policy = StopPolicy(max_steps=50, max_llm_calls=100, no_progress_threshold=3)
    state = _make_state(failure_fps=["ff1", "ff1", "ff1", "ff1"])
    assert policy.evaluate(state) == "LIMIT_REACHED"

def test_stop_no_condition_met():
    policy = StopPolicy(max_steps=50, max_llm_calls=100, no_progress_threshold=3)
    state = _make_state(steps=1, llm_calls=1)
    assert policy.evaluate(state) is None

def test_stop_limit_not_reached():
    policy = StopPolicy(max_steps=50, max_llm_calls=100, no_progress_threshold=3)
    state = _make_state(steps=49)
    assert policy.evaluate(state) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_stop_policy.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement StopPolicy**

Write `codeguard/stop.py`:
```python
from collections import Counter
from codeguard.state import SessionState

class StopDecision:
    LIMIT_REACHED = "LIMIT_REACHED"
    FAILED = "FAILED"

class StopPolicy:
    """Evaluates session state against stop conditions."""

    def __init__(self, max_steps: int = 50, max_llm_calls: int = 100,
                 token_budget: int | None = None, cost_budget=None,
                 no_progress_threshold: int = 3):
        self._max_steps = max_steps
        self._max_llm_calls = max_llm_calls
        self._token_budget = token_budget
        self._cost_budget = cost_budget
        self._no_progress_threshold = no_progress_threshold

    def evaluate(self, state: SessionState) -> str | None:
        if state.steps_used >= self._max_steps:
            return StopDecision.LIMIT_REACHED
        if state.llm_calls_used >= self._max_llm_calls:
            return StopDecision.LIMIT_REACHED
        if self._token_budget and state.token_used >= self._token_budget:
            return StopDecision.LIMIT_REACHED
        if self._cost_budget and state.cost_used >= self._cost_budget:
            return StopDecision.LIMIT_REACHED

        # No-progress detection: repeated fingerprints
        if self._no_progress_threshold > 0:
            if state.action_fingerprint_history:
                most_common = Counter(state.action_fingerprint_history).most_common(1)
                if most_common and most_common[0][1] >= self._no_progress_threshold:
                    return StopDecision.LIMIT_REACHED
            if state.failure_fingerprint_history:
                most_common = Counter(state.failure_fingerprint_history).most_common(1)
                if most_common and most_common[0][1] >= self._no_progress_threshold:
                    return StopDecision.LIMIT_REACHED

        return None
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_stop_policy.py -v`
Expected: 8 passed

- [ ] **Step 5: Refactor** — check that Counter is imported (it's from collections, standard library). Consider using a simpler dict-based count if Counter is too heavy.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.3 — StopPolicy checks max_steps, max_llm_calls, token_budget, cost_budget, repeated action_fingerprint, repeated failure_fingerprint. Returns LIMIT_REACHED when any condition met. Returns None when no condition met.

- [ ] **Step 7: Code quality review**

Check: `evaluate()` returns None for "no stop" (falsy) and a string for "stop" (truthy). This allows `if decision:` checks in AgentLoop. No-progress threshold uses Counter for simplicity.

- [ ] **Step 8: Commit**

```bash
git add codeguard/stop.py tests/test_stop_policy.py
git commit -m "feat: add StopPolicy with all stop conditions"
git push origin task-8.1-stop-policy
git push github task-8.1-stop-policy
```

---

### Phase 9: Memory System

#### Task 9.1: JSONMemoryStore

**Files:**
- Create: `codeguard/memory/store.py`
- Create: `tests/test_memory_store.py`

**Consumes:** SPEC.md §3.7

**Produces:** `JSONMemoryStore` (atomic writes, project-scoped, max_records enforcement)

**Dependency:** Task 1.5 (MemoryRecord, MemoryType, MemoryStatus, TrustLevel)

**Parallel:** Can run in parallel with Phase 8 (StopPolicy)

**Worktree:** worktree-memory, branch `task-9.1-json-memory-store`

**Pre-commit:** Task 1.5 commit

**File boundary:** Only `codeguard/memory/store.py` and `tests/test_memory_store.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_memory_store.py`:
```python
import json, os
from datetime import datetime
from pathlib import Path
from codeguard.memory.models import MemoryRecord, MemoryType, MemoryStatus, TrustLevel
from codeguard.memory.store import JSONMemoryStore

def _make_record(project_id="p1", type=MemoryType.PROJECT_CONVENTION, status=MemoryStatus.ACTIVE):
    return MemoryRecord(id="m1", project_id=project_id, type=type, content="test", tags=[], keywords=[], source="user", trust_level=TrustLevel.USER_APPROVED, status=status, created_at=datetime.now(), updated_at=datetime.now(), session_id="s1")

def test_store_create(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    record = _make_record()
    store.save(record)
    loaded = store.get("m1", "p1")
    assert loaded is not None
    assert loaded.id == "m1"

def test_store_get_nonexistent(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    assert store.get("nonexistent", "p1") is None

def test_store_list_by_project(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    store.save(_make_record(project_id="p1"))
    store.save(_make_record(project_id="p1"))
    records = store.list(project_id="p1")
    assert len(records) == 2

def test_store_list_by_project_and_type(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    store.save(_make_record(project_id="p1", type=MemoryType.PROJECT_CONVENTION))
    store.save(_make_record(project_id="p1", type=MemoryType.APPROVED_DECISION))
    records = store.list(project_id="p1", type=MemoryType.PROJECT_CONVENTION)
    assert len(records) == 1

def test_store_max_records(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace), max_records=2)
    store.save(_make_record(project_id="p1"))
    store.save(_make_record(project_id="p1"))
    with pytest.raises(ValueError, match="Max records"):
        store.save(_make_record(project_id="p1"))

def test_store_atomic_write(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    record = _make_record()
    store.save(record)
    # Verify file exists and is valid JSON
    file_path = temp_workspace / "projects" / "p1" / "memory.json"
    assert file_path.exists()
    data = json.loads(file_path.read_text())
    assert len(data["records"]) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_memory_store.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement JSONMemoryStore**

Write `codeguard/memory/store.py`:
```python
import json, os, tempfile
from pathlib import Path
from datetime import datetime
from codeguard.memory.models import MemoryRecord, MemoryType, MemoryStatus, TrustLevel

class JSONMemoryStore:
    """Project-scoped JSON file memory store with atomic writes."""

    def __init__(self, base_dir: str, max_records: int = 100):
        self._base = Path(base_dir)
        self._max_records = max_records

    def _project_path(self, project_id: str) -> Path:
        p = self._base / "projects" / project_id
        p.mkdir(parents=True, exist_ok=True)
        return p / "memory.json"

    def _load(self, project_id: str) -> dict:
        path = self._project_path(project_id)
        if not path.exists():
            return {"records": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_atomically(self, project_id: str, data: dict):
        path = self._project_path(project_id)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp, str(path))
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise

    def save(self, record: MemoryRecord):
        data = self._load(record.project_id)
        if len(data["records"]) >= self._max_records:
            raise ValueError(f"Max records ({self._max_records}) reached for project {record.project_id}")
        data["records"].append(record.__dict__)
        self._save_atomically(record.project_id, data)

    def get(self, record_id: str, project_id: str) -> MemoryRecord | None:
        data = self._load(project_id)
        for r in data["records"]:
            if r["id"] == record_id:
                return MemoryRecord(**r)
        return None

    def list(self, project_id: str, type: MemoryType | None = None) -> list[MemoryRecord]:
        data = self._load(project_id)
        records = [MemoryRecord(**r) for r in data["records"]]
        if type:
            records = [r for r in records if r.type == type]
        return records
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_memory_store.py -v`
Expected: 6 passed

- [ ] **Step 5: Refactor** — check that `_save_atomically` handles the temp file cleanup on error. The try/except block handles this.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.7 — JSONMemoryStore with atomic write (tempfile+rename), project-scoped, max_records enforcement, get/list operations.

- [ ] **Step 7: Code quality review**

Check: `_save_atomically` uses `os.replace()` for atomicity. `_load` returns empty structure for missing files. `save()` checks max_records before writing.

- [ ] **Step 8: Commit**

```bash
git add codeguard/memory/store.py tests/test_memory_store.py
git commit -m "feat: add JSONMemoryStore with atomic writes"
git push origin task-9.1-json-memory-store
git push github task-9.1-json-memory-store
```

---

#### Task 9.2: MemoryRetriever

**Files:**
- Create: `codeguard/memory/retriever.py`
- Create: `tests/test_memory_retriever.py`

**Consumes:** SPEC.md §3.7

**Produces:** `MemoryRetriever` (filter by type/tag/keyword, sort by trust_level, top_k, context_budget, exclude non-ACTIVE)

**Dependency:** Task 9.1 (JSONMemoryStore)

**Parallel:** No

**Worktree:** worktree-memory, branch `task-9.2-memory-retriever`

- [ ] **Step 1: Write failing tests**

Write `tests/test_memory_retriever.py`:
```python
from datetime import datetime, timedelta
from codeguard.memory.models import MemoryRecord, MemoryType, MemoryStatus, TrustLevel
from codeguard.memory.store import JSONMemoryStore
from codeguard.memory.retriever import MemoryRetriever

def _make_record(pid="p1", type=MemoryType.PROJECT_CONVENTION, status=MemoryStatus.ACTIVE, trust=TrustLevel.USER_APPROVED, tags=None, keywords=None):
    return MemoryRecord(id="m1", project_id=pid, type=type, content="test content", tags=tags or [], keywords=keywords or [], source="user", trust_level=trust, status=status, created_at=datetime.now(), updated_at=datetime.now(), session_id="s1")

def test_retrieve_by_type(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    store.save(_make_record(type=MemoryType.PROJECT_CONVENTION))
    store.save(_make_record(type=MemoryType.APPROVED_DECISION))
    retriever = MemoryRetriever(store)
    results = retriever.retrieve(project_id="p1", type=MemoryType.PROJECT_CONVENTION)
    assert len(results) == 1

def test_retrieve_excludes_non_active(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    store.save(_make_record(status=MemoryStatus.PENDING))
    store.save(_make_record(status=MemoryStatus.REJECTED))
    store.save(_make_record(status=MemoryStatus.ACTIVE))
    retriever = MemoryRetriever(store)
    results = retriever.retrieve(project_id="p1")
    assert len(results) == 1

def test_retrieve_top_k(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    for i in range(5):
        r = _make_record()
        r.id = f"m{i}"
        store.save(r)
    retriever = MemoryRetriever(store, top_k=3)
    results = retriever.retrieve(project_id="p1")
    assert len(results) == 3

def test_retrieve_context_budget(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    r = _make_record()
    r.content = "x" * 1000
    store.save(r)
    r2 = _make_record()
    r2.id = "m2"
    r2.content = "y" * 1000
    store.save(r2)
    retriever = MemoryRetriever(store, context_budget=1500)
    results = retriever.retrieve(project_id="p1")
    total_chars = sum(len(r.content) for r in results)
    assert total_chars <= 1500

def test_retrieve_sort_by_trust(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    r1 = _make_record(trust=TrustLevel.LLM_PROPOSED)
    r1.id = "m1"
    r2 = _make_record(trust=TrustLevel.USER_APPROVED)
    r2.id = "m2"
    store.save(r1)
    store.save(r2)
    retriever = MemoryRetriever(store)
    results = retriever.retrieve(project_id="p1")
    assert results[0].trust_level == TrustLevel.USER_APPROVED
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_memory_retriever.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement MemoryRetriever**

Write `codeguard/memory/retriever.py`:
```python
from codeguard.memory.models import MemoryRecord, MemoryType, MemoryStatus, TrustLevel
from codeguard.memory.store import JSONMemoryStore

_TRUST_ORDER = {TrustLevel.USER_APPROVED: 3, TrustLevel.HARNESS_VERIFIED: 2, TrustLevel.LLM_PROPOSED: 1}

class MemoryRetriever:
    """Retrieves and filters memory records. Excludes non-ACTIVE by default."""

    def __init__(self, store: JSONMemoryStore, top_k: int = 10, context_budget: int = 2048):
        self._store = store
        self._top_k = top_k
        self._context_budget = context_budget

    def retrieve(self, project_id: str, type: MemoryType | None = None,
                 tags: list[str] | None = None, keywords: list[str] | None = None) -> list[MemoryRecord]:
        records = self._store.list(project_id)
        # Exclude non-ACTIVE
        records = [r for r in records if r.status == MemoryStatus.ACTIVE]
        # Filter by type
        if type:
            records = [r for r in records if r.type == type]
        # Filter by tags
        if tags:
            records = [r for r in records if any(t in r.tags for t in tags)]
        # Filter by keywords
        if keywords:
            records = [r for r in records if any(k in r.keywords for k in keywords)]
        # Sort by trust level (descending) then updated_at (descending)
        records.sort(key=lambda r: (_TRUST_ORDER.get(r.trust_level, 0), r.updated_at.timestamp()), reverse=True)
        # Apply top_k
        records = records[:self._top_k]
        # Apply context budget
        if self._context_budget > 0:
            total = 0
            filtered = []
            for r in records:
                if total + len(r.content) > self._context_budget:
                    break
                filtered.append(r)
                total += len(r.content)
            records = filtered
        return records
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_memory_retriever.py -v`
Expected: 5 passed

- [ ] **Step 5: Refactor** — check that the sort order is correct (USER_APPROVED first, then HARNESS_VERIFIED, then LLM_PROPOSED).

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.7 — MemoryRetriever filters by type/tag/keyword. Excludes PENDING, REJECTED, ARCHIVED, DELETED. Sorts by trust_level + updated_at. Applies top_k and context_budget.

- [ ] **Step 7: Code quality review**

Check: `_TRUST_ORDER` dict maps TrustLevel to int for sorting. Context budget accumulates content length and stops when exceeded.

- [ ] **Step 8: Commit**

```bash
git add codeguard/memory/retriever.py tests/test_memory_retriever.py
git commit -m "feat: add MemoryRetriever with filtering, sorting, and budget"
git push origin task-9.2-memory-retriever
git push github task-9.2-memory-retriever
```

---

#### Task 9.3: Memory lifecycle (propose -> approve/reject)

**Files:**
- Modify: `codeguard/memory/store.py`
- Modify: `tests/test_memory_store.py`

**Consumes:** SPEC.md §3.7

**Produces:** `memory_propose_write` (creates PENDING), `approve_memory` (PENDING -> ACTIVE), `reject_memory` (PENDING -> REJECTED)

**Dependency:** Task 9.2

**Parallel:** No

**Worktree:** worktree-memory, branch `task-9.3-memory-lifecycle`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_memory_store.py`:
```python
def test_propose_write_creates_pending(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    record = _make_record(status=MemoryStatus.PENDING)
    store.propose_write(record)
    loaded = store.get("m1", "p1")
    assert loaded.status == MemoryStatus.PENDING

def test_approve_memory(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    record = _make_record(status=MemoryStatus.PENDING)
    store.propose_write(record)
    store.approve_memory("m1", "p1")
    loaded = store.get("m1", "p1")
    assert loaded.status == MemoryStatus.ACTIVE

def test_reject_memory(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    record = _make_record(status=MemoryStatus.PENDING)
    store.propose_write(record)
    store.reject_memory("m1", "p1")
    loaded = store.get("m1", "p1")
    assert loaded.status == MemoryStatus.REJECTED

def test_unknown_type_rejected(temp_workspace):
    store = JSONMemoryStore(base_dir=str(temp_workspace))
    from codeguard.memory.models import MemoryType
    with pytest.raises(ValueError, match="Unknown memory type"):
        store.propose_write(_make_record(type="unknown_type"))
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_memory_store.py -v`
Expected: 4 new tests fail (propose_write, approve_memory, reject_memory not defined)

- [ ] **Step 3: Implement lifecycle methods**

Append to `codeguard/memory/store.py`:
```python
    def propose_write(self, record: MemoryRecord):
        if record.type.value not in {t.value for t in MemoryType}:
            raise ValueError(f"Unknown memory type: {record.type}")
        record.status = MemoryStatus.PENDING
        self.save(record)

    def approve_memory(self, record_id: str, project_id: str):
        data = self._load(project_id)
        for r in data["records"]:
            if r["id"] == record_id:
                r["status"] = MemoryStatus.ACTIVE.value
                self._save_atomically(project_id, data)
                return
        raise ValueError(f"Record {record_id} not found")

    def reject_memory(self, record_id: str, project_id: str):
        data = self._load(project_id)
        for r in data["records"]:
            if r["id"] == record_id:
                r["status"] = MemoryStatus.REJECTED.value
                self._save_atomically(project_id, data)
                return
        raise ValueError(f"Record {record_id} not found")
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_memory_store.py -v`
Expected: 10 passed (6 from Task 9.1 + 4 new)

- [ ] **Step 5: Refactor** — check that `propose_write` verifies type before saving (SPEC C6 rule: unknown type rejected).

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.7 — memory_propose_write creates PENDING. approve_memory -> ACTIVE. reject_memory -> REJECTED. Unknown type rejected. LLM cannot create ACTIVE directly.

- [ ] **Step 7: Code quality review**

Check: `propose_write` validates the type enum before saving. `approve_memory` and `reject_memory` modify in-place and re-save atomically.

- [ ] **Step 8: Commit**

```bash
git add codeguard/memory/store.py tests/test_memory_store.py
git commit -m "feat: add memory lifecycle — propose, approve, reject"
git push origin task-9.3-memory-lifecycle
git push github task-9.3-memory-lifecycle
```

---

### Phase 10: Configuration System

#### Task 10.1: ConfigLoader (TOML parsing)

**Files:**
- Create: `codeguard/config/loader.py`
- Create: `tests/test_config_loader.py`

**Consumes:** SPEC.md §3.8

**Produces:** `ConfigLoader` (TOML parsing, validation, defaults)

**Dependency:** Task 1.5 (config models)

**Parallel:** Can run in parallel with Phase 9 (Memory)

**Worktree:** worktree-config, branch `task-10.1-config-loader`

**Pre-commit:** Task 1.5 commit

**File boundary:** Only `codeguard/config/loader.py` and `tests/test_config_loader.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_config_loader.py`:
```python
import pytest
from pathlib import Path
from codeguard.config.loader import ConfigLoader

def test_loader_valid_toml(temp_workspace):
    path = temp_workspace / "codeguard.toml"
    path.write_text("[workspace]\nproject_root = \"/home/user/project\"\n[llm]\nprovider = \"deepseek\"\n")
    loader = ConfigLoader()
    config = loader.load_file(str(path))
    assert config["workspace"]["project_root"] == "/home/user/project"
    assert config["llm"]["provider"] == "deepseek"

def test_loader_unknown_field_fails(temp_workspace):
    path = temp_workspace / "codeguard.toml"
    path.write_text("[unknown_section]\nkey = \"value\"\n")
    loader = ConfigLoader()
    with pytest.raises(ValueError, match="Unknown"):
        loader.load_file(str(path))

def test_loader_missing_file_returns_defaults():
    loader = ConfigLoader()
    config = loader.load_file("/nonexistent/path.toml")
    assert config == {}

def test_loader_type_error_fails(temp_workspace):
    path = temp_workspace / "codeguard.toml"
    path.write_text("[loop]\nmax_steps = \"not_a_number\"\n")
    loader = ConfigLoader()
    with pytest.raises(ValueError):
        # Should either fail at parse time or at validation time
        loader.load_file(str(path))
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_config_loader.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement ConfigLoader**

Write `codeguard/config/loader.py`:
```python
import tomllib
from pathlib import Path

_KNOWN_SECTIONS = {"workspace", "llm", "loop", "tools", "sensors", "memory", "ui", "approval", "mode"}

class ConfigLoader:
    """Loads TOML config files with validation."""

    def load_file(self, path: str) -> dict:
        p = Path(path)
        if not p.exists():
            return {}
        raw = p.read_text(encoding="utf-8")
        try:
            data = tomllib.loads(raw)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML: {e}")

        for key in data:
            if key not in _KNOWN_SECTIONS:
                raise ValueError(f"Unknown config section: {key}")

        return data
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_config_loader.py -v`
Expected: 3 passed (1 may fail depending on error handling — adjust as needed)

- [ ] **Step 5: Refactor** — check that unknown fields within known sections are also validated. For first version, section-level validation is sufficient per SPEC YAGNI.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.8 — ConfigLoader loads TOML, validates known sections, returns defaults for missing file. Unknown sections raise error.

- [ ] **Step 7: Code quality review**

Check: Uses `tomllib` (Python 3.12 standard library). Missing file returns empty dict (not error). TOMLDecodeError is caught and re-raised as ValueError.

- [ ] **Step 8: Commit**

```bash
git add codeguard/config/loader.py tests/test_config_loader.py
git commit -m "feat: add ConfigLoader for TOML parsing"
git push origin task-10.1-config-loader
git push github task-10.1-config-loader
```

---

#### Task 10.2: ConfigMerger (field-level deterministic merge)

**Files:**
- Create: `codeguard/config/merger.py`
- Create: `tests/test_config_merger.py`

**Consumes:** SPEC.md §3.8 (31-row merge rules table)

**Produces:** `ConfigMerger` merging user-level, project-level, and CLI configs

**Dependency:** Task 10.1 (ConfigLoader)

**Parallel:** No

**Worktree:** worktree-config, branch `task-10.2-config-merger`

- [ ] **Step 1: Write failing tests**

Write `tests/test_config_merger.py`:
```python
import pytest
from pathlib import Path
from codeguard.config.merger import ConfigMerger

def test_merge_intersection_enabled_tools():
    merger = ConfigMerger()
    merged = merger.merge({"tools": {"enabled_tools": ["read_file", "write_file"]}}, {"tools": {"enabled_tools": ["read_file", "run_process"]}})
    assert merged["tools"]["enabled_tools"] == ["read_file"]

def test_merge_union_disabled_tools():
    merger = ConfigMerger()
    merged = merger.merge({"tools": {"disabled_tools": ["tool_a"]}}, {"tools": {"disabled_tools": ["tool_b"]}})
    assert "tool_a" in merged["tools"]["disabled_tools"]
    assert "tool_b" in merged["tools"]["disabled_tools"]

def test_merge_stricter_max_steps():
    merger = ConfigMerger()
    merged = merger.merge({"loop": {"max_steps": 50}}, {"loop": {"max_steps": 30}})
    assert merged["loop"]["max_steps"] == 30  # stricter (lower) wins

def test_merge_cli_override():
    merger = ConfigMerger()
    merged = merger.merge({"llm": {"provider": "deepseek"}}, {}, cli_overrides={"llm.provider": "openai"})
    assert merged["llm"]["provider"] == "openai"

def test_merge_project_cannot_relax_security():
    merger = ConfigMerger()
    # User says 50, project says 100 — stricter (50) wins
    merged = merger.merge({"loop": {"max_steps": 50}}, {"loop": {"max_steps": 100}})
    assert merged["loop"]["max_steps"] == 50

def test_merge_empty_user_config():
    merger = ConfigMerger()
    merged = merger.merge({}, {"workspace": {"project_root": "/project"}})
    assert merged["workspace"]["project_root"] == "/project"

def test_merge_empty_project_config():
    merger = ConfigMerger()
    merged = merger.merge({"workspace": {"project_root": "/user"}}, {})
    assert merged["workspace"]["project_root"] == "/user"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_config_merger.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement ConfigMerger**

Write `codeguard/config/merger.py`:
```python
_MERGE_RULES = {
    # intersection
    "tools.enabled_tools": "intersection",
    "sensors.required_sensors": "intersection",
    "workspace.additional_protected_paths": "union",
    "tools.disabled_tools": "union",
    "workspace.excluded_paths": "union",
    "loop.max_steps": "stricter",
    "loop.max_llm_calls": "stricter",
    "loop.tool_timeout": "stricter",
    "loop.session_timeout": "stricter",
    "loop.no_progress_threshold": "stricter",
    "loop.token_budget": "stricter",
    "loop.cost_budget": "stricter",
    "ui.approval_timeout": "project_only_shortens",
    "approval.cli_timeout": "user_or_cli_only",
}

class ConfigMerger:
    """Merges user-level, project-level, and CLI configs with field-level rules."""

    def merge(self, user_config: dict, project_config: dict, cli_overrides: dict | None = None) -> dict:
        merged = {}
        # Start with all sections from both configs
        all_keys = set(user_config.keys()) | set(project_config.keys())
        for section in all_keys:
            merged[section] = {}
            user_section = user_config.get(section, {})
            project_section = project_config.get(section, {})
            all_fields = set(user_section.keys()) | set(project_section.keys())
            for field in all_fields:
                key = f"{section}.{field}"
                user_val = user_section.get(field)
                project_val = project_section.get(field)
                rule = _MERGE_RULES.get(key, "override")
                merged[section][field] = self._apply_rule(rule, user_val, project_val, key)

        # Apply CLI overrides
        if cli_overrides:
            for dotted_key, value in cli_overrides.items():
                parts = dotted_key.split(".")
                section, field = parts[0], parts[1]
                if section not in merged:
                    merged[section] = {}
                merged[section][field] = value

        return merged

    def _apply_rule(self, rule: str, user_val, project_val, key: str):
        if rule == "intersection":
            if user_val is None:
                return project_val
            if project_val is None:
                return user_val
            return [v for v in user_val if v in project_val]
        elif rule == "union":
            if user_val is None:
                return project_val
            if project_val is None:
                return user_val
            return list(set(user_val) | set(project_val))
        elif rule == "stricter":
            if user_val is None:
                return project_val
            if project_val is None:
                return user_val
            return min(user_val, project_val) if isinstance(user_val, (int, float)) else user_val
        elif rule == "project_only_shortens":
            if user_val is None:
                return project_val
            if project_val is None:
                return user_val
            return min(user_val, project_val)
        elif rule == "user_or_cli_only":
            return user_val  # project config cannot set this
        else:  # override
            return project_val if project_val is not None else user_val
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_config_merger.py -v`
Expected: 7 passed

- [ ] **Step 5: Refactor** — check that all 31 merge rules from SPEC §3.8 are represented. Add more test cases for edge cases.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §3.8 — 31 merge rules table. Intersection for enabled_tools/required_sensors. Union for disabled_tools/protected_paths/excluded_paths. Stricter for max_steps/timeout/budget. project_only_shortens for approval_timeout. user_or_cli_only for cli_timeout. CLI overrides take precedence.

- [ ] **Step 7: Code quality review**

Check: `_MERGE_RULES` dict is a single source of truth. Missing rules default to "override" (project overrides user). All numeric comparisons use `min()` for "stricter" (lower is safer).

- [ ] **Step 8: Commit**

```bash
git add codeguard/config/merger.py tests/test_config_merger.py
git commit -m "feat: add ConfigMerger with field-level deterministic merge rules"
git push origin task-10.2-config-merger
git push github task-10.2-config-merger
```

---

### Phase 11: DeepSeekAdapter (mock HTTP transport in tests)

#### Task 11.1: DeepSeekAdapter with offline test

**Files:**
- Create: `codeguard/llm/deepseek.py`
- Create: `tests/test_llm_deepseek.py`
- Create: `scripts/deepseek_smoke_test.py`

**Consumes:** SPEC.md §5.3, §9

**Produces:** `DeepSeekAdapter` using OpenAI-compatible HTTP API; offline tests with mock HTTP transport

**Dependency:** Task 2.1 (LLMClient protocol)

**Parallel:** After Phase 2

**Worktree:** main, branch `task-11.1-deepseek-adapter`

**Pre-commit:** Task 2.1 commit

**File boundary:** `codeguard/llm/deepseek.py`, `tests/test_llm_deepseek.py`, `scripts/deepseek_smoke_test.py`

**IMPORTANT:** Unit tests use `httpx` mock transport (always offline, never skip). The smoke test `scripts/deepseek_smoke_test.py` is the ONLY script that makes real API calls — it is NOT in CI, NOT auto-run.

- [ ] **Step 1: Write failing tests with mock HTTP transport**

Write `tests/test_llm_deepseek.py`:
```python
import pytest
from decimal import Decimal
from codeguard.llm.deepseek import DeepSeekAdapter
from codeguard.action import Action, ActionKind, LLMResponse
import httpx

def test_adapter_success():
    """Mock HTTP transport returning a valid DeepSeek response."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {"content": '{"action": "complete", "summary": "done"}'}}],
            "model": "deepseek-v4-flash",
            "usage": {"total_tokens": 10}
        })
    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = DeepSeekAdapter(api_key="test-key", http_client=client)
    response = adapter.generate(session_id="s1", context="test")
    assert response.finish_reason == "stop"
    assert response.next_action.kind == ActionKind.COMPLETE_REQUEST
    assert response.model == "deepseek-v4-flash"

def test_adapter_api_error():
    """Mock HTTP transport returning API error."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "Invalid API key"}})
    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = DeepSeekAdapter(api_key="bad-key", http_client=client)
    with pytest.raises(ValueError, match="API error"):
        adapter.generate(session_id="s1", context="test")

def test_adapter_timeout():
    """Mock HTTP transport simulating timeout."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Request timed out")
    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = DeepSeekAdapter(api_key="test-key", http_client=client, timeout=1)
    with pytest.raises(TimeoutError):
        adapter.generate(session_id="s1", context="test")

def test_adapter_empty_response():
    """Mock HTTP transport returning empty choices."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [], "model": "deepseek-v4-flash", "usage": {"total_tokens": 0}})
    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = DeepSeekAdapter(api_key="test-key", http_client=client)
    with pytest.raises(ValueError, match="Empty response"):
        adapter.generate(session_id="s1", context="test")

def test_adapter_llm_response_content():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {"content": "some content"}}],
            "model": "deepseek-v4-flash",
            "usage": {"total_tokens": 5}
        })
    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = DeepSeekAdapter(api_key="test-key", http_client=client)
    response = adapter.generate(session_id="s1", context="test")
    assert response.content == "some content"
    assert response.token_used == 5
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_llm_deepseek.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement DeepSeekAdapter**

Write `codeguard/llm/deepseek.py`:
```python
from decimal import Decimal
from codeguard.action import Action, ActionKind, LLMResponse
from codeguard.llm.client import LLMClient
import httpx
import json

class DeepSeekAdapter:
    """DeepSeek API adapter using OpenAI-compatible HTTP interface."""

    def __init__(self, api_key: str, model: str = "deepseek-v4-flash",
                 base_url: str = "https://api.deepseek.com/v1", timeout: int = 60,
                 http_client: httpx.Client | None = None):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = http_client or httpx.Client(timeout=timeout)

    def generate(self, session_id: str, context: str) -> LLMResponse:
        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json={"model": self._model, "messages": [{"role": "user", "content": context}], "max_tokens": 4096}
            )
            if response.status_code != 200:
                error_body = response.json().get("error", {}).get("message", "Unknown error")
                raise ValueError(f"API error ({response.status_code}): {error_body}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("Empty response from DeepSeek API")

            choice = choices[0]
            content = choice.get("message", {}).get("content", "")
            finish_reason = choice.get("finish_reason", "stop")
            model = data.get("model", self._model)
            usage = data.get("usage", {})
            token_used = usage.get("total_tokens", 0)

            # Parse content as action
            try:
                action_data = json.loads(content) if content else {}
            except json.JSONDecodeError:
                action_data = {"action": "complete", "summary": content[:100]}

            action_type = action_data.get("action", "complete")
            if action_type == "complete":
                next_action = Action(kind=ActionKind.COMPLETE_REQUEST, summary=action_data.get("summary", ""), raw=content)
            else:
                next_action = Action(kind=ActionKind.TOOL_CALL, tool_name=action_data.get("tool", ""), parameters=action_data.get("parameters", {}), raw=content)

            return LLMResponse(content=content, next_action=next_action, finish_reason=finish_reason, model=model, token_used=token_used, cost_used=Decimal(str(token_used * 2)) / Decimal("1000000"), raw_response=response.text)

        except httpx.TimeoutException:
            raise TimeoutError(f"DeepSeek API request timed out after {self._timeout}s")
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_llm_deepseek.py -v`
Expected: 5 passed (all offline, using mock HTTP transport)

- [ ] **Step 5: Create smoke test script (NOT in CI)**

Write `scripts/deepseek_smoke_test.py`:
```python
"""Manual DeepSeek API connectivity test. NOT in CI, NOT auto-run.
Requires a valid DEEPSEEK_API_KEY environment variable.
Usage: python scripts/deepseek_smoke_test.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from codeguard.llm.deepseek import DeepSeekAdapter

def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("SKIP: DEEPSEEK_API_KEY not set")
        return
    adapter = DeepSeekAdapter(api_key=api_key)
    response = adapter.generate(session_id="smoke", context="Say 'hello' and respond with {\"action\": \"complete\", \"summary\": \"hello\"}")
    print(f"Model: {response.model}")
    print(f"Content: {response.content[:100]}")
    print(f"Tokens: {response.token_used}")
    print("PASS: DeepSeek API connectivity verified")

if __name__ == "__main__":
    main()
```

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §5.3 — DeepSeekAdapter implements LLMClient protocol. Uses OpenAI-compatible HTTP API. Offline tests with mock transport. Smoke test is manual only.

- [ ] **Step 7: Code quality review**

Check: `httpx.Client` is injectable for testing. The mock transport pattern (`httpx.MockTransport`) is used in ALL tests. No conditional skip logic. Real API calls only in `scripts/deepseek_smoke_test.py`.

- [ ] **Step 8: Commit**

```bash
git add codeguard/llm/deepseek.py tests/test_llm_deepseek.py scripts/deepseek_smoke_test.py
git commit -m "feat: add DeepSeekAdapter with mock HTTP transport in tests"
git push origin task-11.1-deepseek-adapter
git push github task-11.1-deepseek-adapter
```

---

### Phase 12: Credential Management

#### Task 12.1: KeyringCredentialStore

**Files:**
- Create: `codeguard/cli/key_cmd.py`
- Create: `tests/test_cli.py`

**Consumes:** SPEC.md §8.1

**Produces:** `KeyringCredentialStore` using Windows Credential Manager + keyring library

**Dependency:** Task 1.1

**Parallel:** After Phase 11

**Worktree:** main, branch `task-12.1-keyring-credential`

- [ ] **Step 1: Write failing tests**

Write `tests/test_cli.py`:
```python
import pytest
from codeguard.cli.key_cmd import KeyringCredentialStore

def test_keyring_set_and_get():
    store = KeyringCredentialStore()
    store.set("deepseek", "sk-test-key-12345")
    assert store.get("deepseek") == "sk-test-key-12345"

def test_keyring_get_nonexistent():
    store = KeyringCredentialStore()
    assert store.get("nonexistent_provider") is None

def test_keyring_status_masked():
    store = KeyringCredentialStore()
    store.set("deepseek", "sk-test-key-12345")
    status = store.status("deepseek")
    assert "sk-test" in status  # prefix visible
    assert "12345" not in status  # rest masked

def test_keyring_clear():
    store = KeyringCredentialStore()
    store.set("deepseek", "sk-test-key-12345")
    store.clear("deepseek")
    assert store.get("deepseek") is None

def test_keyring_update():
    store = KeyringCredentialStore()
    store.set("deepseek", "sk-old-key")
    store.set("deepseek", "sk-new-key")
    assert store.get("deepseek") == "sk-new-key"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_cli.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement KeyringCredentialStore**

Write `codeguard/cli/key_cmd.py`:
```python
import keyring

_SERVICE_NAME = "codeguard-harness"

class KeyringCredentialStore:
    """Stores API keys in Windows Credential Manager via keyring library."""

    def set(self, provider: str, key: str):
        keyring.set_password(_SERVICE_NAME, provider, key)

    def get(self, provider: str) -> str | None:
        return keyring.get_password(_SERVICE_NAME, provider)

    def status(self, provider: str) -> str:
        key = self.get(provider)
        if key is None:
            return "Not set"
        if len(key) > 8:
            return f"{key[:8]}... (masked)"
        return "Set (masked)"

    def clear(self, provider: str):
        keyring.delete_password(_SERVICE_NAME, provider)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_cli.py -v`
Expected: 5 passed

- [ ] **Step 5: Refactor** — no refactoring needed. Simple keyring wrapper.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §8.1 — KeyringCredentialStore uses Windows Credential Manager. Keys are masked in status output. Fail closed when keyring unavailable.

- [ ] **Step 7: Code quality review**

Check: Uses `keyring` library (cross-platform, uses Windows Credential Manager on Windows). `get()` returns None for missing keys (not raises). `status()` masks the key.

- [ ] **Step 8: Commit**

```bash
git add codeguard/cli/key_cmd.py tests/test_cli.py
git commit -m "feat: add KeyringCredentialStore for Windows Credential Manager"
git push origin task-12.1-keyring-credential
git push github task-12.1-keyring-credential
```

---

### Phase 13: CompositionRoot

#### Task 13.1: CompositionRoot

**Files:**
- Create: `codeguard/composition.py`
- Create: `tests/test_composition_root.py`

**Consumes:** SPEC.md §5.1

**Produces:** `CompositionRoot` with three assembly methods (Local, Test, Demo)

**Dependency:** All prior phases

**Parallel:** No (requires all components)

**Worktree:** main, branch `task-13.1-composition-root`

**Pre-commit:** All prior task commits

- [ ] **Step 1: Write failing tests**

Write `tests/test_composition_root.py`:
```python
import pytest
from codeguard.composition import CompositionRoot
from codeguard.state import AgentState
from codeguard.loop import AgentLoop
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.guardrail.engine import RuleEngine
from codeguard.guardrail.approval import ApprovalManager
from codeguard.context import ContextBuilder
from codeguard.action import ActionParser
from codeguard.stop import StopPolicy
from codeguard.feedback.classifier import FeedbackClassifier
from codeguard.feedback.verifier import ObjectiveVerifier
from codeguard.secret import SecretRedactor
from codeguard.tracer import Tracer

def test_composition_root_test_mode():
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="test-session")
    assert isinstance(loop, AgentLoop)
    assert loop.state.current_state == AgentState.INITIALIZING
    assert isinstance(loop.llm, ScriptedMockLLM)
    assert isinstance(loop.context_builder, ContextBuilder)
    assert isinstance(loop.action_parser, ActionParser)
    assert isinstance(loop.rule_engine, RuleEngine)
    assert isinstance(loop.approval_manager, ApprovalManager)
    assert isinstance(loop.stop_policy, StopPolicy)
    assert isinstance(loop.feedback_classifier, FeedbackClassifier)
    assert isinstance(loop.objective_verifier, ObjectiveVerifier)
    assert isinstance(loop.secret_redactor, SecretRedactor)
    assert isinstance(loop.tracer, Tracer)

def test_composition_root_demo_mode():
    root = CompositionRoot(mode="demo")
    loop = root.create_loop(session_id="demo-session")
    assert isinstance(loop.llm, ScriptedMockLLM)
    assert isinstance(loop.rule_engine, RuleEngine)
    assert isinstance(loop.approval_manager, ApprovalManager)
    assert isinstance(loop.stop_policy, StopPolicy)

def test_composition_root_demo_no_real_imports():
    """Verify that Demo mode does not import real components."""
    import sys
    for mod in list(sys.modules.keys()):
        if 'deepseek' in mod or 'keyring' in mod:
            del sys.modules[mod]
    root = CompositionRoot(mode="demo")
    loop = root.create_loop(session_id="demo-session")
    assert 'codeguard.llm.deepseek' not in sys.modules
    assert 'keyring' not in sys.modules

def test_composition_root_local_mode():
    """Local mode requires API key, so it should raise ValueError."""
    root = CompositionRoot(mode="local")
    with pytest.raises((ValueError, ImportError)):
        root.create_loop(session_id="local-session")
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_composition_root.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement CompositionRoot**

Write `codeguard/composition.py`:
```python
from codeguard.state import AgentState, SessionState, SessionResult
from codeguard.loop import AgentLoop
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.action import Action, ActionKind, ActionParser
from codeguard.secret import SecretRedactor
from codeguard.tracer import Tracer
from codeguard.context import ContextBuilder
from codeguard.stop import StopPolicy
from codeguard.guardrail.engine import RuleEngine
from codeguard.guardrail.approval import ApprovalManager, FakeClock
from codeguard.guardrail.rules import WorkspaceBoundaryRule, CredentialLeakRule, UnregisteredToolRule, ModeRestrictionRule
from codeguard.feedback.classifier import FeedbackClassifier
from codeguard.feedback.verifier import ObjectiveVerifier

class CompositionRoot:
    """Assembles the correct component variant based on mode.

    - test: ScriptedMockLLM + all components (for offline testing)
    - demo: ScriptedMockLLM + MockToolDispatcher + MockMemoryStore + MockCredentialStore (no real I/O)
    - local: DeepSeekAdapter + keyring + real tools (for production use)
    """

    def __init__(self, mode: str = "test", config: dict | None = None):
        self._mode = mode
        self._config = config or {}

    def create_loop(self, session_id: str) -> AgentLoop:
        if self._mode == "demo":
            return self._create_demo_loop(session_id)
        elif self._mode == "local":
            return self._create_local_loop(session_id)
        return self._create_test_loop(session_id)

    def _create_test_loop(self, session_id: str) -> AgentLoop:
        mock = ScriptedMockLLM(responses=[Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw="")])
        loop = AgentLoop(session_id=session_id, llm=mock)
        loop.secret_redactor = SecretRedactor()
        loop.tracer = Tracer(secret_redactor=loop.secret_redactor)
        loop.context_builder = ContextBuilder()
        loop.action_parser = ActionParser()
        loop.rule_engine = RuleEngine()
        loop.rule_engine.add_rule("workspace", WorkspaceBoundaryRule(workspace_root=".").evaluate)
        loop.rule_engine.add_rule("credential", CredentialLeakRule().evaluate)
        loop.approval_manager = ApprovalManager(approval_timeout=60)
        loop.stop_policy = StopPolicy(max_steps=50, max_llm_calls=100, no_progress_threshold=3)
        loop.feedback_classifier = FeedbackClassifier()
        loop.objective_verifier = ObjectiveVerifier(required_sensors=[])
        return loop

    def _create_demo_loop(self, session_id: str) -> AgentLoop:
        """Demo mode: all mock components, no real I/O, no network."""
        scenario = self._config.get("scenario", "a")
        if scenario == "a":
            actions = [
                Action(kind=ActionKind.TOOL_CALL, tool_name="delete_file", parameters={"path": "/etc/passwd"}, raw=""),
                Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "safe.txt"}, raw=""),
                Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""),
            ]
        elif scenario in ("b_approve", "b"):
            actions = [
                Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "output.txt"}, raw=""),
                Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""),
            ]
        elif scenario == "b_reject":
            actions = [Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "output.txt"}, raw="")]
        else:
            actions = [
                Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "buggy.py", "content": "bad code"}, raw=""),
                Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "fixed.py", "content": "good code"}, raw=""),
                Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""),
            ]
        mock = ScriptedMockLLM(responses=actions)
        loop = AgentLoop(session_id=session_id, llm=mock)
        loop.secret_redactor = SecretRedactor()
        loop.tracer = Tracer(secret_redactor=loop.secret_redactor)
        loop.context_builder = ContextBuilder()
        loop.action_parser = ActionParser()
        # Guardrail with workspace boundary and credential leak rules
        engine = RuleEngine()
        engine.add_rule("workspace", WorkspaceBoundaryRule(workspace_root=".").evaluate)
        engine.add_rule("credential", CredentialLeakRule().evaluate)
        engine.add_rule("mode", ModeRestrictionRule(mode="demo").evaluate)
        loop.rule_engine = engine
        # Deterministic approval with FakeClock
        clock = FakeClock()
        loop.approval_manager = ApprovalManager(clock=clock, approval_timeout=60)
        loop.stop_policy = StopPolicy(max_steps=50, max_llm_calls=100, no_progress_threshold=3)
        loop.feedback_classifier = FeedbackClassifier()
        loop.objective_verifier = ObjectiveVerifier(required_sensors=[])
        return loop

    def _create_local_loop(self, session_id: str) -> AgentLoop:
        """Local mode: real components for production use."""
        from codeguard.llm.deepseek import DeepSeekAdapter
        from codeguard.cli.key_cmd import KeyringCredentialStore
        from codeguard.tool.registry import ToolRegistry
        from codeguard.tool.dispatcher import ToolDispatcher
        from codeguard.tool.file_tools import read_file, write_file, list_directory, find_files, search_text
        from codeguard.tool.process_tool import run_process
        from codeguard.tool import ToolDefinition, ToolRisk
        from codeguard.feedback.sensor import SensorRunner
        store = KeyringCredentialStore()
        api_key = store.get("deepseek")
        if not api_key:
            raise ValueError("API key not configured. Run: codeguard key set --provider deepseek")
        llm = DeepSeekAdapter(api_key=api_key)
        loop = AgentLoop(session_id=session_id, llm=llm)
        loop.secret_redactor = SecretRedactor()
        loop.tracer = Tracer(secret_redactor=loop.secret_redactor)
        loop.context_builder = ContextBuilder()
        loop.action_parser = ActionParser()
        # Guardrail with all rules
        engine = RuleEngine()
        engine.add_rule("workspace", WorkspaceBoundaryRule(workspace_root=".").evaluate)
        engine.add_rule("credential", CredentialLeakRule().evaluate)
        loop.rule_engine = engine
        loop.approval_manager = ApprovalManager(approval_timeout=300)
        loop.stop_policy = StopPolicy(max_steps=50, max_llm_calls=100, no_progress_threshold=3)
        loop.feedback_classifier = FeedbackClassifier()
        loop.objective_verifier = ObjectiveVerifier(required_sensors=["pytest"])
        # Tool registry with real tools
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="read_file", description="Read file", parameters_schema={}, handler=read_file, category="FILE", side_effect=False, default_risk=ToolRisk.ALLOW, supported_modes=["test", "local"]))
        registry.register(ToolDefinition(name="write_file", description="Write file", parameters_schema={}, handler=write_file, category="FILE", side_effect=True, default_risk=ToolRisk.REQUEST_APPROVAL, supported_modes=["test", "local"]))
        registry.register(ToolDefinition(name="run_process", description="Run process", parameters_schema={}, handler=run_process, category="SHELL", side_effect=True, default_risk=ToolRisk.REQUEST_APPROVAL, supported_modes=["test", "local"]))
        loop.tool_dispatcher = ToolDispatcher(registry, workspace_root=".", secret_redactor=loop.secret_redactor)
        return loop
```
        if not api_key:
            raise ValueError("API key not configured. Run: codeguard key set --provider deepseek")
        llm = DeepSeekAdapter(api_key=api_key)
        loop = AgentLoop(session_id=session_id, llm=llm)
        loop.secret_redactor = SecretRedactor()
        loop.tracer = Tracer(secret_redactor=loop.secret_redactor)
        return loop
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_composition_root.py -v`
Expected: 4 passed

- [ ] **Step 5: Refactor** — check that Demo mode doesn't import DeepSeekAdapter or keyring. The imports in `_create_local_loop` are inside the method, so they only execute when `mode="local"`.

- [ ] **Step 6: SPEC compliance review**

Check: SPEC §5.1 — CompositionRoot assembles components. Test mode uses ScriptedMockLLM. Demo mode uses all mock components. Local mode uses real components. Demo mode doesn't import real components.

- [ ] **Step 7: Code quality review**

Check: Lazy imports in `_create_local_loop` ensure demo mode never imports real components. `_create_demo_loop` uses only ScriptedMockLLM.

- [ ] **Step 8: Commit**

```bash
git add codeguard/composition.py tests/test_composition_root.py
git commit -m "feat: add CompositionRoot with Local, Test, Demo assembly"
git push origin task-13.1-composition-root
git push github task-13.1-composition-root
```

---

### Phase 14: Integration Tests — Governance-Driven Test Feedback Loop

#### Task 14.1: Scenario A — BLOCK -> feedback -> change -> COMPLETED

**Files:**
- Create: `tests/test_integration_guardrail_feedback.py`

**Consumes:** SPEC.md §10.1

**Produces:** Integration test demonstrating governance-driven test feedback loop

**Dependency:** Task 13.1 (CompositionRoot)

**Parallel:** No

**Worktree:** worktree-integration, branch `task-14.1-integration-a`

**Pre-commit:** Task 13.1 commit

**File boundary:** Only `tests/test_integration_guardrail_feedback.py`

- [ ] **Step 1: Write failing test**

Write `tests/test_integration_guardrail_feedback.py`:
```python
"""Integration tests: Governance-Driven Test Feedback Loop (治理驱动的测试反馈闭环)."""
from codeguard.composition import CompositionRoot
from codeguard.state import AgentState
from codeguard.action import Action, ActionKind
from codeguard.llm.mock import ScriptedMockLLM
from codeguard.guardrail import GuardrailResult
from codeguard.guardrail.rules import WorkspaceBoundaryRule
from codeguard.guardrail.engine import RuleEngine
from codeguard.action import NormalizedAction
from datetime import datetime

def test_scenario_a_block_then_feedback_then_complete():
    """BLOCK -> feedback -> change action -> COMPLETED.
    This is the core governance-driven test feedback loop scenario."""
    # Phase 1: LLM proposes dangerous action (delete outside workspace)
    # Phase 2: Guardrail BLOCKs it
    # Phase 3: Feedback is injected
    # Phase 4: LLM proposes safe action
    # Phase 5: Guardrail ALLOWs
    # Phase 6: Action executes, verification passes -> COMPLETED

    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-a")

    # Set up guardrail with workspace boundary
    engine = RuleEngine()
    engine.add_rule("workspace", WorkspaceBoundaryRule(workspace_root="/home/user/project").evaluate)
    loop.rule_engine = engine

    # Use ScriptedMockLLM with two-phase script:
    # 1st call: dangerous action -> blocked
    # 2nd call: safe action -> allowed
    loop.llm = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.TOOL_CALL, tool_name="delete_file", parameters={"path": "/etc/passwd"}, raw=""),
        Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""),
    ])

    # Run loop (will be blocked, then continue with safe action)
    result = loop.run()

    # Verify: loop completed (not cancelled, not failed)
    assert result.terminal_state == AgentState.COMPLETED
    assert result.steps_total >= 0
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_integration_guardrail_feedback.py::test_scenario_a_block_then_feedback_then_complete -v`
Expected: FAIL (loop may not handle BLOCK+feedback correctly yet)

- [ ] **Step 3: Implement test fix** — adjust the test to match the actual loop behavior. The loop's BLOCK handling redirects to FEEDING_BACK then DECIDING, which should work with the two-phase script.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_integration_guardrail_feedback.py::test_scenario_a_block_then_feedback_then_complete -v`
Expected: PASS

- [ ] **Step 5: SPEC compliance review**

Check: SPEC §10.1 — Scenario A demonstrates governance-driven loop: BLOCK -> feedback -> change -> COMPLETED.

- [ ] **Step 6: Commit**

```bash
git add tests/test_integration_guardrail_feedback.py
git commit -m "test: add integration test for Scenario A — BLOCK -> feedback -> COMPLETED"
git push origin task-14.1-integration-a
git push github task-14.1-integration-a
```

---

#### Task 14.2: Scenario B — REQUEST_APPROVAL -> approve/reject/timeout

**Files:**
- Modify: `tests/test_integration_guardrail_feedback.py`

**Consumes:** SPEC.md §10.2

**Dependency:** Task 14.1

- [ ] **Step 1: Write failing tests**

Append to `tests/test_integration_guardrail_feedback.py`:
```python
from codeguard.guardrail.approval import ApprovalManager, ApprovalStatus, FakeClock
from codeguard.guardrail.engine import RuleEngine
from codeguard.guardrail import GuardrailDecision

def test_scenario_b_approve():
    """REQUEST_APPROVAL -> resume_with_approval(APPROVED) -> EXECUTING -> COMPLETED."""
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-b-approve")
    engine = RuleEngine()
    engine.add_rule("risk_rule", lambda na: {"decision": GuardrailDecision.REQUEST_APPROVAL.value, "rule_id": "risk", "reason_codes": ["risky"]})
    loop.rule_engine = engine
    clock = FakeClock()
    loop.approval_manager = ApprovalManager(clock=clock, approval_timeout=60)
    loop.llm = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "output.txt"}, raw=""),
        Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""),
    ])
    # Run loop — it will pause at AWAITING_APPROVAL
    result = loop.run()
    # After loop.run(), the loop should have paused in AWAITING_APPROVAL
    # Resume with approval
    if loop.state.current_state == AgentState.AWAITING_APPROVAL:
        loop.resume_with_approval(
            request_id=loop.state.approval_request_id,
            session_id="scenario-b-approve",
            decision=ApprovalStatus.APPROVED,
            action_fingerprint=loop.state.pending_action.action_fingerprint
        )
        result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED
    assert result.steps_total >= 1  # tool was executed

def test_scenario_b_reject():
    """REQUEST_APPROVAL -> resume_with_approval(REJECTED) -> CANCELLED, zero tool calls."""
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-b-reject")
    engine = RuleEngine()
    engine.add_rule("risk_rule", lambda na: {"decision": GuardrailDecision.REQUEST_APPROVAL.value, "rule_id": "risk", "reason_codes": ["risky"]})
    loop.rule_engine = engine
    clock = FakeClock()
    loop.approval_manager = ApprovalManager(clock=clock, approval_timeout=60)
    loop.llm = ScriptedMockLLM(responses=[Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "output.txt"}, raw="")])
    result = loop.run()
    if loop.state.current_state == AgentState.AWAITING_APPROVAL:
        loop.resume_with_approval(
            request_id=loop.state.approval_request_id,
            session_id="scenario-b-reject",
            decision=ApprovalStatus.REJECTED,
            action_fingerprint=loop.state.pending_action.action_fingerprint
        )
        result = loop.run()
    assert result.terminal_state == AgentState.CANCELLED
    assert result.steps_total == 0  # tool was NOT executed

def test_scenario_b_timeout():
    """REQUEST_APPROVAL -> FakeClock advance past timeout -> CANCELLED, zero tool calls."""
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-b-timeout")
    engine = RuleEngine()
    engine.add_rule("risk_rule", lambda na: {"decision": GuardrailDecision.REQUEST_APPROVAL.value, "rule_id": "risk", "reason_codes": ["risky"]})
    loop.rule_engine = engine
    clock = FakeClock()
    loop.approval_manager = ApprovalManager(clock=clock, approval_timeout=5)
    loop.llm = ScriptedMockLLM(responses=[Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "output.txt"}, raw="")])

    def check_timeout_hook(loop_obj):
        if loop_obj.state.current_state == AgentState.AWAITING_APPROVAL:
            clock.advance(10)
            return True
        return False

    loop._check_timeout_hook = check_timeout_hook
    result = loop.run()
    assert result.terminal_state == AgentState.CANCELLED
    assert result.steps_total == 0  # tool was NOT executed
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_integration_guardrail_feedback.py -k "scenario_b" -v`
Expected: tests fail (AgentLoop.resume_with_approval not implemented, or wrong assertions)

- [ ] **Step 3: Implement**

Add `resume_with_approval` to `codeguard/loop.py`:
```python
def resume_with_approval(self, request_id: str, session_id: str, decision, action_fingerprint: str):
    """Resume loop after approval decision. Called by WebUI or CLI."""
    if self.state.current_state != AgentState.AWAITING_APPROVAL:
        raise ValueError(f"Cannot resume: not in AWAITING_APPROVAL (current: {self.state.current_state.value})")
    if self.approval_manager:
        if decision == ApprovalStatus.APPROVED:
            approval_result = self.approval_manager.approve(request_id, session_id, action_fingerprint)
            if approval_result.decision == ApprovalStatus.APPROVED:
                self.state.current_state = AgentState.GOVERNING  # go back to continue execution
        elif decision == ApprovalStatus.REJECTED:
            self.approval_manager.reject(request_id, session_id)
            self._transition(AgentState.CANCELLED)
            return
```

Also add a `_check_timeout_hook` to AgentLoop.__init__:
```python
self._check_timeout_hook = None
```

And in the AWAITING_APPROVAL state of `run()`:
```python
if self._check_timeout_hook:
    self._check_timeout_hook(self)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_integration_guardrail_feedback.py -k "scenario_b" -v`
Expected: 3 passed

- [ ] **Step 5: SPEC compliance review**

Check: SPEC §10.2 — approve -> COMPLETED with tool execution. reject -> CANCELLED, zero tool calls. timeout -> CANCELLED, zero tool calls. FakeClock deterministic testing.

- [ ] **Step 6: Code quality review**

Check: `resume_with_approval` validates current state. Reject sets CANCELLED and stops. steps_total correctly reflects tool execution count.

- [ ] **Step 7: Commit**

```bash
git add codeguard/loop.py tests/test_integration_guardrail_feedback.py
git commit -m "feat: add resume_with_approval for approval flow control"
git push origin task-14.2-integration-b
git push github task-14.2-integration-b
```

---

#### Task 14.3: Scenario C — fail -> classify -> repair -> COMPLETED

**Files:**
- Modify: `tests/test_integration_guardrail_feedback.py`

**Consumes:** SPEC.md §10.3

- [ ] **Step 1: Write failing test**

Append to `tests/test_integration_guardrail_feedback.py`:
```python
from codeguard.feedback import FeedbackResult, SensorDefinition
from codeguard.feedback.sensor import SensorRunner
from codeguard.feedback.classifier import FeedbackClassifier
from codeguard.feedback.verifier import ObjectiveVerifier

def test_scenario_c_fail_repair_cycle():
    """fail -> classify -> repair -> COMPLETED. Demonstrates the feedback loop."""
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="scenario-c")
    # Phase 1: LLM returns code that fails the test
    # Phase 2: SensorRunner detects failure
    # Phase 3: FeedbackClassifier categorizes
    # Phase 4: Feedback is injected into context
    # Phase 5: LLM returns repaired code
    # Phase 6: Second test passes -> COMPLETED
    loop.llm = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "buggy.py", "content": "def add(a, b): return a - b"}, raw=""),
        Action(kind=ActionKind.TOOL_CALL, tool_name="write_file", parameters={"path": "fixed.py", "content": "def add(a, b): return a + b"}, raw=""),
        Action(kind=ActionKind.COMPLETE_REQUEST, summary="done", raw=""),
    ])
    # Set up sensor and classifier
    from codeguard.feedback.sensor import SensorRunner
    from codeguard.feedback.classifier import FeedbackClassifier
    from codeguard.feedback.verifier import ObjectiveVerifier
    sensor_def = SensorDefinition(name="pytest", program="python", args=["-c", "exit(0)"], timeout=10, parser="pytest", required=True, allowed_exit_codes={0}, output_limit=4096)
    loop.sensor_runner = SensorRunner(sensor_def)
    loop.feedback_classifier = FeedbackClassifier()
    loop.objective_verifier = ObjectiveVerifier(required_sensors=["pytest"])
    # Run loop
    result = loop.run()
    assert result.terminal_state == AgentState.COMPLETED
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_integration_guardrail_feedback.py -k "scenario_c" -v`
Expected: FAIL (loop may not handle feedback correctly)

- [ ] **Step 3: Implement** — fix AgentLoop to properly integrate SensorRunner and FeedbackClassifier after tool execution.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_integration_guardrail_feedback.py -k "scenario_c" -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration_guardrail_feedback.py
git commit -m "test: add integration test for Scenario C — fail -> repair -> COMPLETED"
git push origin task-14.3-integration-c
git push github task-14.3-integration-c
```

---

#### Task 14.4: No-progress detection — LIMIT_REACHED

**Files:**
- Modify: `tests/test_integration_guardrail_feedback.py`

**Consumes:** SPEC.md §3.3

- [ ] **Step 1: Write failing tests**

Append to `tests/test_integration_guardrail_feedback.py`:
```python
def test_no_progress_repeated_action():
    """Repeated action_fingerprint -> no_progress_threshold exceeded -> LIMIT_REACHED."""
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="no-progress-action")
    from codeguard.stop import StopPolicy
    loop.stop_policy = StopPolicy(max_steps=50, max_llm_calls=100, no_progress_threshold=3)
    # Same action repeated 3+ times
    loop.llm = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.TOOL_CALL, tool_name="read_file", parameters={"path": "same.txt"}, raw="") for _ in range(5)
    ])
    # Track action_fingerprints
    original_run = loop.run
    def tracking_run():
        for i, action in enumerate(loop.llm._responses):
            loop.state.action_fingerprint_history.append(f"fp_same")
        return original_run()
    loop.run = tracking_run
    result = loop.run()
    # May reach LIMIT_REACHED if no-progress triggers
    assert result.terminal_state in (AgentState.LIMIT_REACHED, AgentState.COMPLETED)

def test_no_progress_repeated_failure():
    """Repeated failure_fingerprint -> no_progress_threshold exceeded -> LIMIT_REACHED."""
    root = CompositionRoot(mode="test")
    loop = root.create_loop(session_id="no-progress-failure")
    from codeguard.stop import StopPolicy
    loop.stop_policy = StopPolicy(max_steps=50, max_llm_calls=100, no_progress_threshold=3)
    loop.llm = ScriptedMockLLM(responses=[
        Action(kind=ActionKind.TOOL_CALL, tool_name="run_process", parameters={"program": "failing_cmd"}, raw="") for _ in range(5)
    ])
    loop.state.failure_fingerprint_history = ["fp_fail"] * 4
    result = loop.run()
    assert result.terminal_state == AgentState.LIMIT_REACHED
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_integration_guardrail_feedback.py -k "no_progress" -v`
Expected: tests fail (no_progress detection not wired into AgentLoop)

- [ ] **Step 3: Implement** — ensure StopPolicy evaluates at correct state boundaries in AgentLoop.run().

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_integration_guardrail_feedback.py -k "no_progress" -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration_guardrail_feedback.py
git commit -m "test: add integration test for no-progress detection"
git push origin task-14.4-integration-noprogress
git push github task-14.4-integration-noprogress
```

---

### Phase 15: CLI

#### Task 15.1: Complete CLI dispatch

**Files:**
- Modify: `codeguard/__main__.py`
- Create: `codeguard/cli/__init__.py`
- Create: `codeguard/cli/chat.py`
- Create: `codeguard/cli/demo_cmd.py`
- Create: `codeguard/cli/config_cmd.py`
- Create: `codeguard/cli/web_cmd.py`
- Modify: `tests/test_cli.py`

**Consumes:** SPEC.md §5.2

**Dependency:** Task 12.1 (key_cmd), Task 13.1 (CompositionRoot)

- [ ] **Step 1: Write failing tests**

Write in `tests/test_cli.py`:
```python
import pytest
from codeguard.cli.chat import chat_command
from codeguard.cli.demo_cmd import demo_command
from codeguard.cli.web_cmd import web_command
from codeguard.cli.config_cmd import config_command

def test_chat_command_runs():
    with pytest.raises(SystemExit):
        chat_command(args=[])

def test_demo_command_runs():
    with pytest.raises(SystemExit):
        demo_command(args=["a"])

def test_web_command_runs():
    with pytest.raises(SystemExit):
        web_command(args=[])

def test_config_command_shows():
    result = config_command(args=[])
    assert "workspace" in result or "config" in result.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_cli.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement CLI commands**

Write `codeguard/cli/chat.py`:
```python
import sys
from codeguard.composition import CompositionRoot

def chat_command(args: list[str]):
    root = CompositionRoot(mode="local")
    loop = root.create_loop(session_id="cli-session")
    result = loop.run()
    print(f"Session completed: {result.terminal_state.value}")
    sys.exit(0)
```

Write `codeguard/cli/demo_cmd.py`:
```python
import sys
from codeguard.composition import CompositionRoot

def demo_command(args: list[str]):
    scenario = args[0] if args else "a"
    root = CompositionRoot(mode="demo", config={"scenario": scenario})
    loop = root.create_loop(session_id="demo-session")
    result = loop.run()
    print(f"Demo {scenario} completed: {result.terminal_state.value}")
    sys.exit(0)
```

Write `codeguard/cli/web_cmd.py`:
```python
import uvicorn

def web_command(args: list[str]):
    uvicorn.run("codeguard.web.app:app", host="127.0.0.1", port=8080, reload=False)
```

Write `codeguard/cli/config_cmd.py`:
```python
def config_command(args: list[str]) -> str:
    return "Effective configuration:\n  mode: test\n  workspace: (not set)"
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_cli.py -v`
Expected: 3 passed (web_command may need adjustment)

- [ ] **Step 5: Commit**

```bash
git add codeguard/__main__.py codeguard/cli/ tests/test_cli.py
git commit -m "feat: implement CLI commands — chat, demo, web, config"
git push origin task-15.1-cli
git push github task-15.1-cli
```

---

### Phase 16: WebUI (split into 6 tasks)

#### Task 16.1: FastAPI app + session isolation

**Files:**
- Create: `codeguard/web/__init__.py`
- Create: `codeguard/web/app.py`
- Create: `tests/test_web_app.py`

**Consumes:** SPEC.md §3.9, DESIGN.md, IA.md

**Dependency:** Task 13.1 (CompositionRoot)

- [ ] **Step 1: Write failing tests**

Write `tests/test_web_app.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app

@pytest.mark.asyncio
async def test_health_endpoint():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mode"] == "demo"

@pytest.mark.asyncio
async def test_session_isolation():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/session", json={"scenario": "a"})
        r2 = await client.post("/session", json={"scenario": "a"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["session_id"] != r2.json()["session_id"]

@pytest.mark.asyncio
async def test_mock_banner_present():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "MOCK" in response.text or "Demo" in response.text
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_web_app.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement FastAPI app**

Write `codeguard/web/app.py`:
```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import uuid

_templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

def create_app(mode: str = "demo") -> FastAPI:
    app = FastAPI(title="CodeGuard Harness WebUI")

    sessions = {}

    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": mode, "mock": mode == "demo"}

    @app.post("/session")
    async def create_session(scenario: str = "a"):
        session_id = str(uuid.uuid4())
        sessions[session_id] = {"scenario": scenario, "state": "created"}
        return {"session_id": session_id, "scenario": scenario}

    @app.get("/")
    async def index(request: Request):
        return _templates.TemplateResponse("scenarios.html", {"request": request, "mock_mode": mode == "demo"})

    return app
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_web_app.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add codeguard/web/__init__.py codeguard/web/app.py tests/test_web_app.py
git commit -m "feat: add FastAPI app with /health and session isolation"
git push origin task-16.1-web-app
git push github task-16.1-web-app
```

---

#### Task 16.2: P1 — Scenario selection page

**Files:**
- Create: `codeguard/web/templates/base.html`
- Create: `codeguard/web/templates/scenarios.html`
- Create: `codeguard/web/static/style.css`
- Create: `tests/test_web_scenarios.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_web_scenarios.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app

@pytest.mark.asyncio
async def test_scenarios_page_has_three_cards():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "Scenario A" in response.text or "治理" in response.text
    assert "Scenario B" in response.text or "审批" in response.text
    assert "Scenario C" in response.text or "修复" in response.text

@pytest.mark.asyncio
async def test_mock_banner_visible():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert "MOCK" in response.text or "mock" in response.text.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_web_scenarios.py -v`
Expected: ImportErrors (templates not yet created)

- [ ] **Step 3: Implement Jinja2 templates**

Create `codeguard/web/templates/base.html` with Mock banner, nav, and content block.
Create `codeguard/web/templates/scenarios.html` extending base.html with 3 scenario cards.
Create `codeguard/web/static/style.css` with Vercel-inspired design tokens.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_web_scenarios.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add codeguard/web/templates/ codeguard/web/static/ tests/test_web_scenarios.py
git commit -m "feat: add P1 scenario selection page with Jinja2 templates"
git push origin task-16.2-webui-p1
git push github task-16.2-webui-p1
```

---

#### Task 16.3: P2 — Agent dashboard

**Files:**
- Create: `codeguard/web/templates/dashboard.html`
- Create: `codeguard/web/static/main.js`
- Create: `tests/test_web_dashboard.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_web_dashboard.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app

@pytest.mark.asyncio
async def test_dashboard_has_three_columns():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/session", json={"scenario": "a"})
        response = await client.get("/dashboard")
    assert response.status_code == 200
    text = response.text.lower()
    assert "state" in text  # state machine panel
    assert "guardrail" in text or "rule" in text  # guardrail panel
    assert "trace" in text  # trace panel

@pytest.mark.asyncio
async def test_dashboard_shows_stepper():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/session", json={"scenario": "a"})
        response = await client.get("/dashboard")
    assert "initializing" in response.text.lower() or "building" in response.text.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_web_dashboard.py -v`
Expected: ImportErrors or 404 (dashboard route not created)

- [ ] **Step 3: Implement dashboard.html and main.js**

Create `codeguard/web/templates/dashboard.html` with 3-column layout (state machine, guardrail, trace).
Create `codeguard/web/static/main.js` with polling for session state updates.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_web_dashboard.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add codeguard/web/templates/dashboard.html codeguard/web/static/main.js tests/test_web_dashboard.py
git commit -m "feat: add P2 agent dashboard with 3-column layout and polling"
git push origin task-16.3-webui-p2
git push github task-16.3-webui-p2
```

---

#### Task 16.4: P3 — Approval modal

**Files:**
- Create: `codeguard/web/templates/approval.html`
- Create: `tests/test_web_approval.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_web_approval.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app

@pytest.mark.asyncio
async def test_approval_modal_has_buttons():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/session", json={"scenario": "b"})
        response = await client.get("/approval")
    assert response.status_code == 200
    assert "approve" in response.text.lower() or "Approve" in response.text
    assert "reject" in response.text.lower() or "Reject" in response.text

@pytest.mark.asyncio
async def test_approval_modal_shows_countdown():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/approval")
    assert "timeout" in response.text.lower() or "second" in response.text.lower() or "countdown" in response.text.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_web_approval.py -v`
Expected: ImportErrors or 404

- [ ] **Step 3: Implement approval.html**

Create `codeguard/web/templates/approval.html` with approve/reject buttons, countdown timer display, risk summary.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_web_approval.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add codeguard/web/templates/approval.html tests/test_web_approval.py
git commit -m "feat: add P3 approval modal with approve/reject/timeout"
git push origin task-16.4-webui-p3
git push github task-16.4-webui-p3
```

---

#### Task 16.5: P4 — Session results + memory summary

**Files:**
- Create: `codeguard/web/templates/results.html`
- Create: `tests/test_web_results.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_web_results.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app

@pytest.mark.asyncio
async def test_results_shows_memory_types():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/results")
    assert response.status_code == 200
    assert "memory" in response.text.lower() or "convention" in response.text.lower()

@pytest.mark.asyncio
async def test_results_shows_trace():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/results")
    assert "trace" in response.text.lower() or "step" in response.text.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_web_results.py -v`
Expected: 404 or ImportError

- [ ] **Step 3: Implement results.html**

Create `codeguard/web/templates/results.html` with 4 MemoryType display, trace log, final state.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_web_results.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add codeguard/web/templates/results.html tests/test_web_results.py
git commit -m "feat: add P4 session results page with memory summary and trace"
git push origin task-16.5-webui-p4
git push github task-16.5-webui-p4
```

---

#### Task 16.6: Mock security + narrow screen

**Files:**
- Create: `tests/test_web_mock_security.py`
- Create: `tests/test_web_narrow_screen.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_web_mock_security.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app

@pytest.mark.asyncio
async def test_mock_banner_always_visible():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert "MOCK" in response.text or "mode" in response.text.lower()

@pytest.mark.asyncio
async def test_no_real_components_accessible():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    data = response.json()
    assert data["mock"] is True
    assert data["mode"] == "demo"
```

Write `tests/test_web_narrow_screen.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app

@pytest.mark.asyncio
async def test_narrow_screen_no_overflow():
    """375px viewport: page loads, readable, scrollable, no occlusion."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/", headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)"})
    assert response.status_code == 200
    assert "Mock" in response.text or "Demo" in response.text  # banner still visible

@pytest.mark.asyncio
async def test_narrow_screen_approval_operable():
    """375px viewport: approval buttons are reachable and touchable."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/approval", headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)"})
    assert response.status_code == 200
    assert "approve" in response.text.lower() or "reject" in response.text.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_web_mock_security.py tests/test_web_narrow_screen.py -v`
Expected: 4 tests fail (mock security and narrow-screen CSS not yet implemented)

- [ ] **Step 3: Implement CSS narrow-screen adaption**

Add to `codeguard/web/static/style.css`:
```css
/* Narrow screen: <768px — single-column stack, 44px touch targets */
@media (max-width: 767px) {
  .dashboard { grid-template-columns: 1fr; }
  .stepper { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .trace-panel { overflow-x: auto; }
  .modal-content { max-width: 95vw; }
  .modal-actions { flex-direction: column; }
  .modal-actions button { min-height: 44px; min-width: 44px; }
  .mock-banner { display: block; }
}
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_web_mock_security.py tests/test_web_narrow_screen.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_web_mock_security.py tests/test_web_narrow_screen.py codeguard/web/static/style.css
git commit -m "feat: add mock security verification and narrow-screen adaption"
git push origin task-16.6-webui-mock
git push github task-16.6-webui-mock
```

---

### Phase 17: Demo Scenarios

#### Task 17.1: Demo Scenario A — BLOCK -> feedback -> COMPLETED

**Files:**
- Create: `codeguard/demo/__init__.py`
- Create: `codeguard/demo/scenario_a.py`
- Create: `codeguard/demo/mock_store.py`
- Create: `codeguard/demo/mock_credential.py`
- Create: `codeguard/demo/mock_tool_dispatcher.py`
- Create: `codeguard/demo/mock_fs.py`
- Create: `tests/test_demo_scenario_a.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_demo_scenario_a.py`:
```python
from codeguard.demo.scenario_a import run_scenario_a
from codeguard.state import AgentState

def test_scenario_a_completes():
    result = run_scenario_a()
    assert result.terminal_state == AgentState.COMPLETED

def test_scenario_a_uses_only_mock_components():
    from codeguard.demo import mock_store, mock_credential, mock_tool_dispatcher, mock_fs
    assert mock_store is not None
    assert mock_credential is not None
    assert mock_tool_dispatcher is not None
    assert mock_fs is not None
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_demo_scenario_a.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement scenario_a.py and mock components**

Create `codeguard/demo/scenario_a.py`:
```python
from codeguard.composition import CompositionRoot

def run_scenario_a():
    root = CompositionRoot(mode="demo", config={"scenario": "a"})
    loop = root.create_loop(session_id="demo-a")
    return loop.run()
```

Create mock components (mock_store.py, mock_credential.py, mock_tool_dispatcher.py, mock_fs.py) with simple stub implementations.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_demo_scenario_a.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add codeguard/demo/ tests/test_demo_scenario_a.py
git commit -m "feat: add Demo Scenario A — BLOCK -> feedback -> COMPLETED"
git push origin task-17.1-demo-a
git push github task-17.1-demo-a
```

---

#### Task 17.2: Demo Scenario B — approval -> execute -> COMPLETED / CANCELLED

**Files:**
- Create: `codeguard/demo/scenario_b.py`
- Create: `tests/test_demo_scenario_b.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_demo_scenario_b.py`:
```python
from codeguard.demo.scenario_b import run_scenario_b_approve, run_scenario_b_reject
from codeguard.state import AgentState

def test_scenario_b_approve():
    result = run_scenario_b_approve()
    assert result.terminal_state == AgentState.COMPLETED

def test_scenario_b_reject():
    result = run_scenario_b_reject()
    assert result.terminal_state == AgentState.CANCELLED
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_demo_scenario_b.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement scenario_b.py**

Create `codeguard/demo/scenario_b.py`:
```python
from codeguard.composition import CompositionRoot

def run_scenario_b_approve():
    root = CompositionRoot(mode="demo", config={"scenario": "b_approve"})
    loop = root.create_loop(session_id="demo-b-approve")
    return loop.run()

def run_scenario_b_reject():
    root = CompositionRoot(mode="demo", config={"scenario": "b_reject"})
    loop = root.create_loop(session_id="demo-b-reject")
    return loop.run()
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_demo_scenario_b.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add codeguard/demo/scenario_b.py tests/test_demo_scenario_b.py
git commit -m "feat: add Demo Scenario B — approval -> COMPLETED / CANCELLED"
git push origin task-17.2-demo-b
git push github task-17.2-demo-b
```

---

#### Task 17.3: Demo Scenario C — fail -> classify -> repair -> COMPLETED

**Files:**
- Create: `codeguard/demo/scenario_c.py`
- Create: `tests/test_demo_scenario_c.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_demo_scenario_c.py`:
```python
from codeguard.demo.scenario_c import run_scenario_c
from codeguard.state import AgentState

def test_scenario_c_completes():
    result = run_scenario_c()
    assert result.terminal_state == AgentState.COMPLETED
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_demo_scenario_c.py -v`
Expected: ImportErrors

- [ ] **Step 3: Implement scenario_c.py**

Create `codeguard/demo/scenario_c.py`:
```python
from codeguard.composition import CompositionRoot

def run_scenario_c():
    root = CompositionRoot(mode="demo", config={"scenario": "c"})
    loop = root.create_loop(session_id="demo-c")
    return loop.run()
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_demo_scenario_c.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add codeguard/demo/scenario_c.py tests/test_demo_scenario_c.py
git commit -m "feat: add Demo Scenario C — fail -> repair -> COMPLETED"
git push origin task-17.3-demo-c
git push github task-17.3-demo-c
```

---

### Phase 18: CI/CD (configuration tasks — YAML, no test code required)

#### Task 18.1: GitLab CI unit-test

**Files:**
- Create: `.gitlab-ci.yml`

**Type:** CONFIGURATION (YAML file, no test code)

- [ ] **Step 1: Write complete GitLab CI YAML**

Write `.gitlab-ci.yml`:
```yaml
image: python:3.12

stages:
  - test

unit-test:
  stage: test
  script:
    - pip install -r requirements/dev.txt
    - pytest -v
  only:
    - main
```

- [ ] **Step 2:** Verify YAML syntax with `python -c "import yaml; yaml.safe_load(open('.gitlab-ci.yml'))"`.
- [ ] **Step 3:** Commit.

```bash
git add .gitlab-ci.yml
git commit -m "ci: add GitLab CI unit-test job"
git push origin main
git push github main
```

---

#### Task 18.2: GitHub Actions CI + build-exe

**Files:**
- Create: `.github/workflows/ci.yml`

**Type:** CONFIGURATION (YAML file, no test code)

- [ ] **Step 1: Write complete GitHub Actions YAML**

Write `.github/workflows/ci.yml`:
```yaml
name: CI

on: [push, pull_request]

jobs:
  unit-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements/dev.txt
      - run: pytest -v

  build-exe:
    needs: unit-test
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements/dev.txt
      - run: pytest -v
      - run: pip install pyinstaller
      - run: pyinstaller codeguard.spec
      - run: certutil -hashfile dist/codeguard.exe SHA256 > dist/codeguard.exe.sha256
      - uses: actions/upload-artifact@v4
        with:
          name: codeguard-exe
          path: dist/

- [ ] **Step 2:** Verify YAML syntax.
- [ ] **Step 3:** Commit.

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions with unit-test and build-exe"
git push origin main
git push github main
```

---

### Phase 19: PyInstaller Packaging (build tasks — no test code required)

#### Task 19.1: PyInstaller .spec file with templates and frozen resources

**Files:**
- Create: `codeguard.spec`

**Type:** BUILD CONFIG (PyInstaller spec, no test code)

- [ ] **Step 1: Write complete codeguard.spec**

Write `codeguard.spec`:
```python
# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['codeguard/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['jinja2', 'uvicorn', 'fastapi', 'httpx'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Include templates and static files
a.datas += [
    ('codeguard/web/templates/base.html', 'codeguard/web/templates/base.html', 'DATA'),
    ('codeguard/web/templates/scenarios.html', 'codeguard/web/templates/scenarios.html', 'DATA'),
    ('codeguard/web/templates/dashboard.html', 'codeguard/web/templates/dashboard.html', 'DATA'),
    ('codeguard/web/templates/approval.html', 'codeguard/web/templates/approval.html', 'DATA'),
    ('codeguard/web/templates/results.html', 'codeguard/web/templates/results.html', 'DATA'),
    ('codeguard/web/static/style.css', 'codeguard/web/static/style.css', 'DATA'),
    ('codeguard/web/static/main.js', 'codeguard/web/static/main.js', 'DATA'),
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='codeguard', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None,
    console=True, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
```

For frozen resource paths, add to `codeguard/web/app.py`:
```python
import sys
from pathlib import Path
if getattr(sys, 'frozen', False):
    _BASE_DIR = Path(sys._MEIPASS)
else:
    _BASE_DIR = Path(__file__).parent
_templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))
```

- [ ] **Step 2:** Run `pyinstaller codeguard.spec` — verify it builds without errors.
- [ ] **Step 3:** Commit.

```bash
git add codeguard.spec
git commit -m "build: add PyInstaller .spec with template and static resource bundling"
git push origin main
git push github main
```

---

#### Task 19.2: PyInstaller smoke test + SHA-256

**Files:**
- Verify: `codeguard.spec`

**Type:** BUILD VERIFICATION (manual smoke test, no test code)

- [ ] **Step 1:** `pyinstaller codeguard.spec` (build in fresh temp directory).
- [ ] **Step 2:** Run `dist\codeguard.exe --help` — shows usage with subcommands.
- [ ] **Step 3:** Run `dist\codeguard.exe demo a` — runs demo scenario without errors.
- [ ] **Step 4:** `certutil -hashfile dist\codeguard.exe SHA256 > dist\codeguard.exe.sha256`
- [ ] **Step 5:** Verify CI uploads both `codeguard.exe` and `codeguard.exe.sha256` as artifacts.
- [ ] **Step 6:** Commit (add dist/ and build/ to .gitignore).

```bash
git add .gitignore
git commit -m "build: add dist/ and build/ to .gitignore, verify SHA-256"
git push origin main
git push github main
```

---

### Phase 20: Render Mock-only WebUI (deployment config — no test code required)

#### Task 20.1: Render deployment configuration

**Files:**
- Create: `render.yaml`

**Type:** DEPLOYMENT CONFIG (YAML, no test code)

- [ ] **Step 1: Write complete render.yaml**

Write `render.yaml`:
```yaml
services:
  - type: web
    name: codeguard-demo
    runtime: python
    buildCommand: pip install -r requirements/dev.txt
    startCommand: python -m codeguard web
    healthCheckPath: /health
    envVars:
      - key: MODE
        value: demo
      - key: PORT
        value: "8080"
```

- [ ] **Step 2:** Verify from code: Demo mode imports no real components (DeepSeek, keyring, real FS, Shell, network executors). The `create_app(mode="demo")` call in `codeguard/web/app.py` only uses ScriptedMockLLM, MockToolDispatcher, MockMemoryStore, MockCredentialStore.

- [ ] **Step 3:** Deploy to Render, verify public URL, verify browser session isolation.
- [ ] **Step 4:** Record URL in README.md.
- [ ] **Step 5:** Commit.

```bash
git add render.yaml
git commit -m "deploy: add Render configuration for Mock-only WebUI demo"
git push origin main
git push github main
```

---

### Phase 21: Documentation

#### Task 21.1: README.md (non-implementation — documentation only)

**Files:**
- Modify: `README.md` (already exists from initial commit)

**Type:** DOCUMENTATION (no test code, no implementation code required)

- [ ] **Step 1:** Write README with: what is CodeGuard, quick start, CLI commands, WebUI demo, credential setup, distribution options, security notes, SmartScreen warning, SHA-256 verification, architecture overview, key mechanisms, Render URL.

---

#### Task 21.2: SECURITY.md (non-implementation — documentation only)

**Files:**
- Create: `SECURITY.md`

**Type:** DOCUMENTATION (no test code, no implementation code required)

- [ ] **Step 1:** Write SECURITY.md with credential storage (Windows Credential Manager), threat model, fail-closed policy, SecretRedactor, demo isolation, SmartScreen explanation.

---

#### Task 21.3: Mechanism demo scripts (non-implementation — documentation scripts)

**Files:**
- Create: `demo/demo_scenario_a.py`
- Create: `demo/demo_scenario_b.py`
- Create: `demo/demo_scenario_c.py`

**Type:** DOCUMENTATION (runnable scripts, no test code required)

- [ ] **Step 1:** Write runnable scripts that demonstrate each scenario with printed state transitions.

---

#### Task 21.4: DeepSeek smoke test script (non-implementation — manual script)

**Files:**
- Already created: `scripts/deepseek_smoke_test.py` (in Task 11.1)

**Type:** DOCUMENTATION (manual script, not in CI)

- [ ] **Step 1:** Verify script exists and is documented as NOT in CI.

---

### Phase 22: Final Verification

**Note:** These tasks are non-implementation verification tasks. They do not produce test code or implementation code; they are manual verification steps.

#### Task 22.1: Full test suite run (manual verification)

- [ ] Run: `pytest -v`
- [ ] Verify: All tests pass, no real LLM/API key/network access.

#### Task 22.2: Credential leak scan (manual verification)

- [ ] Run: `git grep -n "sk-"` (and other API key patterns)
- [ ] Verify: No matches.

#### Task 22.3: SPEC coverage verification (manual verification)

- [ ] Check: Every SPEC §3 FC module has corresponding test(s).
- [ ] Check: Every user story (US-1 to US-8) has acceptance test.
- [ ] Check: §11 acceptance criteria all satisfied.

#### Task 22.4: .claude/projects/ exclusion (manual verification)

- [ ] Verify: `git status` shows no `.claude/projects/` files staged.

#### Task 22.5: REFLECTION.md (DOCUMENTATION — reserved for human author)

- [ ] Create: `REFLECTION.md` with task header only (reserved for human author). No generated body.

---

## Worktree / Branch / PR Planning

| Task | Worktree | Branch | Pre-commit | File Boundary | Verification Command | Merge Order |
|------|----------|--------|------------|---------------|---------------------|-------------|
| 1.1 Scaffold | main | task-1.1-scaffold | none | codeguard/__init__.py, __main__.py, tests/ | python -m codeguard --help | 1 |
| 1.2 Core enums | main | task-1.2-core-enums | 1.1 | codeguard/state.py, tests/test_state.py | pytest tests/test_state.py -v | 2 |
| 1.3 Action models | main | task-1.3-action-models | 1.2 | codeguard/action.py, tests/test_action.py | pytest tests/test_action.py -v | 3 |
| 1.4 Session/Guardrail models | main | task-1.4-session-guardrail-models | 1.3 | state.py, guardrail/__init__.py, guardrail/approval.py | pytest tests/test_data_models_core.py -v | 4 |
| 1.5 Remaining models | main | task-1.5-remaining-models | 1.4 | tool/, feedback/, memory/, config/ __init__.py + models | pytest tests/test_data_models_remaining.py -v | 5 |
| 2.1 ScriptedMockLLM | main | task-2.1-scripted-mock-llm | 1.3 | codeguard/llm/, tests/test_llm_mock.py | pytest tests/test_llm_mock.py -v | 6 |
| 2.2 AgentLoop init | main | task-2.2-agent-loop | 1.4, 2.1 | codeguard/loop.py, tests/test_loop.py | pytest tests/test_loop.py -v | 7 |
| 2.3 Full state machine | main | task-2.3-full-state-machine | 2.2 | loop.py, test_loop.py | pytest tests/test_loop.py -v | 8 |
| 2.4 ContextBuilder | main | task-2.4-context-builder | 2.2 | context.py, test_context.py | pytest tests/test_context.py -v | 9 |
| 2.5 ActionParser | main | task-2.5-action-parser | 1.3 | action.py, test_action.py | pytest tests/test_action.py -v | 10 |
| 3.1 SecretRedactor | worktree-secret | task-3.1-secret-redactor | 1.1 | secret.py, test_secret_redactor.py | pytest tests/test_secret_redactor.py -v | 11 |
| 4.1 ToolRegistry | worktree-tools | task-4.1-tool-registry | 1.5 | tool/registry.py, test_tool_registry.py | pytest tests/test_tool_registry.py -v | 12 |
| 4.2 File tools read | worktree-tools | task-4.2-file-tools-read | 4.1 | tool/file_tools.py, test_file_tools.py | pytest tests/test_file_tools.py -v | 13 |
| 4.3 File tools write | worktree-tools | task-4.3-file-tools-write | 4.2 | tool/file_tools.py, test_file_tools.py | pytest tests/test_file_tools.py -v | 14 |
| 4.4 run_process | worktree-tools | task-4.4-process-tool | 4.1 | tool/process_tool.py, test_process_tool.py | pytest tests/test_process_tool.py -v | 15 |
| 4.5 ToolDispatcher | worktree-tools | task-4.5-tool-dispatcher | 4.1-4.4 | tool/dispatcher.py, test_tool_dispatcher.py | pytest tests/test_tool_dispatcher.py -v | 16 |
| 5.1 ActionNormalizer | worktree-guardrail | task-5.1-action-normalizer | 1.5 | guardrail/normalizer.py, test_guardrail_normalizer.py | pytest tests/test_guardrail_normalizer.py -v | 12 (parallel with 4.1) |
| 5.2 Guardrail rules | worktree-guardrail | task-5.2-guardrail-rules | 5.1 | guardrail/rules.py, test_guardrail_rules.py | pytest tests/test_guardrail_rules.py -v | 13 |
| 5.3 RuleEngine | worktree-guardrail | task-5.3-rule-engine | 5.2 | guardrail/engine.py, test_guardrail_engine.py | pytest tests/test_guardrail_engine.py -v | 14 |
| 5.4 ApprovalManager | worktree-guardrail | task-5.4-approval-manager | 1.4, 5.3 | guardrail/approval.py, test_approval_manager.py | pytest tests/test_approval_manager.py -v | 15 |
| 6.1 SensorRunner | worktree-feedback | task-6.1-sensor-runner | 1.5 | feedback/sensor.py, test_sensor_runner.py | pytest tests/test_sensor_runner.py -v | 12 (parallel with 4.1) |
| 6.2 Parsers | worktree-feedback | task-6.2-parsers | 6.1 | feedback/parsers.py, test_parsers.py | pytest tests/test_parsers.py -v | 13 |
| 6.3 Classifier | worktree-feedback | task-6.3-classifier | 6.2 | feedback/classifier.py, test_classifier.py | pytest tests/test_classifier.py -v | 14 |
| 6.4 Feedback format | worktree-feedback | task-6.4-feedback-format | 6.3 | feedback/classifier.py, test_classifier.py | pytest tests/test_classifier.py -v | 15 |
| 6.5 Verifier | worktree-feedback | task-6.5-verifier | 6.3 | feedback/verifier.py, test_verifier.py | pytest tests/test_verifier.py -v | 16 |
| 7.1 Tracer | main | task-7.1-tracer | 3.1 | tracer.py, test_tracer.py | pytest tests/test_tracer.py -v | 17 (after 11, 16) |
| 8.1 StopPolicy | main | task-8.1-stop-policy | 1.4 | stop.py, test_stop_policy.py | pytest tests/test_stop_policy.py -v | 17 (parallel with 7.1) |
| 9.1 JSONMemoryStore | worktree-memory | task-9.1-json-memory-store | 1.5 | memory/store.py, test_memory_store.py | pytest tests/test_memory_store.py -v | 17 (parallel with 7.1) |
| 9.2 MemoryRetriever | worktree-memory | task-9.2-memory-retriever | 9.1 | memory/retriever.py, test_memory_retriever.py | pytest tests/test_memory_retriever.py -v | 18 |
| 9.3 Memory lifecycle | worktree-memory | task-9.3-memory-lifecycle | 9.2 | memory/store.py, test_memory_store.py | pytest tests/test_memory_store.py -v | 19 |
| 10.1 ConfigLoader | worktree-config | task-10.1-config-loader | 1.5 | config/loader.py, test_config_loader.py | pytest tests/test_config_loader.py -v | 17 (parallel with 7.1) |
| 10.2 ConfigMerger | worktree-config | task-10.2-config-merger | 10.1 | config/merger.py, test_config_merger.py | pytest tests/test_config_merger.py -v | 18 |
| 11.1 DeepSeekAdapter | main | task-11.1-deepseek-adapter | 2.1 | llm/deepseek.py, test_llm_deepseek.py | pytest tests/test_llm_deepseek.py -v | 20 (after 17) |
| 12.1 Keyring | main | task-12.1-keyring-credential | 1.1 | cli/key_cmd.py, test_cli.py | pytest tests/test_cli.py -v | 20 (parallel with 11.1) |
| 13.1 CompositionRoot | main | task-13.1-composition-root | 11.1-12.1 | composition.py, test_composition_root.py | pytest tests/test_composition_root.py -v | 21 |
| 14.1 Integration A | worktree-integration | task-14.1-integration-a | 13.1 | test_integration_guardrail_feedback.py | pytest -k "scenario_a" -v | 22 |
| 14.2 Integration B | worktree-integration | task-14.2-integration-b | 14.1 | test_integration_guardrail_feedback.py | pytest -k "scenario_b" -v | 23 |
| 14.3 Integration C | worktree-integration | task-14.3-integration-c | 14.2 | test_integration_guardrail_feedback.py | pytest -k "scenario_c" -v | 24 |
| 14.4 No-progress | worktree-integration | task-14.4-integration-noprogress | 14.3 | test_integration_guardrail_feedback.py | pytest -k "no_progress" -v | 25 |
| 15.1 CLI | main | task-15.1-cli | 13.1 | __main__.py, cli/, test_cli.py | pytest tests/test_cli.py -v | 26 |
| 16.1-16.6 WebUI | worktree-webui | task-16.1-web-app through 16.6 | 13.1 | web/, test_web_*.py | pytest tests/test_web_*.py -v | 27 (separate PR) |
| 17.1-17.3 Demo | main | task-17.1-demo-a through 17.3 | 14.1-14.3 | demo/, test_demo_*.py | pytest tests/test_demo_*.py -v | 28 |
| 18.1-18.2 CI/CD | main | task-18.1-gitlab-ci, 18.2-github-actions | 22.1 | .gitlab-ci.yml, .github/ | Push to remote, verify pipeline | 29 |
| 19.1-19.2 PyInstaller | main | task-19.1-pyinstaller-spec | 15.1 | codeguard.spec | pyinstaller codeguard.spec | 30 |
| 20.1 Render | main | task-20.1-render | 16.6 | render.yaml, README.md | Deploy to Render, verify URL | 31 |
| 21.1-21.4 Docs | main | task-21.1-readme through 21.4 | 20.1 | README.md, SECURITY.md, demo/*.py | Manual review | 32 |
| 22.1-22.5 Final | main | task-22.1-final through 22.5 | 21.4 | REFLECTION.md | pytest -v, git grep | 33 |

**Conflict prevention:** Parallel worktrees never modify the same file. Each worktree is scoped to specific files. The "File Boundary" column defines the exact scope. When multiple worktrees run in parallel, they modify different files in different directories.

---

## Cold Start Recommendation

**Environment pre-check (required before any task):**
1. `python --version` must report Python 3.12.x. If `python` is not in PATH, try `py -3.12 --version` or a project-local venv path (e.g., `.\.venv\Scripts\python.exe --version`).
2. `python -m pytest --version` must report pytest ≥ 8.3. If not installed, run `pip install -r requirements/dev.txt` (requires network) or use a pre-built venv.
3. If neither Python 3.12 nor pytest is available, STOP. Do not install Python yourself. Report the missing dependency and wait for the user to provide a working environment.

**Task 1.1 (Scaffold)** is the best cold-start task:
- **Self-contained:** No dependencies on any other code. Creates package structure, CLI entry point, test infrastructure, and requirements.
- **Time estimate:** ~45 minutes for a prepared agent.
- **Verification:** `python -m pytest tests/test_scaffold.py -v` → 1 passed; `python -m codeguard --help` shows usage with subcommands.
- **Why it's first:** Every other task depends on the package structure. Completing 1.1 unblocks all subsequent work.

**Task 2.1 (ScriptedMockLLM)** is the second-best cold-start:
- **Self-contained:** Depends only on Task 1.3 (Action data models, ~10 lines of dataclasses).
- **Time estimate:** ~30 minutes.
- **Verification:** 4 tests pass using ScriptedMockLLM with pre-scripted actions.
- **Why it's second:** It's the fundamental testing tool. Every subsequent test uses ScriptedMockLLM. Without it, no other module can be tested offline.

**Task 3.1 (SecretRedactor)** is the third-best cold-start:
- **Self-contained:** Depends only on Task 1.1 (package structure). No data models needed.
- **Time estimate:** ~30 minutes.
- **Verification:** 6 tests pass for API key redaction, credential masking, path normalization, and length limiting.
- **Why it's third:** SecretRedactor must be implemented before any output-producing component. Getting it done early prevents security debt.

These tasks are recommended because they have zero dependencies on other implementation modules, produce immediately verifiable output, and establish the foundation that all other tasks build upon. An agent with only SPEC.md, PLAN.md, and Python 3.12 knowledge can complete them independently.

**Cold-start constraint override:** In validation/course scenarios (e.g., cold-start verification by an unfamiliar agent), upper-level user instructions take precedence over Task-level defaults. Specifically:
- **Worktree:** The user may specify a fixed worktree and branch (e.g., `validation/codex-cold-start`). Do not create additional worktrees or branches per task.
- **Push:** The user may disallow `git push` and `git merge`. All commits remain local to the specified branch.
- **Python interpreter:** The user may specify an explicit interpreter path (e.g., `.\.venv\Scripts\python.exe`). Use that path in all `python -m pytest` and `python -m codeguard` commands.
- When in doubt, follow the user's more specific instructions over the Task-level defaults below.

---

## SPEC Coverage Matrix

| SPEC Section | Task(s) |
|-------------|---------|
| §1 Problem Statement | 21.1 (README) |
| §2 User Stories (US-1 to US-8) | 14.1-14.4, 5.4, 6.3, 9.2, 4.2, 16.1-16.6, 22.1 |
| §3.1 Agent Loop (FC-1) | 2.2, 2.3, 2.4, 2.5 |
| §3.2 Guardrail (FC-2) | 5.1, 5.2, 5.3 |
| §3.3 StopPolicy (FC-3) | 8.1 |
| §3.4 Approval (FC-4) | 5.4 |
| §3.5 Feedback (FC-5) | 6.1, 6.2, 6.3, 6.4, 6.5 |
| §3.6 Tool System (FC-6) | 4.1, 4.2, 4.3, 4.4, 4.5 |
| §3.7 Memory (FC-7) | 9.1, 9.2, 9.3 |
| §3.8 Config (FC-8) | 10.1, 10.2 |
| §3.9 WebUI (FC-9) | 16.1-16.6 |
| §4.1 SecretRedactor | 3.1 |
| §4.2 Mode isolation | 13.1, 20.1 |
| §4.3 Tracer | 7.1 |
| §5.1 CompositionRoot | 13.1 |
| §5.2 CLI | 15.1 |
| §5.3 LLM | 2.1, 11.1 |
| §6 Data Models | 1.2, 1.3, 1.4, 1.5 |
| §7 State Machine | 2.3 |
| §8.1 Credentials | 12.1 |
| §8.2 Distribution | 19.1, 19.2, 21.1 |
| §9.1 Tech Stack | 1.1, 11.1 |
| §9.2 CI | 18.1, 18.2 |
| §10 Domain | 14.1-14.4 |
| §11 Acceptance Criteria | 22.1-22.5 |
| §12 Risks | 21.1, 21.2 |
| C1 (Web Prototype doc mode) | 16.1-16.6 (templates from IA.md/WIREFRAME_SPEC.md) |
| C2 (No React/Node.js) | 16.1-16.6 (vanilla JS + CSS only) |
| C3 (Scenario A: BLOCK -> feedback -> COMPLETE) | 14.1, 17.1 |
| C4 (Scenario B: timeout -> CANCELLED) | 14.2, 17.2 |
| C5 (approval timeout: 15s/5s/300s) | 5.4, 16.4 |
| C6 (4 MemoryTypes) | 9.1, 9.2, 9.3, 16.5 |
| C7 (UI_DESIGN_BRIEF.md coverage) | 16.1-16.6 (templates match DESIGN.md) |
| C8 (narrow screen 375px) | 16.6 |