"""Emo CLI — Rich TUI REPL."""

from __future__ import annotations

import sys
import os
import argparse
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme
from rich import print as rprint

from emo.config import load_config, Config, ConfigError
from emo.memory import SessionMemory, PersistentMemory
from emo.providers import LiteLLMProvider
from emo.agent import Supervisor, BaseAgent
from emo.agent.agents import GeneralAgent, CodeAgent, ResearchAgent
from emo.skills import load_skills


# ── Theme ─────────────────────────────────────────────────────────────────────

EMO_THEME = Theme({
    "info": "dim cyan",
    "warning": "yellow",
    "error": "bold red",
    "user": "bold blue",
    "agent": "bold green",
    "supervisor": "dim magenta",
    "tool": "dim yellow",
    "header": "bold cyan",
    "muted": "dim white",
})

PROMPT_STYLE = Style.from_dict({
    "prompt": "ansiblue bold",
})


# ── CLI state ─────────────────────────────────────────────────────────────────

class EmoApp:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.console = Console(theme=EMO_THEME, highlight=False)
        self.session_memory = SessionMemory(config.context_window)
        self.persistent_memory = PersistentMemory(config.memory_db_path)
        self.provider = LiteLLMProvider(config)
        self.extra_context = self._build_extra_context()
        self.supervisor = Supervisor(
            provider=self.provider,
            session=self.session_memory,
            memory=self.persistent_memory,
            extra_context=self.extra_context,
        )
        # Register built-in agents
        self.supervisor.register("general", GeneralAgent)
        self.supervisor.register("code", CodeAgent)
        self.supervisor.register("research", ResearchAgent)
        self._current_agent_name = "general"
        self._turn = 0

    def _build_extra_context(self) -> str:
        parts: list[str] = []
        skills = load_skills(self.config.skills_dir)
        if skills:
            parts.append(f"## Skills\n\n{skills}")
        mem_block = self.persistent_memory.format_for_prompt()
        if mem_block:
            parts.append(mem_block)
        return "\n\n".join(parts)

    def _refresh_context(self) -> None:
        """Rebuild extra context and push to all agents."""
        self.extra_context = self._build_extra_context()
        self.supervisor.update_context(self.extra_context)

    def _print_header(self) -> None:
        self.console.print()
        self.console.print(Panel.fit(
            "[header]emo[/header] [muted]— personal AI agent[/muted]",
            border_style="cyan",
            padding=(0, 2),
        ))
        self.console.print(f"[muted]model:[/muted] [info]{self.config.model}[/info]"
                           + (f"  [muted]via:[/muted] [info]{self.config.api_base}[/info]" if self.config.api_base else "")
                           + f"  [muted]supervisor:[/muted] [info]{'on' if self.config.supervisor_enabled else 'off'}[/info]")
        self.console.print("[muted]type [bold]/help[/bold] for commands, [bold]Ctrl+D[/bold] or [bold]/exit[/bold] to quit[/muted]")
        self.console.print()

    def _print_help(self) -> None:
        self.console.print(Panel(
            "\n".join([
                "[bold]/help[/bold]              Show this help",
                "[bold]/new[/bold]               Start a new conversation (clears session)",
                "[bold]/model <name>[/bold]      Switch model (e.g. /model anthropic/claude-3-5-sonnet-20241022)",
                "[bold]/agent <name>[/bold]      Force a specific agent: general, code, research",
                "[bold]/auto[/bold]              Return to automatic supervisor routing",
                "[bold]/memory[/bold]            Show all stored facts",
                "[bold]/remember <k> <v>[/bold]  Store a fact (e.g. /remember name Alice)",
                "[bold]/forget <key>[/bold]      Delete a stored fact",
                "[bold]/skills[/bold]            List loaded skills",
                "[bold]/status[/bold]            Show session stats",
                "[bold]/exit[/bold]              Quit",
            ]),
            title="[header]Commands[/header]",
            border_style="cyan",
        ))

    def _handle_command(self, cmd: str) -> bool:
        """Handle /commands. Returns True if handled."""
        parts = cmd.strip().split(None, 2)
        name = parts[0].lower()

        if name == "/help":
            self._print_help()
            return True

        if name == "/exit" or name == "/quit":
            self._shutdown()
            sys.exit(0)

        if name == "/new":
            self.session_memory.clear()
            self._turn = 0
            self.console.print("[info]Session cleared. Starting fresh.[/info]")
            return True

        if name == "/model":
            if len(parts) < 2:
                self.console.print(f"[info]Current model: {self.config.model}[/info]")
            else:
                self.config._data["model"] = parts[1]
                self.console.print(f"[info]Model switched to: {parts[1]}[/info]")
            return True

        if name == "/agent":
            if len(parts) < 2:
                self.console.print(f"[info]Current agent: {self._current_agent_name}[/info]")
            else:
                agent_name = parts[1].lower()
                if agent_name in self.supervisor.agent_names:
                    self._current_agent_name = agent_name
                    self.console.print(f"[info]Forced agent: {agent_name}[/info]")
                else:
                    known = ", ".join(self.supervisor.agent_names)
                    self.console.print(f"[error]Unknown agent. Choose: {known}[/error]")
            return True

        if name == "/auto":
            self._current_agent_name = "auto"
            self.console.print("[info]Supervisor routing enabled.[/info]")
            return True

        if name == "/memory":
            facts = self.persistent_memory.get_all_facts()
            if not facts:
                self.console.print("[muted]No stored facts.[/muted]")
            else:
                lines = "\n".join(f"  [bold]{k}[/bold]: {v}" for k, v in facts.items())
                self.console.print(Panel(lines, title="[header]Stored Facts[/header]", border_style="cyan"))
            return True

        if name == "/remember":
            if len(parts) < 3:
                self.console.print("[error]Usage: /remember <key> <value>[/error]")
            else:
                self.persistent_memory.set_fact(parts[1], parts[2])
                self._refresh_context()
                self.console.print(f"[info]Remembered: [bold]{parts[1]}[/bold] = {parts[2]}[/info]")
            return True

        if name == "/forget":
            if len(parts) < 2:
                self.console.print("[error]Usage: /forget <key>[/error]")
            else:
                self.persistent_memory.delete_fact(parts[1])
                self._refresh_context()
                self.console.print(f"[info]Forgotten: {parts[1]}[/info]")
            return True

        if name == "/skills":
            skills_dir = self.config.skills_dir
            if not skills_dir.exists():
                self.console.print(f"[muted]No skills directory at {skills_dir}[/muted]")
            else:
                files = list(skills_dir.glob("*.md"))
                if not files:
                    self.console.print("[muted]No skills loaded.[/muted]")
                else:
                    self.console.print("[info]Loaded skills:[/info]")
                    for f in sorted(files):
                        self.console.print(f"  [bold]{f.stem}[/bold]  [muted]{f}[/muted]")
            return True

        if name == "/status":
            self.console.print(
                f"[info]Model:[/info] {self.config.model}\n"
                + (f"[info]API base:[/info] {self.config.api_base}\n" if self.config.api_base else "")
                + f"[info]Agent:[/info] {self._current_agent_name}\n"
                f"[info]Turn:[/info] {self._turn}\n"
                f"[info]Session messages:[/info] {len(self.session_memory.get())}\n"
                f"[info]Stored facts:[/info] {len(self.persistent_memory.get_all_facts())}\n"
                f"[info]Memory DB:[/info] {self.config.memory_db_path}"
            )
            return True

        return False

    def _run_turn(self, user_input: str) -> None:
        self._turn += 1

        # Route to agent
        if self.config.supervisor_enabled and self._current_agent_name == "auto":
            agent_name, agent = self.supervisor.route(user_input)
            self.console.print(f"[supervisor]→ {agent_name} agent[/supervisor]")
        else:
            if self._current_agent_name == "auto":
                agent_name = "general"
            else:
                agent_name = self._current_agent_name
            agent = self.supervisor.get_agent(agent_name)

        # Stream the response
        self.console.print()
        self.console.print(f"[agent]emo[/agent] ", end="")

        buffer: list[str] = []

        def on_token(token: str) -> None:
            # Tool result lines printed differently
            if token.startswith("\n[tool:"):
                self.console.print()
                self.console.print(f"[tool]{token.strip()}[/tool]")
                self.console.print(f"[agent]emo[/agent] ", end="")
            else:
                self.console.print(token, end="")
                buffer.append(token)

        try:
            reply = agent.run(user_input, on_token=on_token)
        except KeyboardInterrupt:
            self.console.print("\n[warning]Interrupted.[/warning]")
            return
        except Exception as exc:
            self.console.print(f"\n[error]Error: {exc}[/error]")
            return

        # If streaming didn't print anything (no on_token calls), print reply
        if not buffer:
            self.console.print(reply)
        else:
            self.console.print()  # newline after stream

        # Auto-summarise session after N turns
        summarize_after = self.config.get("memory", "summarize_after", default=10)
        if self._turn % summarize_after == 0:
            self._auto_summarise(agent)

    def _auto_summarise(self, agent: BaseAgent) -> None:
        """Ask the agent to summarise the session and save to persistent memory."""
        try:
            summary_prompt = (
                "Summarise this conversation in 2-3 sentences, capturing the key topics, "
                "decisions, and any important facts learned about the user. Be concise."
            )
            summary = agent.run(summary_prompt)
            self.persistent_memory.save_session_summary(summary)
            self._refresh_context()
        except Exception:  # noqa: BLE001
            pass

    def _shutdown(self) -> None:
        self.persistent_memory.close()
        self.console.print("\n[muted]Goodbye.[/muted]")

    def run(self) -> None:
        self._print_header()

        # Default to auto routing
        self._current_agent_name = "auto" if self.config.supervisor_enabled else "general"

        history_path = Path.home() / ".emo" / "history"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_session: PromptSession = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            style=PROMPT_STYLE,
            multiline=False,
        )

        while True:
            try:
                user_input = prompt_session.prompt("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                self._shutdown()
                break

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                handled = self._handle_command(user_input)
                if not handled:
                    self.console.print(f"[error]Unknown command: {user_input.split()[0]}. Type /help.[/error]")
                continue

            self._run_turn(user_input)


# ── Setup wizard ─────────────────────────────────────────────────────────────

_CONFIG_TEMPLATE = """\
# Emo configuration — generated by `emo setup`

model: "{model}"
{api_base_line}
{api_key_line}

agent:
  max_iterations: 20
  context_window: 40000
  temperature: 0.7

memory:
  db_path: "~/.emo/memory.db"
  summarize_after: 10

tools:
  shell: true
  file_read: true
  file_write: true
  web_fetch: true

skills_dir: "~/.emo/skills"

supervisor:
  enabled: true
"""

_PROVIDER_PRESETS = {
    "1": {
        "label": "OpenRouter (recommended — 200+ models, one API key)",
        "api_base": "https://openrouter.ai/api/v1",
        "model_hint": "e.g. google/gemini-2.0-flash-001  or  anthropic/claude-3.5-sonnet",
        "key_env": "OPENROUTER_API_KEY",
        "key_url": "https://openrouter.ai/keys",
    },
    "2": {
        "label": "OpenAI direct",
        "api_base": None,
        "model_hint": "e.g. openai/gpt-4o  or  openai/gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys",
    },
    "3": {
        "label": "Anthropic direct",
        "api_base": None,
        "model_hint": "e.g. anthropic/claude-3-5-sonnet-20241022  or  anthropic/claude-3-haiku-20240307",
        "key_env": "ANTHROPIC_API_KEY",
        "key_url": "https://console.anthropic.com/settings/keys",
    },
    "4": {
        "label": "Ollama (local, no API key needed)",
        "api_base": None,
        "model_hint": "e.g. ollama/llama3.2  or  ollama/mistral",
        "key_env": None,
        "key_url": None,
    },
    "5": {
        "label": "Other OpenAI-compatible endpoint (LM Studio, vLLM, etc.)",
        "api_base": "custom",
        "model_hint": "the model name your endpoint expects",
        "key_env": None,
        "key_url": None,
    },
}


def run_setup(console: Console) -> None:
    """Interactive first-run setup wizard."""
    config_path = Path.home() / ".emo" / "config.yaml"

    console.print()
    console.print(Panel.fit(
        "[header]emo setup[/header] [muted]— first-time configuration[/muted]",
        border_style="cyan", padding=(0, 2),
    ))

    if config_path.exists():
        console.print(f"[warning]Config already exists at {config_path}[/warning]")
        overwrite = input("Overwrite? [y/N] ").strip().lower()
        if overwrite != "y":
            console.print("[muted]Setup cancelled.[/muted]")
            return

    console.print()
    console.print("[bold]Choose your LLM provider:[/bold]")
    for k, p in _PROVIDER_PRESETS.items():
        console.print(f"  [bold]{k}[/bold]  {p['label']}")
    console.print()

    choice = input("Provider [1-5]: ").strip()
    preset = _PROVIDER_PRESETS.get(choice)
    if not preset:
        console.print("[error]Invalid choice. Run `emo setup` again.[/error]")
        return

    console.print()

    # api_base
    if preset["api_base"] == "custom":
        api_base = input("API base URL: ").strip()
    else:
        api_base = preset["api_base"]

    # model
    console.print(f"[muted]Model hint: {preset['model_hint']}[/muted]")
    model = input("Model name: ").strip()
    if not model:
        console.print("[error]Model name is required.[/error]")
        return

    # api_key
    api_key = ""
    if preset["key_env"]:
        if preset["key_url"]:
            console.print(f"[muted]Get your API key at: {preset['key_url']}[/muted]")
        env_val = os.environ.get(preset["key_env"], "")
        if env_val:
            console.print(f"[info]Found {preset['key_env']} in environment — using it.[/info]")
            api_key = ""  # leave blank in file, it'll be picked up from env
        else:
            api_key = input(f"API key (or set {preset['key_env']} env var, leave blank to skip): ").strip()

    # Write config
    api_base_line = f'api_base: "{api_base}"' if api_base else "# api_base: null"
    api_key_line = f'api_key: "{api_key}"' if api_key else "# api_key: null  # set via OPENAI_API_KEY env var"

    content = _CONFIG_TEMPLATE.format(
        model=model,
        api_base_line=api_base_line,
        api_key_line=api_key_line,
    )

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content)
    console.print()
    console.print(f"[info]Config written to {config_path}[/info]")
    console.print("[info]Run [bold]emo[/bold] to start chatting.[/info]")
    console.print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(prog="emo", description="Emo — personal AI agent")
    subparsers = parser.add_subparsers(dest="command")

    # `emo setup`
    subparsers.add_parser("setup", help="Interactive first-run setup wizard")

    # default (chat) args — applied when no subcommand
    parser.add_argument("--config", help="Path to config.yaml", default=None)
    parser.add_argument("--model", help="Model name (e.g. google/gemini-2.0-flash-001)", default=None)
    parser.add_argument("--api-base", help="OpenAI-compatible base URL (e.g. https://openrouter.ai/api/v1)", default=None)
    parser.add_argument("--api-key", help="API key (or set OPENAI_API_KEY env var)", default=None)
    parser.add_argument("--agent", choices=["general", "code", "research"], help="Force a specific agent", default=None)
    parser.add_argument("--no-supervisor", action="store_true", help="Disable supervisor routing")
    parser.add_argument("-m", "--message", help="Single message (non-interactive mode)", default=None)
    args = parser.parse_args()

    console = Console(theme=EMO_THEME)

    # Handle subcommands
    if args.command == "setup":
        run_setup(console)
        return

    # Load config
    config = load_config(args.config)

    # CLI overrides
    if args.model:
        config._data["model"] = args.model
    if args.api_base:
        config._data["api_base"] = args.api_base
    if args.api_key:
        config._data["api_key"] = args.api_key
    if args.no_supervisor:
        config._data["supervisor"]["enabled"] = False

    # Validate model is configured before doing anything else
    try:
        _ = config.litellm_model
    except ConfigError as e:
        console.print()
        console.print(Panel(
            str(e) + "\n\nRun [bold]emo setup[/bold] to configure interactively.",
            title="[error]Configuration required[/error]",
            border_style="red",
        ))
        console.print()
        sys.exit(1)

    app = EmoApp(config)

    if args.message:
        if args.agent:
            app._current_agent_name = args.agent
        else:
            app._current_agent_name = "auto" if config.supervisor_enabled else "general"
        app._run_turn(args.message)
        app._shutdown()
    else:
        if args.agent:
            app._current_agent_name = args.agent
        app.run()


if __name__ == "__main__":
    main()
