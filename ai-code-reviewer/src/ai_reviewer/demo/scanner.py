"""Local repository scanner used by the standalone demo."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from ai_reviewer.demo.models import FileInfo, ProjectSnapshot

LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
}
DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "output",
    ".idea",
    ".vscode",
}


def _python_metrics(content: str) -> tuple[int, int, int]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return (
            len(re.findall(r"^\s*(?:async\s+)?def\s+", content, re.MULTILINE)),
            len(re.findall(r"^\s*class\s+", content, re.MULTILINE)),
            1,
        )

    functions = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
    classes = sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
    branches = sum(
        isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.Try, ast.ExceptHandler))
        for node in ast.walk(tree)
    )
    boolean_ops = sum(isinstance(node, ast.BoolOp) for node in ast.walk(tree))
    return functions, classes, 1 + branches + boolean_ops


def _generic_metrics(content: str) -> tuple[int, int, int]:
    functions = len(re.findall(r"\b(?:function|def|func)\s+[A-Za-z_][\w]*", content))
    classes = len(re.findall(r"\bclass\s+[A-Za-z_][\w]*", content))
    complexity = 1 + len(re.findall(r"\b(if|for|while|catch|case|elif)\b|&&|\|\|", content))
    return functions, classes, complexity


def scan_project(root: str | Path, *, max_file_bytes: int = 500_000) -> ProjectSnapshot:
    """Scan supported source files below *root* and collect lightweight metrics."""
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        raise NotADirectoryError(f"项目目录不存在：{base}")

    files: list[FileInfo] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in LANGUAGE_BY_SUFFIX:
            continue
        relative_parts = path.relative_to(base).parts
        if any(part in DEFAULT_EXCLUDES for part in relative_parts):
            continue
        if path.stat().st_size > max_file_bytes:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        language = LANGUAGE_BY_SUFFIX[path.suffix.lower()]
        if language == "Python":
            function_count, class_count, complexity = _python_metrics(content)
        else:
            function_count, class_count, complexity = _generic_metrics(content)
        files.append(
            FileInfo(
                path=path.relative_to(base).as_posix(),
                language=language,
                line_count=max(1, len(content.splitlines())),
                byte_count=path.stat().st_size,
                function_count=function_count,
                class_count=class_count,
                complexity=complexity,
                content=content,
            )
        )

    languages = sorted({item.language for item in files})
    has_tests = any(
        "test" in item.path.lower() or item.path.lower().startswith(("tests/", "test/"))
        for item in files
    )
    return ProjectSnapshot(
        root=str(base),
        files=files,
        total_lines=sum(item.line_count for item in files),
        languages=languages,
        has_tests=has_tests,
    )
