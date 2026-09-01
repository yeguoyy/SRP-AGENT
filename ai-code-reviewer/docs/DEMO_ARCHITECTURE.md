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

## 设计原则

- **默认离线可运行**：规则检测和 Mock Agent 不依赖外部服务。
- **模型可替换**：真实模型通过 OpenAI 兼容 HTTP 接口接入，业务逻辑不绑定具体 SDK。
- **统一结果结构**：规则检测、Mock 和真实模型最终都转换为 `Finding`。
- **可解释**：每条问题包含文件、行号、类别、严重等级、置信度、来源 Agent 和修复建议。
- **共识聚合**：多个 Agent 在同一文件、同一位置和同一类别的判断会合并，并显示共识数量。
