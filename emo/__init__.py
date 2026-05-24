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

    supervisor = Supervisor(provider, session, memory)

Extending the framework
-----------------------
- **New tool**:    subclass :class:`~emo.tools.BaseTool` or use ``@tool``
- **New agent**:   subclass :class:`~emo.agent.BaseAgent`
- **New memory**:  implement :class:`~emo.memory.BaseMemory` /
                   :class:`~emo.memory.BasePersistentMemory`
- **New provider**: implement :class:`~emo.providers.BaseLLMProvider`
"""

__version__ = "0.1.0"

# Convenience re-exports so ``from emo import X`` works for the most common types
from emo.config import load_config, Config, ConfigError
from emo.providers import BaseLLMProvider, LiteLLMProvider, LLMResponse, ToolCall
from emo.memory import BaseMemory, BasePersistentMemory, SessionMemory, PersistentMemory
from emo.tools import BaseTool, registry, tool
from emo.agent import BaseAgent, Supervisor, GeneralAgent, CodeAgent, ResearchAgent

__all__ = [
    # config
    "load_config", "Config", "ConfigError",
    # providers
    "BaseLLMProvider", "LiteLLMProvider", "LLMResponse", "ToolCall",
    # memory
    "BaseMemory", "BasePersistentMemory", "SessionMemory", "PersistentMemory",
    # tools
    "BaseTool", "registry", "tool",
    # agents
    "BaseAgent", "Supervisor", "GeneralAgent", "CodeAgent", "ResearchAgent",
]
