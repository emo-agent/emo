"""emo.config — configuration loading and typed models.

Public API
----------
::

    from emo.config import load_config, RootConfig, AgentConfig, ConfigError

    cfg = load_config()            # auto-discover config files
    cfg = load_config("my.yaml")   # explicit path
"""

from __future__ import annotations


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


# Re-export the full public surface
from emo.config.models import (  # noqa: E402  (after ConfigError definition)
    AgentConfig,
    FeaturesConfig,
    LLMConfig,
    MCPConfig,
    MemoryConfig,
    PrivilegeConfig,
    RootConfig,
    RouterConfig,
)
from emo.config.loader import load_config, _deep_merge  # noqa: E402

# Legacy alias — some internal code imports Config directly
Config = RootConfig

__all__ = [
    "load_config",
    "ConfigError",
    # typed models
    "RootConfig",
    "Config",          # legacy alias
    "AgentConfig",
    "LLMConfig",
    "MCPConfig",
    "MemoryConfig",
    "PrivilegeConfig",
    "FeaturesConfig",
    "RouterConfig",
    # internals re-exported for tests
    "_deep_merge",
]
