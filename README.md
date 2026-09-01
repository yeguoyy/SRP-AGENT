# SRP-AGENT：智能代码评审与评测项目

本仓库集中管理 SRP-AGENT 项目的三个主要部分：

1. `ai-code-reviewer`：多智能体 AI 代码评审系统，包含 SRP 可执行 Demo。
2. `aacr-bench`：自动代码评审评测框架，已接入 `ai-reviewer` 适配器。
3. `ai-code-reviewer-original-clean`：改造前的干净基线，用于前后版本对比。

## 项目结构

```text
SRP-AGENT
├── ai-code-reviewer                 # 当前主项目和 Demo
├── aacr-bench                       # AACR-Bench 评测项目
├── ai-code-reviewer-original-clean  # 原始基线
├── docs                             # 方案、论文和 API 参考
└── archive                          # 历史快照和差异补丁
```

## 快速运行 Demo

```powershell
cd D:\Code\SRP-AGENT\ai-code-reviewer
.\.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode mock `
  --question "请优先定位高风险安全问题" `
  --output-dir demo\output
```

也可以使用一键脚本：

```powershell
cd D:\Code\SRP-AGENT\ai-code-reviewer
.\run_demo.ps1 -Repo .\demo\sample_project -Mode mock
```

详细说明：

- `ai-code-reviewer/DEMO_GUIDE.md`
- `ai-code-reviewer/docs/DEMO_ARCHITECTURE.md`
- `ai-code-reviewer/docs/TEAM_WORK_REPORT.md`

## AACR-Bench 评测

AACR-Bench 通过适配器调用 `ai-reviewer`，将评审结果转换为统一格式，并计算 Precision、Recall、F1 和行号匹配指标。

适配器位置：`aacr-bench/evaluation/reviewers/ai_reviewer.py`。

## 文档目录

- `docs/competition/`：比赛方案和项目定位。
- `docs/references/`：论文和 DeepSeek API 兼容性参考资料。
- `docs/GIT_REPOSITORY_LAYOUT.md`：根仓库结构和 Git 管理说明。
- `archive/history/`：历史压缩包和版本差异，不参与运行。

## Git 约定

本目录使用一个根级 Git 仓库管理整个 SRP-AGENT。三个项目原本的 Git 元数据会保留为各自目录下的 `.git.backup`，并被 `.gitignore` 忽略；它们不会作为嵌套仓库上传。
