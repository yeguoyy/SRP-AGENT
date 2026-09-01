# SRP 项目阶段性工作报告

> 用途：队内交流、环境交接、Demo 演示和后续开发排期
>
> 日期：2026 年 9 月 1 日
>
> 当前主项目：`D:\Code\SRP\ai-code-reviewer`
> 模型接入详见：`D:\Code\SRP\ai-code-reviewer\docs\MODEL_INTEGRATION.md`

---

## 一、结论摘要

本阶段不是重新开发一个全新的代码评审系统，而是在开源项目 `ai-code-reviewer` 的基础上完成三件事：

1. **保留原项目能力**：GitHub PR / 本地代码评审、多 Agent 并行评审、问题聚合、Markdown/GitHub 输出等。
2. **完成 SRP 比赛 Demo**：增加一个不依赖外部服务即可运行的本地闭环，用于展示“自然语言交互 + 多智能体代码评审 + 可解释评分”。
3. **把 ai-code-reviewer 接入 AACR-Bench**：让 AACR-Bench 能把 `ai-reviewer` 当作一种标准评审器，跑 AACR 数据集并计算 Precision、Recall、F1、行号匹配等指标。

当前可运行的核心 Demo 位于：

```text
D:\Code\SRP\ai-code-reviewer
```

AACR-Bench 评测框架位于：

```text
D:\Code\SRP\aacr-bench
```

两者是**独立项目**。AACR-Bench 不是被复制进 ai-code-reviewer，而是通过命令行调用 `ai-reviewer`，再把输出转换为 AACR 的统一格式。

---

## 二、相较原始 ai-code-reviewer 的改变

这里的“原始版本”指：

```text
D:\Code\SRP\ai-code-reviewer-original-clean
```

该目录与当前主项目的 Git 基线都对应 `a065f22`，因此适合作为改造前对照。

### 1. 新增 SRP 本地 Demo，不破坏原有评审主链路

新增目录：

```text
D:\Code\SRP\ai-code-reviewer\src\ai_reviewer\demo
```

新增能力：

```text
本地项目扫描
→ 静态规则检测
→ 安全 Agent
→ 代码质量 Agent
→ 架构与逻辑 Agent
→ 性能评审 Agent
→ 风格与文档 Agent
→ 问题去重与 Agent 共识
→ 多维度评分
→ JSON / Markdown / HTML 报告
```

这个 Demo 使用独立模块实现，暂时不修改原项目的 GitHub PR 评审主流程，因此可以同时满足：

- 比赛现场离线演示；
- 原 ai-code-reviewer 的工程能力保留；
- 后续逐步把 Demo 能力合并到生产级 Web / GitHub 工作流。

### 2. 增加五类 Demo 组件

| 文件 | 作用 |
|---|---|
| `scanner.py` | 扫描本地项目，统计文件、语言、函数、类、复杂度和测试文件情况 |
| `rules.py` | 检测硬编码凭据、动态执行、SQL 拼接、TODO、复杂函数、缺少测试等问题 |
| `agents.py` | 提供安全、质量、架构、性能、风格与文档五个 Demo Agent；API 模式下也可调用真实模型 |
| `aggregation.py` | 对多个 Agent 的结果做聚合、去重、共识判断和评分 |
| `reporting.py` | 输出 JSON、Markdown、HTML 三种报告 |
| `cli.py` | 提供 `scan`、`rules`、`mock`、`api` 等命令行入口 |

### 3. 增加配置兼容能力

修改：

```text
D:\Code\SRP\ai-code-reviewer\src\ai_reviewer\config.py
```

主要改变：

- 配置文件明确使用 UTF-8，解决 Windows 中文环境默认 GBK 读取 YAML 失败的问题；
- 增加 `AI_REVIEWER_*` 环境变量命名空间；
- 同时兼容原有的 `ANTHROPIC_*` 环境变量；
- 支持统一配置默认模型：`AI_REVIEWER_MODEL`；
- 支持按 Agent 角色配置模型，例如：
  - `AI_REVIEWER_MODEL_SECURITY`
  - `AI_REVIEWER_MODEL_LOGIC`
  - `AI_REVIEWER_MODEL_PATTERNS`
  - `AI_REVIEWER_MODEL_PERFORMANCE`
  - `AI_REVIEWER_MODEL_STYLE`
