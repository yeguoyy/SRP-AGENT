"""CLI entry point for the competition-oriented local demo."""

from __future__ import annotations

import argparse
import json
import sys

from ai_reviewer.demo.models import enum_value
from ai_reviewer.demo.pipeline import run_from_path
from ai_reviewer.demo.reporting import write_reports
from ai_reviewer.demo.rules import detect_findings
from ai_reviewer.demo.scanner import scan_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ai_reviewer.demo",
        description="SRP 多智能体代码质量评审 Demo",
    )
    parser.add_argument("command", nargs="?", choices=["review", "scan", "rules"], default="review")
    parser.add_argument("--repo", required=True, help="待评审的本地项目目录")
    parser.add_argument("--mode", choices=["mock", "rules", "api"], default="mock")
    parser.add_argument("--output-dir", default="demo/output", help="报告输出目录")
    parser.add_argument("--base-url", help="OpenAI 兼容接口地址，例如 https://host/v1")
    parser.add_argument("--api-key", help="模型 API Key，也可使用 LLM_API_KEY")
    parser.add_argument("--model", help="模型名称，也可使用 LLM_MODEL")
    parser.add_argument(
        "--question",
        help="用户的自然语言评审请求，例如：请重点检查安全问题",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        snapshot = scan_project(args.repo)
    except (NotADirectoryError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if args.command == "scan":
        print(json.dumps(enum_value(snapshot), ensure_ascii=False, indent=2))
        return 0

    if args.command == "rules":
        findings = detect_findings(snapshot)
        print(json.dumps(enum_value(findings), ensure_ascii=False, indent=2))
        return 0

    report = run_from_path(
        args.repo,
        mode=args.mode,
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
        user_request=args.question,
    )
    paths = write_reports(report, args.output_dir)
    print("\n=== SRP 智能代码评审 Demo ===")
    print(f"项目：{report.project.root}")
    print(f"文件：{report.project.file_count} 个 | 代码：{report.project.total_lines} 行")
    print(f"模式：{report.mode}")
    if report.user_request:
        print(f"用户请求：{report.user_request}")
    print(f"综合评分：{report.score.overall:.1f} / 100")
    print(f"独立问题：{len(report.findings)} 个")
    print("\n维度评分：")
    for dimension, value in report.score.dimensions.items():
        print(f"  - {dimension:<12} {value:>5.1f}")
    print("\n报告已生成：")
    for name, path in paths.items():
        print(f"  - {name}: {path}")
    if report.errors:
        print("\n降级信息：")
        for error in report.errors:
            print(f"  - {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
