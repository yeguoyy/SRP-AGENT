"""CLI entry point for the competition-oriented local demo."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from rich.console import Console

from ai_reviewer.demo.models import enum_value
from ai_reviewer.demo.pipeline import run_from_path
from ai_reviewer.demo.reporting import write_reports
from ai_reviewer.demo.rules import detect_findings
from ai_reviewer.demo.scanner import scan_project


class DemoProgressReporter:
    """Show live progress while the blocking model calls are running."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self._status = None

    def __enter__(self) -> DemoProgressReporter:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self._stop_status()

    def __call__(self, event: str, data: dict[str, Any]) -> None:
        if event == "scan_start":
            self._start_status("正在扫描项目...")
        elif event == "scan_complete":
            self._finish(
                f"项目扫描完成，发现 {data.get('file_count', 0)} 个文件"
            )
        elif event == "rules_start":
            self._start_status("正在运行确定性规则检测...")
        elif event == "rules_complete":
            self._finish(
                f"确定性规则检测完成，发现 {data.get('finding_count', 0)} 个候选问题"
            )
        elif event == "agent_start":
            self._start_status(f"{data.get('agent_name', 'Agent')} 正在分析...")
        elif event == "agent_retry":
            self._stop_status()
            self.console.print(
                f"↻ {data.get('agent_name', 'Agent')} 第 "
                f"{data.get('retry_number', 2)} 次请求..."
            )
            self._start_status(f"{data.get('agent_name', 'Agent')} 正在分析...")
        elif event == "agent_complete":
            elapsed = data.get("elapsed_ms", 0) / 1000
            self._finish(
                f"{data.get('agent_name', 'Agent')} 完成，耗时 {elapsed:.1f} 秒，"
                f"发现 {data.get('finding_count', 0)} 个问题"
            )
        elif event == "agent_fallback":
            self._stop_status()
            agent_name = data.get("agent_name", "Agent")
            error = data.get("error", "未知错误")
            self.console.print(f"⚠ {agent_name} 请求失败，已降级到离线规则：{error}")
        elif event == "aggregation_start":
            self._start_status("正在聚合评审结果...")
        elif event == "aggregation_complete":
            self._finish(
                f"评审结果聚合完成，得到 {data.get('finding_count', 0)} 个独立问题"
            )

    def _start_status(self, message: str) -> None:
        if self._status is None:
            self._status = self.console.status(message, spinner="dots")
            self._status.start()
        else:
            self._status.update(message)

    def _stop_status(self) -> None:
        if self._status is not None:
            self._status.stop()
            self._status = None

    def _finish(self, message: str) -> None:
        self._stop_status()
        self.console.print(f"✓ {message}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ai_reviewer.demo",
        description="SRP 多智能体代码质量评审 Demo",
    )
    parser.add_argument("command", nargs="?", choices=["review", "scan", "rules"], default="review")
    parser.add_argument("--repo", required=True, help="待评审的本地项目目录")
    parser.add_argument("--mode", choices=["mock", "rules", "api"], default="mock")
    parser.add_argument(
        "--agents",
        type=int,
        choices=range(1, 6),
        default=3,
        help="启用前 N 个评审角色（1-5，默认 3）",
    )
    parser.add_argument("--output-dir", default="demo/output", help="报告输出目录")
    parser.add_argument("--config", help="统一配置文件路径，例如 config.yaml")
    parser.add_argument(
        "--protocol",
        choices=["openai_chat_completions", "openai_responses", "anthropic_messages"],
        help="覆盖配置文件中的 LLM 协议",
    )
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
    # Progress goes to stderr so scan/rules keep their JSON stdout machine-readable.
    console = Console(file=sys.stderr, markup=False)

    if args.command in {"scan", "rules"}:
        with console.status("正在扫描项目...", spinner="dots"):
            try:
                snapshot = scan_project(args.repo)
            except (NotADirectoryError, OSError) as exc:
                console.print(f"错误：{exc}", style="bold red")
                return 2
        console.print(f"✓ 项目扫描完成，发现 {snapshot.file_count} 个文件")

        if args.command == "scan":
            print(json.dumps(enum_value(snapshot), ensure_ascii=False, indent=2))
            return 0

        with console.status("正在运行确定性规则检测...", spinner="dots"):
            findings = detect_findings(snapshot)
        console.print(f"✓ 确定性规则检测完成，发现 {len(findings)} 个候选问题")
        print(json.dumps(enum_value(findings), ensure_ascii=False, indent=2))
        return 0

    try:
        with DemoProgressReporter(console) as progress:
            report = run_from_path(
                args.repo,
                mode=args.mode,
                config_path=args.config,
                protocol=args.protocol,
                base_url=args.base_url,
                api_key=args.api_key,
                model=args.model,
                user_request=args.question,
                agent_count=args.agents,
                progress_callback=progress,
            )
            with console.status("正在生成报告...", spinner="dots"):
                paths = write_reports(report, args.output_dir)
            console.print("✓ 报告生成完成")
    except (NotADirectoryError, OSError) as exc:
        console.print(f"错误：{exc}", style="bold red")
        return 2
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
