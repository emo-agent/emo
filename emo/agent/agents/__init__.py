"""Legacy Python agent subclasses — kept for backwards compatibility.

As of v0.2, agents are defined in YAML files (``~/.emo/agents/*.yaml`` or
``.emo/agents/*.yaml``).  These Python classes still work and can be
registered with the :class:`~emo.agent.supervisor.Supervisor` via
``supervisor.register(name, AgentClass)``, but the preferred approach is to
use YAML-driven :class:`~emo.config.AgentConfig` objects discovered by
:mod:`emo.agent.loader`.

Adding a new agent (YAML, preferred)
-------------------------------------
Create ``~/.emo/agents/myagent.yaml``::

    prompt: "You are a specialist in..."
    tools:
      - file_read
      - shell
    llm:
      temperature: 0.3

Adding a new agent (Python, legacy)
-------------------------------------
::

    from emo.agent import BaseAgent

    class AnalystAgent(BaseAgent):
        name = "analyst"
        system_prompt = "You are a data analyst..."
        tool_names = ["shell", "file_read"]

    supervisor.register("analyst", AnalystAgent)
"""

from __future__ import annotations

from emo.agent.base_agent import BaseAgent


class GeneralAgent(BaseAgent):
    name = "general"
    system_prompt = (
        "You are Emo, a helpful personal AI assistant. "
        "You are thoughtful, concise, and practical.\n"
        "You have access to shell commands, file operations, and web fetching.\n"
        "Always prefer the simplest solution. Think step by step for complex tasks.\n"
        "When you run shell commands, explain what you're doing and why."
    )
    tool_names = None  # all registered tools


class CodeAgent(BaseAgent):
    name = "code"
    system_prompt = (
        "You are Emo's code specialist. "
        "You excel at writing, reviewing, debugging, and refactoring code.\n"
        "You have access to shell commands and file operations.\n\n"
        "Guidelines:\n"
        "- Prefer running code to verify it works rather than just writing it\n"
        "- Show diffs when editing existing files when possible\n"
        "- Explain your approach before diving into implementation\n"
        "- Use the shell tool to run tests, linters, and build commands"
    )
    tool_names = ["shell", "file_read", "file_write"]


class ResearchAgent(BaseAgent):
    name = "research"
    system_prompt = (
        "You are Emo's research specialist. "
        "You are skilled at finding, summarising, and synthesising information.\n"
        "You have access to web fetching to look things up.\n\n"
        "Guidelines:\n"
        "- Fetch multiple sources when needed for accuracy\n"
        "- Cite where information came from\n"
        "- Summarise clearly and concisely\n"
        "- Flag when information might be outdated"
    )
    tool_names = ["web_fetch", "file_read", "file_write"]
