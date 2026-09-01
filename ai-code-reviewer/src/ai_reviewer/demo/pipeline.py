"""End-to-end runner for the local competition demo."""

from __future__ import annotations

from ai_reviewer.demo.agents import build_agents
from ai_reviewer.demo.aggregation import build_report
from ai_reviewer.demo.llm import LLMError, OpenAICompatibleClient
from ai_reviewer.demo.models import AgentResult, DemoReport, ProjectSnapshot
from ai_reviewer.demo.rules import detect_findings


def run_demo(
    snapshot: ProjectSnapshot,
    *,
    mode: str = "mock",
    client: OpenAICompatibleClient | None = None,
    user_request: str | None = None,
) -> DemoReport:
    """Run scan, deterministic checks, agents, consensus, and scoring."""
    rule_findings = detect_findings(snapshot)
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
        return build_report(snapshot, results, mode=mode, user_request=user_request)

    errors: list[str] = []
    results: list[AgentResult] = []
    for agent in build_agents():
        result = agent.review(snapshot, rule_findings, mode=mode, client=client)
        results.append(result)
        if result.error:
            errors.append(f"{result.agent_name}: {result.error}")
    return build_report(snapshot, results, mode=mode, user_request=user_request, errors=errors)


def run_from_path(
    root: str,
    *,
    mode: str = "mock",
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    user_request: str | None = None,
) -> DemoReport:
    from ai_reviewer.demo.scanner import scan_project

    snapshot = scan_project(root)
    client = None
    if mode == "api":
        try:
            client = OpenAICompatibleClient(base_url=base_url, api_key=api_key, model=model)
        except LLMError as exc:
            # Agents will use their deterministic fallback and the report will still be useful.
            client = None
            report = run_demo(snapshot, mode="api", client=None, user_request=user_request)
            report.errors.insert(0, str(exc))
            return report
    return run_demo(snapshot, mode=mode, client=client, user_request=user_request)

