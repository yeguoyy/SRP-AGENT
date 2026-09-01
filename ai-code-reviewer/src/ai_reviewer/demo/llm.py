"""LLM protocol adapters used by the local demo.

The demo deliberately routes by wire protocol rather than by model vendor:
DeepSeek and OpenAI can both use the OpenAI-compatible adapters, while Claude
uses the Anthropic Messages adapter.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import httpx
from dotenv import load_dotenv

from ai_reviewer.config import LLMConfig
from ai_reviewer.demo.models import Finding, ProjectSnapshot, finding_from_dict

# Load the demo project's local .env without overriding variables explicitly set by the shell.
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


class LLMError(RuntimeError):
    """Raised when an LLM endpoint cannot be used."""


RetryCallback = Callable[[int, int, str], None]


class ReviewClient(Protocol):
    """Small common interface shared by all three protocol adapters."""

    def review(
        self,
        *,
        agent_name: str,
        focus: str,
        snapshot: ProjectSnapshot,
        retry_callback: RetryCallback | None = None,
    ) -> tuple[list[Finding], str]: ...


class _BaseHttpClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_tokens: int = 1600,
        retries: int = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.retries = retries
        if not self.base_url:
            raise LLMError("未配置模型 base_url")
        if not self.api_key:
            raise LLMError("未配置模型 API Key")
        if not self.model:
            raise LLMError("未配置模型名称")

    def _post_with_retry(
        self,
        endpoint: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        *,
        agent_name: str,
        retry_callback: RetryCallback | None,
    ) -> httpx.Response:
        attempts = self.retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = httpx.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return response
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < attempts:
                    if retry_callback is not None:
                        retry_callback(attempt + 1, attempts, agent_name)
                    continue
                raise LLMError(
                    f"模型请求失败：读取超时（已尝试 {attempts} 次，单次超时 {self.timeout:g} 秒）"
                ) from exc
            except httpx.HTTPError as exc:
                raise LLMError(f"模型请求失败：{exc}") from exc

        raise LLMError(f"模型请求失败：{last_error or '未知错误'}")

    def _finish_review(self, content: Any, agent_name: str) -> tuple[list[Finding], str]:
        if not content:
            raise LLMError("模型返回了空内容；请检查模型名称、输出限制和协议配置")
        parsed = _parse_json_content(content)
        findings = [finding_from_dict(item, agent_name) for item in parsed.get("findings", [])]
        return findings, str(parsed.get("summary", f"{agent_name} 完成评审。"))

    @staticmethod
    def _prompt(agent_name: str, focus: str, snapshot: ProjectSnapshot) -> str:
        files = []
        for file_info in snapshot.files:
            content = file_info.content
            if len(content) > 12_000:
                content = content[:12_000] + "\n...[内容已截断]"
            files.append(
                f"### {file_info.path} ({file_info.language}, {file_info.line_count} lines)\n{content}"
            )
        return (
            f"评审角色：{agent_name}\n关注方向：{focus}\n"
            "最多输出 5 个最重要问题。每个 finding 必须包含 file_path、line_start、line_end、"
            "severity、category、title、description、recommendation、confidence（0 到 1 之间的数字）。"
            "description 和 recommendation 各不超过 120 字。只能引用真实文件和行号。\n\n"
            + "\n\n".join(files)
        )


class OpenAICompatibleClient(_BaseHttpClient):
    """Adapter for the OpenAI Chat Completions protocol.

    This is protocol-oriented rather than vendor-oriented: DeepSeek, OpenAI and
    other compatible gateways can all use this adapter by changing ``base_url``.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_tokens: int | None = None,
        retries: int | None = None,
        disable_thinking: bool | None = None,
    ) -> None:
        resolved_model = model or os.getenv("LLM_MODEL", "")
        super().__init__(
            base_url=base_url or os.getenv("LLM_BASE_URL", ""),
            api_key=api_key or os.getenv("LLM_API_KEY", ""),
            model=resolved_model,
            timeout=timeout if timeout is not None else _env_float("LLM_TIMEOUT", 60.0, minimum=1.0),
            max_tokens=max_tokens
            if max_tokens is not None
            else _env_int("LLM_MAX_TOKENS", 1600, minimum=256),
            retries=retries if retries is not None else _env_int("LLM_RETRIES", 1, minimum=0),
        )
        # Directly constructed clients are commonly used in tests and library
        # integrations. In that case explicit constructor values must not be
        # silently changed by a repository-local .env. The pipeline/factory
        # passes ``disable_thinking`` explicitly, so the legacy .env behavior is
        # still preserved for calls that rely entirely on environment settings.
        explicit_connection = base_url is not None or api_key is not None or model is not None
        self.disable_thinking = (
            disable_thinking
            if disable_thinking is not None
            else (
                resolved_model.startswith("deepseek-v4")
                if explicit_connection
                else _thinking_disabled(default=resolved_model.startswith("deepseek-v4"))
            )
        )

    def review(
        self,
        *,
        agent_name: str,
        focus: str,
        snapshot: ProjectSnapshot,
        retry_callback: RetryCallback | None = None,
    ) -> tuple[list[Finding], str]:
        prompt = self._prompt(agent_name, focus, snapshot)
        endpoint = _append_endpoint(self.base_url, "chat/completions")
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.1,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是软件工程代码评审专家。只返回合法 JSON，不要 Markdown。"
                        "JSON 格式必须是 {\"summary\": string, \"findings\": array}。"
                        "最多输出 5 个最重要问题；description 和 recommendation 要简洁。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        # Retain compatibility with DeepSeek reasoning models for the legacy
        # .env path, but never send this field to an unknown provider by default.
        if self.disable_thinking:
            payload["thinking"] = {"type": "disabled"}
        response = self._post_with_retry(
            endpoint,
            payload,
            {"Authorization": f"Bearer {self.api_key}"},
            agent_name=agent_name,
            retry_callback=retry_callback,
        )
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(f"Chat Completions 响应格式异常：{exc}") from exc
        return self._finish_review(content, agent_name)


