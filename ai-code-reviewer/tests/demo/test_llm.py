from pathlib import Path

import httpx

from ai_reviewer.config import LLMConfig
from ai_reviewer.demo import llm
from ai_reviewer.demo.llm import (
    AnthropicMessagesClient,
    OpenAICompatibleClient,
    OpenAIResponsesClient,
    create_demo_client,
)
from ai_reviewer.demo.scanner import scan_project

SAMPLE = Path(__file__).parents[2] / "demo" / "sample_project"


def _response(content: str = '{"summary":"ok","findings":[]}') -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
        request=httpx.Request("POST", "https://example.test/chat/completions"),
    )


def test_deepseek_v4_request_bounds_output_and_disables_thinking(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs["json"]
        return _response()

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    client = OpenAICompatibleClient(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="deepseek-v4-flash",
        retries=0,
    )

    findings, summary = client.review(
        agent_name="架构与逻辑 Agent",
        focus="模块职责和耦合",
        snapshot=scan_project(SAMPLE),
    )

    assert findings == []
    assert summary == "ok"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["payload"]["max_tokens"] == 1600
    assert captured["payload"]["thinking"] == {"type": "disabled"}


def test_unknown_provider_does_not_receive_deepseek_thinking_parameter(monkeypatch):
    captured = {}
    def fake_post(_url, **kwargs):
        captured["payload"] = kwargs["json"]
        return _response()

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    client = OpenAICompatibleClient(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="generic-model",
        retries=0,
    )

    client.review(agent_name="测试 Agent", focus="代码质量", snapshot=scan_project(SAMPLE))

    assert "thinking" not in captured["payload"]


def test_timeout_retries_and_reports_retry_callback(monkeypatch):
    calls = {"count": 0}
    retries = []

    def fake_post(_url, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ReadTimeout("simulated timeout")
        return _response()

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    client = OpenAICompatibleClient(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="generic-model",
        timeout=3,
        retries=1,
        disable_thinking=False,
    )

    findings, summary = client.review(
        agent_name="架构与逻辑 Agent",
        focus="模块职责和耦合",
        snapshot=scan_project(SAMPLE),
        retry_callback=lambda attempt, total, agent: retries.append((attempt, total, agent)),
    )

    assert findings == []
    assert summary == "ok"
    assert calls["count"] == 2
    assert retries == [(2, 2, "架构与逻辑 Agent")]



def test_openai_responses_request_and_output_text(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs["json"]
        captured["headers"] = kwargs["headers"]
        return httpx.Response(
            200,
            json={"output_text": '{"summary":"responses-ok","findings":[]}'},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    client = OpenAIResponsesClient(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="gpt-4.1",
        max_tokens=2048,
        retries=0,
    )

    findings, summary = client.review(
        agent_name="代码质量 Agent",
        focus="可维护性",
        snapshot=scan_project(SAMPLE),
    )

    assert findings == []
    assert summary == "responses-ok"
    assert captured["url"] == "https://example.test/v1/responses"
    assert captured["payload"]["max_output_tokens"] == 2048
    assert captured["payload"]["input"]
    assert captured["headers"] == {"Authorization": "Bearer test-key"}


def test_anthropic_messages_request_and_content_array_response(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs["json"]
        captured["headers"] = kwargs["headers"]
        return httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": '{"summary":"anthropic-ok",'},
                    {"type": "text", "text": '"findings":[]}'},
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    client = AnthropicMessagesClient(
        base_url="https://example.test",
        api_key="test-key",
        model="claude-sonnet-5",
        retries=0,
    )

    findings, summary = client.review(
        agent_name="安全评审 Agent",
        focus="安全性",
        snapshot=scan_project(SAMPLE),
    )

    assert findings == []
    assert summary == "anthropic-ok"
    assert captured["url"] == "https://example.test/v1/messages"
    assert captured["payload"]["messages"][0]["role"] == "user"
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert "Authorization" not in captured["headers"]


def test_create_demo_client_routes_by_protocol():
    common = {
        "api_key": "test-key",
        "model": "test-model",
        "timeout_seconds": 10,
        "max_tokens": 512,
        "max_retries": 0,
    }
    assert isinstance(
        create_demo_client(LLMConfig(protocol="openai_chat_completions", **common)),
        OpenAICompatibleClient,
    )
    assert isinstance(
        create_demo_client(LLMConfig(protocol="openai_responses", **common)),
        OpenAIResponsesClient,
    )
    assert isinstance(
        create_demo_client(LLMConfig(protocol="anthropic_messages", **common)),
        AnthropicMessagesClient,
    )
