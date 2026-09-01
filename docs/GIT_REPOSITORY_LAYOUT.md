# SRP-AGENT 根 Git 仓库说明

## 当前策略

本地目录 `D:\Code\SRP` 是唯一的 Git 仓库根目录，远程 GitHub 仓库名称为 `SRP-AGENT`。本地目录名和远程仓库名可以不同，不需要为了远程改名而重命名本地文件夹。

以下目录原先有独立 Git 元数据：

- `ai-code-reviewer/.git`
- `aacr-bench/.git`
- `aacr-bench/evaluation/repo/vllm-project__vllm/.git`
- `aacr-bench/deliverables/aacr-bench-ppt/tmp-edit/localclone-test/myrepo-src/.git`
- `aacr-bench/deliverables/aacr-bench-ppt/tmp-edit/localclone-test/myrepo-dst/.git`

它们已改名为 `.git.backup`，以避免根仓库把这些目录记录成嵌套仓库。`.git.backup` 不会上传到 GitHub。

## 提交前检查

```powershell
cd D:\Code\SRP
git status
git status --ignored
git diff --check
git ls-files
```

重点确认不提交：`.git.backup/`、`.venv/`、`__pycache__/`、`.env` 和密钥文件、下载的外部仓库和生成结果。

建议提交前使用：

```powershell
git diff --stat
git diff --cached --stat
git diff --cached --check
```

确认暂存区内容无误后再执行 `git commit`；本次整理不自动执行 commit、push 或 pull。
