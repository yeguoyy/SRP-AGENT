"""LLM adapters for the demo. The default path is deterministic and offline."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from ai_reviewer.demo.models import Finding, ProjectSnapshot, finding_from_dict


class LLMError(RuntimeError):
    """Raised when an OpenAI-compatible endpoint cannot be used."""


class OpenAICompatibleClient:
    """Small dependency-light adapter for DeepSeek/讯飞-compatible endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 45.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "")
        self.timeout = timeout
        if not self.base_url:
            raise LLMError("未配置 LLM_BASE_URL")
        if not self.api_key:
            raise LLMError("未配置 LLM_API_KEY")
        if not self.model:
            raise LLMError("未配置 LLM_MODEL")

    def review(
        self,
        *,
        agent_name: str,
        focus: str,
        snapshot: ProjectSnapshot,
    ) -> tuple[list[Finding], str]:
        prompt = self._prompt(agent_name, focus, snapshot)
        endpoint = self.base_url
        if not endpoint.endswith("/chat/completions"):
            endpoint = f"{endpoint}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是软件工程代码评审专家。只返回合法 JSON，不要 Markdown。"
                        "JSON 格式必须是 {\"summary\": string, \"findings\": array}。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = httpx.post(endpoint, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(f"模型请求失败：{exc}") from exc

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
            "每个 finding 必须包含 file_path、line_start、line_end、severity、category、"
            "title、description、recommendation、confidence。只能引用真实文件和行号。\n\n"
            + "\n\n".join(files)
        )


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
