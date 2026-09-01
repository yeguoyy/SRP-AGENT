"""End-to-end runner for the local competition demo."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from ai_reviewer.config import LLMConfig, load_config
from ai_reviewer.demo.agents import build_agents
from ai_reviewer.demo.aggregation import build_report
from ai_reviewer.demo.llm import LLMError, ReviewClient, create_demo_client
from ai_reviewer.demo.models import AgentResult, DemoReport, ProjectSnapshot
from ai_reviewer.demo.rules import detect_findings

ProgressCallback = Callable[[str, dict[str, Any]], None]


def _notify(callback: ProgressCallback | None, event: str, **data: Any) -> None:
    if callback is not None:
        callback(event, data)


def run_demo(
    snapshot: ProjectSnapshot,
    *,
    mode: str = "mock",
    client: ReviewClient | None = None,
    user_request: str | None = None,
    agent_count: int = 3,
    progress_callback: ProgressCallback | None = None,
) -> DemoReport:
    """Run scan, deterministic checks, agents, consensus, and scoring."""
    _notify(progress_callback, "rules_start")
    rule_findings = detect_findings(snapshot)
    _notify(progress_callback, "rules_complete", finding_count=len(rule_findings))
    if mode == "rules":
        results = [
            AgentResult(
                agent_name="规则检测器",
                focus="安全、质量、复杂度和测试资产",
                findings=rule_findings,
                summary=f"离线规则检测完成，发现 {len(rule_findings)} 个候选问题。",
                elapsed_ms=0,
            )
        ]
        _notify(progress_callback, "aggregation_start")
        report = build_report(snapshot, results, mode=mode, user_request=user_request)
        _notify(progress_callback, "aggregation_complete", finding_count=len(report.findings))
        return report

    errors: list[str] = []
    results: list[AgentResult] = []
    for agent in build_agents(agent_count):
        _notify(progress_callback, "agent_start", agent_name=agent.name)
        result = agent.review(
            snapshot,
            rule_findings,
            mode=mode,
            client=client,
            progress_callback=progress_callback,
        )
        results.append(result)
        if result.error:
            errors.append(f"{result.agent_name}: {result.error}")
            _notify(
                progress_callback,
                "agent_fallback",
                agent_name=result.agent_name,
                elapsed_ms=result.elapsed_ms,
                error=result.error,
                finding_count=len(result.findings),
            )
        else:
            _notify(
                progress_callback,
                "agent_complete",
                agent_name=result.agent_name,
                elapsed_ms=result.elapsed_ms,
                finding_count=len(result.findings),
            )
    _notify(progress_callback, "aggregation_start")
    report = build_report(snapshot, results, mode=mode, user_request=user_request, errors=errors)
    _notify(progress_callback, "aggregation_complete", finding_count=len(report.findings))
    return report


def _env_config(
    *,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
    protocol: str | None,
) -> LLMConfig:
    """Build the backwards-compatible Demo config from the local ``.env``."""
    selected_protocol = (protocol or os.getenv("LLM_PROTOCOL") or "openai_chat_completions").strip()
    default_base_url = (
        "https://api.anthropic.com"
        if selected_protocol == "anthropic_messages"
        else "https://api.openai.com/v1"
    )
    selected_key = api_key or os.getenv("LLM_API_KEY", "")
    selected_model = model or os.getenv("LLM_MODEL", "")
    if not selected_model:
        selected_model = "claude-sonnet-5" if selected_protocol == "anthropic_messages" else "gpt-4.1"
    try:
        timeout = int(os.getenv("LLM_TIMEOUT", "60"))
    except ValueError:
        timeout = 60
    try:
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1600"))
    except ValueError:
        max_tokens = 1600
    try:
        retries = int(os.getenv("LLM_RETRIES", "1"))
    except ValueError:
        retries = 1
    thinking = os.getenv("LLM_THINKING") or None
    return LLMConfig(
        protocol=selected_protocol,
        api_key=selected_key,
        api_key_env="LLM_API_KEY",
        base_url=base_url or os.getenv("LLM_BASE_URL", default_base_url),
        model=selected_model,
        timeout_seconds=max(timeout, 1),
        max_tokens=max(max_tokens, 256),
        max_retries=max(retries, 0),
        default_model=selected_model,
        thinking=thinking,
    )


def _resolve_demo_config(
    config_path: str | None,
    *,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
    protocol: str | None,
) -> LLMConfig:
    # The repository config is the default source for all normal project runs.
    # Keep the environment-only path as a compatibility fallback when the
    # command is launched from a directory that has no config.yaml.
    selected_path = Path(config_path) if config_path else Path("config.yaml")
    if config_path or selected_path.exists():
        config = load_config(selected_path)
        configured = config.llm or config.anthropic
        if configured is None:
            raise LLMError("配置文件中没有 llm 配置")
        updates: dict[str, Any] = {}
        if base_url is not None:
            updates["base_url"] = base_url
        if api_key is not None:
            updates["api_key"] = api_key
        if model is not None:
            updates["model"] = model
            updates["default_model"] = model
        if protocol is not None:
            updates["protocol"] = protocol
        return replace(configured, **updates) if updates else configured
    return _env_config(base_url=base_url, api_key=api_key, model=model, protocol=protocol)
def run_from_path(
    root: str,
    *,
    mode: str = "mock",
    config_path: str | None = None,
    protocol: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    user_request: str | None = None,
    agent_count: int = 3,
    progress_callback: ProgressCallback | None = None,
) -> DemoReport:
    from ai_reviewer.demo.scanner import scan_project

    _notify(progress_callback, "scan_start", root=root)
    snapshot = scan_project(root)
    _notify(
        progress_callback,
        "scan_complete",
        file_count=snapshot.file_count,
        total_lines=snapshot.total_lines,
    )
    client: ReviewClient | None = None
    if mode == "api":
        try:
            llm_config = _resolve_demo_config(
                config_path,
                base_url=base_url,
                api_key=api_key,
                model=model,
                protocol=protocol,
            )
            client = create_demo_client(llm_config)
        except LLMError as exc:
            # Agents will use their deterministic fallback and the report will still be useful.
            report = run_demo(
                snapshot,
                mode="api",
                client=None,
                user_request=user_request,
                agent_count=agent_count,
                progress_callback=progress_callback,
            )
            report.errors.insert(0, str(exc))
            return report
    return run_demo(
        snapshot,
        mode=mode,
        client=client,
        user_request=user_request,
        agent_count=agent_count,
        progress_callback=progress_callback,
    )

