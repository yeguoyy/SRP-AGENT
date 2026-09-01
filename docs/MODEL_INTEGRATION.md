# 模型接入说明

本文说明 `SRP-AGENT` 中三个相关组件如何连接大模型，以及它们之间的协议区别。

> 本机目录当前保持为 `D:\Code\SRP`，GitHub 仓库名称为 `SRP-AGENT`。文中的命令均按本机目录编写。

## 一、先看整体关系

```text
                    ┌──────────────────────────────┐
                    │        大模型服务 / 网关       │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              │                                         │
   OpenAI Chat Completions 协议                 Anthropic Messages 协议
              │                                         │
              ▼                                         ▼
   SRP Demo API 模式                         ai-code-reviewer 主程序
   LLM_BASE_URL / LLM_API_KEY                AI_REVIEWER_BASE_URL / KEY / MODEL
   /chat/completions                          /messages（由 SDK 调用）
                                                        │
                                                        ▼
                                             AACR-Bench 适配器调用
                                             evaluation/reviewers/ai_reviewer.py
```

项目中存在两条模型调用链，**协议不能混用**：

| 调用链 | 用途 | 协议 | 主要配置 |
|---|---|---|---|
| SRP Demo API 模式 | 比赛演示、快速验证 | OpenAI-compatible Chat Completions | `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` |
| `ai-reviewer` 主程序 | GitHub PR / 本地 diff / AACR-Bench | Anthropic Messages API | `AI_REVIEWER_API_KEY`、`AI_REVIEWER_BASE_URL`、`AI_REVIEWER_MODEL` |

如果模型网关只提供 `/v1/chat/completions`，只能直接接入 Demo API 模式；要接入主程序和 AACR-Bench，网关还必须提供 Anthropic Messages API 兼容层，或者使用支持协议转换的网关。

## 二、接入 SRP Demo 模型

### 1. 方式 A：PowerShell 设置环境变量

进入主项目目录：

```powershell
cd D:\Code\SRP\ai-code-reviewer
```

设置 OpenAI-compatible 接口的三个必要参数：

```powershell
$env:LLM_BASE_URL="https://your-openai-compatible-endpoint/v1"
$env:LLM_API_KEY="your-api-key"
$env:LLM_MODEL="your-model-id"
```

然后运行真实模型模式：

```powershell
.\.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode api `
  --question "请优先定位高风险安全问题" `
  --output-dir demo\output-api
```

`LLM_BASE_URL` 填接口的基础地址即可。程序会自动请求：

```text
{LLM_BASE_URL}/chat/completions
```

如果填写的地址已经以 `/chat/completions` 结尾，程序不会重复拼接。

### 2. 方式 B：使用命令行参数

命令行参数可以替代同名环境变量：

```powershell
.\.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode api `
  --base-url "https://your-openai-compatible-endpoint/v1" `
  --api-key "your-api-key" `
  --model "your-model-id"
```

建议日常使用环境变量，避免把 API Key 写入命令历史；命令行参数适合临时测试。

### 3. 接口返回格式

Demo 会读取 OpenAI-compatible 响应中的：

```json
{
  "choices": [
    {
      "message": {
        "content": "{\"summary\":\"...\",\"findings\":[]}"
      }
    }
  ]
}
```

其中 `message.content` 必须是 JSON，结构如下：

```json
{
  "summary": "本轮评审摘要",
  "findings": [
    {
      "file_path": "auth.py",
      "line_start": 10,
      "line_end": 10,
      "severity": "high",
      "category": "security",
      "title": "问题标题",
      "description": "问题说明",
      "recommendation": "修复建议",
      "confidence": 0.95
    }
  ]
}
```

程序会校验文件路径和行号是否来自被扫描的项目，并将多个 Agent 的结果聚合为 JSON、Markdown 和 HTML 报告。

### 4. Demo 模型接入失败怎么办

Demo 的 API 请求失败时会回退到确定性规则检测，报告仍然会生成，同时在终端输出“降级信息”。可以先用离线模式验证代码链路：

```powershell
.\.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode mock `
  --output-dir demo\output
```

## 三、接入 `ai-code-reviewer` 主程序

主程序使用 Anthropic Messages API，由 `anthropic` SDK 发起请求，适用于：

- `ai-reviewer review-pr owner/repo 123`
- 本地 diff 评审；
- Webhook 服务；
- AACR-Bench 适配器调用。

### 1. 使用环境变量

