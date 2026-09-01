# SRP-AGENT：智能代码评审与评测项目

本地工作区目录为 `D:\Code\SRP`，GitHub 远程仓库名称为 `SRP-AGENT`。本仓库集中管理以下主要部分：

1. `ai-code-reviewer`：多智能体 AI 代码评审系统，包含可执行的 SRP Demo；
2. `aacr-bench`：自动代码评审评测框架，已接入 `ai-reviewer` 适配器；
3. `ai-code-reviewer-original-clean`：改造前的干净基线，用于前后版本对比。

## 项目结构

```text
D:\Code\SRP
├── ai-code-reviewer                 # 当前主项目和 Demo
├── aacr-bench                       # AACR-Bench 评测项目
├── ai-code-reviewer-original-clean  # 原始基线
├── docs                             # 方案、论文和 API 参考
└── archive                          # 历史快照和差异补丁
```

## 快速运行 Demo

```powershell
cd D:\Code\SRP\ai-code-reviewer
.\.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode mock `
  --agents 3 `
  --question "请优先定位高风险安全问题" `
  --output-dir demo\output
```

Demo 支持三种本地模式：

- `rules`：只运行确定性规则检测，不调用模型；
- `mock`：使用离线 Mock Agent，不需要 API Key；
- `api`：读取项目根目录 `config.yaml`，通过三协议适配器调用模型。

Demo 有五个评审角色，可用 `--agents 1` 到 `--agents 5` 选择前 N 个角色；默认运行 3 个角色。

也可以使用一键脚本：

```powershell
cd D:\Code\SRP\ai-code-reviewer
.\run_demo.ps1 -Repo .\demo\sample_project -Mode mock
```

详细说明：

- `ai-code-reviewer/DEMO_GUIDE.md`：Demo 使用指南；
- `ai-code-reviewer/docs/DEMO_ARCHITECTURE.md`：Demo 架构和五角色说明；
- `ai-code-reviewer/docs/TEAM_WORK_REPORT.md`：队内阶段性工作报告；
- `ai-code-reviewer/docs/MODEL_INTEGRATION.md`：三种模型协议、配置和测试步骤；
- `docs/MODEL_INTEGRATION.md`：根仓库中 Demo、主程序和 AACR-Bench 的整体接入关系。

## 模型协议

系统按接口协议路由，而不是按厂商写独立适配器：

- `openai_chat_completions`：`/chat/completions`，适用于 OpenAI 兼容服务和 DeepSeek；
- `openai_responses`：`/responses`，适用于 OpenAI Responses 兼容服务；
- `anthropic_messages`：`/v1/messages`，适用于 Anthropic Messages 及兼容网关。

协议、地址、模型和运行参数写在 `ai-code-reviewer/config.yaml`；API Key 和 GitHub Token 放在本机 `.env`，真实密钥不提交到 Git。

## AACR-Bench 评测

AACR-Bench 通过适配器调用 `ai-reviewer`，将评审结果转换为统一格式，并计算 Precision、Recall、F1 和行号匹配指标。

适配器位置：`aacr-bench/evaluation/reviewers/ai_reviewer.py`。

## 文档目录

- `docs/competition/`：比赛方案和项目定位；
- `docs/references/`：论文和 API 兼容性参考资料；
- `docs/GIT_REPOSITORY_LAYOUT.md`：根仓库结构和 Git 管理说明；
- `archive/history/`：历史压缩包和版本差异，不参与运行。

## Git 约定

本地目录 `D:\Code\SRP` 使用一个根级 Git 仓库管理整个项目，远程仓库对应 GitHub 的 `SRP-AGENT`。各子项目原有的 Git 元数据已保留为各自目录下的 `.git.backup`，并被 `.gitignore` 忽略；它们不会作为嵌套仓库上传。
