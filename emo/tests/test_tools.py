"""Tests for emo.tools — BaseTool, ToolRegistry, @tool decorator, built-ins."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from emo.tools import (
    BaseTool,
    ToolRegistry,
    registry as global_registry,
    tool,
    ShellTool,
    FileReadTool,
    FileWriteTool,
    WebFetchTool,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

class EchoTool(BaseTool):
    name = "echo"
    description = "Returns its input."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def run(self, text: str) -> str:
        return text


class ErrorTool(BaseTool):
    name = "error_tool"
    description = "Always raises."
    parameters = {"type": "object", "properties": {}, "required": []}

    def run(self) -> str:
        raise ValueError("intentional error")


# ── BaseTool ──────────────────────────────────────────────────────────────────

class TestBaseTool:
    def test_schema_structure(self):
        t = EchoTool()
        s = t.schema()
        assert s["type"] == "function"
        assert s["function"]["name"] == "echo"
        assert s["function"]["description"] == "Returns its input."
        assert "properties" in s["function"]["parameters"]

    def test_call_delegates_to_run(self):
        t = EchoTool()
        assert t(text="hello") == "hello"

    def test_repr(self):
        assert "echo" in repr(EchoTool())

    def test_cannot_instantiate_without_run(self):
        with pytest.raises(TypeError):
            class BadTool(BaseTool):
                name = "bad"
            BadTool()  # abstract — no run()


# ── ToolRegistry ──────────────────────────────────────────────────────────────

class TestToolRegistry:
    def setup_method(self):
        # Fresh isolated registry for each test
        self.reg = ToolRegistry()

    def test_register_and_get(self):
        self.reg.register(EchoTool())
        t = self.reg.get("echo")
        assert isinstance(t, EchoTool)

    def test_get_missing_returns_none(self):
        assert self.reg.get("nonexistent") is None

    def test_get_all_no_filter(self):
        self.reg.register(EchoTool())
        self.reg.register(ErrorTool())
        assert len(self.reg.get_all()) == 2

    def test_get_all_with_enabled_filter(self):
        self.reg.register(EchoTool())
        self.reg.register(ErrorTool())
        result = self.reg.get_all(enabled={"echo": True, "error_tool": False})
        names = [t.name for t in result]
        assert "echo" in names
        assert "error_tool" not in names

    def test_get_all_defaults_missing_keys_to_true(self):
        self.reg.register(EchoTool())
        result = self.reg.get_all(enabled={})   # empty map → all enabled
        assert len(result) == 1

    def test_contains(self):
        self.reg.register(EchoTool())
        assert "echo" in self.reg
        assert "other" not in self.reg

    def test_len(self):
        assert len(self.reg) == 0
        self.reg.register(EchoTool())
        assert len(self.reg) == 1

    def test_schemas(self):
        self.reg.register(EchoTool())
        schemas = self.reg.schemas()
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"

    def test_schemas_subset(self):
        echo = EchoTool()
        err = ErrorTool()
        self.reg.register(echo)
        self.reg.register(err)
        schemas = self.reg.schemas([echo])
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "echo"

    # dispatch

    def test_dispatch_string_args(self):
        self.reg.register(EchoTool())
        result = self.reg.dispatch("echo", '{"text": "hi"}')
        assert result == "hi"

    def test_dispatch_dict_args(self):
        self.reg.register(EchoTool())
        result = self.reg.dispatch("echo", {"text": "hi"})
        assert result == "hi"

    def test_dispatch_unknown_tool(self):
        result = self.reg.dispatch("ghost", "{}")
        assert "unknown tool" in result.lower()

    def test_dispatch_tool_error_returns_string(self):
        self.reg.register(ErrorTool())
        result = self.reg.dispatch("error_tool", "{}")
        assert "Error" in result
        assert "intentional error" in result

    def test_dispatch_none_result_returns_done(self):
        class NullTool(BaseTool):
            name = "null"
            description = ""
            parameters = {"type": "object", "properties": {}, "required": []}
            def run(self): return None

        self.reg.register(NullTool())
        assert self.reg.dispatch("null", "{}") == "Done."

    def test_register_returns_tool(self):
        t = EchoTool()
        returned = self.reg.register(t)
        assert returned is t


# ── @tool decorator ───────────────────────────────────────────────────────────

class TestToolDecorator:
    def setup_method(self):
        # Use a fresh registry so decorator tests don't pollute global state
        self.reg = ToolRegistry()

    def test_decorator_with_args(self):
        @tool(
            name="add",
            description="Adds two numbers.",
            parameters={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
        )
        def add(a: int, b: int) -> str:
            return str(a + b)

        # Manually register into isolated registry for assertion
        # (global registry also got it, but we test the returned function)
        assert callable(add)
        assert add(a=2, b=3) == "5"   # original function still works

    def test_decorator_no_args(self):
        @tool
        def greet(name: str) -> str:
            """Greets someone."""
            return f"Hello {name}"

        assert callable(greet)
        assert greet(name="World") == "Hello World"

    def test_global_registry_has_decorated_tools(self):
        # Built-in tools registered at module import time
        assert "shell" in global_registry
        assert "file_read" in global_registry
        assert "file_write" in global_registry
        assert "web_fetch" in global_registry


# ── Built-in tools ────────────────────────────────────────────────────────────

class TestShellTool:
    def setup_method(self):
        self.tool = ShellTool()

    def test_simple_command(self):
        result = self.tool.run(command="echo hello")
        assert "hello" in result

    def test_stderr_included(self):
        result = self.tool.run(command="echo err >&2")
        assert "err" in result

    def test_nonzero_exit_code_reported(self):
        result = self.tool.run(command="exit 1")
        assert "exit code: 1" in result

    def test_no_output(self):
        result = self.tool.run(command="true")
        assert result == "(no output)"

    def test_timeout_parameter(self):
        result = self.tool.run(command="echo ok", timeout=5)
        assert "ok" in result


class TestFileReadTool:
    def setup_method(self):
        self.tool = FileReadTool()

    def test_read_existing_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("line1\nline2\nline3")
        result = self.tool.run(path=str(f))
        assert result == "line1\nline2\nline3"

    def test_max_lines(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("\n".join(str(i) for i in range(100)))
        result = self.tool.run(path=str(f), max_lines=5)
        assert result.count("\n") == 4   # 5 lines → 4 newlines

    def test_missing_file(self):
        result = self.tool.run(path="/nonexistent/path/file.txt")
        assert "Error" in result
        assert "not found" in result


class TestFileWriteTool:
    def setup_method(self):
        self.tool = FileWriteTool()

    def test_write_creates_file(self, tmp_path):
        target = tmp_path / "out.txt"
        result = self.tool.run(path=str(target), content="hello")
        assert target.read_text() == "hello"
        assert "Written" in result

    def test_write_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "a" / "b" / "c.txt"
        self.tool.run(path=str(target), content="nested")
        assert target.read_text() == "nested"

    def test_write_overwrites(self, tmp_path):
        target = tmp_path / "file.txt"
        target.write_text("old")
        self.tool.run(path=str(target), content="new")
        assert target.read_text() == "new"

    def test_reports_char_count(self, tmp_path):
        target = tmp_path / "f.txt"
        result = self.tool.run(path=str(target), content="abc")
        assert "3" in result


class TestWebFetchTool:
    def setup_method(self):
        self.tool = WebFetchTool()

    def test_successful_fetch(self, mocker):
        mock_resp = MagicMock()
        mock_resp.text = "page content"
        mock_resp.raise_for_status = MagicMock()
        mocker.patch("emo.tools.httpx.get", return_value=mock_resp)

        result = self.tool.run(url="http://example.com")
        assert result == "page content"

    def test_truncation(self, mocker):
        mock_resp = MagicMock()
        mock_resp.text = "x" * 10000
        mock_resp.raise_for_status = MagicMock()
        mocker.patch("emo.tools.httpx.get", return_value=mock_resp)

        result = self.tool.run(url="http://example.com", max_chars=100)
        assert len(result) == 103   # 100 chars + "..."
        assert result.endswith("...")

    def test_fetch_error_returns_string(self, mocker):
        mocker.patch("emo.tools.httpx.get", side_effect=Exception("connection refused"))
        result = self.tool.run(url="http://bad.invalid")
        assert "Error" in result
        assert "connection refused" in result
