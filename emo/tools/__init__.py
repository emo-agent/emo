"""Tool system — BaseTool ABC, registry, decorator, and built-in tools.

Extending tools
---------------
Option 1 — subclass BaseTool::

    class MyTool(BaseTool):
        name = "my_tool"
        description = "Does something useful."
        parameters = {
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        }

        def run(self, input: str) -> str:
            return input.upper()

    registry.register(MyTool())

Option 2 — @tool decorator on a plain function::

    @tool(description="Add two numbers.")
    def add(a: int, b: int) -> str:
        return str(a + b)

    # auto-registered in the global registry
"""

from __future__ import annotations

import json
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable

import httpx


# ── Base class ────────────────────────────────────────────────────────────────

class BaseTool(ABC):
    """Abstract base for all tools.

    Subclass this and implement :meth:`run`. Set class attributes
    ``name``, ``description``, and ``parameters`` (OpenAI JSON-schema format).
    """

    name: str
    description: str = ""
    parameters: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

    @abstractmethod
    def run(self, **kwargs: Any) -> str:
        """Execute the tool and return a string result."""

    def __call__(self, **kwargs: Any) -> str:
        return self.run(**kwargs)

    def schema(self) -> dict[str, Any]:
        """Return the OpenAI function-calling JSON schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __repr__(self) -> str:
        return f"<Tool {self.name!r}>"


# ── Registry ──────────────────────────────────────────────────────────────────

class ToolRegistry:
    """Central store of available tools.

    The module exposes a global singleton ``registry``. Agents call
    :meth:`get_all` (optionally filtered by an enabled-map from config) and
    :meth:`dispatch` to execute tools by name.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> BaseTool:
        """Register a tool instance. Returns the tool (useful as a decorator target)."""
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_all(self, enabled: dict[str, bool] | None = None) -> list[BaseTool]:
        """Return registered tools, optionally filtered by an enabled map.

        If *enabled* is None every tool is returned. If it is a dict, a tool
        is included when ``enabled.get(tool.name, True)`` is truthy.
        """
        if enabled is None:
            return list(self._tools.values())
        return [t for t in self._tools.values() if enabled.get(t.name, True)]

    def dispatch(self, name: str, arguments: str | dict[str, Any]) -> str:
        """Look up *name* and call it with *arguments*. Always returns a string."""
        tool = self.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        try:
            kwargs = json.loads(arguments) if isinstance(arguments, str) else arguments
            result = tool(**kwargs)
            return str(result) if result is not None else "Done."
        except Exception as exc:  # noqa: BLE001
            return f"Error: {exc}"

    def schemas(self, tools: list[BaseTool] | None = None) -> list[dict[str, Any]]:
        """Return OpenAI-schema list for *tools* (or all registered tools)."""
        return [t.schema() for t in (tools if tools is not None else self._tools.values())]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# Global registry — import and use this in agents / extensions
registry = ToolRegistry()


# ── @tool decorator ───────────────────────────────────────────────────────────

def tool(
    fn: Callable | None = None,
    *,
    name: str | None = None,
    description: str = "",
    parameters: dict[str, Any] | None = None,
) -> Callable:
    """Register a plain function as a tool.

    Can be used with or without arguments::

        @tool
        def greet(name: str) -> str: ...

        @tool(description="Runs a shell command.", parameters={...})
        def shell(command: str) -> str: ...
    """

    def decorator(f: Callable) -> Callable:
        tool_name = name or f.__name__
        tool_desc = description or f.__doc__ or ""
        tool_params = parameters or {"type": "object", "properties": {}, "required": []}

        _fn = f  # capture for closure

        class _FnTool(BaseTool):
            def run(self, **kwargs: Any) -> str:  # type: ignore[override]
                result = _fn(**kwargs)
                return str(result) if result is not None else "Done."

        _FnTool.name = tool_name  # type: ignore[assignment]
        _FnTool.description = tool_desc  # type: ignore[assignment]
        _FnTool.parameters = tool_params  # type: ignore[assignment]

        registry.register(_FnTool())
        return f

    if fn is not None:
        # Called as @tool without parentheses
        return decorator(fn)
    return decorator


# ── Built-in tools ────────────────────────────────────────────────────────────

class ShellTool(BaseTool):
    """Run a shell command and return stdout + stderr."""

    name = "shell"
    description = "Run a shell command and return stdout + stderr. Use for system tasks, running code, git, etc."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to run"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)", "default": 30},
        },
        "required": ["command"],
    }

    def run(self, command: str, timeout: int = 30) -> str:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        parts = []
        if result.stdout.strip():
            parts.append(result.stdout.strip())
        if result.stderr.strip():
            parts.append(f"[stderr]\n{result.stderr.strip()}")
        if result.returncode != 0:
            parts.append(f"[exit code: {result.returncode}]")
        return "\n".join(parts) if parts else "(no output)"


class FileReadTool(BaseTool):
    """Read the contents of a file."""

    name = "file_read"
    description = "Read the contents of a file."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or relative file path"},
            "max_lines": {"type": "integer", "description": "Max lines to return (default: all)"},
        },
        "required": ["path"],
    }

    def run(self, path: str, max_lines: int | None = None) -> str:
        p = Path(path).expanduser()
        if not p.exists():
            return f"Error: file not found: {path}"
        text = p.read_text(errors="replace")
        if max_lines:
            return "\n".join(text.splitlines()[:max_lines])
        return text


class FileWriteTool(BaseTool):
    """Write content to a file (creates or overwrites)."""

    name = "file_write"
    description = "Write content to a file (creates or overwrites)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to write"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }

    def run(self, path: str, content: str) -> str:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Written {len(content)} chars to {path}"


class WebFetchTool(BaseTool):
    """Fetch the text content of a URL."""

    name = "web_fetch"
    description = "Fetch the text content of a URL."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch"},
            "max_chars": {"type": "integer", "description": "Max characters to return (default 8000)"},
        },
        "required": ["url"],
    }

    def run(self, url: str, max_chars: int = 8000) -> str:
        try:
            resp = httpx.get(
                url, timeout=15, follow_redirects=True,
                headers={"User-Agent": "emo-agent/0.1"},
            )
            resp.raise_for_status()
            text = resp.text
            return text[:max_chars] + ("..." if len(text) > max_chars else "")
        except Exception as exc:  # noqa: BLE001
            return f"Error fetching {url}: {exc}"


# Register all built-ins
registry.register(ShellTool())
registry.register(FileReadTool())
registry.register(FileWriteTool())
registry.register(WebFetchTool())


# ── Convenience re-exports (kept for any legacy internal usage) ───────────────

def get_tool(name: str) -> BaseTool | None:
    return registry.get(name)


def get_all_tools(enabled: dict[str, bool] | None = None) -> list[BaseTool]:
    return registry.get_all(enabled)


def tool_schemas(tools: list[BaseTool]) -> list[dict[str, Any]]:
    return registry.schemas(tools)


def dispatch_tool(name: str, arguments: str | dict) -> str:
    return registry.dispatch(name, arguments)
