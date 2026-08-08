from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FeedbackResult:
    sensor_id: str
    program: str
    args: list[str]
    status: str
    failure_category: Optional[str] = None
    exit_code: Optional[int] = None
    failure_fingerprint: Optional[str] = None
    validation_type: str = "INTERMEDIATE"
    summary: str = ""
    diagnostics: list = field(default_factory=list)
    duration: float = 0.0
    retryable: bool = False
    raw_output_truncated: str = ""


@dataclass
class SensorDefinition:
    name: str
    program: str
    args: list[str] = field(default_factory=list)
    cwd: Optional[str] = None
    timeout: int = 30
    parser: str = "generic"
    required: bool = True
    allowed_exit_codes: set[int] = field(default_factory=lambda: {0})
    output_limit: int = 4096


@dataclass
class Diagnostic:
    file: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    code: Optional[str] = None
    message: str = ""
    category: str = ""