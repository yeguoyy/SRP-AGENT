# SRP Demo 使用指南

这是面向产业命题赛道的本地可执行原型，围绕“自然语言交互 + 多智能体代码评审 + 可解释质量评分”展示完整闭环。后续 Demo 开发以本目录的实现为基础，模型接入统一读取项目根目录的 `config.yaml`。

## 一键离线运行

在 `D:\Code\SRP\ai-code-reviewer` 项目根目录执行：

```powershell
.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode mock `
  --output-dir demo\output
```

不需要 API Key，也不需要 GitHub 凭据。运行后会生成：

- `demo/output/review-report.json`：机器可读结果
- `demo/output/review-report.md`：适合队内交流的 Markdown 报告
- `demo/output/review-report.html`：适合现场展示的可视化报告

## 本地 Demo 的三种模式

```powershell
# 1. 只运行确定性规则检测：不调用模型
.venv\Scripts\python.exe -m ai_reviewer.demo rules `
  --repo demo\sample_project

# 2. 离线 Mock 多 Agent：不调用外部 API，推荐比赛现场使用
.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode mock

# 3. API 模式：读取 config.yaml，调用选定的模型协议
.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode api `
  --agents 3 `
  --config config.yaml

```

API 模式启动时会读取 `--config` 指定的 YAML；不传 `--config` 时默认查找项目根目录的 `config.yaml`。配置文件负责协议、地址、模型和参数，`.env` 负责密钥，不应把真实密钥写入 YAML：

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

```dotenv
# D:\Code\SRP\ai-code-reviewer\.env
DEEPSEEK_API_KEY=your-api-key
```

## 选择 Demo 评审角色数量

Demo 现在与完整 `ai-code-reviewer` 一样提供五类评审角色。默认仍运行前 3 个角色，以保持原有演示速度；可以通过 `--agents N` 选择前 N 个角色，范围为 1 到 5：

| 顺序 | Demo 角色 | 对应完整系统角色 | 主要关注点 |
| --- | --- | --- | --- |
| 1 | 安全评审 Agent | `security-reviewer` | 凭据、注入、危险调用和安全边界 |
| 2 | 代码质量 Agent | `patterns-reviewer` | 可维护性、代码异味、模式一致性 |
| 3 | 架构与逻辑 Agent | `logic-reviewer` | 模块职责、依赖耦合和业务正确性 |
| 4 | 性能评审 Agent | `performance-reviewer` | 复杂度、性能瓶颈和资源使用 |
| 5 | 风格与文档 Agent | `style-reviewer` | 风格、可读性、文档和测试资产 |

```powershell
# 默认：运行前 3 个角色
.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode mock `
  --agents 3

# 运行全部 5 个角色
.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode api `
  --agents 5 `
  --config config.yaml
```

`--agents` 只影响 `mock` 和 `api` 评审模式；`rules` 模式只运行确定性规则检测，不启动 Agent。API 模式下，选择 5 个角色也会产生 5 次独立模型评审请求，耗时和费用会相应增加。

也可以用命令行临时覆盖连接参数：

```powershell
.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode api `
  --config config.yaml `
  --protocol openai_chat_completions `
  --base-url https://api.deepseek.com `
  --model deepseek-v4-flash
```

## 三协议配置

协议按“接口协议”选择，不按厂商写适配器。DeepSeek 不需要独立客户端，使用 OpenAI Chat Completions 协议即可。

| `llm.protocol` | 典型 `base_url` | `api_key_env` 示例 | 说明 |
| --- | --- | --- | --- |
| `openai_chat_completions` | `https://api.deepseek.com` 或兼容网关 | `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` | 请求 `/chat/completions`；DeepSeek 走这里 |
| `openai_responses` | `https://api.openai.com/v1` | `OPENAI_API_KEY` | 请求 `/responses`；解析 `output_text` |
| `anthropic_messages` | `https://api.anthropic.com` | `ANTHROPIC_API_KEY` | 请求 `/v1/messages`；使用 `x-api-key` 和 Anthropic headers |

完整模板见 `config.example.yaml`。外部三协议适配完成后，Demo 可以直接接入：它通过 `create_demo_client()` 根据 `llm.protocol` 路由到相应客户端，扫描、规则、聚合、评分和报告逻辑不需要改。完整 GitHub 评审也读取同一份 `llm:` 配置。

