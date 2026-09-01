"""Consensus aggregation and transparent scoring for the demo."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from difflib import SequenceMatcher

from ai_reviewer.demo.models import (
    SEVERITY_RANK,
    AgentResult,
    DemoReport,
    Finding,
    ProjectSnapshot,
    ScoreBreakdown,
    Severity,
)

DIMENSION_WEIGHTS = {
    "security": 0.25,
    "quality": 0.25,
    "architecture": 0.20,
    "complexity": 0.15,
    "testing": 0.15,
}
PENALTIES = {
    Severity.CRITICAL: 24.0,
    Severity.WARNING: 10.0,
    Severity.SUGGESTION: 4.0,
    Severity.NITPICK: 1.0,
}


def _similar(left: Finding, right: Finding) -> bool:
    if left.file_path != right.file_path or left.category != right.category:
        return False
    if abs(left.line_start - right.line_start) > 3:
        return False
    if left.line_start == right.line_start:
        return True
    return SequenceMatcher(None, left.title.lower(), right.title.lower()).ratio() >= 0.35


def _clusters(findings: list[Finding]) -> list[list[Finding]]:
    clusters: list[list[Finding]] = []
    for finding in findings:
        for cluster in clusters:
            if any(_similar(finding, existing) for existing in cluster):
                cluster.append(finding)
                break
        else:
            clusters.append([finding])
    return clusters


def consolidate(findings: list[Finding], agent_count: int) -> list[Finding]:
    """Merge findings by file/location/category and calculate consensus metadata."""
    if not findings:
        return []
    consolidated: list[Finding] = []
    for cluster in _clusters(findings):
        representative = max(cluster, key=lambda item: item.confidence)
        agent_names = sorted({agent for item in cluster for agent in item.source_agents})
        severity = max(cluster, key=lambda item: SEVERITY_RANK[item.severity]).severity
        confidence = sum(item.confidence for item in cluster) / len(cluster)
        recommendation = representative.recommendation
        alternatives = sorted(
            {
                item.recommendation
                for item in cluster
                if item.recommendation and item.recommendation != recommendation
            }
        )
        if alternatives:
            recommendation += "；补充建议：" + "；".join(alternatives[:2])
        consensus = len(agent_names) / max(agent_count, 1)
        description = representative.description
        if consensus >= 0.67:
            description += f"（{len(agent_names)} 个 Agent 达成共识，置信度 {confidence:.0%}。）"
        consolidated.append(
            Finding(
                file_path=representative.file_path,
                line_start=representative.line_start,
                line_end=representative.line_end,
                severity=severity,
                category=representative.category,
                title=representative.title,
                description=description,
                recommendation=recommendation,
                confidence=confidence,
                source_agents=agent_names,
            )
        )
    return sorted(
        consolidated,
        key=lambda item: (
            -SEVERITY_RANK[item.severity],
            -len(item.source_agents),
            item.file_path,
            item.line_start,
        ),
    )


def score(findings: list[Finding]) -> ScoreBreakdown:
    penalties: dict[str, float] = defaultdict(float)
    for finding in findings:
        dimension = finding.category.value
        if dimension not in DIMENSION_WEIGHTS:
            dimension = "quality"
        consensus_multiplier = 0.75 + 0.25 * (len(finding.source_agents) / 3)
        penalties[dimension] += PENALTIES[finding.severity] * consensus_multiplier

    dimensions = {
        dimension: round(max(0.0, min(100.0, 100.0 - penalties[dimension])), 1)
        for dimension in DIMENSION_WEIGHTS
    }
    overall = round(
        sum(dimensions[dimension] * weight for dimension, weight in DIMENSION_WEIGHTS.items()),
        1,
    )
    return ScoreBreakdown(
        overall=overall,
        dimensions=dimensions,
        weights=dict(DIMENSION_WEIGHTS),
    )


def build_report(
    snapshot: ProjectSnapshot,
    agent_results: list[AgentResult],
    *,
    mode: str,
    user_request: str | None = None,
    errors: list[str] | None = None,
) -> DemoReport:
    all_findings = [finding for result in agent_results for finding in result.findings]
    consolidated = consolidate(all_findings, len(agent_results))
    score_breakdown = score(consolidated)
    critical = sum(item.severity == Severity.CRITICAL for item in consolidated)
    warning = sum(item.severity == Severity.WARNING for item in consolidated)
    summary = (
        f"项目包含 {snapshot.file_count} 个源文件、{snapshot.total_lines} 行代码；"
        f"三个评审 Agent 聚合后发现 {len(consolidated)} 个独立问题，"
        f"其中严重问题 {critical} 个、警告 {warning} 个，综合评分 {score_breakdown.overall:.1f}/100。"
    )
    return DemoReport(
        project=snapshot,
        agent_results=agent_results,
        findings=consolidated,
        score=score_breakdown,
        summary=summary,
        generated_at=datetime.now(UTC).isoformat(),
        mode=mode,
        user_request=user_request,
        errors=errors or [],
    )
