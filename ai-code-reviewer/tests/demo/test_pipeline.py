from pathlib import Path

from ai_reviewer.demo.models import finding_from_dict
from ai_reviewer.demo.pipeline import _resolve_demo_config, run_from_path
from ai_reviewer.demo.reporting import write_reports
from ai_reviewer.demo.scanner import scan_project


def test_sample_project_scans_and_runs_end_to_end(tmp_path: Path):
    sample = Path(__file__).parents[2] / "demo" / "sample_project"
    snapshot = scan_project(sample)
    assert snapshot.file_count == 4
    assert snapshot.total_lines > 50
    assert not snapshot.has_tests

    report = run_from_path(str(sample), mode="mock")
    titles = {finding.title for finding in report.findings}
    assert any("硬编码" in title for title in titles)
    assert any("复杂度" in title for title in titles)
    assert report.score.overall < 100

    paths = write_reports(report, tmp_path)
    assert all(path.exists() for path in paths.values())
    assert "SRP 智能代码评审报告" in paths["markdown"].read_text(encoding="utf-8")
    assert "<html" in paths["html"].read_text(encoding="utf-8")


def test_model_confidence_accepts_qualitative_and_percentage_values():
    assert finding_from_dict({"confidence": "high"}, "测试 Agent").confidence == 0.9
    assert finding_from_dict({"confidence": "85%"}, "测试 Agent").confidence == 0.85
    assert finding_from_dict({"confidence": "not-a-number"}, "测试 Agent").confidence == 0.65


def test_pipeline_emits_progress_events():
    sample = Path(__file__).parents[2] / "demo" / "sample_project"
    events: list[str] = []

    report = run_from_path(
        str(sample),
        mode="mock",
        progress_callback=lambda event, _data: events.append(event),
    )

    assert report.findings
    assert events[:4] == [
        "scan_start",
        "scan_complete",
        "rules_start",
        "rules_complete",
    ]
    assert events.count("agent_start") == 3
    assert events.count("agent_complete") == 3
    assert events[-2:] == ["aggregation_start", "aggregation_complete"]


def test_demo_api_defaults_to_repository_config(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        """llm:\n  protocol: openai_responses\n  base_url: https://example.test/v1\n  api_key: test-key\n  model: test-model\n""",
        encoding="utf-8",
    )

    config = _resolve_demo_config(
        None,
        base_url=None,
        api_key=None,
        model=None,
        protocol=None,
    )

    assert config.protocol == "openai_responses"
    assert config.base_url == "https://example.test/v1"
    assert config.model == "test-model"


def test_demo_can_select_five_agents():
    from ai_reviewer.demo.agents import build_agents

    agents = build_agents(5)

    assert len(agents) == 5
    assert [agent.name for agent in agents] == [
        "安全评审 Agent",
        "代码质量 Agent",
        "架构与逻辑 Agent",
        "性能评审 Agent",
        "风格与文档 Agent",
    ]
