"""Supervisor — routes user messages to the most appropriate sub-agent.

Extending the supervisor
------------------------
Register additional agents at runtime::

    supervisor.register("analyst", AnalystAgent)
    # or with a pre-built instance:
    supervisor.register_instance("analyst", my_analyst)

Change the default fallback agent::

    supervisor.default = "analyst"

Swap the routing logic entirely by subclassing::

    class MyRouter(Supervisor):
        def _classify(self, user_input: str) -> str:
            # keyword-based routing, no LLM call
            if "code" in user_input.lower():
                return "code"
            return "general"
"""

from __future__ import annotations

from typing import Type

from emo.agent.base_agent import BaseAgent
from emo.memory import BaseMemory, BasePersistentMemory
from emo.providers import BaseLLMProvider


_ROUTING_PROMPT = """\
You are a routing assistant. Given the user's message, decide which specialist \
agent should handle it.

Agents:
- general: general conversation, personal tasks, planning, writing, questions
- code: writing code, debugging, refactoring, shell commands, devops, file operations
- research: looking things up on the web, summarising articles, fact-finding

Reply with ONLY one word: general, code, or research."""


class Supervisor:
    """Routes requests to the appropriate sub-agent.

    Agents are lazily instantiated from their class the first time they are
    needed, so registering a new agent type is zero-cost until it is used.

    Args:
        provider: Shared :class:`~emo.providers.BaseLLMProvider` instance.
        session: Shared :class:`~emo.memory.BaseMemory` — all agents use the
            same session so history is preserved across agent switches.
        memory: Shared :class:`~emo.memory.BasePersistentMemory` instance.
        extra_context: Skills / memory block injected into every agent's prompt.
        default: Name of the fallback agent (default ``"general"``).
    """

    def __init__(
        self,
        provider: BaseLLMProvider,
        session: BaseMemory,
        memory: BasePersistentMemory,
        extra_context: str = "",
        default: str = "general",
    ) -> None:
        self.provider = provider
        self.session = session
        self.memory = memory
        self.extra_context = extra_context
        self.default = default

        # Maps name → agent class (registered but not yet instantiated)
        self._agent_classes: dict[str, Type[BaseAgent]] = {}
        # Maps name → live agent instance (created on first use)
        self._agent_instances: dict[str, BaseAgent] = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, name: str, agent_class: Type[BaseAgent]) -> None:
        """Register an agent class under *name*.

        The agent is instantiated lazily on first use. Any existing instance
        for this name is cleared so the new class takes effect immediately.
        """
        self._agent_classes[name] = agent_class
        self._agent_instances.pop(name, None)  # drop stale instance if any

    def register_instance(self, name: str, agent: BaseAgent) -> None:
        """Register a pre-built agent instance directly."""
        self._agent_instances[name] = agent

    def update_context(self, extra_context: str) -> None:
        """Push updated context (skills / memory) to all live agent instances."""
        self.extra_context = extra_context
        for agent in self._agent_instances.values():
            agent.extra_context = extra_context

    # ── Routing ───────────────────────────────────────────────────────────────

    def route(self, user_input: str) -> tuple[str, BaseAgent]:
        """Classify *user_input* and return ``(agent_name, agent)``."""
        name = self._classify(user_input)
        return name, self.get_agent(name)

    def get_agent(self, name: str) -> BaseAgent:
        """Return the agent for *name*, instantiating it on first access."""
        # Prefer live instance
        if name in self._agent_instances:
            return self._agent_instances[name]
        # Try to instantiate from registered class
        if name in self._agent_classes:
            instance = self._agent_classes[name](
                provider=self.provider,
                session=self.session,
                memory=self.memory,
                extra_context=self.extra_context,
            )
            self._agent_instances[name] = instance
            return instance
        # Fall back to default
        return self.get_agent(self.default)

    @property
    def agent_names(self) -> list[str]:
        """Names of all registered agents."""
        return list(dict.fromkeys(list(self._agent_classes) + list(self._agent_instances)))

    # ── Routing logic (overridable) ───────────────────────────────────────────

    def _classify(self, user_input: str) -> str:
        """Ask the LLM to classify the request. Returns a registered agent name."""
        try:
            text = self.provider.complete_simple([
                {"role": "system", "content": _ROUTING_PROMPT},
                {"role": "user", "content": user_input},
            ]).lower().strip()
            if text in self._agent_classes or text in self._agent_instances:
                return text
        except Exception:  # noqa: BLE001
            pass
        return self.default
