"""YAML-based agent discovery and configuration loading.

Agent config files are discovered in two locations (merged lowest → highest
priority, so project-level files override global ones):

  1. ``~/.emo/agents/<name>.yaml``   — global per-user agents
  2. ``.emo/agents/<name>.yaml``     — project-local agents (cwd)

On first startup, if ``~/.emo/agents/`` doesn't exist or is missing any of
the three built-in agents, the bundled default YAMLs (``emo/agent/defaults/``)
are copied there automatically.

Usage::

    from emo.agent.loader import load_agent_configs, ensure_default_agents

    ensure_default_agents()          # call once at startup
    agents = load_agent_configs(root_config)
    # agents: dict[str, AgentConfig]
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from emo.config.loader import _deep_merge, _coerce_agent
from emo.config.models import AgentConfig, RootConfig


# Directory containing the bundled default YAML files shipped with the package
_DEFAULTS_DIR = Path(__file__).parent / "defaults"

_BUILTIN_NAMES = ("general", "code", "research")


def ensure_default_agents(agents_dir: Path | None = None) -> None:
    """Create ``~/.emo/agents/`` and write missing built-in agent YAMLs.

    Safe to call on every startup — it only writes files that don't exist yet.

    Args:
        agents_dir: Override the destination directory (used in tests).
    """
    dest = agents_dir or (Path.home() / ".emo" / "agents")
    dest.mkdir(parents=True, exist_ok=True)

    for name in _BUILTIN_NAMES:
        target = dest / f"{name}.yaml"
        if not target.exists():
            src = _DEFAULTS_DIR / f"{name}.yaml"
            if src.exists():
                shutil.copy2(src, target)


def _load_yaml_file(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _agent_files_in_dir(directory: Path) -> dict[str, Path]:
    """Return ``{name: path}`` for all ``*.yaml`` files in *directory*."""
    if not directory.exists():
        return {}
    return {p.stem: p for p in sorted(directory.glob("*.yaml"))}


def load_agent_configs(
    root_config: RootConfig,
    global_agents_dir: Path | None = None,
    local_agents_dir: Path | None = None,
) -> dict[str, AgentConfig]:
    """Discover and build :class:`~emo.config.AgentConfig` for every agent.

    Merge stack for each agent (lowest → highest priority):

    1. ``root_config.agent`` — shared default from main config
    2. ``~/.emo/agents/<name>.yaml`` — global per-user override
    3. ``.emo/agents/<name>.yaml`` (cwd) — project-local override

    Args:
        root_config: The resolved top-level config (provides the shared default).
        global_agents_dir: Override ``~/.emo/agents/`` (used in tests).
        local_agents_dir: Override ``.emo/agents/`` in cwd (used in tests).

    Returns:
        Dict mapping agent name → :class:`~emo.config.AgentConfig`.
    """
    global_dir = global_agents_dir or (Path.home() / ".emo" / "agents")
    local_dir = local_agents_dir or (Path.cwd() / ".emo" / "agents")

    # Collect all agent names across both directories
    global_files = _agent_files_in_dir(global_dir)
    local_files = _agent_files_in_dir(local_dir)
    all_names = dict.fromkeys(list(global_files) + list(local_files))  # preserves order, dedupes

    # Convert the shared AgentConfig default back to a plain dict for merging
    import dataclasses
    shared_default = _agent_config_to_dict(root_config.agent)

    result: dict[str, AgentConfig] = {}
    for name in all_names:
        merged = shared_default.copy()

        # Layer 1: global file
        if name in global_files:
            merged = _deep_merge(merged, _load_yaml_file(global_files[name]))

        # Layer 2: local file (highest priority)
        if name in local_files:
            merged = _deep_merge(merged, _load_yaml_file(local_files[name]))

        result[name] = _coerce_agent(merged, name=name)
        result[name].name = name  # always use filename as canonical name

    return result


def _agent_config_to_dict(cfg: AgentConfig) -> dict[str, Any]:
    """Convert an AgentConfig dataclass to a plain dict suitable for merging."""
    import dataclasses
    d = dataclasses.asdict(cfg)
    # Strip MCPConfig.extra back to the top-level dict structure that YAML uses
    mcps_out = []
    for mcp in d.get("mcps", []):
        entry = {k: v for k, v in mcp.items() if k != "extra"}
        entry.update(mcp.get("extra", {}))
        mcps_out.append(entry)
    d["mcps"] = mcps_out
    return d