- 默认 Agent 顺序调整为：

```text
security → logic → patterns → performance → style
```

Demo 命令行的 `--agents N` 决定启用前 N 个 Agent，范围为 1-5，默认仍使用 3 个；完整系统的 `--agents N` 也继续保留。

### 4. 适配新版 Anthropic SDK 参数行为

修改：

```text
D:\Code\SRP\ai-code-reviewer\src\ai_reviewer\agents\anthropic_client.py
```

新版 Anthropic SDK 的生成方法不再直接接受部分 `temperature` 参数。当前代码将相关参数放进 `extra_body`，保持与新版 SDK 及 Anthropic 兼容网关的适配能力。

### 5. 增加测试和文档

新增：

```text
D:\Code\SRP\ai-code-reviewer\tests\demo
D:\Code\SRP\ai-code-reviewer\DEMO_GUIDE.md
D:\Code\SRP\ai-code-reviewer\docs\DEMO_ARCHITECTURE.md
D:\Code\SRP\ai-code-reviewer\run_demo.ps1
```

并更新：

```text
D:\Code\SRP\ai-code-reviewer\tests\test_config.py
D:\Code\SRP\ai-code-reviewer\uv.lock
D:\Code\SRP\ai-code-reviewer\.gitignore
```

---

## 三、当前 ai-code-reviewer 文件结构

### 1. 核心生产代码

```text
D:\Code\SRP\ai-code-reviewer\src\ai_reviewer
├─ agents
│  ├─ base.py                 # Agent 抽象和公共逻辑
│  ├─ security.py             # 安全评审 Agent
│  ├─ performance.py          # 性能评审 Agent
│  ├─ patterns.py             # 模式/规范评审 Agent
│  └─ anthropic_client.py     # Anthropic API 客户端
├─ context
│  ├─ builder.py              # 构建模型上下文和提示词
│  ├─ local_source.py         # 本地代码上下文
│  ├─ pr_checkout.py           # PR 仓库准备
│  └─ neighbors.py             # 邻近代码上下文
├─ github
│  ├─ client.py                # GitHub API
│  ├─ formatter.py             # GitHub 评论格式化
│  ├─ publish.py               # 结果发布
│  ├─ task_queue.py            # 任务队列
│  └─ webhook.py               # Webhook 入口
├─ orchestrator
│  ├─ orchestrator.py          # Agent 并发编排和重试
│  └─ aggregator.py            # 多 Agent 结果聚合
├─ models
│  ├─ findings.py              # Finding 数据模型
│  ├─ review.py                # Review 数据模型
│  └─ context.py               # 上下文数据模型
├─ security
│  └─ scanner.py               # 安全预扫描
├─ tools
│  └─ repo_tools.py            # Agent 使用的仓库工具
├─ validation
│  └─ fix_check.py             # 修复结果验证
├─ docs                       # 文档分析和自动更新
├─ review.py                  # 本地/PR 评审主逻辑
├─ cli.py                     # `ai-reviewer` 命令行入口
├─ config.py                  # 配置加载
└─ session.py                 # 评审会话管理
```

### 2. SRP Demo 代码

```text
D:\Code\SRP\ai-code-reviewer\src\ai_reviewer\demo
├─ __init__.py
├─ __main__.py
├─ models.py                  # Demo 数据模型
├─ scanner.py                 # 项目扫描
├─ rules.py                   # 规则检测
├─ agents.py                  # Demo Agent
├─ llm.py                     # OpenAI-compatible API 客户端
├─ aggregation.py             # 聚合、去重、评分
├─ pipeline.py                # Demo 流程
├─ reporting.py               # JSON/Markdown/HTML 报告
└─ cli.py                     # CLI
```