在 PowerShell 中：

```powershell
cd D:\Code\SRP\ai-code-reviewer

$env:AI_REVIEWER_API_KEY="your-api-key"
$env:AI_REVIEWER_BASE_URL="https://your-anthropic-compatible-gateway"
$env:AI_REVIEWER_MODEL="your-model-id"
$env:AI_REVIEWER_AGENTS="3"
```

其中：

- `AI_REVIEWER_API_KEY`：API Key 或网关 Token；
- `AI_REVIEWER_BASE_URL`：Anthropic Messages API 兼容网关基础地址；
- `AI_REVIEWER_MODEL`：网关实际暴露的模型 ID；
- `AI_REVIEWER_AGENTS`：启用的 Agent 数量，范围为 1–5，默认评测场景使用 3 个。

主程序也兼容旧变量名：

```powershell
$env:ANTHROPIC_API_KEY="your-api-key"
$env:ANTHROPIC_BASE_URL="https://your-anthropic-compatible-gateway"
$env:ANTHROPIC_MODEL="your-model-id"
```

优先使用 `AI_REVIEWER_*`，这样不会和其他工具的 `ANTHROPIC_*` 配置混在一起。

### 2. 使用 `config.yaml`

复制模板：

```powershell
cd D:\Code\SRP\ai-code-reviewer
Copy-Item config.example.yaml config.yaml
```

至少确认以下配置：

```yaml
anthropic:
  api_key: ${AI_REVIEWER_API_KEY}
  base_url: ${AI_REVIEWER_BASE_URL}
  default_model: ${AI_REVIEWER_MODEL}
  timeout_seconds: 600
  max_retries: 3

agents:
  - name: security-reviewer
    model: ${AI_REVIEWER_MODEL}
    focus_areas: [security, authentication]
```

配置文件支持 `${环境变量名}` 展开。不要把真实 API Key 直接提交到 Git；`config.yaml` 已被根目录 `.gitignore` 忽略。

### 3. 为不同 Agent 指定不同模型

如果没有在 YAML 的 `agents[].model` 中显式指定模型，可以按角色设置：

```powershell
$env:AI_REVIEWER_MODEL="general-model"
$env:AI_REVIEWER_MODEL_SECURITY="security-model"
$env:AI_REVIEWER_MODEL_LOGIC="logic-model"
$env:AI_REVIEWER_MODEL_PATTERNS="quality-model"
$env:AI_REVIEWER_MODEL_PERFORMANCE="performance-model"
$env:AI_REVIEWER_MODEL_STYLE="style-model"
```

角色名称取 Agent 名称去掉 `-reviewer` 后缀并转为大写。若 `config.yaml` 中已经写了对应的 `agents[].model`，YAML 配置优先于环境变量。

### 4. 检查配置是否生效

```powershell
.\.venv\Scripts\ai-reviewer.exe config show --config .\config.yaml
```

重点检查：

- API Base URL 是否为 Anthropic 协议网关；
- 模型 ID 是否为网关实际支持的名称；
- 每个 Agent 显示的模型是否符合预期。

## 四、AACR-Bench 如何使用这个模型

AACR-Bench 不直接实现模型请求，而是调用 `ai-reviewer` 可执行文件：

```text
AACR-Bench
  → evaluation/reviewers/ai_reviewer.py
  → ai-reviewer review --base <commit> --output json --agents N
  → Anthropic-compatible gateway
  → JSON review result
  → AACR-Bench metrics
```

### 1. 配置评测环境

```powershell
cd D:\Code\SRP\aacr-bench\evaluation
Copy-Item .env.example .env
```

在 `.env` 中填写 `ai-reviewer` 的配置：

```dotenv
AI_REVIEWER_API_KEY=your-api-key
AI_REVIEWER_BASE_URL=https://your-anthropic-compatible-gateway
AI_REVIEWER_MODEL=your-model-id
AI_REVIEWER_AGENTS=3
AI_REVIEWER_COMMAND=D:/Code/SRP/ai-code-reviewer/.venv/Scripts/ai-reviewer.exe
```

也可以在 PowerShell 中直接设置：

```powershell
$env:AI_REVIEWER_API_KEY="your-api-key"
$env:AI_REVIEWER_BASE_URL="https://your-anthropic-compatible-gateway"
$env:AI_REVIEWER_MODEL="your-model-id"
$env:AI_REVIEWER_AGENTS="3"
$env:AI_REVIEWER_COMMAND="D:\Code\SRP\ai-code-reviewer\.venv\Scripts\ai-reviewer.exe"
```

