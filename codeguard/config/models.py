from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional


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
    required_sensors: list[str] = field(default_factory=list)
    sensor_order: list[str] = field(default_factory=list)
    timeout_per_sensor: int = 30
    output_limit: int = 4096


@dataclass
class MemoryConfig:
    enabled: bool = True
    max_records: int = 100
    top_k: int = 10
    context_budget: int = 2048
    allowed_types: list[str] = field(default_factory=list)


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
    workspace: WorkspaceConfig
    llm: LLMConfig
    loop: LoopConfig
    tools: ToolsConfig
    sensors: SensorsConfig
    memory: MemoryConfig
    ui: UIConfig
    approval: ApprovalConfig
    mode: str = "test"
    source: dict[str, str] = field(default_factory=dict)