"""Tests for emo.providers — BaseLLMProvider, LiteLLMProvider, LLMResponse, ToolCall."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call
from types import SimpleNamespace

import pytest

from emo.providers import (
    BaseLLMProvider,
    LiteLLMProvider,
    LLMResponse,
    ToolCall,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_config(
    model="openai/gpt-4o",
    api_base=None,
    api_key=None,
    temperature=0.7,
):
    cfg = MagicMock()
    cfg.litellm_model = model
    cfg.api_base = api_base
    cfg.api_key = api_key
    cfg.temperature = temperature
    return cfg


def _litellm_response(content="hello", tool_calls=None):
    """Build a fake litellm blocking response."""
    msg = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
    )
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


def _stream_chunks(tokens, tool_call_deltas=None):
    """Yield fake streaming chunks."""
    for token in tokens:
        delta = SimpleNamespace(content=token, tool_calls=None)
        yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])
    if tool_call_deltas:
        for tc_delta in tool_call_deltas:
            delta = SimpleNamespace(content=None, tool_calls=[tc_delta])
            yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


# ── LLMResponse & ToolCall data classes ──────────────────────────────────────

class TestDataClasses:
    def test_llm_response_defaults(self):
        r = LLMResponse()
        assert r.content == ""
        assert r.tool_calls == []

    def test_llm_response_with_values(self):
        tc = ToolCall(id="tc1", name="shell", arguments='{"command":"ls"}')
        r = LLMResponse(content="done", tool_calls=[tc])
        assert r.content == "done"
        assert len(r.tool_calls) == 1
        assert r.tool_calls[0].name == "shell"

    def test_tool_call_fields(self):
        tc = ToolCall(id="x", name="file_read", arguments='{"path":"/tmp/f"}')
        assert tc.id == "x"
        assert tc.name == "file_read"
        assert tc.arguments == '{"path":"/tmp/f"}'


# ── BaseLLMProvider contract ──────────────────────────────────────────────────

class TestBaseLLMProvider:
    def test_cannot_instantiate_without_complete(self):
        with pytest.raises(TypeError):
            class Bad(BaseLLMProvider):
                def complete_simple(self, messages): return ""
            Bad()

    def test_cannot_instantiate_without_complete_simple(self):
        with pytest.raises(TypeError):
            class Bad(BaseLLMProvider):
                def complete(self, messages, tools=None, stream_callback=None):
                    return LLMResponse()
            Bad()

    def test_custom_provider_works(self):
        class ConstProvider(BaseLLMProvider):
            def complete(self, messages, tools=None, stream_callback=None):
                return LLMResponse(content="constant")
            def complete_simple(self, messages):
                return "constant"

        p = ConstProvider()
        r = p.complete([{"role": "user", "content": "hi"}])
        assert r.content == "constant"
        assert p.complete_simple([]) == "constant"


# ── LiteLLMProvider ───────────────────────────────────────────────────────────

class TestLiteLLMProvider:
    def test_base_kwargs_no_extras(self):
        cfg = make_config()
        p = LiteLLMProvider(cfg)
        kwargs = p._base_kwargs()
        assert kwargs["model"] == "openai/gpt-4o"
        assert kwargs["temperature"] == 0.7
        assert "api_base" not in kwargs
        assert "api_key" not in kwargs

    def test_base_kwargs_with_api_base_and_key(self):
        cfg = make_config(api_base="https://openrouter.ai/api/v1", api_key="sk-test")
        p = LiteLLMProvider(cfg)
        kwargs = p._base_kwargs()
        assert kwargs["api_base"] == "https://openrouter.ai/api/v1"
        assert kwargs["api_key"] == "sk-test"

    # complete — blocking path

    def test_complete_blocking_text_only(self, mocker):
        cfg = make_config()
        p = LiteLLMProvider(cfg)
        mocker.patch(
            "emo.providers.litellm.completion",
            return_value=_litellm_response(content="hello world"),
        )
        result = p.complete([{"role": "user", "content": "hi"}])
        assert isinstance(result, LLMResponse)
        assert result.content == "hello world"
        assert result.tool_calls == []

    def test_complete_blocking_with_tool_calls(self, mocker):
        raw_tc = SimpleNamespace(
            id="tc1",
            function=SimpleNamespace(name="shell", arguments='{"command":"ls"}'),
        )
        response = _litellm_response(content="", tool_calls=[raw_tc])
        mocker.patch("emo.providers.litellm.completion", return_value=response)

        cfg = make_config()
        p = LiteLLMProvider(cfg)
        result = p.complete([], tools=[{"type": "function"}])
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "tc1"
        assert result.tool_calls[0].name == "shell"
        assert result.tool_calls[0].arguments == '{"command":"ls"}'

    def test_complete_passes_tools_and_tool_choice(self, mocker):
        mock_completion = mocker.patch(
            "emo.providers.litellm.completion",
            return_value=_litellm_response(),
        )
        schemas = [{"type": "function", "function": {"name": "shell"}}]
        cfg = make_config()
        p = LiteLLMProvider(cfg)
        p.complete([], tools=schemas)

        _, kwargs = mock_completion.call_args
        assert kwargs.get("tools") == schemas or mock_completion.call_args[1].get("tools") == schemas

    # complete — streaming path

    def test_complete_streaming_calls_callback(self, mocker):
        chunks = list(_stream_chunks(["hel", "lo", " world"]))
        mocker.patch("emo.providers.litellm.completion", return_value=iter(chunks))

        received = []
        cfg = make_config()
        p = LiteLLMProvider(cfg)
        result = p.complete([], stream_callback=received.append)

        assert result.content == "hello world"
        assert received == ["hel", "lo", " world"]

    def test_complete_streaming_accumulates_tool_calls(self, mocker):
        # Simulate streaming tool call deltas across three chunks
        tc_delta0 = SimpleNamespace(
            index=0,
            id="tc1",
            function=SimpleNamespace(name="shell", arguments=""),
        )
        tc_delta1 = SimpleNamespace(
            index=0,
            id=None,
            function=SimpleNamespace(name="", arguments='{"command":'),
        )
        tc_delta2 = SimpleNamespace(
            index=0,
            id=None,
            function=SimpleNamespace(name="", arguments='"ls"}'),
        )
        chunks = list(_stream_chunks([], tool_call_deltas=[tc_delta0, tc_delta1, tc_delta2]))
        mocker.patch("emo.providers.litellm.completion", return_value=iter(chunks))

        cfg = make_config()
        p = LiteLLMProvider(cfg)
        result = p.complete([], stream_callback=lambda t: None)

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "tc1"
        assert result.tool_calls[0].name == "shell"
        assert result.tool_calls[0].arguments == '{"command":"ls"}'

    # complete_simple

    def test_complete_simple_returns_text(self, mocker):
        mocker.patch(
            "emo.providers.litellm.completion",
            return_value=_litellm_response(content="  code  "),
        )
        cfg = make_config()
        p = LiteLLMProvider(cfg)
        result = p.complete_simple([{"role": "user", "content": "classify"}])
        assert result == "code"

    def test_complete_simple_uses_low_temperature(self, mocker):
        mock_comp = mocker.patch(
            "emo.providers.litellm.completion",
            return_value=_litellm_response(content="general"),
        )
        cfg = make_config()
        p = LiteLLMProvider(cfg)
        p.complete_simple([{"role": "user", "content": "hi"}])

        call_kwargs = mock_comp.call_args[1]
        assert call_kwargs["temperature"] == 0.0
        assert call_kwargs["max_tokens"] == 10

    def test_complete_simple_returns_empty_on_error(self, mocker):
        mocker.patch(
            "emo.providers.litellm.completion",
            side_effect=Exception("API error"),
        )
        cfg = make_config()
        p = LiteLLMProvider(cfg)
        result = p.complete_simple([])
        assert result == ""

    # _parse_tool_calls

    def test_parse_tool_calls_from_objects(self):
        raw = [SimpleNamespace(
            id="tc1",
            function=SimpleNamespace(name="shell", arguments='{"command":"ls"}'),
        )]
        result = LiteLLMProvider._parse_tool_calls(raw)
        assert len(result) == 1
        assert result[0].id == "tc1"

    def test_parse_tool_calls_from_dicts(self):
        raw = [{"id": "tc2", "function": {"name": "file_read", "arguments": '{"path":"/tmp"}'}}]
        result = LiteLLMProvider._parse_tool_calls(raw)
        assert len(result) == 1
        assert result[0].name == "file_read"

    def test_parse_tool_calls_none(self):
        assert LiteLLMProvider._parse_tool_calls(None) == []

    def test_parse_tool_calls_empty(self):
        assert LiteLLMProvider._parse_tool_calls([]) == []