### 2. 先做预检，再执行一条样本

建议先使用预览模式确认数据集、仓库和命令路径：

```powershell
python -m pipeline run `
  --reviewer ai-reviewer `
  --preview
```

确认无误后再运行真实评测。具体参数以当前 `evaluation` 目录下的 pipeline 帮助为准：

```powershell
python -m pipeline --help
python -m evaluate --help
```

AACR-Bench 的评测结果会保存到 `evaluation/results/` 和 `evaluation/metrics/`，这些运行产物不应提交到 Git。

## 五、测试顺序

### 1. 不接模型：验证 Demo 基础链路

```powershell
cd D:\Code\SRP\ai-code-reviewer
.\.venv\Scripts\python.exe -m pytest tests\demo -q
.\.venv\Scripts\python.exe -m ai_reviewer.demo --repo demo\sample_project --mode mock
```

### 2. 接模型但不跑 AACR：验证 Demo API

```powershell
.\.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode api `
  --output-dir demo\output-api
```

观察终端中的 `模式：api`。如果出现降级信息，优先检查 URL、Key、模型 ID 和返回格式。

### 3. 接主程序：验证 Anthropic 协议

```powershell
.\.venv\Scripts\ai-reviewer.exe config show --config .\config.yaml
.\.venv\Scripts\ai-reviewer.exe --help
```

再选择一个本地测试仓库执行 dry-run 或本地 diff 评审，不要直接对生产仓库执行发布操作。

### 4. 最后接 AACR-Bench

先执行预览，再执行一条样本，最后批量评测。这样可以区分：

- Demo API 配置问题；
- 主程序 Anthropic 协议配置问题；
- AACR-Bench 子进程、仓库 checkout 或指标计算问题。

## 六、常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `未配置 LLM_BASE_URL` | Demo API 模式没有设置地址 | 设置 `LLM_BASE_URL` 或传 `--base-url` |
| `模型请求失败` | URL、Key、网络或模型 ID 错误 | 先用 curl/网关控制台确认接口可用 |
| `模型没有返回合法 JSON` | 模型返回了普通 Markdown 或解释文字 | 保留系统提示，要求只返回 JSON；检查网关是否改变了响应 |
| 主程序 401/404 | 把 OpenAI 地址当成 Anthropic 地址使用 | 更换为 Anthropic Messages API 兼容网关 |
| AACR 找不到 `ai-reviewer` | `AI_REVIEWER_COMMAND` 未设置或路径错误 | 使用绝对路径，确认 `.venv\Scripts\ai-reviewer.exe` 存在 |
| 设置了模型但 Agent 没变化 | YAML 显式写了 `agents[].model` | 删除该字段或直接修改 YAML |
| Key 被提交到 Git | 写进了被跟踪的 Markdown/YAML | 立即撤销 Key，并只使用 `.env`/`config.yaml`；提交前执行 `git diff --cached` |

## 七、安全要求

- 不要把真实 API Key 写进 Markdown、`config.example.yaml`、`.env.example` 或 Git 提交；
- 不要把 `config.yaml`、`.env`、模型响应中的敏感信息上传到 GitHub；
- 评测和 Demo 输出目录仅用于本地验证；
- 使用第三方网关时，确认代码内容、仓库上下文和日志的隐私策略；
- 生产环境建议为不同用途使用不同 Key，并设置额度、超时和重试上限。

## 相关文件

- `D:\Code\SRP\ai-code-reviewer\DEMO_GUIDE.md`：Demo 使用说明；
- `D:\Code\SRP\ai-code-reviewer\demo\config.api.example.yaml`：Demo API 配置示例；
- `D:\Code\SRP\ai-code-reviewer\config.example.yaml`：主程序配置模板；
- `D:\Code\SRP\aacr-bench\evaluation\.env.example`：AACR-Bench 评测环境变量模板；
- `D:\Code\SRP\ai-code-reviewer\src\ai_reviewer\demo\llm.py`：Demo OpenAI-compatible 客户端；
- `D:\Code\SRP\ai-code-reviewer\src\ai_reviewer\agents\anthropic_client.py`：主程序 Anthropic 客户端；
- `D:\Code\SRP\aacr-bench\evaluation\reviewers\ai_reviewer.py`：AACR-Bench 适配器。