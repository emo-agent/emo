"""LLM provider abstraction — BaseLLMProvider and LiteLLMProvider.

Extending providers
-------------------
Implement :class:`BaseLLMProvider` to swap the underlying LLM SDK::

    class OpenAIProvider(BaseLLMProvider):
        def complete(self, messages, tools=None, stream_callback=None):
            ...
        def complete_simple(self, messages):
            ...

    agent = MyAgent(provider=OpenAIProvider(...), ...)

The two methods an agent needs:

* :meth:`complete` — full agentic call; may stream tokens and returns a
  ``LLMResponse`` with optional tool_calls.
* :meth:`complete_simple` — cheap single-turn call; returns only the text
  content (used by the supervisor for routing).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

import litellm

from emo.config import Config


litellm.set_verbose = False  # suppress litellm debug output


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class ToolCall:
    """A single tool invocation requested by the LLM."""
    id: str
    name: str
    arguments: str  # raw JSON string


@dataclass
class LLMResponse:
    """Normalised response from any provider."""
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


# ── Base interface ────────────────────────────────────────────────────────────

class BaseLLMProvider(ABC):
    """Abstract LLM provider.

    Implement this to add a new backend (OpenAI SDK, Anthropic SDK, etc.)
    without touching any agent code.
    """

    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream_callback: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        """Send *messages* to the LLM and return a normalised response.

        Args:
            messages: Conversation history in OpenAI format.
            tools: Optional list of tool schemas (OpenAI function-calling format).
            stream_callback: If provided, called with each text token as it
                arrives. The provider should still return the complete response.
        """

    @abstractmethod
    def complete_simple(self, messages: list[dict[str, Any]]) -> str:
        """Cheap single-turn completion — returns text only.

        Used by the supervisor for intent routing. No tools, no streaming.
        """


# ── LiteLLM provider ─────────────────────────────────────────────────────────

class LiteLLMProvider(BaseLLMProvider):
    """Provider backed by litellm — supports 100+ models via one interface.

    Pass a :class:`~emo.config.Config` object; the provider reads
    ``model``, ``api_base``, ``api_key``, and ``temperature`` from it.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def _base_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.config.litellm_model,
            "temperature": self.config.temperature,
        }
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        return kwargs

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream_callback: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        if stream_callback:
            return self._stream(messages, tools, stream_callback)
        return self._blocking(messages, tools)

    def complete_simple(self, messages: list[dict[str, Any]]) -> str:
        kwargs = self._base_kwargs()
        kwargs["messages"] = messages
        kwargs["temperature"] = 0.0
        kwargs["max_tokens"] = 10
        try:
            response = litellm.completion(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception:  # noqa: BLE001
            return ""

    # ── Private helpers ───────────────────────────────────────────────────────

    def _blocking(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> LLMResponse:
        kwargs = self._base_kwargs()
        kwargs["messages"] = messages
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = litellm.completion(**kwargs)
        msg = response.choices[0].message
        text = msg.content or ""
        tool_calls = self._parse_tool_calls(msg.tool_calls if hasattr(msg, "tool_calls") else None)
        return LLMResponse(content=text, tool_calls=tool_calls)

    def _stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        callback: Callable[[str], None],
    ) -> LLMResponse:
        kwargs = self._base_kwargs()
        kwargs["messages"] = messages
        kwargs["stream"] = True
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = litellm.completion(**kwargs)

        full_text = ""
        tc_accum: dict[int, dict] = {}

        for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                full_text += delta.content
                callback(delta.content)

            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tc_accum:
                        tc_accum[idx] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                    if tc_delta.id:
                        tc_accum[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc_accum[idx]["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc_accum[idx]["function"]["arguments"] += tc_delta.function.arguments

        raw_tool_calls = list(tc_accum.values()) if tc_accum else None
        tool_calls = self._parse_tool_calls(raw_tool_calls)
        return LLMResponse(content=full_text, tool_calls=tool_calls)

    @staticmethod
    def _parse_tool_calls(raw: Any) -> list[ToolCall]:
        if not raw:
            return []
        result = []
        for tc in raw:
            # Handles both object-style (from blocking) and dict-style (from streaming)
            if isinstance(tc, dict):
                result.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                ))
            else:
                result.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                ))
        return result