class OpenAIResponsesClient(_BaseHttpClient):
    """Adapter for the OpenAI Responses protocol."""

    def review(
        self,
        *,
        agent_name: str,
        focus: str,
        snapshot: ProjectSnapshot,
        retry_callback: RetryCallback | None = None,
    ) -> tuple[list[Finding], str]:
        prompt = self._prompt(agent_name, focus, snapshot)
        endpoint = _append_endpoint(self.base_url, "responses")
        payload = {
            "model": self.model,
            "instructions": (
                "你是软件工程代码评审专家。只返回合法 JSON，不要 Markdown。"
                "JSON 格式必须是 {\"summary\": string, \"findings\": array}。"
                "最多输出 5 个最重要问题；description 和 recommendation 要简洁。"
            ),
            "input": prompt,
            "max_output_tokens": self.max_tokens,
        }
        response = self._post_with_retry(
            endpoint,
            payload,
            {"Authorization": f"Bearer {self.api_key}"},
            agent_name=agent_name,
            retry_callback=retry_callback,
        )
        try:
            body = response.json()
            content = _extract_responses_text(body)
        except (TypeError, ValueError) as exc:
            raise LLMError(f"Responses 响应格式异常：{exc}") from exc
        return self._finish_review(content, agent_name)


class AnthropicMessagesClient(_BaseHttpClient):
    """Adapter for the Anthropic Messages protocol."""

    def review(
        self,
        *,
        agent_name: str,
        focus: str,
        snapshot: ProjectSnapshot,
        retry_callback: RetryCallback | None = None,
    ) -> tuple[list[Finding], str]:
        prompt = self._prompt(agent_name, focus, snapshot)
        endpoint = _append_anthropic_endpoint(self.base_url)
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": (
                "你是软件工程代码评审专家。只返回合法 JSON，不要 Markdown。"
                "JSON 格式必须是 {\"summary\": string, \"findings\": array}。"
                "最多输出 5 个最重要问题；description 和 recommendation 要简洁。"
            ),
            "messages": [{"role": "user", "content": prompt}],
        }
        response = self._post_with_retry(
            endpoint,
            payload,
            {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            agent_name=agent_name,
            retry_callback=retry_callback,
        )
        try:
            content = _extract_anthropic_text(response.json())
        except (TypeError, ValueError) as exc:
            raise LLMError(f"Anthropic Messages 响应格式异常：{exc}") from exc
        return self._finish_review(content, agent_name)


def create_demo_client(config: LLMConfig) -> ReviewClient:
    """Create a Demo client from the unified protocol configuration."""
    protocol = config.protocol.strip().lower()
    model = config.model or config.default_model
    thinking = (config.thinking or "").strip().lower()
    disable_thinking = True if thinking in {"disabled", "disable", "off", "false"} else None
    common = {
        "base_url": config.base_url,
        "api_key": config.api_key,
        "model": model,
        "timeout": float(config.timeout_seconds),
        "max_tokens": config.max_tokens,
        "retries": config.max_retries,
    }
    if protocol == "openai_chat_completions":
        return OpenAICompatibleClient(**common, disable_thinking=disable_thinking)
    if protocol == "openai_responses":
        return OpenAIResponsesClient(**common)
    if protocol == "anthropic_messages":
        return AnthropicMessagesClient(**common)
    raise LLMError(
        f"不支持的 LLM 协议：{config.protocol}；可选："
        "openai_chat_completions、openai_responses、anthropic_messages"
    )


def _append_endpoint(base_url: str, suffix: str) -> str:
    if base_url.endswith("/" + suffix):
        return base_url
    return f"{base_url}/{suffix}"


def _append_anthropic_endpoint(base_url: str) -> str:
    if base_url.endswith("/messages"):
        return base_url
    if base_url.endswith("/v1"):
        return f"{base_url}/messages"
    return f"{base_url}/v1/messages"


def _extract_responses_text(body: Any) -> str:
    if isinstance(body, dict) and body.get("output_text"):
        return str(body["output_text"])
    parts: list[str] = []
    for item in body.get("output", []) if isinstance(body, dict) else []:
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if not isinstance(content, dict):
                continue
            if content.get("text") is not None:
                parts.append(str(content["text"]))
    if not parts:
        raise ValueError("响应中没有 output_text 或 output.content.text")
    return "".join(parts)


def _extract_anthropic_text(body: Any) -> str:
    parts = []
    for item in body.get("content", []) if isinstance(body, dict) else []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")))
    if not parts:
        raise ValueError("响应中没有 content.text")
    return "".join(parts)


def _env_float(name: str, default: float, *, minimum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value >= minimum else default


def _env_int(name: str, default: int, *, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value >= minimum else default


def _thinking_disabled(*, default: bool) -> bool:
    raw = os.getenv("LLM_THINKING")
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in {"disabled", "disable", "off", "false", "no", "0"}:
        return True
    if value in {"enabled", "enable", "on", "true", "yes", "1"}:
        return False
    return default


def _parse_json_content(content: Any) -> dict[str, Any]:
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item) for item in content
        )
    text = str(content).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型没有返回合法 JSON：{exc}") from exc
    if not isinstance(parsed, dict):
        raise LLMError("模型返回的 JSON 顶层结构不是对象")
    return parsed
