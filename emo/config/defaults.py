"""Default configuration values for Emo.

These are the baseline dicts that all YAML files are merged on top of.
Keeping them here (not in models.py) means models stay pure dataclasses
with no magic default logic.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Default raw dicts — these mirror the YAML schema exactly.
# load_config() deep-merges user YAML on top of these before coercing
# into typed dataclasses.
# ---------------------------------------------------------------------------

DEFAULT_LLM: dict[str, Any] = {
    "model": None,
    "api_base": None,
    "api_key": None,
    "temperature": 0.7,
    "max_tokens": None,
    "max_iterations": 20,
    "context_window": 40000,
}

DEFAULT_ROUTER_LLM: dict[str, Any] = {
    **DEFAULT_LLM,
    "temperature": 0.0,
    "max_tokens": 10,
}

DEFAULT_AGENT: dict[str, Any] = {
    "name": "",
    "llm": DEFAULT_LLM,
    "prompt": None,
    "tools": None,      # None = all registered tools
    "mcps": [],
    "skills": [],
    "privileges": [],
    "subagents": [],
}

DEFAULT_ROUTER: dict[str, Any] = {
    "enabled": True,
    "llm": DEFAULT_ROUTER_LLM,
    "agents": ["general", "code", "research"],
    "default": "general",
}

DEFAULT_MEMORY: dict[str, Any] = {
    "db_path": "~/.emo/memory.db",
    "max_facts": 200,
    "summarize_after": 10,
}

DEFAULT_FEATURES: dict[str, Any] = {
    "routing": True,
    "memory": True,
    "web": False,
}

DEFAULT_ROOT: dict[str, Any] = {
    "agent": DEFAULT_AGENT,
    "router": DEFAULT_ROUTER,
    "memory": DEFAULT_MEMORY,
    "features": DEFAULT_FEATURES,
    "web": {},
}
