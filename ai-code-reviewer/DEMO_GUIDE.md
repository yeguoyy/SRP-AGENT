# SRP Demo 使用指南

这是面向产业命题赛道的本地可执行原型，围绕“自然语言交互 + 多智能体代码评审 + 可解释质量评分”展示完整闭环。

## 一键离线运行

在项目根目录 `ai-code-reviewer` 中执行：

```powershell
.venv\Scripts\python.exe -m ai_reviewer.demo --repo demo\sample_project --mode mock --output-dir demo\output
```

不需要 API Key，也不需要 GitHub 凭据。运行后会生成：

- `demo/output/review-report.json`：机器可读结果
- `demo/output/review-report.md`：适合材料整理的 Markdown 报告
- `demo/output/review-report.html`：适合现场展示的可视化报告

## 三种运行模式

```powershell
# 只运行确定性规则检测
.venv\Scripts\python.exe -m ai_reviewer.demo rules --repo demo\sample_project

# 离线 Mock 多 Agent（推荐比赛现场）
.venv\Scripts\python.exe -m ai_reviewer.demo --repo demo\sample_project --mode mock

# 接入 OpenAI 兼容接口（DeepSeek、企业网关等）
$env:LLM_BASE_URL="https://your-endpoint/v1"
$env:LLM_API_KEY="your-api-key"
$env:LLM_MODEL="your-model"
.venv\Scripts\python.exe -m ai_reviewer.demo --repo demo\sample_project --mode api
```

API 模式请求失败时，系统会自动回退到离线检测，不会让演示直接崩溃。

模型接入的完整说明（包括 OpenAI-compatible 与 Anthropic Messages API 的区别、AACR-Bench 配置和排错方法）见：`D:\Code\SRP\docs\MODEL_INTEGRATION.md`。

## 现场演示建议

1. 先展示 `demo/sample_project` 中故意植入的硬编码密钥、动态执行、SQL 拼接和复杂业务函数。
2. 运行 Mock 多 Agent，说明安全、质量、架构三个 Agent 分别工作。
3. 打开 `review-report.html`，展示总体评分、维度评分、问题位置、Agent 共识和修复建议。
4. 追问“为什么这个问题是高风险”，结合 Markdown/JSON 中的解释说明可追溯性。
5. 修复示例代码后再次运行，展示评分变化，形成“发现—解释—修复—验证”闭环。

## 当前 Demo 与生产系统的边界

当前版本优先证明比赛所需的技术闭环，输入采用本地项目，输出采用本地报告。GitHub PR、Webhook、自动修复、讯飞平台适配和数据库持久化属于后续扩展，不影响离线 Demo 运行。
