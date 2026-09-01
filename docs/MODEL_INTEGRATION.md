# 模型接入说明

本文说明本地工作区 `D:\Code\SRP` 中的 Demo、`ai-code-reviewer` 主程序和 AACR-Bench 如何共用模型配置。

> 本地目录保持为 `D:\Code\SRP`，GitHub 远程仓库名称为 `SRP-AGENT`。不要因为远程仓库改名而修改本地目录名。

## 一、统一配置原则

当前模型配置以 `ai-code-reviewer/config.yaml` 中的 `llm:` 为准：

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

配置文件负责协议、地址、模型和请求参数；密钥放在 `ai-code-reviewer/.env`：

```dotenv
DEEPSEEK_API_KEY=your-api-key
OPENAI_API_KEY=your-api-key
ANTHROPIC_API_KEY=your-api-key
GITHUB_TOKEN=your-github-token
```

实际使用哪个密钥，由 `llm.api_key_env` 指定。不要把真实密钥写入 YAML、Markdown 或 Git。

## 二、支持的三种协议

协议按服务端接口格式划分，不按厂商划分：

| 配置值 | 请求路径 | 典型服务 |
|---|---|---|
| `openai_chat_completions` | `{base_url}/chat/completions` | OpenAI 兼容网关、DeepSeek、企业模型网关 |
| `openai_responses` | `{base_url}/responses` | OpenAI Responses 兼容服务 |
| `anthropic_messages` | `{base_url}/v1/messages` | Anthropic Messages API 或兼容网关 |

DeepSeek 如果提供 OpenAI 兼容接口，直接使用 `openai_chat_completions`，不需要单独的 DeepSeek 客户端。

## 三、Demo 使用方式

进入 Demo 项目目录：

```powershell
cd D:\Code\SRP\ai-code-reviewer
```

### 1. 离线验证

```powershell
# 确定性规则：不启动 Agent
.\.venv\Scripts\python.exe -m ai_reviewer.demo rules `
  --repo demo\sample_project

# Mock 多角色：不调用外部 API
.\.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode mock `
  --agents 5
```

### 2. API 模式

```powershell
.\.venv\Scripts\python.exe -m ai_reviewer.demo `
  --repo demo\sample_project `
  --mode api `
  --agents 5 `
  --config config.yaml
```

不传 `--config` 时，Demo 默认读取当前项目根目录的 `config.yaml`。也可以用 `--protocol`、`--base-url`、`--model` 临时覆盖 YAML 配置；API Key 建议仍放在 `.env`。

Demo 有五个评审角色，`--agents N` 启用前 N 个角色，范围为 1 到 5，默认值为 3。API 模式下启用 N 个角色会产生 N 次独立模型请求；`rules` 模式不启动 Agent，因此不受该参数影响。

## 四、三个组件的调用链

```text
config.yaml
    |
    +-- openai_chat_completions --> Demo / 主程序的 OpenAI 兼容客户端
    +-- openai_responses        --> Demo / 主程序的 Responses 客户端
    +-- anthropic_messages      --> Anthropic Messages 客户端
                                      |
                                      v
                              统一评审结果结构
                                      |
                         +------------+------------+
                         v                         v
                    本地 Demo 报告              GitHub/AACR 输出
```

- **Demo**：扫描本地项目，运行规则和选定的评审角色，输出 JSON、Markdown、HTML；本地 Demo 不自动发布 GitHub 评论。
- **`ai-reviewer` 主程序**：复用统一 `llm:` 配置，服务于 PR、本地 diff 和 Webhook 评审；是否发布 GitHub 评论由对应入口决定。
- **AACR-Bench**：通过 `aacr-bench/evaluation/reviewers/ai_reviewer.py` 调用 `ai-reviewer`，不单独复制一套模型客户端。

## 五、配置文件职责

- `ai-code-reviewer/config.yaml`：本机运行配置，已加入 `.gitignore`；
- `ai-code-reviewer/config.example.yaml`：可提交的配置模板；
- `ai-code-reviewer/.env`：本机密钥，已加入 `.gitignore`；
- `ai-code-reviewer/.env.example`：密钥变量名示例，不包含真实值；
- `llm.api_key_env`：指定从哪个环境变量读取当前协议的 Key。

旧版 `anthropic:` 配置块及 `LLM_*`、`AI_REVIEWER_*` 环境变量仍保留兼容逻辑，但新开发统一使用 `llm:` + `.env`。

## 六、测试顺序

```powershell
cd D:\Code\SRP\ai-code-reviewer

# 配置和三协议客户端测试
.\.venv\Scripts\python.exe -m pytest tests\demo\test_llm.py tests\test_config.py -q

# Demo 测试
.\.venv\Scripts\python.exe -m pytest tests\demo -q

# 全量测试
.\.venv\Scripts\python.exe -m pytest -q
```

不接真实模型时使用 `mock` 或 `rules`。API 模式出现 404 时，优先检查 `protocol` 和 `base_url` 是否匹配；出现 401/403 时检查 `api_key_env` 指向的环境变量；出现超时时可适当提高 `timeout_seconds`、减少 `max_tokens` 或关闭思考模式。

## 七、相关文件

- `ai-code-reviewer/DEMO_GUIDE.md`：Demo 使用指南；
- `ai-code-reviewer/docs/MODEL_INTEGRATION.md`：主项目内的详细模型协议说明；
- `ai-code-reviewer/config.example.yaml`：统一配置模板；
- `ai-code-reviewer/.env.example`：密钥变量名模板；
- `ai-code-reviewer/src/ai_reviewer/demo/llm.py`：Demo 协议客户端；
- `ai-code-reviewer/src/ai_reviewer/agents/protocol_client.py`：主程序 OpenAI 协议客户端；
- `ai-code-reviewer/src/ai_reviewer/agents/anthropic_client.py`：主程序 Anthropic 客户端；
- `aacr-bench/evaluation/reviewers/ai_reviewer.py`：AACR-Bench 适配器。
