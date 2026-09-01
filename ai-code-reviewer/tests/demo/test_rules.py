from pathlib import Path

from ai_reviewer.demo.rules import detect_findings
from ai_reviewer.demo.scanner import scan_project


def test_rules_detect_secret_sql_and_dynamic_execution():
    sample = Path(__file__).parents[2] / "demo" / "sample_project"
    findings = detect_findings(scan_project(sample))
    titles = {finding.title for finding in findings}
    assert "检测到疑似硬编码敏感凭据" in titles
    assert "检测到高风险动态执行或 Shell 调用" in titles
    assert "SQL 语句可能使用了不安全的字符串拼接" in titles