### 3. 示例项目和输出

```text
D:\Code\SRP\ai-code-reviewer\demo
├─ sample_project
│  ├─ auth.py
│  ├─ config.py
│  ├─ database.py
│  └─ service.py
├─ config.api.example.yaml
└─ output
   ├─ .gitkeep
   ├─ review-report.json
   ├─ review-report.md
   └─ review-report.html
```

`sample_project` 是故意包含问题的演示项目，不是生产代码。

---

## 四、Demo 使用方式

### 1. 离线 Mock 模式，推荐比赛现场使用

```powershell
cd D:\Code\SRP\ai-code-reviewer

.\.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode mock `
  --question "请优先定位高风险安全问题" `
  --output-dir demo\output
```

或者：

```powershell
.\run_demo.ps1 `
  -Repo .\demo\sample_project `
  -Mode mock `
  -Question "请优先定位高风险安全问题"
```

当前一次运行结果：

```text
文件：4 个
代码：96 行
独立问题：10 个
综合评分：70.5 / 100
```

报告文件：

```text
D:\Code\SRP\ai-code-reviewer\demo\output\review-report.json
D:\Code\SRP\ai-code-reviewer\demo\output\review-report.md
D:\Code\SRP\ai-code-reviewer\demo\output\review-report.html
```

### 2. 只运行规则检测

```powershell
.\.venv\Scripts\python.exe -m ai_reviewer.demo rules `
  --repo demo\sample_project
```

### 3. 输出项目扫描结果

```powershell
.\.venv\Scripts\python.exe -m ai_reviewer.demo scan `
  --repo demo\sample_project
```

### 4. 使用真实模型 API

Demo 与完整评审现在统一读取项目根目录的 `config.yaml`，通过 `llm.protocol` 选择三种协议之一：

- `openai_chat_completions`：OpenAI-compatible 网关和 DeepSeek 使用此协议；
- `openai_responses`：OpenAI Responses 接口；
- `anthropic_messages`：Anthropic Messages 接口。

DeepSeek 不需要单独适配器，只需要把 `base_url`、`api_key_env` 和 `model` 配置为 DeepSeek 服务的信息。推荐配置：

```yaml
llm:
  protocol: openai_chat_completions
  base_url: https://api.deepseek.com
  api_key_env: DEEPSEEK_API_KEY
  model: deepseek-v4-flash
  timeout_seconds: 120
  max_tokens: 1600
  retries: 2
```

密钥放在项目根目录 `.env`：

```dotenv
DEEPSEEK_API_KEY=your-api-key
GITHUB_TOKEN=your-github-token
```

然后运行：

```powershell
.\.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode api `
  --config config.yaml `
  --output-dir demo\output
```

`.env` 不应提交到 Git；可参考 `.env.example`。显式 PowerShell 环境变量和命令行参数优先于 `.env`。配置职责是：YAML 保存共享协议/地址/模型/行为，`.env` 保存密钥。

先用 Demo 验证协议后，完整 `review-pr` / `serve` 也会读取同一份 `llm:` 配置。Demo 的 `api` 模式只生成本地报告，不发布 GitHub 评论；GitHub 评论仍只由完整入口负责。详细说明见 `docs/MODEL_INTEGRATION.md`。

---

## 五、AACR-Bench 是什么，以及如何接上 ai-code-reviewer

### 1. AACR-Bench 的角色

AACR-Bench 不是业务应用，而是代码评审能力的评测框架和数据集。它提供：

- PR 数据集；
- base/head commit；
- 参考人工评审评论；
- 标准化评审运行流程；
- 行号匹配、语义匹配、Precision、Recall、F1 等指标。

目录：

```text
D:\Code\SRP\aacr-bench
```

### 2. 连接方式：适配器 + CLI 子进程

AACR 没有直接 import `ai_reviewer` 的 Python 包，而是通过新增适配器：

```text
D:\Code\SRP\aacr-bench\evaluation\reviewers\ai_reviewer.py
```

调用当前项目安装出来的命令：

```text
ai-reviewer
```

完整链路如下：

```text
AACR 数据集样本
  ↓
