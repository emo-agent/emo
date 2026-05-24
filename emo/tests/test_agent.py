"""Tests for emo.agent.base_agent — BaseAgent ReAct loop."""

from __future__ import annotations

from unittest.mock import MagicMock

from emo.agent.agents import CodeAgent, GeneralAgent, ResearchAgent
from emo.agent.base_agent import BaseAgent
from emo.memory import PersistentMemory, SessionMemory
from emo.providers import BaseLLMProvider, LLMResponse, ToolCall
from emo.tools import BaseTool

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_provider(*responses: LLMResponse) -> BaseLLMProvider:
    """Return a mock provider that yields each LLMResponse in order."""
    provider = MagicMock(spec=BaseLLMProvider)
    provider.complete.side_effect = list(responses)
    return provider


def make_deps(tmp_path=None):
    session = SessionMemory()
    if tmp_path:
        memory = PersistentMemory(tmp_path / "test.db")
    else:
        import pathlib
        import tempfile

        _td = tempfile.mkdtemp()
        memory = PersistentMemory(pathlib.Path(_td) / "test.db")
    return session, memory


class UpperTool(BaseTool):
    name = "upper"
    description = "Uppercases text."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def run(self, text: str) -> str:
        return text.upper()


# ── BaseAgent — basic run ─────────────────────────────────────────────────────


class TestBaseAgentRun:
    def test_plain_text_reply(self, tmp_path):
        provider = make_provider(LLMResponse(content="Hello!"))
        session, memory = make_deps(tmp_path)
        agent = GeneralAgent(provider=provider, session=session, memory=memory)

        reply = agent.run("hi")
        assert reply == "Hello!"

    def test_user_message_added_to_session(self, tmp_path):
        provider = make_provider(LLMResponse(content="ok"))
        session, memory = make_deps(tmp_path)
        agent = GeneralAgent(provider=provider, session=session, memory=memory)

        agent.run("test question")
        msgs = session.get()
        assert any(
            m["role"] == "user" and m["content"] == "test question" for m in msgs
        )

    def test_assistant_reply_added_to_session(self, tmp_path):
        provider = make_provider(LLMResponse(content="my answer"))
        session, memory = make_deps(tmp_path)
        agent = GeneralAgent(provider=provider, session=session, memory=memory)

        agent.run("q")
        msgs = session.get()
        assert any(
            m["role"] == "assistant" and m["content"] == "my answer" for m in msgs
        )

    def test_session_is_cumulative(self, tmp_path):
        provider = make_provider(
            LLMResponse(content="first"),
            LLMResponse(content="second"),
        )
        session, memory = make_deps(tmp_path)
        agent = GeneralAgent(provider=provider, session=session, memory=memory)

        agent.run("q1")
        agent.run("q2")
        msgs = session.get()
        roles = [m["role"] for m in msgs]
        assert roles.count("user") == 2
        assert roles.count("assistant") == 2

    def test_system_prompt_included_in_messages(self, tmp_path):
        provider = make_provider(LLMResponse(content="ok"))
        session, memory = make_deps(tmp_path)
        agent = GeneralAgent(provider=provider, session=session, memory=memory)
        agent.run("hi")

        call_args = provider.complete.call_args
        messages = call_args[0][0]  # first positional arg
        assert messages[0]["role"] == "system"
        assert agent.system_prompt in messages[0]["content"]

    def test_extra_context_appended_to_system_prompt(self, tmp_path):
        provider = make_provider(LLMResponse(content="ok"))
        session, memory = make_deps(tmp_path)
        agent = GeneralAgent(
            provider=provider,
            session=session,
            memory=memory,
            extra_context="## Extra instructions",
        )
        agent.run("hi")

        call_args = provider.complete.call_args
        system_content = call_args[0][0][0]["content"]
        assert "## Extra instructions" in system_content

    def test_no_extra_context_when_empty(self, tmp_path):
        provider = make_provider(LLMResponse(content="ok"))
        session, memory = make_deps(tmp_path)
        agent = GeneralAgent(
            provider=provider, session=session, memory=memory, extra_context=""
        )
        agent.run("hi")

        call_args = provider.complete.call_args
        system_content = call_args[0][0][0]["content"]
        # No double-newline artifact from empty extra_context
        assert not system_content.endswith("\n\n")


# ── Tool calls ────────────────────────────────────────────────────────────────


