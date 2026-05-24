"""Supervisor — routes user messages to the most appropriate sub-agent.

The supervisor is now config-driven.  Agent definitions come from
:class:`~emo.config.AgentConfig` objects (loaded from YAML files by
:mod:`emo.agent.loader`).  The routing LLM call uses the parameters from
:class:`~emo.config.RouterConfig`.

Quick-start::

    from emo.agent.loader import ensure_default_agents, load_agent_configs
    from emo.agent.supervisor import Supervisor

    ensure_default_agents()
    agent_configs = load_agent_configs(root_config)
    supervisor = Supervisor(
        provider=provider,
        session=session_memory,
        memory=persistent_memory,
        router_config=root_config.router,
        agent_configs=agent_configs,
    )

Extending — register additional agents at runtime::

    supervisor.register_config("analyst", my_analyst_agent_config)
    # or with a pre-built instance:
    supervisor.register_instance("analyst", my_analyst_agent)

Swap the routing logic by subclassing::

    class MyRouter(Supervisor):
        def _classify(self, user_input: str) -> str:
            return "code" if "code" in user_input.lower() else "general"
"""

from __future__ import annotations

from typing import Type

from emo.agent.base_agent import BaseAgent
from emo.config.models import AgentConfig, RouterConfig
from emo.memory import BaseMemory, BasePersistentMemory
from emo.providers import BaseLLMProvider


_ROUTING_PROMPT_TEMPLATE = """\
You are a routing assistant. Given the user's message, decide which specialist \
agent should handle it.

Agents:
{agent_list}

Reply with ONLY one word — the name of the agent."""


class Supervisor:
    """Routes requests to the appropriate sub-agent.

    Agents can be registered as:
    - :class:`~emo.config.AgentConfig` objects (YAML-driven, preferred)
    - :class:`~emo.agent.base_agent.BaseAgent` subclasses (legacy, still supported)
    - Pre-built :class:`~emo.agent.base_agent.BaseAgent` instances

    All are lazily instantiated — registering is zero-cost until first use.

    Args:
        provider: Shared :class:`~emo.providers.BaseLLMProvider`.
        session: Shared session memory — all agents use the same history.
        memory: Shared persistent memory.
        router_config: :class:`~emo.config.RouterConfig` that controls routing
            LLM params and the list of routable agent names.
        agent_configs: Dict of ``{name: AgentConfig}`` pre-loaded from YAML.
        extra_context: Skills / memory block injected into every agent's prompt.
        default: Fallback agent name when routing fails.
    """

    def __init__(
        self,
        provider: BaseLLMProvider,
        session: BaseMemory,
        memory: BasePersistentMemory,
        router_config: RouterConfig | None = None,
        agent_configs: dict[str, AgentConfig] | None = None,
        extra_context: str = "",
        default: str = "general",
    ) -> None:
        self.provider = provider
        self.session = session
        self.memory = memory
        self.router_config = router_config or RouterConfig()
        self.extra_context = extra_context
        self.default = router_config.default if router_config else default

        # Maps name → AgentConfig (YAML-driven agents)
        self._agent_configs: dict[str, AgentConfig] = dict(agent_configs or {})
        # Maps name → agent class (legacy subclass registration)
        self._agent_classes: dict[str, Type[BaseAgent]] = {}
        # Maps name → live agent instance (created on first use)
        self._agent_instances: dict[str, BaseAgent] = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def register_config(self, name: str, agent_config: AgentConfig) -> None:
        """Register a YAML-driven :class:`~emo.config.AgentConfig`."""
        self._agent_configs[name] = agent_config
        self._agent_instances.pop(name, None)

    def register(self, name: str, agent_class: Type[BaseAgent]) -> None:
        """Register a legacy agent class.  Lazily instantiated on first use."""
        self._agent_classes[name] = agent_class
        self._agent_instances.pop(name, None)

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
        if name in self._agent_instances:
            return self._agent_instances[name]

        # Prefer AgentConfig (YAML-driven)
        if name in self._agent_configs:
            instance = BaseAgent(
                provider=self.provider,
                session=self.session,
                memory=self.memory,
                agent_config=self._agent_configs[name],
                extra_context=self.extra_context,
            )
            self._agent_instances[name] = instance
            return instance

        # Legacy class-based registration
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
        if name != self.default:
            return self.get_agent(self.default)
        raise RuntimeError(f"Default agent {self.default!r} is not registered.")

    @property
    def agent_names(self) -> list[str]:
        """Names of all registered agents (configs, classes, and instances)."""
        return list(
            dict.fromkeys(
                list(self._agent_configs)
                + list(self._agent_classes)
                + list(self._agent_instances)
            )
        )

    # ── Routing logic (overridable) ───────────────────────────────────────────

    def _classify(self, user_input: str) -> str:
        """Ask the LLM to classify the request. Returns a registered agent name."""
        # Build the agent list from router_config.agents filtered to what's registered
        routable = [n for n in self.router_config.agents if n in self.agent_names]
        if not routable:
            routable = self.agent_names[:3]  # fallback: first three registered

        agent_descriptions = self._agent_descriptions()
        agent_list = "\n".join(
            f"- {name}: {agent_descriptions.get(name, 'specialist agent')}"
            for name in routable
        )
        routing_prompt = _ROUTING_PROMPT_TEMPLATE.format(agent_list=agent_list)

        # Use router's own LLM params for the routing call
        router_llm = self.router_config.llm
        try:
            text = self.provider.complete_simple(
                [
                    {"role": "system", "content": routing_prompt},
                    {"role": "user", "content": user_input},
                ],
                temperature=router_llm.temperature,
                max_tokens=router_llm.max_tokens or 10,
            ).lower().strip()
            if text in self._agent_configs or text in self._agent_classes or text in self._agent_instances:
                return text
        except Exception:  # noqa: BLE001
            pass
        return self.default

    def _agent_descriptions(self) -> dict[str, str]:
        """Return short descriptions for routable agents from their prompts."""
        descriptions: dict[str, str] = {
            "general": "general conversation, personal tasks, planning, writing, questions",
            "code": "writing code, debugging, refactoring, shell commands, devops, file operations",
            "research": "looking things up on the web, summarising articles, fact-finding",
        }
        # Override with first line of prompt from AgentConfig when available
        for name, cfg in self._agent_configs.items():
            if cfg.prompt:
                first_line = cfg.prompt.strip().splitlines()[0].strip()
                if first_line:
                    descriptions[name] = first_line
        return descriptions
