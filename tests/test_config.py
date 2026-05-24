"""Tests for emo.config — load_config(), Config, ConfigError."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from emo.config import Config, ConfigError, load_config


# ── Helpers ───────────────────────────────────────────────────────────────────

def write_config(path: Path, data: dict) -> Path:
    path.write_text(yaml.dump(data))
    return path


# ── Config property accessors ─────────────────────────────────────────────────

class TestConfigProperties:
    def make(self, overrides: dict) -> Config:
        from emo.config import _DEFAULT_CONFIG, _deep_merge
        return Config(_deep_merge(_DEFAULT_CONFIG, overrides))

    def test_model_returns_value(self):
        cfg = self.make({"model": "openai/gpt-4o"})
        assert cfg.model == "openai/gpt-4o"

    def test_model_raises_on_missing(self):
        cfg = self.make({"model": None})
        with pytest.raises(ConfigError):
            _ = cfg.model

    def test_litellm_model_no_api_base(self):
        cfg = self.make({"model": "openai/gpt-4o"})
        assert cfg.litellm_model == "openai/gpt-4o"

    def test_litellm_model_with_api_base_prepends_openai(self):
        cfg = self.make({"model": "google/gemini-2.0-flash", "api_base": "https://openrouter.ai/api/v1"})
        assert cfg.litellm_model == "openai/google/gemini-2.0-flash"

    def test_litellm_model_with_api_base_no_double_prefix(self):
        cfg = self.make({"model": "openai/gpt-4o", "api_base": "https://openrouter.ai/api/v1"})
        assert cfg.litellm_model == "openai/gpt-4o"

    def test_temperature_default(self):
        cfg = self.make({})
        assert cfg.temperature == 0.7

    def test_temperature_override(self):
        cfg = self.make({"agent": {"temperature": 0.2}})
        assert cfg.temperature == 0.2

    def test_max_iterations_default(self):
        cfg = self.make({})
        assert cfg.max_iterations == 20

    def test_context_window_default(self):
        cfg = self.make({})
        assert cfg.context_window == 40000

    def test_memory_db_path(self):
        cfg = self.make({"memory": {"db_path": "~/.emo/memory.db"}})
        assert cfg.memory_db_path == Path.home() / ".emo" / "memory.db"

    def test_skills_dir(self):
        cfg = self.make({"skills_dir": "~/.emo/skills"})
        assert cfg.skills_dir == Path.home() / ".emo" / "skills"

    def test_supervisor_enabled_default(self):
        cfg = self.make({})
        assert cfg.supervisor_enabled is True

    def test_supervisor_disabled(self):
        cfg = self.make({"supervisor": {"enabled": False}})
        assert cfg.supervisor_enabled is False

    def test_tools_enabled(self):
        cfg = self.make({"tools": {"shell": False, "web_fetch": True}})
        enabled = cfg.tools_enabled
        assert enabled["shell"] is False
        assert enabled["web_fetch"] is True

    def test_api_base_from_config(self):
        cfg = self.make({"api_base": "https://example.com"})
        assert cfg.api_base == "https://example.com"

    def test_api_base_from_env(self, monkeypatch):
        from emo.config import _DEFAULT_CONFIG, _deep_merge
        monkeypatch.setenv("OPENAI_API_BASE", "https://from-env.com")
        cfg = Config(_deep_merge(_DEFAULT_CONFIG, {"model": "openai/gpt-4o"}))
        assert cfg.api_base == "https://from-env.com"

    def test_api_key_from_config(self):
        cfg = self.make({"api_key": "sk-test"})
        assert cfg.api_key == "sk-test"

    def test_api_key_from_openai_env(self, monkeypatch):
        from emo.config import _DEFAULT_CONFIG, _deep_merge
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        cfg = Config(_deep_merge(_DEFAULT_CONFIG, {"model": "openai/gpt-4o"}))
        assert cfg.api_key == "sk-env"

    def test_api_key_from_emo_env(self, monkeypatch):
        from emo.config import _DEFAULT_CONFIG, _deep_merge
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("EMO_API_KEY", "sk-emo")
        cfg = Config(_deep_merge(_DEFAULT_CONFIG, {"model": "openai/gpt-4o"}))
        assert cfg.api_key == "sk-emo"

    def test_get_nested(self):
        cfg = self.make({"agent": {"temperature": 0.5}})
        assert cfg.get("agent", "temperature") == 0.5

    def test_get_missing_returns_default(self):
        cfg = self.make({})
        assert cfg.get("nonexistent", default="fallback") == "fallback"

    def test_contains(self):
        cfg = self.make({"model": "openai/gpt-4o"})
        assert "model" in cfg
        assert "missing_key" not in cfg


# ── load_config ───────────────────────────────────────────────────────────────

class TestLoadConfig:
    def test_load_from_explicit_path(self, tmp_path):
        p = write_config(tmp_path / "my.yaml", {"model": "anthropic/claude-3-5-sonnet-20241022"})
        cfg = load_config(str(p))
        assert cfg.model == "anthropic/claude-3-5-sonnet-20241022"

    def test_load_merges_with_defaults(self, tmp_path):
        p = write_config(tmp_path / "cfg.yaml", {"model": "openai/gpt-4o"})
        cfg = load_config(str(p))
        # Default values still present
        assert cfg.max_iterations == 20
        assert cfg.temperature == 0.7

    def test_load_from_env_var(self, tmp_path, monkeypatch):
        p = write_config(tmp_path / "env.yaml", {"model": "openai/gpt-4o-mini"})
        monkeypatch.setenv("EMO_CONFIG", str(p))
        cfg = load_config()   # no path arg — should pick up env var
        assert cfg.model == "openai/gpt-4o-mini"

    def test_explicit_path_takes_priority_over_env(self, tmp_path, monkeypatch):
        p_env = write_config(tmp_path / "env.yaml", {"model": "openai/gpt-4o-mini"})
        p_explicit = write_config(tmp_path / "explicit.yaml", {"model": "openai/gpt-4o"})
        monkeypatch.setenv("EMO_CONFIG", str(p_env))
        cfg = load_config(str(p_explicit))
        assert cfg.model == "openai/gpt-4o"

    def test_no_config_file_returns_defaults(self, tmp_path, monkeypatch):
        # Ensure none of the candidate paths exist
        monkeypatch.delenv("EMO_CONFIG", raising=False)
        monkeypatch.chdir(tmp_path)   # cwd has no config.yaml
        # Override home to avoid picking up real ~/.emo/config.yaml
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        cfg = load_config()
        assert cfg.get("model") is None   # no model configured — that's ok

    def test_deep_merge_preserves_nested_defaults(self, tmp_path):
        # User overrides only temperature; other agent settings should survive
        p = write_config(tmp_path / "cfg.yaml", {
            "model": "openai/gpt-4o",
            "agent": {"temperature": 0.1},
        })
        cfg = load_config(str(p))
        assert cfg.temperature == 0.1
        assert cfg.max_iterations == 20   # default preserved

    def test_config_path_stored(self, tmp_path):
        p = write_config(tmp_path / "cfg.yaml", {"model": "openai/gpt-4o"})
        cfg = load_config(str(p))
        assert cfg.config_path == p