class TestBaseAgentToolCalls:
    def _make_agent_with_tool(self, provider, tmp_path, monkeypatch=None):
        """Agent wired to an isolated registry containing only UpperTool."""
        session, memory = make_deps(tmp_path)
        agent = GeneralAgent(
            provider=provider,
            session=session,
            memory=memory,
            tool_names=["upper"],
        )
        agent._tools = [UpperTool()]
        return agent, session

    def test_tool_call_dispatched_and_result_added(self, tmp_path, monkeypatch):
        from emo.tools import registry as global_reg

        # Register UpperTool into the global registry for this test only
        global_reg.register(UpperTool())

        tc = ToolCall(id="tc1", name="upper", arguments='{"text":"hello"}')
        provider = make_provider(
            LLMResponse(content="", tool_calls=[tc]),  # first: tool call
            LLMResponse(content="HELLO"),  # second: final reply
        )
        agent, session = self._make_agent_with_tool(provider, tmp_path)

        reply = agent.run("shout hello")
        assert reply == "HELLO"

        msgs = session.get()
        tool_msgs = [m for m in msgs if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["name"] == "upper"
        assert tool_msgs[0]["content"] == "HELLO"

    def test_on_token_callback_receives_text_tokens(self, tmp_path):
        provider = make_provider(LLMResponse(content="streamed"))
        session, memory = make_deps(tmp_path)
        agent = GeneralAgent(provider=provider, session=session, memory=memory)

        # Provider calls the stream_callback when provided — simulate it
        def streaming_complete(messages, tools=None, stream_callback=None):
            if stream_callback:
                stream_callback("streamed")
            return LLMResponse(content="streamed")

        provider.complete.side_effect = streaming_complete

        tokens = []
        agent.run("hi", on_token=tokens.append)
        assert "streamed" in tokens

    def test_on_token_callback_receives_tool_preview(self, tmp_path):
        from emo.tools import registry as global_reg

        global_reg.register(UpperTool())

        tc = ToolCall(id="tc1", name="upper", arguments='{"text":"hi"}')

        call_count = 0
        tokens = []

        def side_effect(messages, tools=None, stream_callback=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LLMResponse(content="", tool_calls=[tc])
            return LLMResponse(content="HI")

        provider = MagicMock(spec=BaseLLMProvider)
        provider.complete.side_effect = side_effect

        agent, _ = self._make_agent_with_tool(provider, tmp_path)
        agent.run("shout hi", on_token=tokens.append)

        # At least one token should mention the tool name
        tool_tokens = [t for t in tokens if "upper" in t]
        assert tool_tokens

    def test_max_iterations_returns_fallback(self, tmp_path):
        from emo.tools import registry as global_reg

        global_reg.register(UpperTool())

        # Provider always returns a tool call → loop never terminates naturally
        tc = ToolCall(id="tc1", name="upper", arguments='{"text":"x"}')
        provider = MagicMock(spec=BaseLLMProvider)
        provider.complete.return_value = LLMResponse(content="", tool_calls=[tc])

        agent, session = self._make_agent_with_tool(provider, tmp_path)
        agent.max_iterations = 3

        reply = agent.run("loop forever")
        assert "maximum" in reply.lower()
        assert provider.complete.call_count == 3


# ── Tool resolution ───────────────────────────────────────────────────────────


class TestToolResolution:
    def test_code_agent_has_correct_tools(self, tmp_path):
        provider = MagicMock(spec=BaseLLMProvider)
        session, memory = make_deps(tmp_path)
        agent = CodeAgent(provider=provider, session=session, memory=memory)
        names = {t.name for t in agent._tools}
        assert names == {"shell", "file_read", "file_write"}

    def test_research_agent_has_correct_tools(self, tmp_path):
        provider = MagicMock(spec=BaseLLMProvider)
        session, memory = make_deps(tmp_path)
        agent = ResearchAgent(provider=provider, session=session, memory=memory)
        names = {t.name for t in agent._tools}
        assert names == {"web_fetch", "file_read", "file_write"}

    def test_general_agent_has_all_tools(self, tmp_path):
        provider = MagicMock(spec=BaseLLMProvider)
        session, memory = make_deps(tmp_path)
        agent = GeneralAgent(provider=provider, session=session, memory=memory)
        names = {t.name for t in agent._tools}
        assert {"shell", "file_read", "file_write", "web_fetch"}.issubset(names)

    def test_instance_tool_names_override_class(self, tmp_path):
        provider = MagicMock(spec=BaseLLMProvider)
        session, memory = make_deps(tmp_path)
        agent = GeneralAgent(
            provider=provider,
            session=session,
            memory=memory,
            tool_names=["shell"],
        )
        names = {t.name for t in agent._tools}
        assert names == {"shell"}


# ── build_system_prompt hook ──────────────────────────────────────────────────


class TestBuildSystemPrompt:
    def test_default_combines_prompt_and_context(self, tmp_path):
        provider = MagicMock(spec=BaseLLMProvider)
        session, memory = make_deps(tmp_path)
        agent = GeneralAgent(
            provider=provider,
            session=session,
            memory=memory,
            extra_context="EXTRA",
        )
        prompt = agent.build_system_prompt()
        assert agent.system_prompt in prompt
        assert "EXTRA" in prompt

    def test_override_build_system_prompt(self, tmp_path):
        provider = MagicMock(spec=BaseLLMProvider)
        session, memory = make_deps(tmp_path)

        class CustomAgent(BaseAgent):
            name = "custom"
            system_prompt = "base"
            tool_names = None

            def build_system_prompt(self):
                return "completely custom"

        agent = CustomAgent(provider=provider, session=session, memory=memory)
        assert agent.build_system_prompt() == "completely custom"


# ── repr ──────────────────────────────────────────────────────────────────────


class TestRepr:
    def test_repr_includes_name_and_tools(self, tmp_path):
        provider = MagicMock(spec=BaseLLMProvider)
        session, memory = make_deps(tmp_path)
        agent = CodeAgent(provider=provider, session=session, memory=memory)
        r = repr(agent)
        assert "CodeAgent" in r
        assert "code" in r
        assert "shell" in r
