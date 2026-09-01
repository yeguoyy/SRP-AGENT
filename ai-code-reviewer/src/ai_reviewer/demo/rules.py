"""Deterministic rule checks that make the demo useful without an API key."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable

from ai_reviewer.demo.models import Category, Finding, ProjectSnapshot, Severity

SECRET_RE = re.compile(
    r"(?:password|passwd|api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|token|secret)"
    r"\s*[=:]\s*[\"'][^\"']{6,}[\"']",
    re.IGNORECASE,
)
SQL_INTERPOLATION_RE = re.compile(
    r"\b(?:select|insert|update|delete|where)\b.*(?:\{[^}]+\}|\.format\(|\+\s*[A-Za-z_]|%\s*[A-Za-z_(])",
    re.IGNORECASE,
)
DANGEROUS_CALL_RE = re.compile(r"\b(eval|exec)\s*\(|shell\s*=\s*True")
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK)\b", re.IGNORECASE)


def _finding(
    file_path: str,
    line: int,
    severity: Severity,
    category: Category,
    title: str,
    description: str,
    recommendation: str,
    confidence: float,
) -> Finding:
    return Finding(
        file_path=file_path,
        line_start=line,
        line_end=line,
        severity=severity,
        category=category,
        title=title,
        description=description,
        recommendation=recommendation,
        confidence=confidence,
        source_agents=["rule-detector"],
    )


def _python_function_findings(file_path: str, content: str) -> list[Finding]:
    results: list[Finding] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return results
    lines = content.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = getattr(node, "end_lineno", node.lineno)
        function_lines = end - node.lineno + 1
        branch_count = sum(
            isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler))
            for child in ast.walk(node)
        )
        if branch_count >= 6:
            results.append(
                _finding(
                    file_path,
                    node.lineno,
                    Severity.WARNING,
                    Category.COMPLEXITY,
                    f"函数 {node.name} 的分支复杂度偏高",
                    f"该函数包含约 {branch_count} 个条件或循环分支，后续修改和测试成本较高。",
                    "拆分校验、数据处理和副作用操作，优先提取为职责单一的辅助函数。",
                    0.91,
                )
            )
        if function_lines >= 45:
            results.append(
                _finding(
                    file_path,
                    node.lineno,
                    Severity.WARNING,
                    Category.QUALITY,
                    f"函数 {node.name} 过长",
                    f"函数约 {function_lines} 行，已经同时承载多个处理职责。",
                    "按业务步骤拆分函数，并为每个步骤补充单元测试。",
                    0.88,
                )
            )
        if not ast.get_docstring(node) and function_lines >= 15:
            results.append(
                _finding(
                    file_path,
                    node.lineno,
                    Severity.SUGGESTION,
                    Category.QUALITY,
                    f"函数 {node.name} 缺少说明",
                    "较长的公共函数没有 docstring 或行为说明，增加了团队协作成本。",
                    "补充参数、返回值、异常和关键业务规则说明。",
                    0.75,
                )
            )
    if len(lines) > 180:
        results.append(
            _finding(
                file_path,
                1,
                Severity.SUGGESTION,
                Category.ARCHITECTURE,
                "文件规模偏大",
                f"该文件包含 {len(lines)} 行代码，可能存在多个职责聚合在同一模块的问题。",
                "按领域职责拆分模块，降低单文件的理解和变更成本。",
                0.78,
            )
        )
    return results


def detect_findings(snapshot: ProjectSnapshot) -> list[Finding]:
    """Run deterministic checks across a project snapshot."""
    findings: list[Finding] = []
    for file_info in snapshot.files:
        lines = file_info.content.splitlines()
        for line_number, line in enumerate(lines, start=1):
            if SECRET_RE.search(line):
                findings.append(
                    _finding(
                        file_info.path,
                        line_number,
                        Severity.CRITICAL,
                        Category.SECURITY,
                        "检测到疑似硬编码敏感凭据",
                        "代码行中直接出现 password、API key、token 或 secret 等敏感配置。",
                        "立即移除硬编码凭据并轮换已暴露的密钥，改用环境变量或密钥管理服务。",
                        0.97,
                    )
                )
            if DANGEROUS_CALL_RE.search(line):
                findings.append(
                    _finding(
                        file_info.path,
                        line_number,
                        Severity.CRITICAL,
                        Category.SECURITY,
                        "检测到高风险动态执行或 Shell 调用",
                        "eval、exec 或 shell=True 可能让外部输入进入任意代码或命令执行路径。",
                        "避免动态执行；如必须执行命令，使用参数数组、白名单和严格输入校验。",
                        0.94,
                    )
                )
            if SQL_INTERPOLATION_RE.search(line):
                findings.append(
                    _finding(
                        file_info.path,
                        line_number,
                        Severity.WARNING,
                        Category.SECURITY,
                        "SQL 语句可能使用了不安全的字符串拼接",
                        "SQL 语句包含插值、拼接或格式化调用，存在 SQL 注入风险。",
                        "改用参数化查询或 ORM 查询参数，不要把外部输入直接拼接进 SQL。",
                        0.9,
                    )
                )
            if len(line) > 120:
                findings.append(
                    _finding(
                        file_info.path,
                        line_number,
                        Severity.NITPICK,
                        Category.STYLE,
                        "代码行过长",
                        f"当前代码行长度为 {len(line)}，降低了审阅和定位问题时的可读性。",
                        "拆分表达式或使用格式化工具统一代码风格。",
                        0.86,
                    )
                )
            if TODO_RE.search(line):
                findings.append(
                    _finding(
                        file_info.path,
                        line_number,
                        Severity.SUGGESTION,
                        Category.QUALITY,
                        "发现未闭环的 TODO/FIXME 标记",
                        "代码中存在待处理标记，可能意味着功能或缺陷尚未闭环。",
                        "将其转化为可追踪任务，补充负责人、优先级和验收条件。",
                        0.72,
                    )
                )
        if file_info.language == "Python":
            findings.extend(_python_function_findings(file_info.path, file_info.content))

    if snapshot.files and not snapshot.has_tests:
        findings.append(
            _finding(
                snapshot.files[0].path,
                1,
                Severity.WARNING,
                Category.TESTING,
                "项目中未发现测试文件",
                "当前扫描范围内没有识别到 tests 或 test_*.py 等测试资产。",
                "至少为核心业务流程和安全边界补充自动化测试，并在 CI 中执行。",
                0.84,
            )
        )
    return findings


def by_category(findings: Iterable[Finding], category: Category) -> list[Finding]:
    return [finding for finding in findings if finding.category == category]
