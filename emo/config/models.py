"""Typed config models for Emo.

All models are plain dataclasses — no extra dependencies required.
Every field has a default so partial YAML files deep-merge cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LLMConfig:
    """LLM connection and generation parameters."""

    model: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    max_iterations: int = 20
    context_window: int = 40000


@dataclass
class MCPConfig:
    """A single MCP server definition (schema only — not yet connected)."""

    name: str = ""
    type: str = "local"   # "local" | "remote"
    # Arbitrary extra keys (command, url, env, …) stored here
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PrivilegeConfig:
    """Filesystem access rule for a path (schema only — not yet enforced)."""

    path: str = ""
    read: bool = True
    write: bool = False
    execute: bool = False


@dataclass
class AgentConfig:
    """Full configuration for a single agent."""

    name: str = ""
    llm: LLMConfig = field(default_factory=LLMConfig)
    prompt: str | None = None
    tools: list[str] | None = None          # None = all registered tools
    mcps: list[MCPConfig] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    privileges: list[PrivilegeConfig] = field(default_factory=list)
    subagents: list[str] = field(default_factory=list)


@dataclass
class RouterConfig:
    """Configuration for the supervisor / router agent."""

    enabled: bool = True
    llm: LLMConfig = field(default_factory=lambda: LLMConfig(temperature=0.0, max_tokens=10))
    agents: list[str] = field(default_factory=lambda: ["general", "code", "research"])
    default: str = "general"


@dataclass
class MemoryConfig:
    """Persistent memory settings."""

    db_path: str = "~/.emo/memory.db"
    max_facts: int = 200
    summarize_after: int = 10

    @property
    def resolved_db_path(self) -> Path:
        return Path(self.db_path).expanduser()


@dataclass
class FeaturesConfig:
    """Feature flags."""

    routing: bool = True
    memory: bool = True
    web: bool = False


@dataclass
class RootConfig:
    """Top-level resolved configuration."""

    # The shared default for every agent (also acts as base for router LLM if unset)
    agent: AgentConfig = field(default_factory=AgentConfig)
    router: RouterConfig = field(default_factory=RouterConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    web: dict[str, Any] = field(default_factory=dict)

    # Path of the highest-priority config file that was loaded (for display)
    config_path: Path | None = None

    # ── Convenience accessors ──────────────────────────────────────────────

    @property
    def litellm_model(self) -> str:
        """Model string ready for litellm.

        When ``api_base`` is set, the model must be prefixed with ``openai/``
        so litellm routes through the OpenAI-compatible path.
        """
        from emo.config.models import _require_model  # local import avoids circularity
        m = _require_model(self)
        base = self.api_base  # uses env-var fallback
        if base:
            # When api_base is set we must force litellm through its
            # OpenAI-compatible path so it respects the custom endpoint.
            # Prepend "openai/" unless it's already there — this prevents
            # litellm from parsing "deepseek/model" as provider=deepseek and
            # ignoring api_base entirely.
            return m if m.startswith("openai/") else f"openai/{m}"
        return m

    @property
    def model(self) -> str:
        from emo.config.models import _require_model
        return _require_model(self)

    @property
    def api_base(self) -> str | None:
        import os
        val = self.agent.llm.api_base
        return val or os.environ.get("OPENAI_API_BASE") or os.environ.get("EMO_API_BASE") or None

    @property
    def api_key(self) -> str | None:
        import os
        val = self.agent.llm.api_key
        return val or os.environ.get("OPENAI_API_KEY") or os.environ.get("EMO_API_KEY") or None

    # Legacy-style accessors used by providers and cli (delegation to nested config)
    @property
    def temperature(self) -> float:
        return self.agent.llm.temperature

    @property
    def max_iterations(self) -> int:
        return self.agent.llm.max_iterations

    @property
    def context_window(self) -> int:
        return self.agent.llm.context_window

    @property
    def memory_db_path(self) -> Path:
        return self.memory.resolved_db_path

    @property
    def skills_dir(self) -> Path:
        raw = self.agent.skills[0] if self.agent.skills else "~/.emo/skills"
        return Path(raw).expanduser()

    @property
    def tools_enabled(self) -> dict[str, bool]:
        """Returns a {name: True} dict for all tools listed in agent.tools.

        If agent.tools is None, all tools are considered enabled (returns {}).
        """
        if self.agent.tools is None:
            return {}
        return {name: True for name in self.agent.tools}

    @property
    def supervisor_enabled(self) -> bool:
        return self.router.enabled

    def get(self, *keys: str, default: Any = None) -> Any:
        """Backwards-compatible dot-path accessor for nested values."""
        # Build a plain dict representation for compatibility
        node: Any = _root_config_to_dict(self)
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k, default)
        return node


# ── Internal helpers ──────────────────────────────────────────────────────────

def _require_model(cfg: RootConfig) -> str:
    from emo.config import ConfigError
    val = cfg.agent.llm.model
    if not val:
        raise ConfigError(
            "No model configured.\n\n"
            "Run [bold]emo setup[/bold] to create a config, or add to your config.yaml:\n\n"
            "  agent:\n"
            "    llm:\n"
            "      model: \"google/gemini-2.0-flash-001\"\n"
            "      api_base: \"https://openrouter.ai/api/v1\"\n"
            "      api_key: \"sk-or-...\"\n\n"
            f"Config file location: {cfg.config_path or '~/.emo/config.yaml'}"
        )
    return val


def _root_config_to_dict(cfg: RootConfig) -> dict[str, Any]:
    """Shallow dict view used by the legacy .get() accessor."""
    import dataclasses
    return dataclasses.asdict(cfg)
