"""Base agent — core LLM + tool-use loop.

Extending agents
----------------
Subclass :class:`BaseAgent` and set class attributes::

    class AnalystAgent(BaseAgent):
        name = "analyst"
        system_prompt = "You are a data analyst..."
        tool_names = ["shell", "file_read"]   # None = all tools

Then register it with the Supervisor::

    supervisor.register("analyst", AnalystAgent)

Or use it standalone::

    from emo.providers import LiteLLMProvider
    from emo.memory import SessionMemory, PersistentMemory

    provider = LiteLLMProvider(config)
    agent = AnalystAgent(
        provider=provider,
        session=SessionMemory(),
        memory=PersistentMemory(db_path),
    )
    reply = agent.run("Analyse sales.csv")
"""

from __future__ import annotations

from typing import Any, Callable

from emo.memory import BaseMemory, BasePersistentMemory, SessionMemory, PersistentMemory
from emo.providers import BaseLLMProvider, LLMResponse
from emo.tools import BaseTool, registry as _global_registry


class BaseAgent:
    """Core ReAct-style agent loop.

    All logic lives here. Subclasses only set class-level metadata:
    ``name``, ``system_prompt``, and optionally ``tool_names``.

    Constructor arguments
    ---------------------
    provider:
        Any :class:`~emo.providers.BaseLLMProvider` implementation.
    session:
        Any :class:`~emo.memory.BaseMemory` implementation.
    memory:
        Any :class:`~emo.memory.BasePersistentMemory` implementation.
    extra_context:
        Additional text appended to the system prompt (skills, memory summary).
    tool_names:
        Override the class-level ``tool_names`` for this instance.
    max_iterations:
        Maximum tool-call loops before giving up (default 20).
    """

    name: str = "base"
    system_prompt: str = "You are a helpful AI assistant."
    tool_names: list[str] | None = None   # None = all tools in registry

    def __init__(
        self,
        provider: BaseLLMProvider,
        session: BaseMemory,
        memory: BasePersistentMemory,
        extra_context: str = "",
        tool_names: list[str] | None = None,
        max_iterations: int = 20,
    ) -> None:
        self.provider = provider
        self.session = session
        self.memory = memory
        self.extra_context = extra_context
        self.max_iterations = max_iterations

        # Instance-level tool_names override class-level if provided
        effective_names = tool_names if tool_names is not None else self.tool_names
        self._tools: list[BaseTool] = self._resolve_tools(effective_names)

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        user_input: str,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """Process *user_input* and return the final assistant reply.

        Args:
            user_input: The user's message.
            on_token: Optional callback invoked with each streamed text token.
        """
        self.session.add("user", user_input)

        for _ in range(self.max_iterations):
            messages = self._build_messages()
            schemas = _global_registry.schemas(self._tools) if self._tools else None

            response: LLMResponse = self.provider.complete(
                messages,
                tools=schemas,
                stream_callback=on_token,
            )

            if not response.tool_calls:
                self.session.add("assistant", response.content)
                return response.content

            # Store assistant message with tool_calls
            self.session.add_tool_call(self._response_to_message(response))

            # Dispatch each tool and store results
            for tc in response.tool_calls:
                result = _global_registry.dispatch(tc.name, tc.arguments)
                if on_token:
                    preview = result[:200] + ("..." if len(result) > 200 else "")
                    on_token(f"\n[tool: {tc.name}] → {preview}\n")
                self.session.add_tool_result(tc.id, tc.name, result)

        fallback = "I reached the maximum number of steps. Please try a more specific request."
        self.session.add("assistant", fallback)
        return fallback

    # ── Overridable hooks ─────────────────────────────────────────────────────

    def build_system_prompt(self) -> str:
        """Return the full system prompt string.

        Override to customise how system context is assembled.
        """
        parts = [self.system_prompt]
        if self.extra_context:
            parts.append(self.extra_context)
        return "\n\n".join(parts)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_messages(self) -> list[dict[str, Any]]:
        system = {"role": "system", "content": self.build_system_prompt()}
        return [system] + self.session.get()

    def _resolve_tools(self, names: list[str] | None) -> list[BaseTool]:
        all_tools = _global_registry.get_all()
        if names is None:
            return all_tools
        return [t for t in all_tools if t.name in names]

    @staticmethod
    def _response_to_message(response: LLMResponse) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": response.content or None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in response.tool_calls
            ],
        }

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r} tools={[t.name for t in self._tools]}>"
