# SRP Demo 架构说明

```text
本地项目
   |
   v
ProjectScanner ----> RuleDetector
   |                     |
   +---------------------+----> SecurityAgent
                         +----> QualityAgent
                         +----> ArchitectureAgent
                         +----> PerformanceAgent
                         +----> StyleAndDocumentationAgent
                                      |
                                      v
                          ConsensusAggregator
                                      |
                                      v
                              QualityScorer
                                      |
                    +-----------------+----------------+
                    v                 v                v
                 JSON             Markdown           HTML
```

## 评审角色

Demo 提供五类评审角色。默认运行前 3 个角色，也可以通过命令行 `--agents 1` 到 `--agents 5` 选择启用的角色数量：

1. **SecurityAgent**：敏感信息、注入、危险调用和安全边界；
2. **QualityAgent**：可读性、可维护性、代码异味和测试；
3. **ArchitectureAgent**：模块职责、依赖耦合、业务逻辑和边界情况；
4. **PerformanceAgent**：复杂度、性能瓶颈和资源使用；
5. **StyleAndDocumentationAgent**：编码风格、可读性、注释和文档。

`rules` 模式只运行确定性规则检测，不启动 Agent；`mock` 模式使用离线结果；`api` 模式按照启用的角色数量分别请求模型。

## 模型协议路由

API 模式从项目根目录的 `config.yaml` 读取统一的 `llm:` 配置，根据 `llm.protocol` 选择协议适配器：

```text
config.yaml
    |
    +-- openai_chat_completions --> /chat/completions
    +-- openai_responses        --> /responses
    +-- anthropic_messages      --> /v1/messages
```

协议按接口格式划分，不按厂商划分。DeepSeek 等提供 OpenAI 兼容接口的服务直接使用 `openai_chat_completions`，不需要单独实现 DeepSeek 客户端。

## 设计原则

- **默认离线可运行**：规则检测和 Mock Agent 不依赖外部服务。
- **模型可替换**：真实模型通过统一协议适配器接入，业务逻辑不绑定具体厂商 SDK。
- **统一结果结构**：规则检测、Mock 和真实模型最终都转换为 `Finding`。
- **可解释**：每条问题包含文件、行号、类别、严重等级、置信度、来源 Agent 和修复建议。
- **共识聚合**：多个 Agent 在同一文件、同一位置和同一类别的判断会合并，并显示共识数量。
