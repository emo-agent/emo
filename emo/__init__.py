"""Emo — lightweight personal AI agent framework.

Quick-start
-----------
::

    from emo.config import load_config
    from emo.providers import LiteLLMProvider
    from emo.memory import SessionMemory, PersistentMemory
    from emo.agent import BaseAgent, Supervisor
    from emo.tools import BaseTool, registry

    config = load_config()
    provider = LiteLLMProvider(config)
    session = SessionMemory(config.context_window)
    memory = PersistentMemory(config.memory_db_path)

    supervisor = Supervisor(provider, session, memory, router_config=config.router)

Extending the framework
-----------------------
- **New tool**:    subclass :class:`~emo.tools.BaseTool` or use ``@tool``
- **New agent**:   drop a YAML file in ``~/.emo/agents/`` or ``.emo/agents/``
- **New memory**:  implement :class:`~emo.memory.BaseMemory` /
                   :class:`~emo.memory.BasePersistentMemory`
- **New provider**: implement :class:`~emo.providers.BaseLLMProvider`
"""

__version__ = "0.2.0"

from emo.agent import BaseAgent, Supervisor
from emo.agent.agents import CodeAgent, GeneralAgent, ResearchAgent
from emo.config import (
    AgentConfig,
    ConfigError,
    LLMConfig,
    RootConfig,
    RouterConfig,
    load_config,
)
from emo.config import RootConfig as Config  # legacy alias
from emo.memory import BaseMemory, BasePersistentMemory, PersistentMemory, SessionMemory
from emo.providers import BaseLLMProvider, LiteLLMProvider, LLMResponse, ToolCall
from emo.tools import BaseTool, registry, tool

__all__ = [
    # config
    "load_config",
    "RootConfig",
    "Config",           # legacy alias
    "AgentConfig",
    "LLMConfig",
    "RouterConfig",
    "ConfigError",
    # providers
    "BaseLLMProvider",
    "LiteLLMProvider",
    "LLMResponse",
    "ToolCall",
    # memory
    "BaseMemory",
    "BasePersistentMemory",
    "SessionMemory",
    "PersistentMemory",
    # tools
    "BaseTool",
    "registry",
    "tool",
    # agents
    "BaseAgent",
    "Supervisor",
    "GeneralAgent",
    "CodeAgent",
    "ResearchAgent",
]
