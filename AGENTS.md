# AGENTS.md

## Project

`emo` — lightweight personal AI agent framework (Python, v0.1.0). Multi-agent
orchestration with persistent memory and a Rich TUI REPL. Model/provider-agnostic
via `litellm`.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
emo setup          # interactive config wizard (creates config.yaml)
# or: cp config.yaml.example config.yaml  (then edit manually)
```

**`config.yaml` is gitignored.** Never commit it — it may contain API keys.

## Running

```bash
emo                          # interactive REPL
emo -m "your message"        # single-shot
emo --model anthropic/claude-3-5-sonnet-20241022
emo --agent code             # force a specific sub-agent
emo --no-supervisor          # skip LLM-based routing
emo --config /path/to/config.yaml
```

## No lint, no CI — but there are tests

```bash
pip install -e ".[dev]"      # installs pytest + pytest-mock
pytest                        # run all 151 tests
pytest tests/test_tools.py   # single file
pytest -k "test_dispatch"    # single test by keyword
```

Tests live in `tests/` and cover all core layers without making real LLM calls
(providers are mocked via `pytest-mock`).

## Config search order

1. `--config <path>` CLI flag
2. `EMO_CONFIG` env var
3. `./config.yaml` (cwd)
4. `~/.emo/config.yaml`

**No `model` key = startup failure.** There is no default model.

## litellm model strings

Format: `provider/model` — e.g. `openai/gpt-4o`, `anthropic/claude-3-5-sonnet-20241022`,
`ollama/llama3.2`.

When `api_base` is set (OpenRouter, LM Studio, Ollama REST, vLLM),
`config.litellm_model` auto-prepends `openai/` if the model string doesn't already
start with it. The supervisor routing call uses `temperature=0.0, max_tokens=10`.

## Architecture

```
emo/
├── __init__.py       # Top-level re-exports for all public types
├── cli.py            # Entry point: EmoApp (Rich TUI REPL) + `emo setup` wizard
├── config.py         # load_config(), Config, ConfigError
├── providers/        # BaseLLMProvider ABC + LiteLLMProvider (litellm-backed)
├── memory/           # BaseMemory ABC + SessionMemory (sliding window)
│                     # BasePersistentMemory ABC + PersistentMemory (SQLite)
├── tools/            # BaseTool ABC + ToolRegistry + @tool decorator
│                     # Built-ins: shell, file_read, file_write, web_fetch
├── skills/           # load_skills(): reads *.md from skills_dir into system prompt
└── agent/
    ├── base_agent.py # BaseAgent: ReAct loop over provider + tools + memory
    ├── supervisor.py # Supervisor: lazy agent registry + LLM-based routing
    └── agents/       # GeneralAgent, CodeAgent, ResearchAgent
```

Sub-agent tool access:

| Agent      | Tools                              |
|------------|------------------------------------|
| `general`  | shell, file_read, file_write, web_fetch |
| `code`     | shell, file_read, file_write       |
| `research` | web_fetch, file_read, file_write   |

## Extension points

Every layer has an ABC — swap implementations without touching agent code.

### New tool

```python
from emo.tools import BaseTool, registry

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something."
    parameters = {"type": "object", "properties": {"input": {"type": "string"}}, "required": ["input"]}

    def run(self, input: str) -> str:
        return input.upper()

registry.register(MyTool())
```

Or with the decorator:

```python
from emo.tools import tool

@tool(description="Add two numbers.")
def add(a: int, b: int) -> str:
    return str(a + b)
```

### New agent

```python
from emo.agent import BaseAgent

class AnalystAgent(BaseAgent):
    name = "analyst"
    system_prompt = "You are a data analyst..."
    tool_names = ["shell", "file_read"]  # None = all tools

supervisor.register("analyst", AnalystAgent)
```

### New provider (swap litellm)

```python
from emo.providers import BaseLLMProvider, LLMResponse

class MyProvider(BaseLLMProvider):
    def complete(self, messages, tools=None, stream_callback=None) -> LLMResponse: ...
    def complete_simple(self, messages) -> str: ...

provider = MyProvider(...)
supervisor = Supervisor(provider=provider, ...)
```

### New memory backend

```python
from emo.memory import BaseMemory

class RedisMemory(BaseMemory):
    def add(self, role, content): ...
    def add_tool_call(self, message): ...
    def add_tool_result(self, id, name, content): ...
    def get(self): ...
    def clear(self): ...
```

## Non-obvious conventions

- **`BaseAgent` has no litellm import.** All LLM calls go through the injected
  `BaseLLMProvider`. The only place litellm appears is `emo/providers/__init__.py`.
- **Supervisor is lazy.** Agents are instantiated on first use — registering an
  agent class is zero-cost until it is routed to.
- **All agents share one `SessionMemory` instance.** History is not scoped per
  agent; switching agents mid-session keeps full history.
- **`supervisor.update_context(text)`** pushes new skills/memory to all live
  agent instances. Call this after `/remember`, `/forget`, or skills reload —
  `cli.py` does this via `_refresh_context()`.
- **Skills load once at startup.** Adding `.md` files to `~/.emo/skills/` at
  runtime has no effect until restart (exception: `/remember` and `/forget`
  trigger a refresh).
- **Token counting is approximate:** `len(json.dumps(msg)) // 4` — not real
  tokenization.
- **Tool output is truncated to 200 chars in the REPL UI** but the full result
  is sent to the LLM.
- **`emo/providers/__init__.py`** is no longer a placeholder — it contains
  `BaseLLMProvider`, `LiteLLMProvider`, `LLMResponse`, and `ToolCall`.
- `litellm.set_verbose = False` is set in `emo/providers/__init__.py`.
