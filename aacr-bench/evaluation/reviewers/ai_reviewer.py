"""AI Code Reviewer（Calimero 多智能体评审器）接入模块。

调用 `ai-reviewer review --base <base> --output json` 评审 base...head 的 diff，
并把结果写成统一的结果文件 <safe_id>.json。

与 OCR / Claude / Codex 评审器的差异：
- 多智能体架构：默认 3 个 Claude 智能体（security / logic / patterns）
  并行评审后做共识聚合（consensus scoring），由 `ai-reviewer` 自身完成。
- LLM 配置支持独立的 AI_REVIEWER_* 环境变量：
  AI_REVIEWER_API_KEY / AI_REVIEWER_BASE_URL / AI_REVIEWER_MODEL；
  同时兼容 ANTHROPIC_* 变量作为回退。也可通过 AI_REVIEWER_CONFIG
  指向 ai-code-reviewer 的 config.yaml（用于更细的静态配置）。
- 输出为单个 JSON envelope（format_review_as_json），findings[] 直接可用，
  无需 MCP 增量上报；但 rich 日志可能混入 stdout，因此解析带多级兜底。

环境变量：
  AI_REVIEWER_API_KEY   （必需）Anthropic API key 或转接网关 token
  AI_REVIEWER_BASE_URL  （可选）Anthropic Messages API 兼容网关地址
  AI_REVIEWER_MODEL     （可选）默认模型名
  AI_REVIEWER_COMMAND （可选）ai-reviewer 可执行文件路径，默认 "ai-reviewer"
  AI_REVIEWER_AGENTS  （可选）智能体数量 1-5，默认 3
  AI_REVIEWER_CONFIG  （可选）ai-reviewer 的 config.yaml 绝对路径
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import config
from repo_utils import clean_worktree, diff_stat, log, prepare_repo, run_command
from schema import ReviewInstance


def _ai_reviewer_command() -> str:
    """解析 ai-reviewer 可执行文件路径。

    查找顺序：
      1. 当前 Python 所在 venv 的 Scripts/bin 目录；
      2. evaluation/.venv 的 Scripts/bin 目录（即使当前 Python 未激活该 venv）；
      3. 环境变量 AI_REVIEWER_COMMAND 指定的路径；
      4. PATH 中的 ai-reviewer（全局安装，如 uv tool install / pip install）。
    """
    configured = os.environ.get(config.AI_REVIEWER_COMMAND_VAR, "ai-reviewer")
    # 1/2) 优先查找本地 venv。这样即使用系统 Python 启动 pipeline，
    # 只要 ai-reviewer 安装在 evaluation/.venv 里也能正常找到。
    script_dirs = [Path(sys.executable).resolve().parent]
    evaluation_dir = Path(__file__).resolve().parents[1]
    local_venv_bin = "Scripts" if os.name == "nt" else "bin"
    script_dirs.append(evaluation_dir / ".venv" / local_venv_bin)
    seen_dirs: set[Path] = set()
    for script_dir in script_dirs:
        script_dir = script_dir.resolve()
        if script_dir in seen_dirs:
            continue
        seen_dirs.add(script_dir)
        for candidate in (
            script_dir / "ai-reviewer.exe",
            script_dir / "ai-reviewer.cmd",
            script_dir / "ai-reviewer",
        ):
            if candidate.is_file():
                return str(candidate)
    # 3) 显式指定的命令路径
    if os.path.isabs(configured) and Path(configured).is_file():
        return configured
    # 3) PATH 兜底
    resolved = shutil.which(configured)
    if resolved:
        return resolved
    raise SystemExit(
        f"ai-reviewer CLI not found at '{configured}'. "
        "Install it via: uv tool install git+https://github.com/calimero-network/ai-code-reviewer  "
        "or: pip install ai-code-reviewer"
    )


def ensure_ai_reviewer_installed() -> None:
    command = _ai_reviewer_command()
    result = run_command([command, "--version"])
    if result.returncode != 0:
        raise SystemExit(
            f"ai-reviewer CLI not found at '{command}'. "
            "Install it via: uv tool install git+https://github.com/calimero-network/ai-code-reviewer"
        )
    first_line = result.stdout.strip().splitlines()[0] if result.stdout else "ok"
    log(f"ai-reviewer available ({command}): {first_line}")


def check_env(preview: bool) -> None:
    # 走 AI_REVIEWER_CONFIG 时鉴权由该 yaml 自带（api_key 可直接写在文件里），
    # 环境变量只是无 config 时的回退，因此不再强求 ANTHROPIC_API_KEY。
    if os.environ.get(config.AI_REVIEWER_CONFIG_VAR):
        return
    # Accept the legacy ANTHROPIC_* names too; ai-code-reviewer itself treats
    # them as fallbacks, so the preflight check should not report a false alarm.
    aliases = {
        config.AI_REVIEWER_API_KEY_VAR: (config.AI_REVIEWER_API_KEY_VAR, "ANTHROPIC_API_KEY"),
        config.AI_REVIEWER_BASE_URL_VAR: (config.AI_REVIEWER_BASE_URL_VAR, "ANTHROPIC_BASE_URL"),
        config.AI_REVIEWER_MODEL_VAR: (config.AI_REVIEWER_MODEL_VAR, "ANTHROPIC_MODEL"),
    }
    missing = [
        preferred
        for preferred, names in aliases.items()
        if not any(os.environ.get(name) for name in names)
    ]
    if missing and not preview:
        log(f"WARNING: missing ai-reviewer env vars: {', '.join(missing)}")
        log("ai-reviewer agents will fail until these are set (see evaluation/.env.example).")


def _resolve_agents() -> int:
    raw = os.environ.get(config.AI_REVIEWER_AGENTS_VAR, "3")
    try:
        agents = int(raw)
    except ValueError:
        log(f"WARNING: invalid AI_REVIEWER_AGENTS '{raw}', falling back to 3")
        agents = 3
    return max(1, min(agents, 5))  # ai-reviewer 的 --agents 范围是 1-5


def run_ai_reviewer_review(
    repo_path: Path,
    base_commit: str,
    timeout_minutes: int,
    agents: int,
) -> subprocess.CompletedProcess:
    """运行 `ai-reviewer review --base <base> --output json` 评审 base...HEAD。

    仓库已由 prepare_repo checkout 到 head_commit，HEAD 即被评审的代码状态；
    --base 让 ai-reviewer 用 `git diff <base>...HEAD` 计算 PR diff。
    """
    command = [
        _ai_reviewer_command(),
        "review",
        "--base",
        base_commit,
        "--output",
        "json",
        "--agents",
        str(agents),
    ]
    config_path = os.environ.get(config.AI_REVIEWER_CONFIG_VAR)
    if config_path:
        command.extend(["--config", config_path])

    process_timeout = timeout_minutes * 60 + 300
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"  # 保证 stdout JSON 为 UTF-8，解析稳定
    log(f"$ ai-reviewer review --base {base_commit[:12]} --output json  (cwd={repo_path})")
    try:
        return subprocess.run(
            command,
            cwd=str(repo_path),
            timeout=process_timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as timeout_error:
        log(f"TIMEOUT: ai-reviewer process exceeded {process_timeout}s — treating as failed")
        return subprocess.CompletedProcess(
            args=command,
            returncode=-1,
            stdout=timeout_error.stdout or "",
            stderr=f"Process timed out after {process_timeout} seconds",
        )


def extract_json_envelope(raw_stdout: str) -> Any:
    """从 stdout 中提取 ai-reviewer 的 JSON envelope（多级兜底）。

    ai-reviewer 的 rich 日志走 stdout，JSON 在最后通过 print 输出，因此
    stdout = 日志行 + JSON。依次尝试：
      1. 整体解析；
      2. 从第一个 '{' 截到末尾再解析（跳过前置日志行）；
      3. 最后一行以 '{' 开头的行单独解析。
    全部失败返回 None（调用方按原始文本兜底）。
    """
    text = raw_stdout or ""
    candidates: list[str] = []
    if text.strip():
        candidates.append(text.strip())
    first_brace = text.find("{")
    if first_brace >= 0:
        candidates.append(text[first_brace:].strip())
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    # Rich tracebacks/logs may contain braces before the final pretty-printed
    # JSON envelope. Scan every line that starts an object and use raw_decode so
    # multi-line JSON is handled as one value.
    decoder = json.JSONDecoder()
    starts = [match.start() for match in re.finditer(r"(?m)^\s*\{", text)]
    for start in reversed(starts):
        candidate = text[start:].lstrip()
        try:
            value, _ = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and ("findings" in value or "review_id" in value):
            return value
    return None


def save_result(
    results_dir: Path,
    instance: ReviewInstance,
    review_process: subprocess.CompletedProcess,
    started_at: str,
    duration_seconds: float,
    agents: int,
) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = config.result_path(results_dir, instance.instance_id)

    envelope = extract_json_envelope(review_process.stdout or "")
    review_output_source = "stdout_json"
    if isinstance(envelope, dict):
        findings = envelope.get("findings")
        review_output = findings if isinstance(findings, list) else []
    else:
        # 无法解析出 JSON（失败 / 超时 / 原始文本）：与 claude 的兜底策略一致，
        # 空 findings 进入评测会拉低 recall，非零退出码会记录在结果文件里。
        review_output_source = "stdout_fallback_raw"
        review_output = (review_process.stdout or "").strip() or []

    payload = {
        "instance_id": instance.instance_id,
        "repo": instance.repo,
        "base_commit": instance.base_commit,
        "head_commit": instance.head_commit,
        "reviewer": "ai-code-reviewer",
        "agents": agents,
        "started_at": started_at,
        "duration_seconds": round(duration_seconds, 2),
        "ai_reviewer_exit_code": review_process.returncode,
        "review_output_source": review_output_source,
        "review": envelope if isinstance(envelope, dict) else review_process.stdout,
        "review_output": review_output,
        "stderr": review_process.stderr,
    }
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return out_path


def review_instance(
    instance: ReviewInstance,
    repo_dir: Path,
    results_dir: Path,
    timeout_minutes: int = 30,
    preview: bool = False,
) -> Dict[str, Any]:
    """对单条样本执行 ai-reviewer 评审，返回状态摘要。"""
    log(f"=== [ai-reviewer] Processing {instance.instance_id} ===")

    repo_path = prepare_repo(
        repo_dir=repo_dir,
        clone_url=instance.resolved_clone_url,
        repo_full_name=instance.repo,
        base_commit=instance.base_commit,
        head_commit=instance.head_commit,
    )

    stat = diff_stat(repo_path, instance.base_commit, instance.head_commit)
    log(f"diff stat: {stat}")

    if preview:
        log("Preview mode: skipping ai-reviewer call.")
        return {"instance_id": instance.instance_id, "status": "preview", "diff_stat": stat}

    agents = _resolve_agents()
    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.monotonic()
    review_process = run_ai_reviewer_review(
        repo_path=repo_path,
        base_commit=instance.base_commit,
        timeout_minutes=timeout_minutes,
        agents=agents,
    )
    duration_seconds = time.monotonic() - start_time

    out_path = save_result(
        results_dir=results_dir,
        instance=instance,
        review_process=review_process,
        started_at=started_at,
        duration_seconds=duration_seconds,
        agents=agents,
    )

    # 丢弃 ai-reviewer 在仓库里留下的临时文件，保持工作区干净
    clean_worktree(repo_path)

    status = "ok" if review_process.returncode == 0 else "failed"
    log(f"--- [ai-reviewer] {instance.instance_id} {status} (exit={review_process.returncode}) -> {out_path}")
    return {
        "instance_id": instance.instance_id,
        "status": status,
        "exit_code": review_process.returncode,
        "result_path": str(out_path),
    }