prepare_repo()
  ↓
clone/checkout 到 head_commit
  ↓
计算 base...HEAD diff
  ↓
调用：ai-reviewer review --base <base> --output json --agents N
  ↓
捕获 stdout/stderr
  ↓
提取 JSON envelope
  ↓
保存 AACR 结果文件
  ↓
把 findings 转换成标准评论
  ↓
与 reference_comments 匹配
  ↓
输出 Precision / Recall / F1
```

### 3. AACR 调用命令

适配器实际执行的核心命令类似：

```powershell
ai-reviewer review `
  --base <base_commit> `
  --output json `
  --agents 3
```

其中：

- 仓库已经 checkout 到 `head_commit`；
- `--base <base_commit>` 让 ai-reviewer 评审 `base...HEAD`；
- `--output json` 让结果可以被程序解析；
- `--agents 3` 控制启用的 Agent 数量。

### 4. 结果如何转换

`ai-code-reviewer` 的 Finding 大致包含：

```json
{
  "file_path": "src/example.py",
  "line_start": 20,
  "line_end": 21,
  "severity": "warning",
  "category": "security",
  "title": "问题标题",
  "description": "问题描述"
}
```

AACR 适配器转换为统一评论：

```json
{
  "note": "问题标题\n问题描述",
  "path": "src/example.py",
  "side": "right",
  "from_line": 20,
  "to_line": 21
}
```

然后 AACR 的 `evaluate.py` 使用 `review_output[]` 与数据集中的人工参考评论进行比较。

### 5. AACR 结果目录

结果目录采用 run 机制：

```text
D:\Code\SRP\aacr-bench\evaluation\results\aacr_bench\ai-reviewer\<run_id>
```

指标目录：

```text
D:\Code\SRP\aacr-bench\evaluation\metrics\aacr_bench\ai-reviewer\<run_id>
```

这样可以保留 `baseline`、`deepseek`、`spark` 等多次实验，避免结果互相覆盖。

---

## 六、AACR 的使用和测试方式

### 1. 先确认 ai-reviewer 已安装

```powershell
cd D:\Code\SRP\ai-code-reviewer
.\.venv\Scripts\ai-reviewer.exe --version
```

当前验证结果：

```text
ai-reviewer, version 0.1.1
```

### 2. 配置 AACR 环境变量

进入：

```text
D:\Code\SRP\aacr-bench\evaluation
```

可以复制：

```powershell
Copy-Item .env.example .env
```

主要变量：

```powershell
$env:AI_REVIEWER_COMMAND="D:\Code\SRP\ai-code-reviewer\.venv\Scripts\ai-reviewer.exe"
$env:AI_REVIEWER_API_KEY="your-api-key"
$env:AI_REVIEWER_BASE_URL="https://your-anthropic-compatible-gateway"
$env:AI_REVIEWER_MODEL="your-model"
$env:AI_REVIEWER_AGENTS="3"
```

也可以使用：

```powershell
$env:AI_REVIEWER_CONFIG="D:\Code\SRP\ai-code-reviewer\config.yaml"
```

如果 `config.yaml` 中已经包含 API Key、网关地址和 Agent 配置，可以不再重复设置对应环境变量。

### 3. 只跑 AACR 评审

```powershell
cd D:\Code\SRP\aacr-bench\evaluation

python -m pipeline run `
  --stage review `
  --reviewer ai-reviewer `
  --dataset data\aacr_bench_test5.jsonl `
  --limit 1 `
  --concurrency 1 `
  --run-id srp-ai-reviewer-test
```

### 4. 评审后立即评测

```powershell
python -m pipeline run `
  --stage all `
  --reviewer ai-reviewer `
  --dataset data\aacr_bench_test5.jsonl `
  --limit 1 `
  --concurrency 1 `
  --run-id srp-ai-reviewer-test
```

### 5. 只评测已经生成的结果

