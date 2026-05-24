"""Configuration loader for Emo."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


# No default model — user must configure one. This prevents litellm from
# trying a provider the user never intended based on a hardcoded fallback.
_DEFAULT_CONFIG: dict[str, Any] = {
    "model": None,
    "api_base": None,
    "api_key": None,
    "agent": {
        "max_iterations": 20,
        "context_window": 40000,
        "temperature": 0.7,
    },
    "memory": {
        "db_path": "~/.emo/memory.db",
        "max_facts": 200,
        "summarize_after": 10,
    },
    "tools": {
        "shell": True,
        "file_read": True,
        "file_write": True,
        "web_fetch": True,
    },
    "skills_dir": "~/.emo/skills",
    "supervisor": {
        "enabled": True,
        "agents": ["general", "code", "research"],
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


class Config:
    """Holds resolved configuration for Emo."""

    def __init__(self, data: dict[str, Any], config_path: Path | None = None) -> None:
        self._data = data
        self.config_path = config_path  # path of the loaded file, if any

    def get(self, *keys: str, default: Any = None) -> Any:
        node = self._data
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k, default)
        return node

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    @property
    def model(self) -> str:
        """Raw model string from config. Raises ConfigError if not set."""
        val = self.get("model", default=None)
        if not val:
            raise ConfigError(
                "No model configured.\n\n"
                "Run [bold]emo setup[/bold] to create a config, or add to your config.yaml:\n\n"
                "  # OpenRouter example:\n"
                "  model: \"google/gemini-2.0-flash-001\"\n"
                "  api_base: \"https://openrouter.ai/api/v1\"\n"
                "  api_key: \"sk-or-...\"\n\n"
                "  # Direct OpenAI:\n"
                "  model: \"openai/gpt-4o\"\n\n"
                "  # Direct Anthropic:\n"
                "  model: \"anthropic/claude-3-5-sonnet-20241022\"\n\n"
                f"Config file location: {self.config_path or '~/.emo/config.yaml'}"
            )
        return val

    @property
    def litellm_model(self) -> str:
        """Model string to pass to litellm.

        When api_base is set (OpenRouter / custom endpoint), the model name
        must be prefixed with 'openai/' so litellm routes through its
        OpenAI-compatible path. If the user already added the prefix,
        we don't double it.

        When api_base is NOT set, the model is used as-is (litellm's normal
        routing: openai/gpt-4o, anthropic/claude-..., ollama/..., etc.)
        """
        m = self.model  # raises ConfigError if not set
        if self.api_base:
            if m.startswith("openai/"):
                return m
            return f"openai/{m}"
        return m

    @property
    def api_base(self) -> str | None:
        """Custom OpenAI-compatible base URL."""
        val = self.get("api_base", default=None)
        return val or os.environ.get("OPENAI_API_BASE") or os.environ.get("EMO_API_BASE") or None

    @property
    def api_key(self) -> str | None:
        """API key — config file value, then env vars."""
        val = self.get("api_key", default=None)
        return val or os.environ.get("OPENAI_API_KEY") or os.environ.get("EMO_API_KEY") or None

    @property
    def temperature(self) -> float:
        return self.get("agent", "temperature", default=0.7)

    @property
    def max_iterations(self) -> int:
        return self.get("agent", "max_iterations", default=20)

    @property
    def context_window(self) -> int:
        return self.get("agent", "context_window", default=40000)

    @property
    def memory_db_path(self) -> Path:
        raw = self.get("memory", "db_path", default="~/.emo/memory.db")
        return Path(raw).expanduser()

    @property
    def skills_dir(self) -> Path:
        raw = self.get("skills_dir", default="~/.emo/skills")
        return Path(raw).expanduser()

    @property
    def tools_enabled(self) -> dict[str, bool]:
        return self.get("tools", default={})

    @property
    def supervisor_enabled(self) -> bool:
        return self.get("supervisor", "enabled", default=True)


def load_config(path: Path | str | None = None) -> Config:
    """Load config from file, merging with defaults.

    Search order:
      1. Explicit path argument
      2. EMO_CONFIG env var
      3. ./config.yaml (cwd)
      4. ~/.emo/config.yaml
    """
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path).expanduser())
    env = os.environ.get("EMO_CONFIG")
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path.cwd() / "config.yaml")
    candidates.append(Path.home() / ".emo" / "config.yaml")

    user_data: dict[str, Any] = {}
    found_path: Path | None = None
    for candidate in candidates:
        if candidate.exists():
            with candidate.open() as f:
                loaded = yaml.safe_load(f) or {}
            user_data = loaded
            found_path = candidate
            break

    merged = _deep_merge(_DEFAULT_CONFIG, user_data)
    return Config(merged, config_path=found_path)
