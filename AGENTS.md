# AGENTS.md

## Project

`emo` — monorepo with two independent parts:
- **Python backend** (`emo/`): lightweight multi-agent framework, Rich TUI REPL, model-agnostic via `litellm`
- **Web frontend** (`web/`): SvelteKit 5 app — see `web/AGENTS.md` for web-specific rules

---

## Python: Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
# Config is required — no default model
cp config.yaml.example .emo.yaml   # then edit
# or:
emo setup                           # interactive wizard
```

**`.emo.yaml` and `config.yaml` are gitignored.** Never commit them — they contain API keys.

## Python: Running

```bash
emo                          # interactive REPL
emo -m "your message"        # single-shot
emo --model anthropic/claude-3-5-sonnet-20241022
emo --agent code             # force a specific sub-agent
emo --no-supervisor          # skip LLM-based routing
emo --config /path/to/config.yaml
```

## Python: Tests

```bash
pip install -e ".[dev]"           # installs pytest + pytest-mock
pytest                             # run all 182 tests
pytest emo/tests/test_tools.py    # single file
pytest -v                          # per-test results
pytest -k "test_dispatch"          # single test by keyword
```

Tests live in `emo/tests/`. No real LLM calls — providers are mocked via `pytest-mock`.

## Config search order

1. `--config <path>` CLI flag
2. `EMO_CONFIG` env var
3. `.emo.yaml` (cwd)
4. `~/.emo/config.yaml`

**No `model` key = startup failure.**

## litellm model strings

Format: `provider/model` — e.g. `openai/gpt-4o`, `anthropic/claude-3-5-sonnet-20241022`, `ollama/llama3.2`.

When `api_base` is set (OpenRouter, LM Studio, vLLM, etc.), `litellm_model` always prepends `openai/` to force the OpenAI-compatible path — **even if the model already has a provider prefix** (e.g. `deepseek/deepseek-v4-flash` → `openai/deepseek/deepseek-v4-flash`). litellm strips `openai/` before sending the request body, so the endpoint receives the correct model string. Without this, litellm ignores `api_base` and routes to the native provider.

The supervisor routing call always uses `temperature=0.0, max_tokens=10`.

## Architecture

```
emo/
├── cli.py            # EmoApp (Rich TUI REPL) + `emo setup` wizard
├── config/           # load_config(), RootConfig, typed dataclasses (replaces config.py)
│   ├── models.py     # LLMConfig, AgentConfig, RouterConfig, RootConfig, litellm_model logic
│   ├── loader.py     # load_config(), _deep_merge(), _coerce_root(), router LLM inheritance
│   └── defaults.py   # default raw dicts
├── providers/        # BaseLLMProvider ABC + LiteLLMProvider
├── memory/           # SessionMemory (sliding window) + PersistentMemory (SQLite)
├── tools/            # BaseTool ABC, ToolRegistry, @tool decorator, built-ins
├── skills/           # load_skills(): reads *.md from skills_dir into system prompt
└── agent/
    ├── base_agent.py # BaseAgent: ReAct loop
    ├── supervisor.py # Supervisor: lazy agent registry + LLM-based routing
    ├── loader.py     # ensure_default_agents(), load_agent_configs()
    ├── defaults/     # general.yaml, code.yaml, research.yaml (bundled)
    └── agents/       # GeneralAgent, CodeAgent, ResearchAgent (legacy Python subclasses)
```

## Config schema (v0.2.0)

Top-level flat keys (`model:`, `api_base:`, `api_key:`) are **not supported** — hard break from v0.1.
Use nested schema:

```yaml
agent:
  llm:
    model: "deepseek/deepseek-v4-flash"
    api_base: "https://openrouter.ai/api/v1"
    api_key: "sk-..."
    temperature: 0.7

router:
  enabled: true
  llm:
    temperature: 0.0
    max_tokens: 10
```

`router.llm` inherits `model`/`api_base`/`api_key` from `agent.llm` automatically — no need to repeat credentials.

Per-agent overrides: `~/.emo/agents/<name>.yaml`. Filename stem is the canonical agent name.

## Non-obvious conventions

- `BaseAgent` has no litellm import — all LLM calls go through the injected `BaseLLMProvider`.
- Supervisor is lazy — agents instantiate on first use.
- All agents share one `SessionMemory` instance (history is not scoped per agent).
- `supervisor.update_context(text)` must be called after `/remember`, `/forget`, or skills reload — `cli.py` does this via `_refresh_context()`.
- `empty tools: []` in YAML coerces to `None` (meaning all tools), not an empty list.
- Token counting is approximate: `len(json.dumps(msg)) // 4`.
- Tool output is truncated to 200 chars in REPL UI but full result goes to LLM.

## Sub-agent tool access

| Agent      | Tools                                   |
|------------|-----------------------------------------|
| `general`  | shell, file_read, file_write, web_fetch |
| `code`     | shell, file_read, file_write            |
| `research` | web_fetch, file_read, file_write        |

---

## Web frontend (`web/`)

See **`web/AGENTS.md`** for full web-specific rules. Key facts:

- SvelteKit + Svelte 5, **runes mode forced project-wide** (set in `svelte.config.js`)
- Package manager: **pnpm** (not npm or yarn)
- UI: **shadcn-svelte** (nova style, mist base color, lucide icons) — use `pnpm dlx shadcn-svelte@latest add <component>`
- AI elements: **svelte-ai-elements** — docs at https://svelte-ai-elements.vercel.app/docs/installation
- CSS: Tailwind v4 via `@tailwindcss/vite` plugin (no `tailwind.config.js` — config is in CSS)
- Global CSS: `src/routes/layout.css`
- Component aliases: `$lib/components`, `$lib/components/ui` (shadcn), `$lib/hooks`, `$lib/utils`
- Svelte MCP server active via `.opencode/opencode.json` — use it for Svelte 5 / SvelteKit docs