```powershell
python -m pipeline run `
  --stage eval `
  --reviewer ai-reviewer `
  --dataset data\aacr_bench_test5.jsonl `
  --run-id srp-ai-reviewer-test
```

### 6. 不调用模型的预览模式

用于先检查数据和仓库准备流程：

```powershell
python -m pipeline run `
  --stage review `
  --reviewer ai-reviewer `
  --dataset data\aacr_bench.jsonl `
  --limit 1 `
  --preview
```

预览模式不会真正调用 ai-reviewer 模型，但可能会执行仓库准备、clone 或 checkout。

### 7. 已完成的 AACR 适配器烟测

已验证：

- `evaluation/reviewers/ai_reviewer.py` 可以正常 import；
- `ai-reviewer --version` 可正常返回 `0.1.1`；
- JSON envelope 提取逻辑可以从日志 + JSON 混合 stdout 中提取 findings；
- AACR CLI 已注册 `--reviewer ai-reviewer`；
- `evaluate.py` 已注册 ai-reviewer finding 到标准评论的转换逻辑。

---

## 七、如何测试 SRP Demo

### Demo 专项测试

```powershell
cd D:\Code\SRP\ai-code-reviewer
.\.venv\Scripts\python.exe -m pytest -q tests\demo --disable-warnings
```

结果：

```text
4 passed
```

### Ruff 检查

```powershell
.\.venv\Scripts\ruff.exe check src\ai_reviewer\demo tests\demo
```

结果：

```text
All checks passed!
```

### API 缺省配置降级测试

```powershell
.\.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode api `
  --output-dir demo\output-api-fallback
```

在未配置 API 时，Demo 会降级到离线规则/Mock 结果，并输出报告，不会因缺少 API Key 直接退出。

### 当前测试状态

三协议改造后，Anthropic 旧客户端的兼容测试已恢复，完整测试不再因为 `temperature` 参数或旧测试 Patch 点失败。当前建议按以下顺序验证：

1. `tests\demo`：Demo 扫描、规则、Mock、API 客户端和进度流程；
2. `tests\test_config.py`：统一 `llm:` 配置、`api_key_env`、协议校验和旧配置兼容；
3. `tests\test_review.py`、`tests\test_anthropic_client.py`：完整 PR 评审主链路与 Anthropic 兼容性；
4. `pytest -q`：最终全量回归。

---

## 八、SRP 目录下多个 ai-code-reviewer 版本说明

### 1. 建议保留

#### `D:\Code\SRP\ai-code-reviewer`

**必须保留。**

这是当前主开发目录，包含：

- 原 ai-code-reviewer 核心代码；
- SRP Demo；
- 当前配置改造；
- 测试和报告。

后续所有开发、演示、提交都以此目录为准。

#### `D:\Code\SRP\aacr-bench`

**如果要做 AACR 评测，则保留。**

它是独立的评测框架，不是 ai-code-reviewer 的重复版本。只有在不再做基准测试时，才可以从运行环境中移除。

### 2. 可选保留

#### `D:\Code\SRP\ai-code-reviewer-original-clean`

**建议暂时保留。**

它是与主项目基线相同的干净版本，用于：

- 查看改造前后差异；
- 出现问题时对比原始代码；
- 形成队内技术说明。

如果已经完成代码审查并且不再需要对比，可以删除。

#### `D:\Code\SRP\ai-code-reviewer-base-2afd063`

**历史版本，可选保留。**

对应较早的上游 commit `2afd063`，主要用于历史复现和版本比较。当前 Demo 不依赖它。

#### `D:\Code\SRP\ai-coder-reviewer-master-Reimplement`

**另一个独立复现/重实现版本，可选保留。**

它不是当前主项目的运行依赖。只有在需要比较“原项目复现”和“重实现路线”时才保留。

### 3. 明确属于重复副本、通常不需要

#### `D:\Code\SRP\base-clean`

这是 `ai-code-reviewer-base-2afd063` 的非 Git 清理副本。当前没有独立运行价值，通常可以删除。

#### `D:\Code\SRP\reimplement-clean`

