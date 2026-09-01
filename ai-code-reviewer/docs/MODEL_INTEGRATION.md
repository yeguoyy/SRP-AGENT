# 模型接入与三协议配置

本文说明 `ai-code-reviewer` 当前统一的模型接入方式。实现按接口协议路由，不按厂商创建客户端。

## 1. 支持的三种协议

配置字段是 `llm.protocol`：

| 协议值 | 请求地址 | 适用模型/服务 |
| --- | --- | --- |
| `openai_chat_completions` | `{base_url}/chat/completions` | OpenAI-compatible 网关、DeepSeek、企业模型网关 |
| `openai_responses` | `{base_url}/responses` | 支持 OpenAI Responses 的服务 |
| `anthropic_messages` | `{base_url}/v1/messages` | Anthropic Messages API 或兼容网关 |

DeepSeek 不需要单独的 `DeepSeekClient`。只要服务端提供 OpenAI Chat Completions 兼容接口，就使用 `openai_chat_completions`。

## 2. 推荐配置

从 `config.example.yaml` 复制或参考其内容创建 `config.yaml`。实际密钥放在项目根目录 `.env`：

```yaml
llm:
  protocol: openai_chat_completions
  base_url: https://api.deepseek.com
  api_key_env: DEEPSEEK_API_KEY
  model: deepseek-v4-flash
  timeout_seconds: 120
  max_tokens: 1600
  retries: 2

github:
  token: ${GITHUB_TOKEN}
```

```dotenv
DEEPSEEK_API_KEY=your-api-key
GITHUB_TOKEN=your-github-token
```

### OpenAI Chat Completions

```yaml
llm:
  protocol: openai_chat_completions
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  model: gpt-4o-mini
```

如果使用 DeepSeek 或其他兼容网关，只需要替换 `base_url`、`api_key_env` 和 `model`，不需要修改 Python 代码。

### OpenAI Responses

```yaml
llm:
  protocol: openai_responses
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  model: gpt-4.1
```

客户端发送 `instructions`、`input` 和 `max_output_tokens`，并读取 `output_text` 或 `output[].content[].text`。

### Anthropic Messages

```yaml
llm:
  protocol: anthropic_messages
  base_url: https://api.anthropic.com
  api_key_env: ANTHROPIC_API_KEY
  model: claude-sonnet-5
```

客户端请求 `/v1/messages`，使用 `x-api-key`、`anthropic-version` 和 JSON body。完整 PR 评审在该协议下还保留原有的工具调用、上下文探索和思考配置。

## 3. 配置文件与 `.env` 的职责

- `config.yaml`：本机运行配置，负责协议、地址、模型、超时、token 上限、重试次数和 Agent 行为；该文件已加入 `.gitignore`，不上传密钥或本机配置。`config.example.yaml` 才是提交到仓库的模板。
- `.env`：本机私密配置，负责 API Key、GitHub Token 等密钥；该文件已加入 `.gitignore`，不要提交真实密钥。
- `api_key_env`：告诉程序从哪个环境变量读取当前协议的 Key。
- `--config`：Demo 可以显式指定 YAML 路径；不指定时默认读取项目根目录的 `config.yaml`。
- 命令行参数和显式 PowerShell 环境变量优先于 `.env`。

旧项目仍兼容 `anthropic:` 配置块，以及 `LLM_*`、`AI_REVIEWER_*` 环境变量；新开发统一使用 `llm:`。

## 4. Demo 与完整评审如何共用配置

Demo 通过 `ai_reviewer.demo.llm.create_demo_client()` 路由：

```text
config.yaml
    ↓
config.llm.protocol
    ├─ openai_chat_completions → OpenAICompatibleClient
    ├─ openai_responses        → OpenAIResponsesClient
    └─ anthropic_messages      → AnthropicMessagesClient
```

因此，先在 Demo 中验证协议、URL、模型和响应格式后，完整 `review-pr` / `serve` 也可以读取同一份 `llm:` 配置。扫描、Agent、聚合和报告逻辑不需要为 DeepSeek 再复制一套。

需要注意：本地 Demo 的 `api` 模式只写本地报告；它不会自动发布 GitHub 评论。发布评论属于完整 `review-pr` 或 `serve` 入口。

## 5. 测试命令

```powershell
# 三协议客户端与配置测试
.venv\Scripts\python.exe -m pytest tests\demo\test_llm.py tests\test_config.py -q

# Demo 离线测试
.venv\Scripts\python.exe -m pytest tests\demo -q

# 全量测试
.venv\Scripts\python.exe -m pytest -q
```

不想真实调用模型时，使用 `mock` 或 `rules`：

```powershell
.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode mock

.venv\Scripts\python.exe -m ai_reviewer.demo rules `
  --repo demo\sample_project
```

## 6. 常见错误定位

- **404**：通常是协议和 URL 不匹配，例如把 `/anthropic/chat/completions` 当成 Anthropic Messages 地址；检查 `protocol` 和 `base_url`。
- **401/403**：检查 `api_key_env` 指向的变量是否存在，确认没有把变量名误写成 Key 本身。
- **超时**：先确认模型名和服务商支持的协议，再适当提高 `timeout_seconds`、减少 `max_tokens` 或关闭 DeepSeek 思考模式。
- **响应格式异常**：确认服务端返回的是该协议的标准结构；客户端不会把 Chat Completions、Responses、Messages 三种响应混用解析。
- **`.env` 不生效**：确认文件路径是项目根目录，变量名与 `api_key_env` 完全一致，并重新启动终端进程。
