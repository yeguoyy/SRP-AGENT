"""Config loading tests."""

import textwrap
from pathlib import Path

from ai_reviewer.config import load_config


def test_load_anthropic_config(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    monkeypatch.setenv("GITHUB_TOKEN", "gh-test")
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        textwrap.dedent("""
        anthropic:
          api_key: ${ANTHROPIC_API_KEY}
          default_model: claude-sonnet-4-6
          enable_prompt_caching: true
        github:
          token: ${GITHUB_TOKEN}
        agents:
          - name: security-reviewer
            model: claude-sonnet-4-6
            focus_areas: [security]
            thinking_enabled: true
            allow_tool_use: true
            max_tool_calls: 20
    """)
    )
    cfg = load_config(cfg_file)
    assert cfg.anthropic is not None
    assert cfg.anthropic.api_key == "sk-test-123"
    assert cfg.anthropic.default_model == "claude-sonnet-4-6"
    assert cfg.anthropic.enable_prompt_caching is True
    assert cfg.agents[0].thinking_enabled is True
    assert cfg.agents[0].allow_tool_use is True
    assert cfg.agents[0].max_tool_calls == 20


def test_agent_defaults_sized_for_sonnet5():
    from ai_reviewer.config import AgentConfig

    cfg = AgentConfig(name="a", model="m", focus_areas=[])
    assert cfg.max_tokens == 8192


def test_anthropic_retries_default_is_resilient():
    # Long review calls drop connections transiently; 1 retry was too few.
    from ai_reviewer.config import AnthropicApiConfig

    assert AnthropicApiConfig(api_key="x").max_retries == 3


def test_pull_context_fields_default():
    from ai_reviewer.config import _parse_config

    cfg = _parse_config({"github": {"token": "t"}})
    assert cfg.anthropic.full_file_max_lines == 300
    assert cfg.anthropic.hunk_context_lines == 60
    assert cfg.anthropic.conventions_max_chars == 16_000


def test_pull_context_fields_parse_from_yaml():
    from ai_reviewer.config import _parse_config

    cfg = _parse_config(
        {
            "github": {"token": "t"},
            "anthropic": {
                "full_file_max_lines": 120,
                "hunk_context_lines": 25,
                "conventions_max_chars": 4096,
            },
        }
    )
    assert cfg.anthropic.full_file_max_lines == 120
    assert cfg.anthropic.hunk_context_lines == 25
    assert cfg.anthropic.conventions_max_chars == 4096


def test_ai_reviewer_env_namespace_and_role_models(monkeypatch):
    from ai_reviewer.config import _parse_config

    monkeypatch.setenv("AI_REVIEWER_API_KEY", "gateway-key")
    monkeypatch.setenv("AI_REVIEWER_BASE_URL", "https://gateway.example/anthropic")
    monkeypatch.setenv("AI_REVIEWER_MODEL", "gateway-default")
    monkeypatch.setenv("AI_REVIEWER_MODEL_SECURITY", "security-model")
    monkeypatch.setenv("AI_REVIEWER_MODEL_PERFORMANCE", "performance-model")
    monkeypatch.setenv("AI_REVIEWER_MODEL_PATTERNS", "patterns-model")

    cfg = _parse_config({"github": {"token": "t"}})

    assert cfg.anthropic.api_key == "gateway-key"
    assert cfg.anthropic.base_url == "https://gateway.example/anthropic"
    assert cfg.anthropic.default_model == "gateway-default"
    assert [agent.name for agent in cfg.agents] == [
        "security-reviewer",
        "logic-reviewer",
        "patterns-reviewer",
        "performance-reviewer",
        "style-reviewer",
    ]
    assert [agent.model for agent in cfg.agents] == [
        "security-model",
        "gateway-default",
        "patterns-model",
        "performance-model",
        "gateway-default",
    ]


def test_ai_reviewer_yaml_values_override_env(monkeypatch):
    from ai_reviewer.config import _parse_config

    monkeypatch.setenv("AI_REVIEWER_API_KEY", "env-key")
    monkeypatch.setenv("AI_REVIEWER_BASE_URL", "https://env.example")
    monkeypatch.setenv("AI_REVIEWER_MODEL", "env-model")
    monkeypatch.setenv("AI_REVIEWER_MODEL_SECURITY", "env-security")

    cfg = _parse_config(
        {
            "github": {"token": "t"},
            "anthropic": {
                "api_key": "yaml-key",
                "base_url": "https://yaml.example",
                "default_model": "yaml-model",
            },
            "agents": [
                {
                    "name": "security-reviewer",
                    "model": "yaml-security",
                    "focus_areas": ["security"],
                }
            ],
        }
    )

    assert cfg.anthropic.api_key == "yaml-key"
    assert cfg.anthropic.base_url == "https://yaml.example"
    assert cfg.anthropic.default_model == "yaml-model"
    assert cfg.agents[0].model == "yaml-security"