### 思考模式说明

终端里的“正在分析”只是运行状态提示，不代表程序可以读取或展示模型的隐藏思维过程。`llm.thinking` 仅由支持该字段的适配器处理；对于 DeepSeek v4 的 Chat Completions，可设置 `thinking: disabled` 以减少超时风险。Anthropic 完整 PR 评审的思考开关仍由各 Agent 的 `thinking_enabled` 控制。

## 运行过程提示

模型请求可能持续几十秒，CLI 会显示实时状态和重试信息：

```text
⠋ 正在扫描项目...
✓ 项目扫描完成，发现 4 个文件
✓ 确定性规则检测完成，发现 10 个候选问题
⠋ 安全评审 Agent 正在分析...
✓ 安全评审 Agent 完成，耗时 8.4 秒
⠋ 代码质量 Agent 正在分析...
✓ 代码质量 Agent 完成，耗时 6.1 秒
⠋ 架构与逻辑 Agent 正在分析...
⚠ 架构与逻辑 Agent 请求失败，已降级到离线规则：请求超时
⠋ 正在聚合评审结果...
✓ 评审结果聚合完成，得到 16 个独立问题
✓ 报告生成完成
```

API 请求失败时，Demo 会保留已完成的结果，并将失败 Agent 降级到离线规则；这不等于模型调用成功。若每次都失败，应先检查 `protocol`、`base_url`、`model`、密钥环境变量和服务商是否真的支持对应协议。

## Demo 与完整 GitHub 系统的区别

这里容易把“模式”和“入口”混在一起。准确说法不是五种 `--mode`，而是 **3 种本地 Demo 模式 + 2 个完整 GitHub 系统入口**：

### 本地 Demo 的 3 种模式

| 模式 | 作用 | 调用模型 | 发布 GitHub 评论 |
| --- | --- | --- | --- |
| `mock` | 离线模拟多智能体评审 | 否 | 否 |
| `rules` | 确定性规则检测 | 否 | 否 |
| `api` | 调用 `config.yaml` 选定的三协议之一 | 是，可失败降级 | 否 |

本地 Demo 的输入是本地项目目录，输出是本地 JSON、Markdown 和 HTML 报告。当前没有 `--mode github`，所以 Demo 不会自动上传报告或发布 GitHub 评论。

### 完整 GitHub 系统的 2 个入口

| 入口 | 作用 | 是否可以发布 GitHub 评论 |
| --- | --- | --- |
| `review-pr` | 读取指定 GitHub Pull Request，完成完整 AI 评审 | 是，默认发布路径 |
| `serve` | 接收 GitHub PR Webhook 并触发评审 | 是，需要配置 Webhook、Token 和模型 Key |

```powershell
# 手动评审 GitHub PR
.venv\Scripts\ai-reviewer.exe review-pr owner/repo 123

# 启动 Webhook 服务
.venv\Scripts\ai-reviewer.exe serve
```

因此：**五个是产品入口/运行方式的总数，不是五种 Demo 模式**。本地 Demo 三种模式均不发布 GitHub 评论；只有 `review-pr` 和 `serve` 才进入 GitHub 输出链路。

## 现场演示建议

1. 展示 `demo/sample_project` 中故意植入的硬编码密钥、动态执行、SQL 拼接和复杂业务函数。
2. 运行 Mock 多 Agent，说明安全、质量、架构三个 Agent 分别工作。
3. 打开 `review-report.html`，展示总体评分、维度评分、问题位置、Agent 共识和修复建议。
4. 追问“为什么这个问题是高风险”，结合 Markdown/JSON 中的解释说明可追溯性。
5. 修复示例代码后再次运行，展示评分变化，形成“发现—解释—修复—验证”闭环。

## 相关文档

- `config.example.yaml`：三协议配置模板
- `.env.example`：密钥和本地环境变量模板
- `docs/MODEL_INTEGRATION.md`：模型协议、配置优先级和排错说明
- `docs/TEAM_WORK_REPORT.md`：队内工作报告、目录结构和 AACR-Bench 接入说明
- `docs/DEMO_ARCHITECTURE.md`：Demo 结构说明