这是 `ai-coder-reviewer-master-Reimplement` 的非 Git 清理副本。当前没有独立运行价值，通常可以删除。

### 4. 根目录下的历史归档文件

以下文件不是运行依赖：

```text
D:\Code\SRP\archive\history\base.tar
D:\Code\SRP\archive\history\reimplement.tar
D:\Code\SRP\archive\history\reimplement-code.diff
```

建议：

- 需要保留历史备份：移到 `D:\Code\SRP\archive`；
- 不需要回滚/复现：确认后删除；
- 不要把这些压缩包和大补丁加入最终项目提交。

以下内容也主要是资料或分析材料，不参与 Demo 运行：

```text
D:\Code\SRP\docs\references\AACR-Bench：Evaluating Automatic Code Review with Holistic Repository-Level Context.pdf
D:\Code\SRP\docs\competition\比赛融合方案与思路.md
D:\Code\SRP\docs\references\deepseek-anthropic-api\deepseek_anthropic_doc.txt
D:\Code\SRP\docs\references\deepseek-anthropic-api\raw\doc_*.txt
```

其中 `比赛融合方案与思路.md` 可以作为参赛材料保留；其余资料可统一归档。

### 5. AACR-Bench 中的临时文件

以下文件属于运行/调试产物，不建议提交：

```text
D:\Code\SRP\aacr-bench\evaluation\tmp_ai_reviewer_debug.txt
D:\Code\SRP\aacr-bench\imgs\table3.png
```

其中 `tmp_ai_reviewer_debug.txt` 是临时调试输出，应加入忽略规则或在确认不再需要后删除。

---

## 九、推荐的队内目录整理方案

如果要简化工作区，建议最终整理为：

```text
D:\Code\SRP
├─ ai-code-reviewer       # 主项目 + SRP Demo，必须保留
├─ aacr-bench             # AACR 评测框架，需要评测时保留
├─ archive                # 历史版本、压缩包、diff、旧报告
├─ 比赛融合方案与思路.md   # 比赛方案材料
└─ AACR-Bench...pdf        # 论文/资料，可选
```

可归档目录：

```text
ai-code-reviewer-original-clean
ai-code-reviewer-base-2afd063
ai-coder-reviewer-master-Reimplement
base-clean
reimplement-clean
base.tar
reimplement.tar
reimplement-code.diff
```

当前不建议直接删除主项目中已有的未提交改动：

```text
D:\Code\SRP\ai-code-reviewer\src\ai_reviewer\agents\anthropic_client.py
D:\Code\SRP\ai-code-reviewer\src\ai_reviewer\config.py
D:\Code\SRP\ai-code-reviewer\tests\test_config.py
D:\Code\SRP\ai-code-reviewer\uv.lock
```

这些文件是当前改造的一部分。

---

## 十、当前阶段的限制和下一步

当前版本已经完成：

- 离线可执行 Demo；
- 多 Agent 评审结果展示；
- 评分和报告生成；
- API 模式与失败降级；
- AACR-Bench 评审器接入；
- 评审结果转换和指标计算入口。

下一步建议按以下顺序：

1. **增加 Web 页面**：项目目录、自然语言问题、Agent 状态、评分卡片、问题详情和报告下载；
2. **让自然语言请求真正影响路由**：例如“重点检查安全”自动提升安全 Agent 权重；
3. **增加修复前后对比**：修复示例代码，重新评审，展示评分变化；
4. **接入讯飞星火适配器**：保留现有统一 LLM 接口；
5. **使用 AACR-Bench 生成对比数据**：单 Agent、多 Agent、不同模型之间比较 Precision、Recall 和误报率。

---

## 十一、一句话交接结论

> `ai-code-reviewer` 是主产品和 Demo，`aacr-bench` 是外部评测工具；当前通过 `ai-reviewer` CLI + AACR 适配器完成连接。SRP Demo 已经可以离线运行，历史版本目录不参与运行，建议保留主项目和 AACR，其他副本归档或删除。
