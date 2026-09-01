from ai_reviewer.demo.aggregation import consolidate, score
from ai_reviewer.demo.models import Category, Finding, Severity


def _finding(agent: str, title: str = "同一问题") -> Finding:
    return Finding(
        file_path="a.py",
        line_start=3,
        line_end=3,
        severity=Severity.WARNING,
        category=Category.SECURITY,
        title=title,
        description="存在风险",
        recommendation="修复",
        confidence=0.8,
        source_agents=[agent],
    )


def test_consolidate_same_location_reaches_consensus():
    findings = consolidate([_finding("安全评审 Agent"), _finding("代码质量 Agent", "SQL 构造方式需要改进")], 3)
    assert len(findings) == 1
    assert findings[0].source_agents == ["代码质量 Agent", "安全评审 Agent"]
    assert findings[0].confidence == 0.8


def test_score_penalizes_critical_security_finding():
    result = score([_finding("安全评审 Agent")])
    assert result.dimensions["security"] < 100
    assert 0 < result.overall < 100


def test_score_uses_selected_agent_count():
    from ai_reviewer.demo.aggregation import score

    finding = _finding("安全评审 Agent")
    one_agent = score([finding], agent_count=1)
    five_agents = score([finding], agent_count=5)

    assert one_agent.overall < five_agents.overall
