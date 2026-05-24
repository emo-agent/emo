"""Tests for emo.config — load_config(), RootConfig, typed models, ConfigError."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from emo.config import (
    AgentConfig,
    ConfigError,
    FeaturesConfig,
    LLMConfig,
    MemoryConfig,
    RootConfig,
    RouterConfig,
    load_config,
)
from emo.config.loader import _deep_merge


# ── Helpers ───────────────────────────────────────────────────────────────────

def write_config(path: Path, data: dict) -> Path:
    path.write_text(yaml.dump(data))
    return path


def make_config(**overrides) -> RootConfig:
    """Build a RootConfig with specific agent.llm overrides."""
    llm_overrides = overrides.pop("llm", {})
    agent_overrides = overrides.pop("agent", {})

    llm = LLMConfig(**{**{"model": "openai/gpt-4o"}, **llm_overrides})
    agent = AgentConfig(**{**{"llm": llm}, **agent_overrides})
    return RootConfig(agent=agent, **overrides)


# ── _deep_merge ───────────────────────────────────────────────────────────────

class TestDeepMerge:
    def test_simple_override(self):
        result = _deep_merge({"a": 1, "b": 2}, {"b": 99})
        assert result == {"a": 1, "b": 99}

    def test_nested_merge_preserves_unset_keys(self):
        base = {"agent": {"temperature": 0.7, "max_iterations": 20}}
        override = {"agent": {"temperature": 0.1}}
        result = _deep_merge(base, override)
        assert result["agent"]["temperature"] == 0.1
        assert result["agent"]["max_iterations"] == 20

    def test_base_not_mutated(self):
        base = {"a": {"b": 1}}
        _deep_merge(base, {"a": {"b": 2}})
        assert base["a"]["b"] == 1

    def test_non_dict_value_overrides_dict(self):
        result = _deep_merge({"a": {"nested": 1}}, {"a": "flat"})
        assert result["a"] == "flat"


# ── LLMConfig ─────────────────────────────────────────────────────────────────

class TestLLMConfig:
    def test_defaults(self):
        llm = LLMConfig()
        assert llm.model is None
        assert llm.temperature == 0.7
        assert llm.max_iterations == 20
        assert llm.context_window == 40000

    def test_custom_values(self):
        llm = LLMConfig(model="openai/gpt-4o", temperature=0.2, max_tokens=512)
        assert llm.model == "openai/gpt-4o"
        assert llm.temperature == 0.2
        assert llm.max_tokens == 512


# ── AgentConfig ───────────────────────────────────────────────────────────────

class TestAgentConfig:
    def test_defaults(self):
        cfg = AgentConfig()
        assert cfg.name == ""
        assert cfg.tools is None
        assert cfg.mcps == []
        assert cfg.subagents == []

    def test_tools_list(self):
        cfg = AgentConfig(tools=["shell", "file_read"])
        assert cfg.tools == ["shell", "file_read"]


# ── RootConfig properties ─────────────────────────────────────────────────────

class TestRootConfigProperties:
    def test_model_returns_value(self):
        cfg = make_config()
        assert cfg.model == "openai/gpt-4o"

    def test_model_raises_on_missing(self):
        cfg = RootConfig(agent=AgentConfig(llm=LLMConfig(model=None)))
        with pytest.raises(ConfigError):
            _ = cfg.model

    def test_litellm_model_no_api_base(self):
        cfg = make_config()
        assert cfg.litellm_model == "openai/gpt-4o"

    def test_litellm_model_with_api_base_prepends_openai_for_any_non_openai_model(self):
        # With api_base set, litellm must use the openai/ prefix to route through
        # the OpenAI-compatible path. litellm strips openai/ before sending to the
        # endpoint, so deepseek/model → POST body contains deepseek/model (correct).
        cfg = make_config(llm={"model": "google/gemini-2.0-flash", "api_base": "https://openrouter.ai/api/v1"})
        assert cfg.litellm_model == "openai/google/gemini-2.0-flash"

    def test_litellm_model_with_api_base_openrouter_deepseek(self):
        cfg = make_config(llm={"model": "deepseek/deepseek-v4-flash", "api_base": "https://openrouter.ai/api/v1"})
        assert cfg.litellm_model == "openai/deepseek/deepseek-v4-flash"

    def test_litellm_model_with_api_base_openai_prefix_unchanged(self):
        cfg = make_config(llm={"model": "openai/gpt-4o", "api_base": "https://openrouter.ai/api/v1"})
        assert cfg.litellm_model == "openai/gpt-4o"

    def test_temperature_default(self):
        cfg = RootConfig()
        assert cfg.temperature == 0.7

    def test_temperature_override(self):
        cfg = make_config(llm={"temperature": 0.2})
        assert cfg.temperature == 0.2

    def test_max_iterations_default(self):
        cfg = RootConfig()
        assert cfg.max_iterations == 20

    def test_context_window_default(self):
        cfg = RootConfig()
        assert cfg.context_window == 40000

    def test_memory_db_path(self):
        cfg = RootConfig(memory=MemoryConfig(db_path="~/.emo/memory.db"))
        assert cfg.memory_db_path == Path.home() / ".emo" / "memory.db"

    def test_supervisor_enabled_default(self):
        cfg = RootConfig()
        assert cfg.supervisor_enabled is True

    def test_supervisor_disabled(self):
        cfg = RootConfig(router=RouterConfig(enabled=False))
        assert cfg.supervisor_enabled is False

    def test_tools_enabled_none_returns_empty_dict(self):
        cfg = make_config(agent={"tools": None})
        assert cfg.tools_enabled == {}

    def test_tools_enabled_list(self):
        cfg = RootConfig(agent=AgentConfig(tools=["shell", "web_fetch"]))
        enabled = cfg.tools_enabled
        assert enabled["shell"] is True
        assert enabled["web_fetch"] is True

    def test_api_base_from_config(self):
        cfg = make_config(llm={"api_base": "https://example.com"})
        assert cfg.api_base == "https://example.com"

    def test_api_base_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_BASE", "https://from-env.com")
        cfg = make_config()
        assert cfg.api_base == "https://from-env.com"

    def test_api_key_from_config(self):
        cfg = make_config(llm={"api_key": "sk-test"})
        assert cfg.api_key == "sk-test"

    def test_api_key_from_openai_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        cfg = make_config()
        assert cfg.api_key == "sk-env"

    def test_api_key_from_emo_env(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("EMO_API_KEY", "sk-emo")
        cfg = make_config()
        assert cfg.api_key == "sk-emo"


# ── RouterConfig ──────────────────────────────────────────────────────────────

class TestRouterConfig:
    def test_defaults(self):
        r = RouterConfig()
        assert r.enabled is True
        assert r.default == "general"
        assert "general" in r.agents
        assert "code" in r.agents
        assert "research" in r.agents

    def test_router_llm_defaults_low_temperature(self):
        r = RouterConfig()
        assert r.llm.temperature == 0.0
        assert r.llm.max_tokens == 10


# ── load_config ───────────────────────────────────────────────────────────────

class TestLoadConfig:
    def test_load_from_explicit_path(self, tmp_path):
        p = write_config(tmp_path / "my.yaml", {
            "agent": {"llm": {"model": "anthropic/claude-3-5-sonnet-20241022"}}
        })
        cfg = load_config(str(p))
        assert cfg.model == "anthropic/claude-3-5-sonnet-20241022"

    def test_load_merges_with_defaults(self, tmp_path):
        p = write_config(tmp_path / "cfg.yaml", {
            "agent": {"llm": {"model": "openai/gpt-4o"}}
        })
        cfg = load_config(str(p))
        assert cfg.max_iterations == 20
        assert cfg.temperature == 0.7

    def test_load_from_env_var(self, tmp_path, monkeypatch):
        p = write_config(tmp_path / "env.yaml", {
            "agent": {"llm": {"model": "openai/gpt-4o-mini"}}
        })
        monkeypatch.setenv("EMO_CONFIG", str(p))
        cfg = load_config()
        assert cfg.model == "openai/gpt-4o-mini"

    def test_explicit_path_takes_priority_over_env(self, tmp_path, monkeypatch):
        p_env = write_config(tmp_path / "env.yaml", {
            "agent": {"llm": {"model": "openai/gpt-4o-mini"}}
        })
        p_explicit = write_config(tmp_path / "explicit.yaml", {
            "agent": {"llm": {"model": "openai/gpt-4o"}}
        })
        monkeypatch.setenv("EMO_CONFIG", str(p_env))
        cfg = load_config(str(p_explicit))
        assert cfg.model == "openai/gpt-4o"

    def test_no_config_file_returns_defaults(self, tmp_path, monkeypatch):
        monkeypatch.delenv("EMO_CONFIG", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        cfg = load_config()
        assert cfg.agent.llm.model is None

    def test_deep_merge_preserves_nested_defaults(self, tmp_path):
        p = write_config(tmp_path / "cfg.yaml", {
            "agent": {"llm": {"model": "openai/gpt-4o", "temperature": 0.1}}
        })
        cfg = load_config(str(p))
        assert cfg.temperature == 0.1
        assert cfg.max_iterations == 20

    def test_config_path_stored(self, tmp_path):
        p = write_config(tmp_path / "cfg.yaml", {
            "agent": {"llm": {"model": "openai/gpt-4o"}}
        })
        cfg = load_config(str(p))
        assert cfg.config_path == p

    def test_all_configs_merged(self, tmp_path, monkeypatch):
        """All found config files should be merged, not just the first."""
        # Home config sets model
        home = tmp_path / "home"
        (home / ".emo").mkdir(parents=True)
        write_config(home / ".emo" / "config.yaml", {
            "agent": {"llm": {"model": "openai/gpt-4o", "temperature": 0.5}}
        })
        # Explicit path overrides temperature only
        p_explicit = write_config(tmp_path / "explicit.yaml", {
            "agent": {"llm": {"temperature": 0.1}}
        })
        monkeypatch.delenv("EMO_CONFIG", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        cfg = load_config(str(p_explicit))
        # Model comes from home config; temperature from explicit (higher priority)
        assert cfg.model == "openai/gpt-4o"
        assert cfg.temperature == 0.1

    def test_router_config_loaded(self, tmp_path):
        p = write_config(tmp_path / "cfg.yaml", {
            "agent": {"llm": {"model": "openai/gpt-4o"}},
            "router": {"enabled": False, "agents": ["general"]},
        })
        cfg = load_config(str(p))
        assert cfg.router.enabled is False
        assert cfg.router.agents == ["general"]

    def test_memory_config_loaded(self, tmp_path):
        p = write_config(tmp_path / "cfg.yaml", {
            "agent": {"llm": {"model": "openai/gpt-4o"}},
            "memory": {"db_path": "/tmp/test.db", "summarize_after": 5},
        })
        cfg = load_config(str(p))
        assert cfg.memory.db_path == "/tmp/test.db"
        assert cfg.memory.summarize_after == 5

    def test_features_config_loaded(self, tmp_path):
        p = write_config(tmp_path / "cfg.yaml", {
            "agent": {"llm": {"model": "openai/gpt-4o"}},
            "features": {"routing": False, "memory": True, "web": True},
        })
        cfg = load_config(str(p))
        assert cfg.features.routing is False
        assert cfg.features.web is True

    def test_agent_tools_list_loaded(self, tmp_path):
        p = write_config(tmp_path / "cfg.yaml", {
            "agent": {
                "llm": {"model": "openai/gpt-4o"},
                "tools": ["shell", "file_read"],
            }
        })
        cfg = load_config(str(p))
        assert cfg.agent.tools == ["shell", "file_read"]

    def test_agent_prompt_loaded(self, tmp_path):
        p = write_config(tmp_path / "cfg.yaml", {
            "agent": {
                "llm": {"model": "openai/gpt-4o"},
                "prompt": "You are a helpful bot.",
            }
        })
        cfg = load_config(str(p))
        assert cfg.agent.prompt == "You are a helpful bot."

    def test_cwd_emo_yaml_discovered(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("EMO_CONFIG", raising=False)
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "nohome"))
        write_config(tmp_path / ".emo.yaml", {
            "agent": {"llm": {"model": "openai/gpt-4o-mini"}}
        })
        cfg = load_config()
        assert cfg.model == "openai/gpt-4o-mini"
