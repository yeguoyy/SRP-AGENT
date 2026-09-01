from pathlib import Path

from ai_reviewer.demo.pipeline import run_from_path
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
