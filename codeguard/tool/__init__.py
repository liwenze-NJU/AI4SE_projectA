from dataclasses import dataclass, field
from typing import Optional, Callable


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters_schema: dict
    handler: Callable
    category: str = "FILE"
    side_effect: bool = False
    default_risk: str = "ALLOW"
    supported_modes: list[str] = field(default_factory=lambda: ["TEST"])
    result_schema: Optional[dict] = None
    timeout_limit: int = 30


@dataclass
class ToolResult:
    tool_name: str
    status: str
    output_summary: str
    diagnostics: list
    exit_code: Optional[int] = None
    changed_files: list[str] = field(default_factory=list)
    duration: float = 0.0
    truncated: bool = False
    error_category: Optional[str] = None
    audit_id: str = ""