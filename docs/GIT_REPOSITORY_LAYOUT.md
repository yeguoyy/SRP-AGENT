# SRP-AGENT 根 Git 仓库说明

## 当前策略

`D:\Code\SRP-AGENT-AGENT` 是唯一的 Git 仓库根目录，统一管理三个保留项目和配套文档。

以下目录原先有独立 Git 元数据：

- `ai-code-reviewer/.git`
- `aacr-bench/.git`
- `aacr-bench/evaluation/repo/vllm-project__vllm/.git`
- `aacr-bench/deliverables/aacr-bench-ppt/tmp-edit/localclone-test/myrepo-src/.git`
- `aacr-bench/deliverables/aacr-bench-ppt/tmp-edit/localclone-test/myrepo-dst/.git`

它们已改名为 `.git.backup`，以避免根仓库把这些目录记录成嵌套仓库。`.git.backup` 不会上传到 GitHub。

## 提交前检查

```powershell
cd D:\Code\SRP-AGENT-AGENT
git status
git status --ignored
git ls-files
```

重点确认不提交：`.git.backup/`、`.venv/`、`__pycache__/`、`.env` 和密钥文件、下载的外部仓库和生成结果。
