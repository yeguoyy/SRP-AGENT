"""Deterministic multi-agent orchestration for the competition demo."""

from __future__ import annotations

import time
from dataclasses import replace

from ai_reviewer.demo.llm import LLMError, OpenAICompatibleClient
from ai_reviewer.demo.models import AgentResult, Category, Finding, ProjectSnapshot, Severity


class DemoAgent:
    name = "基础评审 Agent"
    focus = "综合代码质量"

    def review(
        self,
        snapshot: ProjectSnapshot,
        rule_findings: list[Finding],
        *,
        mode: str = "mock",
        client: OpenAICompatibleClient | None = None,
    ) -> AgentResult:
        started = time.perf_counter()
        try:
            if mode == "api":
                if client is None:
                    raise LLMError("API 模式未初始化模型客户端")
                findings, summary = client.review(
                    agent_name=self.name,
                    focus=self.focus,
                    snapshot=snapshot,
                )
                return AgentResult(
                    agent_name=self.name,
                    focus=self.focus,
                    findings=findings,
                    summary=summary,
                    elapsed_ms=int((time.perf_counter() - started) * 1000),
                )
            findings = self._mock_findings(snapshot, rule_findings)
            return AgentResult(
                agent_name=self.name,
                focus=self.focus,
                findings=findings,
                summary=self._summary(findings),
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )
        except LLMError as exc:
            findings = self._mock_findings(snapshot, rule_findings)
            return AgentResult(
                agent_name=self.name,
                focus=self.focus,
                findings=findings,
                summary=f"模型不可用，已降级到离线规则：{exc}",
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                used_fallback=True,
                error=str(exc),
            )

    def _mock_findings(self, snapshot: ProjectSnapshot, rule_findings: list[Finding]) -> list[Finding]:
        return list(rule_findings)

    def _summary(self, findings: list[Finding]) -> str:
        return f"{self.name} 完成评审，发现 {len(findings)} 个候选问题。"


class SecurityAgent(DemoAgent):
    name = "安全评审 Agent"
    focus = "敏感信息、注入、危险调用和安全边界"

    def _mock_findings(self, snapshot: ProjectSnapshot, rule_findings: list[Finding]) -> list[Finding]:
        return [
            _for_agent(finding, self.name)
            for finding in rule_findings
            if finding.category == Category.SECURITY
        ]


class QualityAgent(DemoAgent):
    name = "代码质量 Agent"
    focus = "可读性、可维护性、复杂度、代码异味和测试"

    def _mock_findings(self, snapshot: ProjectSnapshot, rule_findings: list[Finding]) -> list[Finding]:
        selected = [
            finding
            for finding in rule_findings
            if finding.category in {Category.QUALITY, Category.COMPLEXITY, Category.STYLE, Category.TESTING}
        ]
        # Quality agent independently notices unsafe SQL as a correctness/quality concern.
        selected.extend(
            finding
            for finding in rule_findings
            if finding.category == Category.SECURITY and "SQL" in finding.title
        )
        return [_for_agent(finding, self.name, soften_sql=True) for finding in selected]


class ArchitectureAgent(DemoAgent):
    name = "架构与逻辑 Agent"
    focus = "模块职责、依赖耦合、业务逻辑和演进风险"

    def _mock_findings(self, snapshot: ProjectSnapshot, rule_findings: list[Finding]) -> list[Finding]:
        selected = [
            finding
            for finding in rule_findings
            if finding.category in {Category.ARCHITECTURE, Category.COMPLEXITY}
        ]
        if any(item.path.endswith("service.py") for item in snapshot.files) and any(
            item.path.endswith("database.py") for item in snapshot.files
        ):
            service = next(item for item in snapshot.files if item.path.endswith("service.py"))
            line = next(
                (index for index, value in enumerate(service.content.splitlines(), start=1) if "database" in value.lower()),
                1,
            )
            selected.append(
                Finding(
                    file_path=service.path,
                    line_start=line,
                    line_end=line,
                    severity=Severity.WARNING,
                    category=Category.ARCHITECTURE,
                    title="业务服务与数据访问职责耦合",
                    description="服务层直接持有数据库访问细节，后续替换存储或测试业务逻辑的成本较高。",
                    recommendation="抽取 Repository 或数据访问接口，让服务层依赖抽象而不是具体数据库实现。",
                    confidence=0.83,
                    source_agents=[self.name],
                )
            )
        return [_for_agent(finding, self.name) for finding in selected]


def _for_agent(finding: Finding, agent_name: str, *, soften_sql: bool = False) -> Finding:
    title = finding.title
    description = finding.description
    if soften_sql and "SQL" in title:
        title = "SQL 构造方式需要改进"
        description = "从代码质量和业务可靠性角度看，当前 SQL 构造方式不利于维护，也可能放大输入风险。"
    return replace(finding, title=title, description=description, source_agents=[agent_name], id="")


def build_agents() -> list[DemoAgent]:
    return [SecurityAgent(), QualityAgent(), ArchitectureAgent()]

