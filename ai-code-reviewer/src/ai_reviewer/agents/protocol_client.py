"""HTTP adapters for non-Anthropic full-review protocols.

The existing Anthropic client remains responsible for the rich Messages tool-use
loop. This module provides the same small client surface for OpenAI Chat
Completions and OpenAI Responses, allowing the review orchestration to share its
agent, aggregation, and GitHub code without a vendor-specific client.

OpenAI-compatible protocols intentionally run without repository tools for now:
the complete PR context is already included in the request, while Anthropic keeps
its existing pull-based tool loop and prompt caching behavior.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Protocol

import httpx

from ai_reviewer.agents.anthropic_client import AnthropicReviewResult, UsageStats
from ai_reviewer.config import LLMConfig


class ReviewClient(Protocol):
    """Common async surface consumed by ``ReviewAgent`` and cross-review."""

    config: LLMConfig

    async def run_review(
        self,
        model: str,
        system_blocks: list[dict[str, Any]],
        user_blocks: list[dict[str, Any]],
        output_schema: dict[str, Any],
        tool_registry: Any,
        enable_thinking: bool = False,
        max_tokens: int = 8192,
        temperature: float = 0.3,
        max_tool_rounds: int = 20,
        max_review_seconds: float | None = None,
    ) -> AnthropicReviewResult: ...

    async def complete_simple(
        self,
        model: str,
        system: str | list[dict[str, Any]],
        user: str,
        max_tokens: int = 8192,
        temperature: float = 0.2,
    ) -> str: ...

    async def close(self) -> None: ...


class OpenAIProtocolClient:
    """One HTTP implementation for Chat Completions and Responses."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.api_key = config.api_key
        self.default_model = config.model or config.default_model
        if not self.base_url:
            raise ValueError("未配置模型 base_url")
        if not self.api_key:
            raise ValueError(f"未配置模型 API Key（环境变量：{config.api_key_env}）")
        if not self.default_model:
            raise ValueError("未配置模型名称")
        self._client = httpx.AsyncClient(timeout=float(config.timeout_seconds))

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        attempts = max(int(self.config.max_retries), 0) + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await self._client.post(
                    endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict):
                    raise ValueError("模型响应顶层结构不是对象")
                return body
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(min(2**attempt, 4))
                    continue
                raise RuntimeError(
                    f"模型请求失败：读取超时（已尝试 {attempts} 次，单次超时 {self.config.timeout_seconds} 秒）"
                ) from exc
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500 and attempt + 1 < attempts:
                    await asyncio.sleep(min(2**attempt, 4))
                    continue
                raise RuntimeError(f"模型请求失败：{exc}") from exc
        raise RuntimeError(f"模型请求失败：{last_error or '未知错误'}")

    async def run_review(
        self,
        model: str,
        system_blocks: list[dict[str, Any]],
        user_blocks: list[dict[str, Any]],
        output_schema: dict[str, Any],
        tool_registry: Any,
        enable_thinking: bool = False,
        max_tokens: int = 8192,
        temperature: float = 0.3,
        max_tool_rounds: int = 20,
        max_review_seconds: float | None = None,
    ) -> AnthropicReviewResult:
        del tool_registry, max_tool_rounds, output_schema
        system = _blocks_to_text(system_blocks)
        user = _blocks_to_text(user_blocks)
        if enable_thinking:
            user += "\n\n请先充分分析，但最终只输出要求的 JSON。"
        raw = await self._complete(model, system, user, max_tokens, temperature, max_review_seconds)
        parsed = _parse_json(raw)
        return AnthropicReviewResult(
            parsed=parsed,
            raw_text=raw,
            usage=UsageStats(),
            tool_calls=[],
        )

    async def complete_simple(
        self,
        model: str,
        system: str | list[dict[str, Any]],
        user: str,
        max_tokens: int = 8192,
        temperature: float = 0.2,
    ) -> str:
        return await self._complete(
            model,
            _blocks_to_text(system) if isinstance(system, list) else system,
            user,
            max_tokens,
            temperature,
            None,
        )

    async def _complete(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
        deadline: float | None,
    ) -> str:
        del deadline  # httpx timeout is the per-request ceiling for this adapter.
        model = model or self.default_model
        instruction = (
            system
            + "\n\nReturn valid JSON only. The expected top-level shape is "
            + '{"summary": string, "findings": array}.\n'
        ).strip()
        if self.config.protocol == "openai_responses":
            payload: dict[str, Any] = {
                "model": model,
                "instructions": instruction,
                "input": user,
                "max_output_tokens": max_tokens,
            }
            endpoint = _append_endpoint(self.base_url, "responses")
        else:
            payload = {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": user},
                ],
            }
            endpoint = _append_endpoint(self.base_url, "chat/completions")
        body = await self._post(endpoint, payload)
        try:
            if self.config.protocol == "openai_responses":
                return _extract_responses_text(body)
            content = body["choices"][0]["message"]["content"]
            if isinstance(content, list):
                return "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
            return str(content)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError(f"模型响应格式异常：{exc}") from exc

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> OpenAIProtocolClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()


def create_review_client(config: LLMConfig) -> ReviewClient:
    """Create the full-review client selected by ``llm.protocol``."""
    if config.protocol == "anthropic_messages":
        from ai_reviewer.agents.anthropic_client import AnthropicClient

        return AnthropicClient(config)
    if config.protocol in {"openai_chat_completions", "openai_responses"}:
        return OpenAIProtocolClient(config)
    raise ValueError(f"不支持的 LLM 协议：{config.protocol}")


def _blocks_to_text(blocks: str | list[dict[str, Any]]) -> str:
    if isinstance(blocks, str):
        return blocks
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, dict) and block.get("text") is not None:
            parts.append(str(block["text"]))
    return "\n".join(parts)


def _append_endpoint(base_url: str, suffix: str) -> str:
    if base_url.endswith("/" + suffix):
        return base_url
    return f"{base_url}/{suffix}"


def _extract_responses_text(body: dict[str, Any]) -> str:
    if body.get("output_text"):
        return str(body["output_text"])
    parts: list[str] = []
    for item in body.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("text") is not None:
                parts.append(str(content["text"]))
    if not parts:
        raise ValueError("响应中没有 output_text 或 output.content.text")
    return "".join(parts)


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    if not text.startswith("{"):
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            text = match.group(0)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("模型 JSON 顶层结构不是对象")
    return parsed
