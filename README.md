# emo

Lightweight personal AI agent — multi-agent orchestration, persistent memory, provider-agnostic.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Copy and edit config
cp config.yaml.example config.yaml
# Set your API key in config.yaml or via env var:
export OPENAI_API_KEY=sk-...

emo
```

## CLI flags

```
emo                          # interactive REPL
emo -m "your question"       # single message, non-interactive
emo --model anthropic/claude-3-5-sonnet-20241022
emo --agent code             # force code agent
emo --no-supervisor          # skip routing, use general agent
```

## Slash commands (inside REPL)

| Command | Description |
|---|---|
| `/help` | Show all commands |
| `/new` | Clear session, start fresh |
| `/model <name>` | Switch model on the fly |
| `/agent <name>` | Force agent: general, code, research |
| `/auto` | Return to supervisor routing |
| `/memory` | Show stored facts |
| `/remember <key> <value>` | Store a fact |
| `/forget <key>` | Delete a fact |
| `/skills` | List loaded skills |
| `/status` | Session stats |
| `/exit` | Quit |

## Config (`config.yaml`)

```yaml
model: "openai/gpt-4o"   # or anthropic/..., ollama/..., openrouter/...
agent:
  max_iterations: 20
  temperature: 0.7
tools:
  shell: true
  file_read: true
  file_write: true
  web_fetch: true
```

## Skills

Drop `.md` files into `~/.emo/skills/` — they're injected into the system prompt automatically.

## Models (via litellm)

```
openai/gpt-4o
anthropic/claude-3-5-sonnet-20241022
ollama/llama3.2          # local
openrouter/google/gemini-2.0-flash-001
```

## Project structure

```
emo/
├── agent/
│   ├── base_agent.py      # core LLM + tool loop
│   ├── supervisor.py      # intent routing
│   └── agents/            # general, code, research
├── memory/                # session + SQLite persistent memory
├── tools/                 # shell, file, web tools
├── skills/                # skills loader
├── config.py              # config loader
└── cli.py                 # Rich TUI REPL
```
