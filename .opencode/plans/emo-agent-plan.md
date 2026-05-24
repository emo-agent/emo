# Emo — Lightweight Personal AI Agent

## Vision

A lightweight, practical personal AI agent inspired by OpenClaw and Hermes Agent.
Built in Python, runs from the terminal, provider-agnostic, with persistent memory
and a supervisor + sub-agent architecture.

---

## Architecture

```
emo/
├── agent/
│   ├── supervisor.py       # Routes tasks to sub-agents
│   ├── base_agent.py       # Base class all agents inherit
│   └── agents/
│       ├── general.py      # General-purpose sub-agent
│       ├── code.py         # Coding-focused sub-agent
│       └── research.py     # Research/web sub-agent
├── memory/
│   ├── session.py          # In-session conversation history
│   └── persistent.py       # Long-term memory (SQLite + summaries)
├── providers/
│   ├── base.py             # LLM provider interface
│   ├── openai.py
│   ├── anthropic.py
│   └── ollama.py           # Local models
├── tools/
│   ├── base.py             # Tool interface
│   ├── shell.py            # Run shell commands
│   ├── file.py             # Read/write files
│   └── web.py              # Web search/fetch
├── skills/
│   └── (markdown files)    # Reusable procedural knowledge
├── cli.py                  # Rich TUI / REPL entry point
├── config.py               # YAML config loader
└── config.yaml.example
```

---

## Core Components

| Component | Description | Implementation |
|---|---|---|
| **Supervisor Agent** | Routes user request to best sub-agent, can spawn parallel tasks | Python class, LLM-driven routing |
| **Sub-agents** | Specialized agents (code, research, general) with different system prompts + toolsets | Inherit `BaseAgent` |
| **Session memory** | In-memory conversation history with context window management | Python list + truncation |
| **Persistent memory** | Summaries, facts, user preferences stored across sessions | SQLite via `sqlite3` |
| **LLM providers** | Swappable backends via a common interface | `litellm` (supports 100+ providers) |
| **Tools** | Shell, file R/W, web search — registered and called via function-calling | Decorator-based registration |
| **Skills** | Markdown files injected into system prompt for domain knowledge | `~/.emo/skills/` directory |
| **CLI/TUI** | Rich terminal interface with streaming, multiline input | `rich` + `prompt_toolkit` |

---

## Key Design Decisions

- **`litellm`** — single interface for OpenAI, Anthropic, Ollama, OpenRouter, etc. Switch model with one config line.
- **SQLite for persistence** — no external DB. Session summaries + facts + user profile in `~/.emo/memory.db`.
- **Minimal dependencies** — `litellm`, `rich`, `prompt_toolkit`, `pyyaml`, `httpx`. Core only.
- **Skills as markdown** — skills are markdown files in `~/.emo/skills/`. No code required, just prompts.
- **Tools as Python functions** — decorated with `@tool`, auto-registered into function-calling schema.

---

## Phased Build Plan

### Phase 1 — Core agent loop
- [ ] `BaseAgent` with LLM call, tool use loop, streaming output
- [ ] `litellm` provider abstraction
- [ ] Basic CLI REPL with `rich`
- [ ] `config.yaml` loader

### Phase 2 — Memory
- [ ] Session memory with sliding window + token budget
- [ ] Persistent memory: SQLite for facts, preferences, session summaries
- [ ] Memory injection into system prompt

### Phase 3 — Supervisor + Sub-agents
- [ ] Supervisor that classifies intent and routes to specialist
- [ ] Code agent (with shell/file tools)
- [ ] Research agent (with web search/fetch tools)
- [ ] General agent (default fallback)

### Phase 4 — Skills + Polish
- [ ] Skills loader from `~/.emo/skills/`
- [ ] Full TUI with panels (Rich layout)
- [ ] `/new`, `/model`, `/skills`, `/memory` CLI commands
- [ ] `pyproject.toml` packaging + `emo` entry point command

---

## Inspiration

- [OpenClaw](https://github.com/openclaw/openclaw) — personal AI assistant gateway, skills, multi-channel
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — self-improving agent, persistent memory, LLM-agnostic, great TUI
