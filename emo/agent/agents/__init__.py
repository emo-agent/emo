"""Built-in sub-agents.

Each agent is a minimal subclass of :class:`~emo.agent.base_agent.BaseAgent`
that sets a name, system prompt, and optionally restricts tool access.

Adding a new agent
------------------
1. Subclass ``BaseAgent`` here (or in your own module).
2. Set ``name``, ``system_prompt``, and ``tool_names``.
3. Register it with the supervisor::

       from emo.agent.agents import AnalystAgent
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
