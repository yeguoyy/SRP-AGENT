"""Standalone models for the competition-oriented local demo."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum
from hashlib import sha1
from typing import Any


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"
    NITPICK = "nitpick"


class Category(StrEnum):
    SECURITY = "security"
    QUALITY = "quality"
    ARCHITECTURE = "architecture"
    COMPLEXITY = "complexity"
    TESTING = "testing"
    STYLE = "style"


SEVERITY_RANK = {
    Severity.NITPICK: 1,
    Severity.SUGGESTION: 2,
    Severity.WARNING: 3,
    Severity.CRITICAL: 4,
}


@dataclass(slots=True)
class Finding:
    """One explainable issue reported by a detector or an agent."""

    file_path: str
    line_start: int
    line_end: int | None
    severity: Severity
    category: Category
    title: str
    description: str
    recommendation: str
    confidence: float = 0.8
    source_agents: list[str] = field(default_factory=list)
    id: str = ""

    def __post_init__(self) -> None:
        self.file_path = self.file_path.replace("\\", "/")
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        if self.line_start < 1:
            self.line_start = 1
        if not self.id:
            raw = f"{self.file_path}:{self.line_start}:{self.category.value}:{self.title}"
            self.id = f"finding-{sha1(raw.encode('utf-8')).hexdigest()[:10]}"

    @property
    def fingerprint(self) -> str:
        """Stable key used for deterministic de-duplication."""
        normalized_title = " ".join(self.title.lower().split())
        return f"{self.file_path}:{self.line_start}:{self.category.value}:{normalized_title}"


@dataclass(slots=True)
class FileInfo:
    path: str
    language: str
    line_count: int
    byte_count: int
    function_count: int
    class_count: int
    complexity: int
    content: str


@dataclass(slots=True)
class ProjectSnapshot:
    root: str
    files: list[FileInfo]
    total_lines: int
    languages: list[str]
    has_tests: bool

    @property
    def file_count(self) -> int:
        return len(self.files)

    def file(self, path: str) -> FileInfo | None:
        normalized = path.replace("\\", "/")
        return next((item for item in self.files if item.path == normalized), None)


@dataclass(slots=True)
class AgentResult:
    agent_name: str
    focus: str
    findings: list[Finding]
    summary: str
    elapsed_ms: int
    used_fallback: bool = False
    error: str | None = None


@dataclass(slots=True)
class ScoreBreakdown:
    overall: float
    dimensions: dict[str, float]
    weights: dict[str, float]


@dataclass(slots=True)
class DemoReport:
    project: ProjectSnapshot
    agent_results: list[AgentResult]
    findings: list[Finding]
    score: ScoreBreakdown
    summary: str
    generated_at: str
    mode: str
    user_request: str | None = None
    errors: list[str] = field(default_factory=list)


def enum_value(value: Any) -> Any:
    """Convert nested dataclass values to JSON-friendly primitives."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [enum_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): enum_value(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return {
            key: enum_value(getattr(value, key))
            for key in value.__dataclass_fields__
        }
    return value


def finding_from_dict(data: dict[str, Any], agent_name: str) -> Finding:
    """Safely normalize a JSON finding returned by a model."""
    severity = str(data.get("severity", Severity.SUGGESTION.value)).lower()
    category = str(data.get("category", Category.QUALITY.value)).lower()
    try:
        parsed_severity = Severity(severity)
    except ValueError:
        parsed_severity = Severity.SUGGESTION
    try:
        parsed_category = Category(category)
    except ValueError:
        parsed_category = Category.QUALITY
    finding = Finding(
        file_path=str(data.get("file_path", data.get("file", "unknown"))),
        line_start=int(data.get("line_start", data.get("line", 1)) or 1),
        line_end=data.get("line_end"),
        severity=parsed_severity,
        category=parsed_category,
        title=str(data.get("title", "未命名问题")),
        description=str(data.get("description", "模型未提供问题描述。")),
        recommendation=str(
            data.get("recommendation", data.get("suggested_fix", "请结合上下文进行人工确认。"))
        ),
        confidence=float(data.get("confidence", 0.65) or 0.65),
        source_agents=[agent_name],
    )
    return finding

