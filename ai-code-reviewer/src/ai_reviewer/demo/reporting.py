"""JSON, Markdown and HTML reporters for the demo output."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from ai_reviewer.demo.models import DemoReport, Finding, enum_value


def write_reports(report: DemoReport, output_dir: str | Path) -> dict[str, Path]:
    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": destination / "review-report.json",
        "markdown": destination / "review-report.md",
        "html": destination / "review-report.html",
    }
    paths["json"].write_text(
        json.dumps(enum_value(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    paths["markdown"].write_text(to_markdown(report), encoding="utf-8")
    paths["html"].write_text(to_html(report), encoding="utf-8")
    return paths


def _severity_label(finding: Finding) -> str:
    return {
        "critical": "严重",
        "warning": "警告",
        "suggestion": "建议",
        "nitpick": "风格",
    }.get(finding.severity.value, finding.severity.value)


def to_markdown(report: DemoReport) -> str:
    lines = [
        "# SRP 智能代码评审报告",
        "",
        f"> 生成时间：{report.generated_at}  | 运行模式：`{report.mode}`",
        "",
        "## 项目概况",
        "",
        f"- 项目路径：`{report.project.root}`",
        f"- 源文件：{report.project.file_count} 个",
        f"- 代码行数：{report.project.total_lines} 行",
        f"- 技术栈：{', '.join(report.project.languages) or '未识别'}",
        f"- 用户请求：{report.user_request or '全面评审'}",
        f"- 是否发现测试：{'是' if report.project.has_tests else '否'}",
        "",
        "## 综合评分",
        "",
        f"### 总分：{report.score.overall:.1f} / 100",
        "",
        "| 维度 | 得分 | 权重 |",
        "|---|---:|---:|",
    ]
    for name, value in report.score.dimensions.items():
        lines.append(f"| {name} | {value:.1f} | {report.score.weights[name]:.0%} |")
    lines += ["", report.summary, "", "## Agent 执行情况", ""]
    for result in report.agent_results:
        fallback = "（已降级）" if result.used_fallback else ""
        lines.append(
            f"- **{result.agent_name}**：{result.summary}{fallback}，耗时 {result.elapsed_ms} ms"
        )
    lines += ["", "## 问题清单", ""]
    if not report.findings:
        lines.append("未发现问题。")
    for index, finding in enumerate(report.findings, start=1):
        agents = ", ".join(finding.source_agents) or "规则检测器"
        lines += [
            f"### {index}. [{_severity_label(finding)}] {finding.title}",
            "",
            f"- 位置：`{finding.file_path}:{finding.line_start}`",
            f"- 类别：`{finding.category.value}`",
            f"- Agent 共识：{len(finding.source_agents)} 个",
            f"- 置信度：{finding.confidence:.0%}",
            f"- 来源：{agents}",
            f"- 描述：{finding.description}",
            f"- 建议：{finding.recommendation}",
            "",
        ]
    if report.errors:
        lines += ["## 降级与错误信息", ""]
        lines.extend(f"- {error}" for error in report.errors)
    return "\n".join(lines) + "\n"


def to_html(report: DemoReport) -> str:
    score_cards = "".join(
        f'<div class="score-card"><span>{escape(name)}</span><strong>{value:.1f}</strong></div>'
        for name, value in report.score.dimensions.items()
    )
    findings = "".join(_finding_html(index, finding) for index, finding in enumerate(report.findings, 1))
    agents = "".join(
        f'<li><b>{escape(result.agent_name)}</b>：{escape(result.summary)} '
        f'<small>{result.elapsed_ms} ms</small></li>'
        for result in report.agent_results
    )
    errors = "" if not report.errors else (
        "<h2>降级与错误信息</h2><ul>"
        + "".join(f"<li>{escape(error)}</li>" for error in report.errors)
        + "</ul>"
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SRP 智能代码评审报告</title>
<style>
:root {{ color-scheme: light; font-family: Inter, "Microsoft YaHei", sans-serif; background:#f4f7fb; color:#172033; }}
body {{ margin:0; }} main {{ max-width:1120px; margin:0 auto; padding:36px 20px 64px; }}
.hero {{ background:linear-gradient(135deg,#14213d,#2e6bff); color:white; border-radius:20px; padding:30px; box-shadow:0 12px 30px #234b9630; }}
.hero h1 {{ margin:0 0 12px; font-size:30px; }} .muted {{ opacity:.78; }}
.overall {{ display:flex; gap:24px; align-items:center; margin-top:18px; }} .overall strong {{ font-size:52px; }}
.grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin:20px 0; }}
.score-card {{ background:white; border-radius:14px; padding:16px; box-shadow:0 4px 14px #1720330d; }}
.score-card span {{ display:block; color:#63708a; font-size:13px; }} .score-card strong {{ display:block; font-size:28px; margin-top:8px; }}
.panel {{ background:white; border-radius:16px; padding:22px; margin-top:20px; box-shadow:0 4px 14px #1720330d; }}
.finding {{ border-left:5px solid #ffb020; padding:14px 16px; background:#fffaf0; margin:12px 0; border-radius:8px; }}
.finding.critical {{ border-color:#e5484d; background:#fff4f4; }} .finding.suggestion,.finding.nitpick {{ border-color:#2e6bff; background:#f4f7ff; }}
.meta {{ color:#63708a; font-size:13px; }} code {{ background:#eef2f8; border-radius:4px; padding:2px 5px; }} li {{ margin:8px 0; }}
@media (max-width:760px) {{ .grid {{ grid-template-columns:repeat(2,1fr); }} .overall {{ align-items:flex-start; flex-direction:column; gap:4px; }} }}
</style></head>
<body><main>
<section class="hero"><h1>SRP 智能代码评审报告</h1><div class="muted">自然语言交互 · 多智能体协作 · 可解释质量评分</div>
<div class="overall"><strong>{report.score.overall:.1f}</strong><div>/ 100<br><span class="muted">{escape(report.summary)}</span></div></div></section>
<div class="grid">{score_cards}</div>
<section class="panel"><h2>项目概况</h2><p>{escape(report.project.root)}</p><p class="meta">{report.project.file_count} 个源文件 · {report.project.total_lines} 行 · {escape(', '.join(report.project.languages) or '未识别')} · {'发现测试文件' if report.project.has_tests else '未发现测试文件'}</p></section>
<section class="panel"><h2>Agent 执行情况</h2><ul>{agents}</ul></section>
<section class="panel"><h2>问题清单（{len(report.findings)}）</h2>{findings or '<p>未发现问题。</p>'}</section>
<section class="panel">{errors}</section>
</main></body></html>"""


def _finding_html(index: int, finding: Finding) -> str:
    severity = finding.severity.value
    agents = "、".join(finding.source_agents) or "规则检测器"
    return f"""<article class="finding {severity}">
<h3>{index}. [{escape(_severity_label(finding))}] {escape(finding.title)}</h3>
<div class="meta"><code>{escape(finding.file_path)}:{finding.line_start}</code> · {escape(finding.category.value)} · Agent 共识 {len(finding.source_agents)} 个 · 置信度 {finding.confidence:.0%}</div>
<p>{escape(finding.description)}</p><p><b>建议：</b>{escape(finding.recommendation)}</p><div class="meta">来源：{escape(agents)}</div>
</article>"""
