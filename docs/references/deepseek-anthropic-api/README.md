# DeepSeek Anthropic API 参考资料

这些文件是项目早期为适配 Anthropic Messages API 而保存的 DeepSeek 文档资料，不是程序运行时依赖。

- `deepseek_anthropic_doc.txt`：较完整的文档保存版本。
- `raw/doc_*.txt`：从同一文档或网页拆分出的字段说明片段，文件名是历史导入编号。

代码真正使用的配置和调用逻辑位于：

- `ai-code-reviewer/src/ai_reviewer/config.py`
- `ai-code-reviewer/src/ai_reviewer/agents/anthropic_client.py`
