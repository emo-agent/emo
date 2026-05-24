"""Config file discovery, YAML parsing, deep-merging, and coercion."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from emo.config.defaults import DEFAULT_ROOT
from emo.config.models import (
    AgentConfig,
    FeaturesConfig,
    LLMConfig,
    MCPConfig,
    MemoryConfig,
    PrivilegeConfig,
    RootConfig,
    RouterConfig,
)


# ---------------------------------------------------------------------------
# Deep merge
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """Return a new dict with *override* recursively merged into *base*."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# Coercion: raw dict → typed dataclasses
# ---------------------------------------------------------------------------

def _coerce_llm(data: dict[str, Any]) -> LLMConfig:
    return LLMConfig(
        model=data.get("model"),
        api_base=data.get("api_base"),
        api_key=data.get("api_key"),
        temperature=float(data.get("temperature", 0.7)),
        max_tokens=data.get("max_tokens"),
        max_iterations=int(data.get("max_iterations", 20)),
        context_window=int(data.get("context_window", 40000)),
    )


def _coerce_mcp(data: dict[str, Any]) -> MCPConfig:
    known = {"name", "type"}
    return MCPConfig(
        name=data.get("name", ""),
        type=data.get("type", "local"),
        extra={k: v for k, v in data.items() if k not in known},
    )


def _coerce_privilege(data: dict[str, Any]) -> PrivilegeConfig:
    return PrivilegeConfig(
        path=data.get("path", ""),
        read=bool(data.get("read", True)),
        write=bool(data.get("write", False)),
        execute=bool(data.get("execute", False)),
    )


def _coerce_agent(data: dict[str, Any], name: str = "") -> AgentConfig:
    llm_data = data.get("llm", {})
    tools = data.get("tools")
    if isinstance(tools, list) and len(tools) == 0:
        tools = None  # empty list → all tools

    return AgentConfig(
        name=data.get("name", name),
        llm=_coerce_llm(llm_data),
        prompt=data.get("prompt"),
        tools=tools,
        mcps=[_coerce_mcp(m) for m in data.get("mcps", [])],
        skills=list(data.get("skills", [])),
        privileges=[_coerce_privilege(p) for p in data.get("privileges", [])],
        subagents=list(data.get("subagents", [])),
    )


def _coerce_router(data: dict[str, Any]) -> RouterConfig:
    from emo.config.defaults import DEFAULT_ROUTER_LLM
    llm_data = _deep_merge(DEFAULT_ROUTER_LLM, data.get("llm", {}))
    return RouterConfig(
        enabled=bool(data.get("enabled", True)),
        llm=_coerce_llm(llm_data),
        agents=list(data.get("agents", ["general", "code", "research"])),
        default=data.get("default", "general"),
    )


def _coerce_root(data: dict[str, Any], config_path: Path | None = None) -> RootConfig:
    mem_data = data.get("memory", {})
    feat_data = data.get("features", {})
    agent = _coerce_agent(data.get("agent", {}))
    router = _coerce_router(data.get("router", {}))

    # Router LLM inherits connection settings from agent.llm when not set explicitly.
    # This means users only need to configure model/api_base/api_key once.
    router_llm_data = data.get("router", {}).get("llm", {})
    if not router_llm_data.get("model"):
        router.llm.model = agent.llm.model
    if not router_llm_data.get("api_base"):
        router.llm.api_base = agent.llm.api_base
    if not router_llm_data.get("api_key"):
        router.llm.api_key = agent.llm.api_key

    return RootConfig(
        agent=agent,
        router=router,
        memory=MemoryConfig(
            db_path=str(mem_data.get("db_path", "~/.emo/memory.db")),
            max_facts=int(mem_data.get("max_facts", 200)),
            summarize_after=int(mem_data.get("summarize_after", 10)),
        ),
        features=FeaturesConfig(
            routing=bool(feat_data.get("routing", True)),
            memory=bool(feat_data.get("memory", True)),
            web=bool(feat_data.get("web", False)),
        ),
        web=dict(data.get("web", {})),
        config_path=config_path,
    )


# ---------------------------------------------------------------------------
# File discovery and loading
# ---------------------------------------------------------------------------

def _candidate_paths(path: str | Path | None) -> list[Path]:
    """Return config file candidates ordered highest → lowest priority."""
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path).expanduser())
    env = os.environ.get("EMO_CONFIG")
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path.cwd() / ".emo.yaml")
    candidates.append(Path.home() / ".emo" / "config.yaml")
    return candidates


def _migrate_v1(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate flat v0.1 config to nested v0.2 schema in-place (returns new dict)."""
    if "model" not in data and "api_base" not in data:
        return data  # already v0.2 or empty

    data = data.copy()
    agent_llm: dict[str, Any] = data.setdefault("agent", {}).setdefault("llm", {})  # type: ignore[union-attr]

    for key in ("model", "api_base", "api_key"):
        if key in data and not agent_llm.get(key):
            agent_llm[key] = data.pop(key)

    # Flat agent keys (temperature, max_iterations, context_window)
    agent_section: dict[str, Any] = data["agent"]
    for key in ("temperature", "max_iterations", "context_window"):
        if key in data and not agent_llm.get(key):
            agent_llm[key] = data.pop(key)
        elif key in agent_section and not agent_llm.get(key):
            agent_llm[key] = agent_section.pop(key)

    # supervisor.enabled → router.enabled
    sup = data.pop("supervisor", None)
    if sup and isinstance(sup, dict) and "enabled" in sup:
        data.setdefault("router", {})["enabled"] = sup["enabled"]  # type: ignore[index]

    # skills_dir stays at root — already handled by _coerce_root via RootConfig
    return data


def load_config(path: str | Path | None = None) -> RootConfig:
    """Load and merge all config files, returning a typed :class:`RootConfig`.

    Search order (highest → lowest priority):

    1. Explicit ``path`` argument
    2. ``EMO_CONFIG`` env var
    3. ``.emo.yaml`` in current working directory
    4. ``~/.emo/config.yaml``

    All found files are collected then merged lowest → highest priority so
    that higher-priority values always win.  The ``config_path`` on the
    returned object points to the highest-priority file found.
    """
    candidates = _candidate_paths(path)

    found: list[tuple[Path, dict[str, Any]]] = []
    for candidate in candidates:
        if candidate.exists():
            with candidate.open() as f:
                loaded = yaml.safe_load(f) or {}
            found.append((candidate, _migrate_v1(loaded)))

    # Merge lowest → highest priority
    merged: dict[str, Any] = DEFAULT_ROOT.copy()
    for _cfg_path, cfg_data in reversed(found):
        merged = _deep_merge(merged, cfg_data)

    highest_path = found[0][0] if found else None
    return _coerce_root(merged, config_path=highest_path)
