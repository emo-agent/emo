"""Tests for emo.agent.loader — YAML-based agent discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from emo.agent.loader import ensure_default_agents, load_agent_configs, _BUILTIN_NAMES
from emo.config import AgentConfig, LLMConfig, RootConfig
from emo.config.models import RouterConfig


# ── Helpers ───────────────────────────────────────────────────────────────────

def write_agent(directory: Path, name: str, data: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / f"{name}.yaml"
    p.write_text(yaml.dump(data))
    return p


def make_root(model: str = "openai/gpt-4o", temperature: float = 0.7) -> RootConfig:
    return RootConfig(
        agent=AgentConfig(llm=LLMConfig(model=model, temperature=temperature)),
        router=RouterConfig(),
    )


# ── ensure_default_agents ─────────────────────────────────────────────────────

class TestEnsureDefaultAgents:
    def test_creates_directory(self, tmp_path):
        dest = tmp_path / "agents"
        assert not dest.exists()
        ensure_default_agents(agents_dir=dest)
        assert dest.exists()

    def test_writes_all_builtin_yamls(self, tmp_path):
        dest = tmp_path / "agents"
        ensure_default_agents(agents_dir=dest)
        for name in _BUILTIN_NAMES:
            assert (dest / f"{name}.yaml").exists()

    def test_does_not_overwrite_existing(self, tmp_path):
        dest = tmp_path / "agents"
        dest.mkdir()
        custom = dest / "general.yaml"
        custom.write_text("prompt: custom")
        ensure_default_agents(agents_dir=dest)
        assert custom.read_text() == "prompt: custom"

    def test_idempotent(self, tmp_path):
        dest = tmp_path / "agents"
        ensure_default_agents(agents_dir=dest)
        ensure_default_agents(agents_dir=dest)  # second call should not fail
        for name in _BUILTIN_NAMES:
            assert (dest / f"{name}.yaml").exists()


# ── load_agent_configs — discovery ───────────────────────────────────────────

class TestLoadAgentConfigsDiscovery:
    def test_loads_agents_from_global_dir(self, tmp_path):
        global_dir = tmp_path / "global"
        write_agent(global_dir, "analyst", {"prompt": "You are an analyst."})
        root = make_root()
        configs = load_agent_configs(root, global_agents_dir=global_dir, local_agents_dir=tmp_path / "local")
        assert "analyst" in configs

    def test_loads_agents_from_local_dir(self, tmp_path):
        local_dir = tmp_path / "local"
        write_agent(local_dir, "reviewer", {"prompt": "You are a reviewer."})
        root = make_root()
        configs = load_agent_configs(root, global_agents_dir=tmp_path / "global", local_agents_dir=local_dir)
        assert "reviewer" in configs

    def test_agents_from_both_dirs_merged_into_one_dict(self, tmp_path):
        global_dir = tmp_path / "global"
        local_dir = tmp_path / "local"
        write_agent(global_dir, "alpha", {"prompt": "global alpha"})
        write_agent(local_dir, "beta", {"prompt": "local beta"})
        root = make_root()
        configs = load_agent_configs(root, global_agents_dir=global_dir, local_agents_dir=local_dir)
        assert "alpha" in configs
        assert "beta" in configs

    def test_returns_empty_when_no_dirs_exist(self, tmp_path):
        root = make_root()
        configs = load_agent_configs(
            root,
            global_agents_dir=tmp_path / "noexist_g",
            local_agents_dir=tmp_path / "noexist_l",
        )
        assert configs == {}


# ── load_agent_configs — merge priority ──────────────────────────────────────

class TestLoadAgentConfigsMergePriority:
    def test_local_overrides_global(self, tmp_path):
        global_dir = tmp_path / "global"
        local_dir = tmp_path / "local"
        write_agent(global_dir, "myagent", {"prompt": "global prompt", "llm": {"temperature": 0.5}})
        write_agent(local_dir, "myagent", {"llm": {"temperature": 0.1}})
        root = make_root()
        configs = load_agent_configs(root, global_agents_dir=global_dir, local_agents_dir=local_dir)
        agent = configs["myagent"]
        # Local temperature wins
        assert agent.llm.temperature == 0.1
        # Global prompt is preserved (local file didn't override it)
        assert agent.prompt == "global prompt"

    def test_shared_default_is_base(self, tmp_path):
        global_dir = tmp_path / "global"
        write_agent(global_dir, "myagent", {"prompt": "custom"})
        # Root config sets temperature = 0.3 as shared default
        root = make_root(temperature=0.3)
        configs = load_agent_configs(root, global_agents_dir=global_dir, local_agents_dir=tmp_path / "local")
        agent = configs["myagent"]
        # Agent file didn't set temperature → inherits from shared default
        assert agent.llm.temperature == 0.3

    def test_agent_file_overrides_shared_default_model(self, tmp_path):
        global_dir = tmp_path / "global"
        write_agent(global_dir, "myagent", {"llm": {"model": "anthropic/claude-3-haiku-20240307"}})
        root = make_root(model="openai/gpt-4o")
        configs = load_agent_configs(root, global_agents_dir=global_dir, local_agents_dir=tmp_path / "local")
        agent = configs["myagent"]
        assert agent.llm.model == "anthropic/claude-3-haiku-20240307"

    def test_tools_list_overridden(self, tmp_path):
        global_dir = tmp_path / "global"
        write_agent(global_dir, "coder", {"tools": ["shell", "file_read"]})
        root = make_root()
        configs = load_agent_configs(root, global_agents_dir=global_dir, local_agents_dir=tmp_path / "local")
        assert configs["coder"].tools == ["shell", "file_read"]

    def test_name_set_from_filename(self, tmp_path):
        global_dir = tmp_path / "global"
        write_agent(global_dir, "mybot", {"prompt": "I am mybot."})
        root = make_root()
        configs = load_agent_configs(root, global_agents_dir=global_dir, local_agents_dir=tmp_path / "local")
        assert configs["mybot"].name == "mybot"


# ── AgentConfig coercion ──────────────────────────────────────────────────────

class TestAgentConfigCoercion:
    def test_empty_tools_list_becomes_none(self, tmp_path):
        """An empty tools list in YAML should mean 'all tools' (None)."""
        global_dir = tmp_path / "global"
        write_agent(global_dir, "agent", {"tools": []})
        root = make_root()
        configs = load_agent_configs(root, global_agents_dir=global_dir, local_agents_dir=tmp_path / "local")
        assert configs["agent"].tools is None

    def test_privileges_coerced(self, tmp_path):
        global_dir = tmp_path / "global"
        write_agent(global_dir, "secure", {
            "privileges": [{"path": "/tmp", "read": True, "write": False}]
        })
        root = make_root()
        configs = load_agent_configs(root, global_agents_dir=global_dir, local_agents_dir=tmp_path / "local")
        priv = configs["secure"].privileges[0]
        assert priv.path == "/tmp"
        assert priv.read is True
        assert priv.write is False

    def test_mcps_coerced(self, tmp_path):
        global_dir = tmp_path / "global"
        write_agent(global_dir, "mcp_agent", {
            "mcps": [{"name": "myserver", "type": "local", "command": "npx myserver"}]
        })
        root = make_root()
        configs = load_agent_configs(root, global_agents_dir=global_dir, local_agents_dir=tmp_path / "local")
        mcp = configs["mcp_agent"].mcps[0]
        assert mcp.name == "myserver"
        assert mcp.type == "local"
        assert mcp.extra.get("command") == "npx myserver"
